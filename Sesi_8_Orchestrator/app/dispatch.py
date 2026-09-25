import json
import re

import httpx

from app.config import settings
from app.llm import llm_complete


# ---------- Knowledge Agent (Planner mode = Sesi 4, tapi diimplement inline supaya tidak butuh service lain) ----------
KNOWLEDGE_PLANNER = """Kamu PLANNER Knowledge. Tentukan need_tool true/false.
{{"need_tool": true, "tool": "search_knowledge", "query": "<query>"}}
ATAU
{{"need_tool": false, "tool": null, "query": null}}

Pertanyaan: {question}
JSON:"""

KNOWLEDGE_ANSWER = """Jawab pertanyaan user dalam Bahasa Indonesia.
Gunakan konteks jika tersedia, jangan mengarang fakta jika konteks kosong.

=== KONTEKS ===
{context}
=== AKHIR KONTEKS ===

Pertanyaan: {question}
Jawaban:"""


def extract_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception: return None


async def dispatch_knowledge(query: str, temperature: float = 0.2):
    """Bisa planner atau react - default planner. Kalau LLM tidak siap, fallback ke rule + search langsung."""
    ka_url = settings.knowledge_api_base
    client = httpx.Client(timeout=30.0)

    plan_raw = await llm_complete(
        KNOWLEDGE_PLANNER.format(question=query),
        max_tokens=150, temperature=temperature,
    )
    plan = extract_json(plan_raw) or {"need_tool": False}

    context_parts = []
    tool_calls = []
    if plan.get("need_tool"):
        try:
            r = client.get(f"{ka_url}/documents/search", params={"q": plan.get("query") or query, "k": 3})
            docs = r.json() if isinstance(r.json(), list) else []
            tool_calls.append({"tool": "search_knowledge", "query": plan.get("query") or query, "hits": len(docs)})
            for i, d in enumerate(docs, 1):
                context_parts.append(f"[{i}] (sumber: {d.get('source')}) {d.get('content','')}")
        except Exception as e:
            tool_calls.append({"tool": "search_knowledge", "error": str(e)})

    answer = await llm_complete(
        KNOWLEDGE_ANSWER.format(context="\n\n".join(context_parts) or "(tidak ada konteks)", question=query),
        max_tokens=500, temperature=temperature,
    )
    return {
        "domain": "knowledge",
        "answer": answer,
        "context": "\n\n".join(context_parts),
        "tool_calls": tool_calls,
        "mode": "planner-executor",
        "planner_decision": plan,
    }


# ---------- ERP Agent (ReAct mode, inline) ----------
ERP_SYSTEM = """Kamu AGENT ERP toko online.

TOOL TERSEDIA (panggil via Action/Action Input):
- list_products - tanpa param
- check_stock - JSON {"product_name":"..."}
- list_customers - tanpa param
- get_order_status - JSON {"order_id":"..."}
- create_order - JSON {"customer_id":"...", "product_id":"...", "qty": N}
- sales_report - JSON {"days": N} atau tanpa param
- FINISH - Action Input = jawaban final ke user

FORMAT:
Thought: ...
Action: <nama_tool | FINISH>
Action Input: <parameter atau jawaban>

Query user: {query}
=== Mulai ===
"""


def _parse_step(output):
    t = re.search(r"Thought:\s*(.+?)(?:\n|$)", output)
    a = re.search(r"Action:\s*(\w+)", output)
    ai = re.search(r"Action Input:\s*(.+)(?:\n|$)", output, re.DOTALL)
    return (t.group(1).strip() if t else ""), (a.group(1).strip() if a else ""), (ai.group(1).strip() if ai else "")


def _erp_tool(action, ai, erp_url, report_url) -> str:
    action = action.strip().lower()
    try:
        params = json.loads(ai) if (ai.startswith("{") or ai.startswith("[")) else {}
    except Exception:
        params = {}
    client = httpx.Client(timeout=30.0)
    try:
        if action == "list_products":
            rows = client.get(f"{erp_url}/products").json()
            return "\n".join(f"- {r['name']} | Rp{r['price']:,.0f} | stok:{r['stock']} | id:{r['id']}" for r in rows[:15])
        if action == "check_stock":
            rows = client.get(f"{erp_url}/products", params={"name": params.get("product_name","")}).json()
            if not rows: return "(tidak ketemu)"
            return "\n".join(f"- {r['name']} - stok: {r['stock']}, harga: Rp{r['price']:,.0f}, id: {r['id']}" for r in rows)
        if action == "list_customers":
            rows = client.get(f"{erp_url}/customers").json()
            return "\n".join(f"- {r['name']} | email:{r.get('email')} | id:{r['id']}" for r in rows[:15])
        if action == "get_order_status":
            return json.dumps(client.get(f"{erp_url}/orders/{params.get('order_id','')}").json(), ensure_ascii=False)
        if action == "create_order":
            body = {"customer_id": params["customer_id"], "items": [{"product_id": params["product_id"], "qty": params["qty"]}]}
            return json.dumps(client.post(f"{erp_url}/orders", json=body).json(), ensure_ascii=False)
        if action == "sales_report":
            days = params.get("days", 7)
            rep = client.post(f"{report_url}/report/sales", json={"days": days}).json()
            if isinstance(rep, dict) and rep.get("narrative"):
                return rep["narrative"]
            return json.dumps(rep, ensure_ascii=False)
    except Exception as e:
        return f"ERROR tool {action}: {e}"
    return f"tool '{action}' tidak dikenali"


async def dispatch_erp(query: str, temperature: float = 0.3):
    history = ERP_SYSTEM.format(query=query)
    steps = []
    for i in range(1, settings.max_react_steps + 1):
        out = await llm_complete(history, max_tokens=500, temperature=temperature, stop=["Observation:"])
        th, act, ai = _parse_step(out)
        step = {"step": i, "thought": th, "action": act, "action_input": ai}
        if (not act) or act.upper() == "FINISH":
            step["observation"] = "Final."
            steps.append(step)
            return {
                "domain": "erp",
                "answer": ai or th or "(kosong)",
                "mode": "react-inline",
                "steps": steps,
            }
        obs = _erp_tool(act, ai, settings.erp_api_base, settings.erp_report_api_base)
        step["observation"] = obs[:900]
        steps.append(step)
        history += out + f"\nObservation: {obs}\n\n"
    return {
        "domain": "erp",
        "answer": f"(melebihi {settings.max_react_steps} langkah)",
        "mode": "react-inline",
        "steps": steps,
    }
