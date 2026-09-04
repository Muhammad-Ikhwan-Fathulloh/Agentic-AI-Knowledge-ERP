import json
import re
import httpx
from app.config import settings
from app.schemas import PlannerDecision


def extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class KnowledgeTools:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.knowledge_api_base
        self.client = httpx.Client(timeout=30.0)

    def search(self, query: str, k: int = 3) -> list:
        try:
            r = self.client.get(f"{self.base_url}/documents/search", params={"q": query, "k": k})
            return r.json() if isinstance(r.json(), list) else []
        except Exception:
            return []


PLANNER_PROMPT = """Kamu adalah PLANNER agent. Tugasmu SATU-SATUNYA: memutuskan apakah pertanyaan user BUTUH tool (pencarian knowledge base) ATAU TIDAK.

Keluarkan HANYA JSON, TIDAK ADA teks lain di luar kurung kurawal. Format PERSIS:
{{"need_tool": true, "tool": "search_knowledge", "query": "<query pencarian yang relevan>"}}
ATAU
{{"need_tool": false, "tool": null, "query": null}}

RULES:
- need_tool = true JIKA pertanyaan menanyakan fakta spesifik, FAQ, SOP, detail produk, kebijakan, atau informasi yang ada di dokumen.
- need_tool = false JIKA pertanyaan adalah sapaan, terima kasih, atau pengetahuan umum yang kamu tahu tanpa pencarian.

Pertanyaan: {question}
JSON:"""


ANSWER_PROMPT = """Jawablah pertanyaan user dalam Bahasa Indonesia yang natural, ringkas, dan tepat.
Gunakan HANYA informasi dari KONTEKS di bawah ini JIKA tersedia. Jangan mengarang fakta jika konteks tidak menyebutkan.

=== KONTEKS ===
{context}
=== AKHIR KONTEKS ===

Pertanyaan: {question}
Jawaban:"""


async def plan_and_execute(question: str, temperature: float = 0.2):
    from app.llm import llm_complete

    llm_calls = 0
    planner_retries = 0
    decision_raw = ""
    parsed: dict | None = None

    for attempt in range(1, settings.planner_max_retry + 2):
        plan_raw = await llm_complete(
            PLANNER_PROMPT.format(question=question),
            max_tokens=200,
            temperature=temperature,
        )
        llm_calls += 1
        parsed = extract_json(plan_raw)
        decision_raw = plan_raw
        if parsed is not None and "need_tool" in parsed:
            break
        planner_retries += 1

    if parsed is None:
        parsed = {"need_tool": False, "tool": None, "query": None}

    decision = PlannerDecision(
        need_tool=bool(parsed.get("need_tool", False)),
        tool=parsed.get("tool"),
        query=parsed.get("query"),
    )

    context_str = ""
    if decision.need_tool and decision.tool == "search_knowledge" and decision.query:
        tools = KnowledgeTools()
        docs = tools.search(decision.query, k=3)
        if docs:
            parts = []
            for i, d in enumerate(docs, 1):
                parts.append(f"[{i}] (Sumber: {d.get('source')}) {d.get('content', '')}")
            context_str = "\n".join(parts)

    final = await llm_complete(
        ANSWER_PROMPT.format(context=context_str or "(tidak ada konteks tambahan)", question=question),
        max_tokens=400,
        temperature=temperature,
        stop=None,
    )
    llm_calls += 1

    return {
        "decision": decision,
        "context": context_str,
        "llm_calls": llm_calls,
        "planner_retries": planner_retries,
        "final_answer": final,
        "_planner_raw": decision_raw,
    }
