import re
from app.llm import llm_complete
from app.tools import tools
from app.schemas import StepLog

REACT_SYSTEM = """Kamu adalah agent Knowledge yang menjawab pertanyaan memakai tool.
Gunakan tool jika informasi yang dibutuhkan tidak ada di ingatanmu.

Tool yang TERSEDIA:
- search_knowledge[query]: mencari dokumen relevan di knowledge base.
- list_documents[limit]: melihat daftar dokumen yang tersimpan.
- create_document[{"source":"...", "content":"..."}]: menyimpan dokumen baru.

FORMAT WAJIB setiap langkah - satu Thought + satu Action + satu Action Input:
Thought: <jelaskan kenapa kamu butuh tool / apa yang kamu pikirkan>
Action: <nama_tool, WAJIB salah satu dari: search_knowledge, list_documents, create_document, atau FINISH>
Action Input: <parameter tool, atau JAWABAN FINAL jika Action=FINISH>

Jika Action bukan FINISH, Observation akan diberikan lalu kamu lanjutkan langkah berikutnya.

ATURAN MULTI-TOPIK (WAJIB DIIKUTI):
- Jika pertanyaan user mengandung LEBIH DARI SATU topik/intent (contoh: "garansi" DAN "pengembalian barang"), kamu HARUS melakukan search_knowledge TERPISAH untuk setiap topik, satu per satu. Jangan gabungkan dua topik berbeda dalam satu query pencarian.
- Sebelum lanjut ke topik berikutnya, tulis di Thought apakah topik saat ini sudah cukup informasinya, dan topik apa saja yang masih belum dicari.
- Jika hasil search_knowledge terlihat terpotong (misalnya berisi langkah bernomor 1-4 tapi terindikasi masih berlanjut, atau skor relevansi rendah/ambigu), gunakan list_documents untuk memverifikasi/melengkapi sebelum melanjutkan.

ATURAN FINISH (WAJIB DIIKUTI - JANGAN DILANGGAR):
- Action FINISH HANYA boleh dipakai setelah SEMUA topik dalam pertanyaan user sudah dicari dan informasinya terkumpul.
- Action Input untuk FINISH TIDAK BOLEH kosong, tidak boleh berupa placeholder seperti "Selesai" atau "jawaban final", dan tidak boleh hanya mengulang Observation mentah-mentah.
- Action Input untuk FINISH WAJIB berupa jawaban lengkap, tersusun rapi (gunakan poin bernomor per topik jika lebih dari satu topik), merangkum seluruh Observation yang relevan menjadi kalimat/instruksi yang siap dibaca langsung oleh user - bukan sekadar menyalin snippet.
- Jika informasi dari knowledge base belum cukup untuk menjawab salah satu topik, JANGAN FINISH dulu - lakukan search_knowledge tambahan dengan query yang berbeda/lebih spesifik.
- Minimal langkah sebelum FINISH = (jumlah topik terdeteksi × minimal 1 search_knowledge per topik) + langkah tambahan jika perlu list_documents.

Contoh benar (satu topik):
Thought: User ingin tahu tentang produk X, saya perlu cari di knowledge base.
Action: search_knowledge
Action Input: produk X fitur dan spesifikasi

Contoh benar (multi-topik - pertanyaan mengandung garansi DAN pengembalian):
Thought: Pertanyaan user mengandung dua topik: klaim garansi dan pengembalian barang. Saya mulai dari topik garansi dulu.
Action: search_knowledge
Action Input: cara klaim garansi barang

Thought: Informasi garansi sudah didapat. Sekarang saya cari topik kedua, yaitu pengembalian barang.
Action: search_knowledge
Action Input: cara pengembalian/return barang

Thought: Kedua topik sudah punya informasi yang cukup dari knowledge base. Saya susun jadi satu jawaban terstruktur per topik.
Action: FINISH
Action Input: Untuk klaim GARANSI: 1) Hubungi CS via WhatsApp dengan foto serial number, 2) CS memberikan nomor tiket dan alamat service center, 3) Kirim unit via ekspedisi yang ditunjuk. Untuk PENGEMBALIAN BARANG: 1) Ajukan return via dashboard maks. 30 hari, 2) Upload foto unboxing dan alasan return, 3) Tim QA memproses 2x24 jam, 4) Jika disetujui kirim barang ke gudang, 5) Refund cair 5-7 hari kerja.

Contoh SALAH (dilarang):
Action: FINISH
Action Input: Selesai - jawaban final.
(^ SALAH karena kosong/placeholder, tidak menjawab pertanyaan user)

=== Mulai percakapan ===
"""

PLACEHOLDER_PATTERNS = [
    r"^selesai\.?$",
    r"^jawaban final\.?$",
    r"^\(jawaban kosong\)$",
    r"^done\.?$",
    r"^-*$",
]

def _is_placeholder_answer(text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return True
    normalized = text.strip().lower()
    return any(re.match(p, normalized) for p in PLACEHOLDER_PATTERNS)


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
    ai = re.search(r"Action Input:\s*(.+)", output, re.DOTALL)
    if ai:
        action_input = ai.group(1).strip()
    return thought, action, action_input


async def react_loop(
    query: str,
    max_steps: int = 8,          # dinaikkan agar cukup untuk multi-topik
    temperature: float = 0.3,
) -> tuple[str, list[StepLog]]:
    history = REACT_SYSTEM + f"Pertanyaan user: {query}\n\n"
    steps: list[StepLog] = []
    finish_retry_used = False

    for step_num in range(1, max_steps + 1):
        output = await llm_complete(
            history,
            max_tokens=400,
            temperature=temperature,
            stop=["Observation:", "=== Mulai"],
        )
        thought, action, action_input = _parse_step(output)
        log = StepLog(
            step=step_num,
            thought=thought or "(tidak terdeteksi)",
            action=action or None,
            action_input=action_input or None,
        )

        # 1) Parsing gagal total (bukan FINISH, bukan tool valid) -> JANGAN dianggap selesai.
        #    Minta LLM mengulang dengan format yang benar.
        valid_actions = {"search_knowledge", "list_documents", "create_document", "finish"}
        if not action or action.lower() not in valid_actions:
            log.observation = (
                "Format tidak valid: Action harus salah satu dari "
                "search_knowledge, list_documents, create_document, atau FINISH. "
                "Ulangi langkah dengan format yang benar."
            )
            steps.append(log)
            history += output + f"\nObservation: {log.observation}\n\n"
            continue  # LANJUT, jangan return

        # 2) LLM eksplisit memilih FINISH
        if action.lower() == "finish":
            if _is_placeholder_answer(action_input) and not finish_retry_used:
                # Tolak jawaban kosong/placeholder, paksa satu kali retry
                finish_retry_used = True
                log.observation = (
                    "FINISH ditolak: Action Input kosong atau hanya placeholder. "
                    "Pastikan semua topik dalam pertanyaan sudah dicari (search_knowledge), "
                    "lalu tulis jawaban lengkap dan terstruktur di Action Input."
                )
                steps.append(log)
                history += output + f"\nObservation: {log.observation}\n\n"
                continue  # paksa LLM coba lagi, bukan langsung return

            log.observation = "Selesai - jawaban final."
            steps.append(log)
            final_answer = action_input if not _is_placeholder_answer(action_input) else (
                "Maaf, informasi belum cukup untuk menjawab semua bagian pertanyaan Anda."
            )
            return final_answer, steps

        # 3) Tool call biasa
        observation = tools.call(action, action_input)
        log.observation = observation[:800]
        steps.append(log)
        history += output + f"\nObservation: {observation}\n\n"

    # Default kalau max_steps habis tanpa FINISH valid
    final = steps[-1].observation if steps else "(tidak ada jawaban)"
    return f"[Melebihi batas langkah] Jawaban sementara: {final}", steps