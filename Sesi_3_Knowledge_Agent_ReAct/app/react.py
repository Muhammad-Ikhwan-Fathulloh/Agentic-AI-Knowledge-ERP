import re
from app.llm import llm_complete
from app.tools import tools
from app.schemas import StepLog


REACT_SYSTEM = """Kamu adalah agent Knowledge yang menjawab pertanyaan memakai tool.
Gunakan tool jika informasi yang dibutuhkan tidak ada di ingatanmu.
Tool yang TERSEDIA:
- search_knowledge[query]: mencari dokumen relevan di knowledge base.
- list_documents[limit]: melihat daftar dokumen yang tersimpan.
- create_document[{\"source\":\"...\", \"content\":\"...\"}]: menyimpan dokumen baru.

FORMAT WAJIB setiap langkah — satu Thought + satu Action + satu Action Input:
Thought: <jelaskan kenapa kamu butuh tool / apa yang kamu pikirkan>
Action: <nama_tool, WAJIB salah satu dari: search_knowledge, list_documents, create_document, atau FINISH>
Action Input: <parameter tool, atau JAWABAN FINAL jika Action=FINISH>

Jika Action bukan FINISH, Observation akan diberikan lalu kamu lanjutkan langkah berikutnya.
Gunakan Action FINISH hanya jika kamu sudah yakin punya jawaban final untuk user.

Contoh benar:
Thought: User ingin tahu tentang produk X, saya perlu cari di knowledge base.
Action: search_knowledge
Action Input: produk X fitur dan spesifikasi

=== Mulai percakapan ===
"""


def _parse_step(output: str):
    thought = ""
    action = ""
    action_input = ""
    t = re.search(r"Thought:\s*(.+?)(?:\n|$)", output)
    if t:
        thought = t.group(1).strip()
    a = re.search(r"Action:\s*(\w+)", output)
    if a:
        action = a.group(1).strip()
    ai = re.search(r"Action Input:\s*(.+)(?:\n|$)", output, re.DOTALL)
    if ai:
        action_input = ai.group(1).strip()
    return thought, action, action_input


async def react_loop(
    query: str,
    max_steps: int = 4,
    temperature: float = 0.3,
) -> tuple[str, list[StepLog]]:
    history = REACT_SYSTEM + f"Pertanyaan user: {query}\n\n"
    steps: list[StepLog] = []

    for step_num in range(1, max_steps + 1):
        output = await llm_complete(
            history,
            max_tokens=400,
            temperature=temperature,
            stop=["Observation:", "=== Mulai"],
        )
        thought, action, action_input = _parse_step(output)
        log = StepLog(step=step_num, thought=thought or "(tidak terdeteksi)", action=action or None, action_input=action_input or None)

        if not action or action.upper() == "FINISH":
            log.observation = "Selesai — jawaban final."
            steps.append(log)
            final_answer = action_input or thought or "(jawaban kosong)"
            return final_answer, steps

        observation = tools.call(action, action_input)
        log.observation = observation[:800]
        steps.append(log)

        history += output + f"\nObservation: {observation}\n\n"

    # Default: ambil jawaban dari observation terakhir
    final = steps[-1].observation if steps else "(tidak ada jawaban)"
    return f"[Melebihi batas langkah] Jawaban sementara: {final}", steps
