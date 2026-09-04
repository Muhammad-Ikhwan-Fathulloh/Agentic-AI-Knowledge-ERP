import re
import json
from app.llm import llm_complete
from app.tools import ERPTools
from app.config import settings

tools = ERPTools()

ERP_REACT_SYSTEM = """Kamu adalah AGENT ERP untuk toko online. Tugasmu: cek stok, lihat produk/pelanggan, cek status order, dan BANTU user membuat order (jika stok cukup).

TOOL YANG TERSEDIA (GUNAKAN HANYA NAMA INI):
- check_stock — cek stok berdasarkan nama produk. Param JSON: {"product_name":"..."}
- list_products — lihat semua produk (tanpa parameter).
- list_customers — lihat semua pelanggan (cari tahu customer_id sebelum create_order).
- get_order_status — cek status order. Param JSON: {"order_id":"..."}
- create_order — SIMULASI buat order, BELUM final. Param JSON: {"customer_id":"...", "product_id":"...", "qty": N}
- confirm_create_order — finalisasi order yang sudah distage (setelah user konfirmasi YA).

RULE PENTING:
  1. SEBELUM create_order: WAJIB panggil check_stock DAHULU untuk pastikan stok cukup.
  2. SEBELUM create_order: WAJIB panggil list_customers DAHULU untuk dapat customer_id yang valid.
  3. Setelah create_order, langkah SELANJUTNYA harus menunggu konfirmasi user (jangan langsung FINISH).

FORMAT WAJIB SETIAP LANGKAH:
Thought: <pemikiranmu 1 kalimat>
Action: <check_stock|list_products|list_customers|get_order_status|create_order|confirm_create_order|FINISH>
Action Input: <JSON atau parameter>

Jika Action=FINISH, isilah Action Input dengan JAWABAN FINAL ke user.

=== Mulai ===
"""


def _parse_step(output):
    t = re.search(r"Thought:\s*(.+?)(?:\n|$)", output)
    a = re.search(r"Action:\s*(\w+)", output)
    ai = re.search(r"Action Input:\s*(.+)(?:\n|$)", output, re.DOTALL)
    return (
        (t.group(1).strip() if t else ""),
        (a.group(1).strip() if a else ""),
        (ai.group(1).strip() if ai else ""),
    )


async def erp_react_loop(
    query: str,
    max_steps: int | None = None,
    temperature: float = 0.3,
    pending_confirm_answer: str | None = None,
):
    max_steps = max_steps or settings.max_react_steps
    history = ERP_REACT_SYSTEM + f"User: {query}\n\n"
    steps = []
    need_confirm = False

    for step_num in range(1, max_steps + 1):
        output = await llm_complete(
            history, max_tokens=500, temperature=temperature,
            stop=["Observation:", "=== Mulai"],
        )
        thought, action, action_input = _parse_step(output)
        step_log = {
            "step": step_num, "thought": thought or "(kosong)",
            "action": action or None, "action_input": action_input or None,
        }

        if (not action) or action.upper() == "FINISH":
            step_log["observation"] = "Selesai."
            steps.append(step_log)
            return {
                "final_answer": action_input or thought,
                "steps": steps,
                "need_human_confirm": False,
            }

        observation = tools.call(action, action_input, pending_confirm_answer)
        step_log["observation"] = observation[:800]
        steps.append(step_log)

        if action == "create_order" and "PERLU KONFIRMASI" in observation:
            need_confirm = True

        history += output + f"\nObservation: {observation}\n\n"

        if need_confirm:
            return {
                "final_answer": observation,
                "steps": steps,
                "need_human_confirm": True,
                "prompt_confirm": "Apakah Anda setuju order ini dibuat? (YA / TIDAK)",
            }
        pending_confirm_answer = None

    return {
        "final_answer": f"[Melebihi batas {max_steps} langkah]",
        "steps": steps,
        "need_human_confirm": False,
    }
