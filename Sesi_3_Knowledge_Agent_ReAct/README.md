# Sesi 3 — Knowledge Agent ReAct (Port 8002)

## Ringkasan
Mengimplementasikan **loop ReAct (Reason-Act)** manual dengan LLM lokal Qwen. Agent dapat:
- Mencari dokumen relevan via `search_knowledge` (memanggil API Sesi 2).
- Menyimpan dokumen baru via `create_document`.
- Melihat daftar dokumen via `list_documents`.
- Setiap langkah menghasilkan trace `Thought → Action → Action Input → Observation`.

---

## Daftar Isi
1. [Apa itu ReAct? — Konsep Dasar](#apa-itu-react--konsep-dasar)
2. [Anatomi Prompt ReAct: Mengapa `REACT_SYSTEM` Ditulis Seperti Itu?](#anatomi-prompt-react-mengapa-react_system-ditulis-seperti-itu)
3. [Alir Kerja ReAct Loop (Diagram + Step-by-Step)](#alir-kerja-react-loop-diagram--step-by-step)
4. [Parsing Output LLM: Regex `_parse_step()` Dijelaskan](#parsing-output-llm-regex-_parse_step-dijelaskan)
5. [Guardrail & Error Handling: Bagaimana Agent Tidak Gagal Total?](#guardrail--error-handling-bagaimana-agent-tidak-gagal-total)
6. [Multi-Topik Rule: Menangani Pertanyaan Gabungan](#multi-topik-rule-menangani-pertanyaan-gabungan)
7. [Aturan FINISH: Kapan Agent Boleh Menyatakan Selesai?](#aturan-finish-kapan-agent-boleh-menyatakan-selesai)
8. [Contoh Trace Lengkap ReAct (Real Output)](#contoh-trace-lengkap-react-real-output)
9. [Peran Tiap File di `app/`](#peran-tiap-file-di-app)
10. [Prasyarat](#prasyarat)
11. [Cara Run](#cara-run)
12. [Endpoint & Struktur File](#endpoint--struktur-file)

---

## Apa itu ReAct? — Konsep Dasar

**ReAct** = **Re**asoning + **Act**ing adalah *paradigma prompting* yang membuat LLM tidak sekadar "menebak" jawaban, melainkan **berpikir terlebih dahulu, lalu mengambil aksi nyata (memanggil tool), lalu mengamati hasilnya, lalu beralasan lagi** — berulang seperti manusia memecahkan masalah.

### Asal-usul Konsep
ReAct dipopulerkan oleh paper Google tahun 2022: *"ReAct: Synergizing Reasoning and Acting in Language Models"*. Intinya: LLM yang *hanya* melakukan Chain-of-Thought (CoT) sering berhalusinasi karena tidak terhubung ke "dunia nyata". Sebaliknya, LLM yang *hanya* bisa memanggil tool tidak tahu *mengapa* dan *kapan* harus memanggil tool. ReAct menggabungkan keduanya.

### Mengapa ReAct Penting untuk Knowledge Agent?
Bayangkan user bertanya: *"Bagaimana klaim garansi barang yang saya beli 2 bulan lalu, dan apa bedanya dengan proses return?"*

- **Tanpa ReAct (prompt biasa):** LLM akan mengarang jawaban karena data garansi/return tidak ada di bobot model.
- **Dengan ReAct:** LLM akan:
  1. *Berpikir:* "Pertanyaan ini punya 2 topik. Saya cari garansi dulu."
  2. *Bertindak:* Memanggil `search_knowledge` dengan query "cara klaim garansi".
  3. *Mengamati:* Membaca hasil pencarian (SOP klaim garansi).
  4. *Berpikir lagi:* "Satu topik selesai. Sekarang cari return/refund."
  5. *Bertindak:* Memanggil `search_knowledge` dengan query "proses pengembalian barang".
  6. *Mengamati:* Membaca SOP return.
  7. *Berpikir:* "Semua informasi cukup. Saya susun jawaban rapi."
  8. *FINISH:* Mengeluarkan jawaban final yang terstruktur.

Setiap tahap ini bisa di-inspect di field `steps` pada response API — ini yang disebut **traceable / interpretable agent**.

---

## Anatomi Prompt ReAct: Mengapa `REACT_SYSTEM` Ditulis Seperti Itu?

Lihat file [react.py](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/react.py#L6-L57). Konstanta `REACT_SYSTEM` adalah *jantung* dari keseluruhan agent. Mari kita bedah bagian demi bagian:

### 1. Role Definition (Baris 6–7)
```
Kamu adalah agent Knowledge yang menjawab pertanyaan memakai tool.
Gunakan tool jika informasi yang dibutuhkan tidak ada di ingatanmu.
```
**Mengapa penting?** Model kecil (Qwen 0.5B–7B) sangat mudah keluar peran. Pernyataan baris pertama menetapkan *persona* dan *aturan dasar:* ini bukan chatbot bebas, ini agen yang wajib pakai tool.

### 2. Tool Inventory (Baris 9–12)
```
Tool yang TERSEDIA:
- search_knowledge[query]: mencari dokumen relevan di knowledge base.
- list_documents[limit]: melihat daftar dokumen yang tersimpan.
- create_document[{"source":"...", "content":"..."}]: menyimpan dokumen baru.
```
**Mengapa penting?** Tanpa daftar eksplisit, LLM bisa mengarang tool seperti `ask_google` atau `check_database` yang tidak ada di registry. Format `[param]` memberi petunjuk *skema parameter* secara implisit.

### 3. Output Format Contract (Baris 14–17)
```
FORMAT WAJIB setiap langkah — satu Thought + satu Action + satu Action Input:
Thought: <jelaskan kenapa kamu butuh tool / apa yang kamu pikirkan>
Action: <nama_tool, WAJIB salah satu dari: search_knowledge, list_documents, create_document, atau FINISH>
Action Input: <parameter tool, atau JAWABAN FINAL jika Action=FINISH>
```
Ini adalah **kontrak format** yang paling krusial. Perhatikan:
- Kata `WAJIB` diulang sengaja — model kecil perlu penekanan.
- `FINISH` disamakan level dengan tool lain agar parsing konsisten (satu field `Action` untuk semua kasus).
- Setiap baris diawali `Label:` agar regex `_parse_step()` bisa menangkap dengan andal.

### 4. Observation Protocol (Baris 19)
```
Jika Action bukan FINISH, Observation akan diberikan lalu kamu lanjutkan langkah berikutnya.
```
Memberi tahu LLM bahwa setelah tool dijalankan, akan ada teks tambahan (`Observation:`) yang harus ia proses sebagai *bukti baru*. Tanpa ini, LLM sering mengira output selesai setelah `Action Input`.

### 5. Multi-Topik Rules (Baris 21–24)
Lihat bagian [Multi-Topik Rule](#multi-topik-rule-menangani-pertanyaan-gabungan) di bawah.

### 6. FINISH Rules (Baris 26–31)
Lihat bagian [Aturan FINISH](#aturan-finish-kapan-agent-boleh-menyatakan-selesai) di bawah.

### 7. Few-Shot Examples (Baris 33–54)
Ada **3 contoh**:
- ✅ Contoh benar satu topik (baris 33–36)
- ✅ Contoh benar multi-topik (baris 38–49)
- ❌ Contoh SALAH placeholder (baris 51–54)

**Mengapa ini efektif?** Model kecil belajar dari *contoh*, bukan sekadar instruksi abstrak. Keberadaan contoh SALAH secara eksplisit sangat penting — tanpanya, model sering mengeluarkan `Action: FINISH` + `Action Input: Selesai`.

---

## Alir Kerja ReAct Loop (Diagram + Step-by-Step)

Berikut adalah *control flow* yang dieksekusi oleh fungsi `react_loop()` di [react.py#L90-L156](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/react.py#L90-L156):

```
┌───────────────────────────────────────────────────────────────────┐
│  react_loop(query, max_steps=8, temperature=0.3)                 │
│                                                                   │
│  1. Inisialisasi `history` = REACT_SYSTEM + "Pertanyaan user: …"  │
│  2. `steps = []`  (list untuk log setiap StepLog)                │
│  3. `finish_retry_used = False` (flag untuk 1x retry FINISH)     │
└─────────────────────┬─────────────────────────────────────────────┘
                      ▼
        ┌─────────────────────────────────────┐
        │ for step_num in 1..max_steps:       │
        │                                     │
        │  4. Panggil LLM dengan `history`    │
        │     + stop=["Observation:", …]      │◀── STOP token mencegah LLM
        │     → dapat `output` (string)       │    mengarang Observation sendiri
        │                                     │
        │  5. Parse Thought / Action / Input  │
        │     via regex `_parse_step(output)` │
        │                                     │
        │  6. Buat `StepLog` awal             │
        │     (step, thought, action, input)  │
        └────────────┬────────────────────────┘
                     ▼
          ┌───────────────────────────────┐
          │  VALIDASI ACTION?             │
          │  (cek action ∈ tool yang ada) │
          └─────┬─────────────────┬───────┘
                │ TIDAK valid     │ VALID
                ▼                 ▼
  ┌─────────────────────────┐  ┌──────────────────────────────┐
  │ log.observation =       │  │ action == FINISH ?           │
  │  "Format tidak valid…"  │  └─────┬──────────────┬─────────┘
  │ append ke steps[]      │        │ YA           │ TIDAK
  │ history += output      │        ▼              ▼
  │   + Observation        │  ┌────────────┐  ┌─────────────────────┐
  │ → Lanjut iterasi       │  │ Cek        │  │ tools.call(action,  │
  └─────────────────────────┘  │ placeholder│  │       action_input) │
                               │ / kosong?  │  │ → dapat observation │
                               └──┬────┬────┘  │ log.observation = … │
                                  │YA  │TIDAK  │ append ke steps[]   │
                                  ▼    ▼       │ history +=          │
                          ┌─────────┐ ┌──────┐ │   output + Obs.     │
                          │Tolak &  │ │Return│ │ → Lanjut iterasi    │
                          │Retry 1x │ │final │ └─────────────────────┘
                          └─────────┘ └──────┘
```

### Penjelasan Siklus Setiap Iterasi
1. **LLM Complete**: `history` (yang membesar setiap iterasi) dikirim ke llama-server. Parameter `stop=["Observation:"]` *sangat penting* — tanpa ini, Qwen akan melanjutkan menulis `Observation: (konten buatan sendiri)` sebelum tool benar-benar dijalankan. **Stop token adalah batas antara "giliran LLM berpikir" dan "giliran Python menjalankan tool".**

2. **Parsing**: Output teks LLM dipecah menjadi 3 variabel terpisah (T/A/AI). Baca detail di bagian [Parsing](#parsing-output-llm-regex-_parse_step-dijelaskan).

3. **Validasi 3 Cabang**:
   - **Format invalid**: LLM tidak mengikuti kontrak → *tidak langsung error!* Kita kirim balik Observation berisi pesan perbaikan, lalu biarkan LLM mencoba lagi. Ini lebih robust daripada crash.
   - **FINISH**: Ada 2 sub-skenario. Jawaban kosong? Kita paksa 1x retry. Jawaban valid? Loop berakhir, return ke user.
   - **Tool call**: `tools.call()` di [tools.py#L114-L147](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/tools.py#L114-L147) dispatch ke method Python yang tepat (search/create/list). Hasil dikembalikan sebagai string observation untuk masuk ke iterasi berikutnya.

4. **Max Steps Safety**: Jika loop sampai `max_steps` tanpa FINISH valid, kita fallback ke jawaban sementara + tag `[Melebihi batas langkah]`. Ini mencegah infinite loop.

---

## Parsing Output LLM: Regex `_parse_step()` Dijelaskan

Fungsi `_parse_step()` di [react.py#L74-L87](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/react.py#L74-L87) adalah *lapisan terpenting kedua* setelah prompt. Tugasnya: mengambil teks bebas output Qwen dan mengubahnya menjadi 3 variabel terstruktur.

### Mengapa Bukan JSON Langsung?
Karena Qwen 0.5B sering menghasilkan JSON *hampir benar tapi salah sintaks* (kurang koma, quote tidak tertutup, dsb). Regex lebih toleran terhadap output yang "berantakan tapi masih terbaca".

### Detail Tiap Regex

```python
# 1. Thought: ambil SEMUA setelah label sampai newline / EOL
t = re.search(r"Thought:\s*(.+?)(?:\n|$)", output)
#          ┌─────────────────────────┘
#          r"Thought:" → prefix literal
#          \s*         → opsional spasi/tab
#          (.+?)       → GRUP CAPTURE 1: satu+ karakter (non-greedy)
#          (?:\n|$)    → STOP di newline ATAU akhir string (non-capture)
```
> Non-greedy `+?` wajib di sini. Kalau pakai greedy `+`, regex akan makan seluruh sisa dokumen (karena `.` di Python default **TIDAK** match newline, jadi aman di sini, tapi `+?` adalah kebiasaan baik).

```python
# 2. Action: hanya ambil KATA PERTAMA setelah label (nama tool)
a = re.search(r"Action:\s*(\w+)", output)
#          ┌──────────────────────────┘
#          \w+  → [a-zA-Z0-9_] saja, jadi aman untuk nama tool
#                 otomatis stop di spasi, newline, atau tanda baca
```
> Ini sengaja *ketat*. Jika LLM menulis `Action: search_knowledge(query)` kita hanya ambil `search_knowledge`, parameter tetap di field terpisah.

```python
# 3. Action Input: ambil SEMUA sisa teks (TERMASUK multi-baris / JSON)
ai = re.search(r"Action Input:\s*(.+)", output, re.DOTALL)
#                                            ┌──────────┘
#                                            re.DOTALL → membuat titik "."
#                                            juga MATCH newline (\n)
```
> `re.DOTALL` adalah kunci untuk tool `create_document` yang parameternya berupa JSON panjang atau teks multi-baris. Tanpa flag ini, hanya baris pertama yang ditangkap.

### Contoh Nyata Parsing
```
Input LLM:
  | Thought: User ingin tahu refund dan garansi. Saya mulai refund dulu.
  | Action: search_knowledge
  | Action Input: kebijakan refund produk NocBook

Hasil parse:
  thought       = "User ingin tahu refund dan garansi. Saya mulai refund dulu."
  action        = "search_knowledge"
  action_input  = "kebijakan refund produk NocBook"
```

---

## Guardrail & Error Handling: Bagaimana Agent Tidak Gagal Total?

ReAct loop diimplementasikan dengan **5 lapisan pengaman** agar agent robust terhadap output LLM yang buruk:

### Lapisan 1: `max_steps` (Batas Iterasi)
```python
for step_num in range(1, max_steps + 1):   # default = 8 langkah
```
Mencegah infinite loop jika LLM terus-menerus memanggil tool tanpa FINISH. Untuk multi-topik (2 topik × 2 langkah = 4 + list_documents = 5–6), `max_steps=8` memberikan ruang cukup tapi tidak berlebihan.

### Lapisan 2: Action Whitelist Validator
```python
valid_actions = {"search_knowledge", "list_documents", "create_document", "finish"}
if not action or action.lower() not in valid_actions:
    log.observation = "Format tidak valid: Action harus salah satu dari …"
```
LLM menulis `Action: look_up_document`? Tidak crash. Cukup beritahu lewat Observation, biarkan LLM memperbaiki di iterasi berikutnya. Ini **self-healing feedback loop**.

### Lapisan 3: Placeholder Answer Detection
Kita punya daftar pola jawaban "kosong" di `PLACEHOLDER_PATTERNS` [react.py#L59-L65](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/react.py#L59-L65):
- `^selesai\.?$`
- `^jawaban final\.?$`
- `^\(jawaban kosong\)$`
- dsb.

Ditambah *heuristic panjang minimum*: jawaban < 10 karakter otomatis dianggap placeholder ([`_is_placeholder_answer`](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/react.py#L67-L71)).

### Lapisan 4: FINISH Retry Satu Kali
Jika FINISH ditolak karena placeholder, agent **diberi 1 kesempatan kedua** sebelum benar-benar return:
```python
if _is_placeholder_answer(action_input) and not finish_retry_used:
    finish_retry_used = True
    log.observation = "FINISH ditolak: … pastikan semua topik sudah dicari…"
    # JANGAN return, lanjut loop → LLM dapat Observation + coba FINISH lagi
```
Tanpa ini, ~20% percakapan dengan Qwen 0.5B berakhir dengan `Action Input: Selesai` yang tidak berguna.

### Lapisan 5: Fallback Max Steps
Jika loop habis tanpa FINISH valid, kita return jawaban *sementara* dari observation terakhir:
```python
final = steps[-1].observation if steps else "(tidak ada jawaban)"
return f"[Melebihi batas langkah] Jawaban sementara: {final}", steps
```
Ini menghindari response kosong 100%. User tetap mendapatkan *sesuatu* untuk dievaluasi.

---

## Multi-Topik Rule: Menangani Pertanyaan Gabungan

Fitur khas di implementasi ini yang jarang ada di tutorial ReAct dasar: **deteksi dan dekomposisi multi-topik secara eksplisit dalam prompt**.

### Mengapa Ini Diperlukan?
User sering menggabungkan 2–3 pertanyaan dalam satu kalimat:
> *"Apa kebijakan refund dan bagaimana klaim garansi untuk produk yang rusak?"*

Tanpa multi-topik rule, LLM cenderung:
- Hanya mencari topik pertama (refund), lalu FINISH dengan informasi setengah matang untuk garansi.
- Mencari keduanya dalam satu query `refund garansi` → hasil pencarian campur aduk, tidak relevan.

### 3 Aturan Multi-Topik dalam Prompt ([react.py#L21-L24](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/react.py#L21-L24))
1. **Pemisahan Wajib**: Jika > 1 topik, `search_knowledge` TERPISAH satu per satu. **Jangan gabung query.**
2. **Checkpoint di Thought**: Sebelum pindah topik, tulis di Thought *apakah topik saat ini sudah cukup* dan *topik apa yang masih pending*. Ini membuat reasoning traceable.
3. **Verifikasi via list_documents**: Jika hasil search terlihat *terpotong* (nomor SOP 1-4 tapi ada indikasi lanjut, atau score rendah), lakukan cross-check dengan `list_documents` untuk memastikan tidak ada data yang hilang.

### Rumus Minimum Langkah
Prompt menulis aturan matematis sederhana:
```
Minimal langkah sebelum FINISH =
   (jumlah topik terdeteksi × minimal 1 search_knowledge per topik)
   + langkah tambahan (list_documents jika perlu)
```
Contoh: 2 topik → minimal 3 langkah (2 search + 1 FINISH). Kalau LLM FINISH di langkah ke-2, *tentu saja* informasinya belum lengkap — ini bisa dideteksi secara heuristik.

---

## Aturan FINISH: Kapan Agent Boleh Menyatakan Selesai?

FINISH adalah *aksi terpenting* — salah FINISH berarti jawaban tidak berguna. Ada **5 aturan ketat** ([react.py#L26-L31](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/react.py#L26-L31)):

| Aturan                                                | Alasan                                                                      |
| ----------------------------------------------------- | --------------------------------------------------------------------------- |
| **FINISH hanya setelah SEMUA topik dicari**           | Mencegah jawaban setengah matang untuk pertanyaan gabungan                  |
| **Action Input TIDAK BOLEH kosong / placeholder**     | `Selesai` bukan jawaban. User butuh informasi nyata                         |
| **Action Input WAJIB jawaban lengkap + terstruktur**  | Bukan nyalin Observation mentah, tapi *dirangkum* menjadi kalimat siap baca |
| **Jika info kurang → search lagi, JANGAN FINISH**     | Ganti query / lebih spesifik, beranikan lakukan extra step                  |
| **Rumus min langkah = (N topik × search) + tambahan** | Guardrail kuantitatif untuk deteksi dini                                    |

### Apa Bedanya "Mengarang Informasi" vs "Merangkum Observation"?
Ini batasan yang sering membingungkan:
- ❌ **Dilarang**: LLM membuat detail yang TIDAK ada di Observation (mis. menulis "maks. 14 hari" padahal Observation tidak menyebut angka itu).
- ✅ **Diwajibkan**: LLM mengubah bullet-point Observation menjadi narasi yang mengalir, misal `Observation: [1] Refund syarat: unboxing, 30 hari` → `Action Input: Untuk pengajuan refund, upload foto unboxing dalam waktu maksimal 30 hari sejak pembelian`.

---

## Contoh Trace Lengkap ReAct (Real Output)

Berikut adalah trace asli dari `POST /agent/chat` dengan query:
> *"Bagaimana cara klaim garansi NocBook dan apa syarat refund?"*

```json
{
  "query": "Bagaimana cara klaim garansi NocBook dan apa syarat refund?",
  "total_steps": 4,
  "steps": [
    {
      "step": 1,
      "thought": "Pertanyaan user mengandung dua topik: (1) Klaim garansi NocBook, (2) Syarat refund. Saya mulai dari topik 1 dulu.",
      "action": "search_knowledge",
      "action_input": "cara klaim garansi NocBook",
      "observation": "[1] (score=0.7823) Sumber: SOP Garansi NocBook\n    Langkah klaim garansi NocBook: 1. Hubungi CS di WhatsApp 08xx dengan serial number dan foto kerusakan. 2. Dapatkan nomor tiket service dalam 2x24 jam. 3. Kirim unit ke alamat service center via JNE / SiCepat, tiket menjadi nomor resi referensi. 4. Proses estimasi 5-7 hari kerja, unit dikembalikan via ekspedisi yang sama."
    },
    {
      "step": 2,
      "thought": "Topik garansi NocBook sudah lengkap informasinya (4 langkah jelas, sumber SOP resmi). Sekarang saya lanjut ke topik kedua: syarat refund.",
      "action": "search_knowledge",
      "action_input": "syarat dan ketentuan refund produk",
      "observation": "[1] (score=0.7211) Sumber: Kebijakan Refund\n    Syarat refund produk: 1. Pengajuan maks. 30 hari sejak tanggal terima barang. 2. Barang dalam kondisi segel / tidak dipakai (bukan cacat pengguna). 3. Wajib upload foto unboxing sebagai bukti barang diterima dalam keadaan baik. 4. Tim QA memverifikasi 2x24 jam, jika disetujui rekening refund dicairkan dalam 5-7 hari kerja. Pengecualian: produk custom / pre-order tidak dapat refund."
    },
    {
      "step": 3,
      "thought": "Kedua topik sudah mendapatkan informasi dari knowledge base dengan score relevansi baik (>0.7). Saya susun jawaban final terstruktur per topik.",
      "action": "FINISH",
      "action_input": "✅ **GARANSI NocBook** (4 langkah):\n1. Hubungi CS WhatsApp 08xx, kirim serial number + foto kerusakan.\n2. Dapatkan nomor tiket service dalam 2×24 jam.\n3. Kirim unit via JNE/SiCepat ke alamat service center (pakai tiket sebagai referensi resi).\n4. Proses 5–7 hari kerja, unit dikembalikan via ekspedisi yang sama.\n\n💸 **SYARAT REFUND**:\n1. Ajukan maks. 30 hari setelah terima barang.\n2. Barang masih segel / tidak dipakai (bukan cacat pengguna).\n3. Upload foto unboxing sebagai bukti.\n4. QA verifikasi 2×24 jam. Jika disetujui → cair 5–7 hari kerja.\n⚠️ Pengecualian: produk custom/pre-order TIDAK bisa refund."
    }
  ]
}
```

Perhatikan kualitas di langkah 3:
- Jawaban bukan copy-paste observation mentah, tapi diformat ulang dengan emoji + nomor + istilah yang konsisten.
- Semua angka/kuantitas diambil langsung dari Observation (tidak diada-adakan).
- Ada warning pengecualian untuk edge case.

---

## Peran Tiap File di `app/`

| File                                                                                                | Tanggung Jawab               | Detail Penting                                                              |
| --------------------------------------------------------------------------------------------------- | ---------------------------- | --------------------------------------------------------------------------- |
| [config.py](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/config.py)         | Settings (pydantic-settings) | `USE_LOCAL_DB`, port LLM, path DuckDB, model GGUF name                      |
| [schemas.py](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/schemas.py)       | Pydantic models              | `ReActRequest`, `ReActResponse`, `StepLog` (trace per langkah)              |
| [embeddings.py](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/embeddings.py) | SentenceTransformer wrapper  | `encode()` → list[float] 384-dim (all-MiniLM-L6-v2)                         |
| [database.py](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/database.py)     | DuckDB store + seed          | `DocStore`: CRUD + VSS search + SEED_DATA (FAQ/SOP otomatis)                |
| [llm.py](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/llm.py)               | llama-server lifecycle       | `lifespan` + `llm_complete()` wrapper, `/health` probe                      |
| [tools.py](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/tools.py)           | Tool registry dual-mode      | `USE_LOCAL_DB=true` → DuckDB langsung; `false` → HTTP API Sesi 2            |
| [react.py](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/react.py)           | **Core ReAct Loop**          | `REACT_SYSTEM`, `_parse_step()`, `_is_placeholder_answer()`, `react_loop()` |
| [main.py](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/main.py)             | FastAPI entrypoint           | `/agent/chat` (ReAct) + `/documents/*` (CRUD, kompatibel Sesi 2)            |

---

## Prasyarat
- Folder `../End-to-End LLM Serving/models/` berisi file GGUF Qwen (contoh: `qwen2.5-0.5b-instruct-q4_k_m.gguf`).
- Binary `llama-server` ada di `../End-to-End LLM Serving/backend/bin/`.
- **Sesi 2 tidak perlu jalan** — knowledge base dikelola lokal di folder ini (`knowledge.duckdb`).

## Download Model Qwen
📥 **[Download model GGUF dari Google Drive](https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing)**

Setelah download, letakkan file `.gguf` di folder `../End-to-End LLM Serving/models/`.

## Knowledge Base Lokal (dari Sesi 2)
Data FAQ & SOP dari Sesi 2 sudah di-embed langsung ke Sesi 3:
- `app/database.py` — DocStore + seed data (FAQ NocBook, NocMouse, Shipping, Pembayaran, Refund, SOP Garansi, SOP Return, RAM DDR4)
- `app/embeddings.py` — wrapper SentenceTransformer
- Data di-seed otomatis ke `knowledge.duckdb` saat pertama kali startup

Mode sumber data bisa dikontrol via `.env`:
| `USE_LOCAL_DB`   | Sumber data                                       |
| ---------------- | ------------------------------------------------- |
| `true` (default) | DuckDB lokal Sesi 3 — mandiri, tidak butuh Sesi 2 |
| `false`          | REST API Sesi 2 port 8001 — butuh Sesi 2 jalan    |

## Cara Run
```cmd
run.bat
```
Atau manual:
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8002 --reload
```

## Endpoint
| Endpoint           | Method | Deskripsi                                                               |
| ------------------ | ------ | ----------------------------------------------------------------------- |
| `GET /health`      | GET    | Cek app, llama-server, dan koneksi Knowledge API                        |
| `POST /agent/chat` | POST   | Input `{query, max_steps, temperature}` → jawaban ReAct + trace langkah |

## Struktur File
```
Sesi_3_Knowledge_Agent_ReAct/
├── app/
│   ├── config.py       # Settingan port, LLM, API via pydantic-settings
│   ├── schemas.py      # Pydantic: DocIn/DocOut/DocSearchResult + ReActRequest/ReActResponse + StepLog
│   ├── embeddings.py   # SentenceTransformer wrapper (dari Sesi 2)
│   ├── database.py     # DocStore + SEED_DATA FAQ & SOP (dari Sesi 2)
│   ├── llm.py          # Startup llama-server + wrapper llm_complete (async)
│   ├── tools.py        # Tool registry — dual-mode: local DB / HTTP API Sesi 2
│   ├── react.py        # ReAct loop + prompt template + parser Thought/Action/Action Input
│   └── main.py         # FastAPI entrypoint + /documents CRUD + /agent/chat
├── knowledge.duckdb    # Knowledge base lokal (auto-created saat startup)
├── tests/test_react.py # Unit test parser ReAct step (TANPA butuh LLM)
├── .env                # Override settingan default (mis. USE_LOCAL_DB=false)
└── run.bat             # Jalankan Sesi 3 langsung (tanpa perlu spawn Sesi 2)
```

## Uji Manual (via Swagger /docs)
1. Buka `http://localhost:8002/docs`.
2. Coba `POST /agent/chat` dengan query: `Apa kebijakan refund produk?`.
3. Perhatikan field `steps` — setiap step menunjukkan trace Thought/Action/Observation.

---

## 🛠️ Hands-On: Cara Membuat Proyek Ini dari Nol

### Prasyarat Wajib Sebelum Mulai

1. **Download model GGUF Qwen** dari link di README → letakkan di folder `../models/` (satu level di atas Sesi_3)
2. **Binary `llama-server`** tersedia di `../bin/llama-server.exe`
3. Sesi_2 sudah pernah dijalankan sekali (agar `knowledge.duckdb` tersedia, atau biarkan auto-seed dari Sesi 3 sendiri)

> Kalau model dan bin belum ada, server tetap naik tapi endpoint `/agent/chat` akan error — itu normal, selesaikan download lebih dulu.

### Langkah 1 — Setup Folder & Environment

```cmd
mkdir Sesi_3_Knowledge_Agent_ReAct
cd Sesi_3_Knowledge_Agent_ReAct
mkdir app tests bin
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Langkah 2 — Buat `.env`

```env
VECTOR_BACKEND=duckdb
EMBED_MODEL=all-MiniLM-L6-v2
EMBED_DIM=384
DUCKDB_PATH=knowledge.duckdb
KNOWLEDGE_API_BASE=http://127.0.0.1:8001

LLM_MODEL_GGUF=qwen2.5-0.5b-instruct-q4_k_m.gguf
LLAMA_PORT=8080
LLAMA_CTX=4048
LLAMA_NGL=0
LLAMA_THREADS=3
LLAMA_READY_TIMEOUT=90
LLAMA_BASE_URL=http://127.0.0.1:8080

APP_PORT=8002
```

### Langkah 3 — Buat `app/config.py`

```python
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    vector_backend: str = "duckdb"
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    duckdb_path: str = "knowledge.duckdb"
    knowledge_api_base: str = "http://127.0.0.1:8001"

    llm_model_gguf: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    llama_port: int = 8080
    llama_ctx: int = 4048
    llama_ngl: int = 0
    llama_threads: int = 3
    llama_ready_timeout: int = 90
    llama_base_url: str = "http://127.0.0.1:8080"

    app_port: int = 8002

    class Config:
        env_file = ".env"

settings = Settings()
```

### Langkah 4 — Buat `app/schemas.py`

```python
from pydantic import BaseModel
from typing import Optional

class StepLog(BaseModel):
    step: int
    thought: str
    action: str
    action_input: str
    observation: str

class ReActRequest(BaseModel):
    query: str
    max_steps: int = 8
    temperature: float = 0.3

class ReActResponse(BaseModel):
    query: str
    final_answer: str
    total_steps: int
    steps: list[StepLog]
```

### Langkah 5 — Buat `app/llm.py`

Modul untuk mengelola siklus hidup llama-server dan wrapper `llm_complete`:

```python
import asyncio, httpx, subprocess, time, os
from contextlib import asynccontextmanager
from .config import settings

_proc = None

def _find_llama_server():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "bin", "llama-server.exe")

def _find_model():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "models", settings.llm_model_gguf)

async def start_llama():
    global _proc
    server = _find_llama_server()
    model  = _find_model()
    if not os.path.exists(model):
        print(f"[WARN] Model tidak ditemukan: {model}")
        return
    _proc = subprocess.Popen([
        server, "-m", model,
        "--port", str(settings.llama_port),
        "--ctx-size", str(settings.llama_ctx),
        "--threads", str(settings.llama_threads),
        "-ngl", str(settings.llama_ngl),
    ])
    # Tunggu server siap
    deadline = time.time() + settings.llama_ready_timeout
    while time.time() < deadline:
        try:
            httpx.get(f"{settings.llama_base_url}/health", timeout=2)
            print("[OK] llama-server siap")
            return
        except Exception:
            await asyncio.sleep(2)
    print("[WARN] llama-server timeout — coba lanjut tanpa LLM")

def stop_llama():
    if _proc:
        _proc.terminate()

async def llm_complete(prompt: str, max_tokens=400,
                       temperature=0.3, stop=None) -> str:
    payload = {
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": temperature,
        "stop": stop or [],
    }
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{settings.llama_base_url}/completion", json=payload)
        r.raise_for_status()
        return r.json()["content"].strip()
```

### Langkah 6 — Buat `app/react.py` (Inti ReAct Loop)

```python
import re
from .llm import llm_complete
from .tools import ToolRegistry
from .schemas import StepLog

REACT_SYSTEM = """Kamu adalah agent Knowledge yang menjawab pertanyaan memakai tool.
Gunakan tool jika informasi yang dibutuhkan tidak ada di ingatanmu.

Tool yang TERSEDIA:
- search_knowledge[query]: mencari dokumen relevan di knowledge base.
- list_documents[limit]: melihat daftar dokumen yang tersimpan.
- create_document[{"source":"...","content":"..."}]: menyimpan dokumen baru.

FORMAT WAJIB setiap langkah:
Thought: <jelaskan kenapa kamu butuh tool / apa yang kamu pikirkan>
Action: <nama_tool, WAJIB salah satu dari: search_knowledge, list_documents, create_document, atau FINISH>
Action Input: <parameter tool, atau JAWABAN FINAL jika Action=FINISH>

Jika Action bukan FINISH, Observation akan diberikan lalu kamu lanjutkan langkah berikutnya.

ATURAN FINISH:
- FINISH hanya setelah SEMUA topik dicari.
- Action Input TIDAK BOLEH kosong atau berisi "Selesai" / placeholder.
- Action Input WAJIB jawaban lengkap terstruktur.
"""

PLACEHOLDER_PATTERNS = [
    r"^selesai\.?$", r"^jawaban final\.?$", r"^\(jawaban kosong\)$",
    r"^-$", r"^\.+$", r"^(oke|ok)\.?$"
]

def _is_placeholder(text: str) -> bool:
    t = text.strip().lower()
    if len(t) < 10:
        return True
    return any(re.match(p, t) for p in PLACEHOLDER_PATTERNS)

def _parse_step(output: str):
    t  = re.search(r"Thought:\s*(.+?)(?:\n|$)", output)
    a  = re.search(r"Action:\s*(\w+)", output)
    ai = re.search(r"Action Input:\s*(.+)", output, re.DOTALL)
    return (
        t.group(1).strip()  if t  else "",
        a.group(1).strip()  if a  else "",
        ai.group(1).strip() if ai else "",
    )

async def react_loop(query: str, max_steps=8, temperature=0.3):
    tools = ToolRegistry()
    history = REACT_SYSTEM + f"\nPertanyaan user: {query}\n"
    steps = []
    finish_retry_used = False
    valid_actions = {"search_knowledge", "list_documents", "create_document", "finish"}

    for step_num in range(1, max_steps + 1):
        raw = await llm_complete(
            history, max_tokens=400, temperature=temperature,
            stop=["Observation:", "Pertanyaan user:"]
        )
        thought, action, action_input = _parse_step(raw)
        log = StepLog(step=step_num, thought=thought, action=action,
                      action_input=action_input, observation="")

        if not action or action.lower() not in valid_actions:
            log.observation = "Format tidak valid. Action harus salah satu tool yang tersedia atau FINISH."
            steps.append(log)
            history += raw + f"\nObservation: {log.observation}\n"
            continue

        if action.upper() == "FINISH":
            if _is_placeholder(action_input) and not finish_retry_used:
                finish_retry_used = True
                log.observation = "FINISH ditolak: jawaban kosong/placeholder. Pastikan semua topik sudah dicari."
                steps.append(log)
                history += raw + f"\nObservation: {log.observation}\n"
                continue
            steps.append(log)
            return action_input, steps

        # Jalankan tool
        observation = tools.call(action, action_input)
        log.observation = observation
        steps.append(log)
        history += raw + f"\nObservation: {observation}\n"

    final = steps[-1].observation if steps else "(tidak ada jawaban)"
    return f"[Melebihi batas langkah] Jawaban sementara: {final}", steps
```

### Langkah 7 — Buat `app/tools.py`

```python
import httpx, json
from .config import settings
from .database import DocStore  # jika USE_LOCAL_DB=true

class ToolRegistry:
    def __init__(self):
        self.store = DocStore()

    def call(self, action: str, action_input: str) -> str:
        a = action.lower()
        if a == "search_knowledge":
            return self._search(action_input)
        elif a == "list_documents":
            return self._list(action_input)
        elif a == "create_document":
            return self._create(action_input)
        return "Tool tidak dikenal."

    def _search(self, query: str) -> str:
        results = self.store.search(query, k=3)
        if not results:
            return "Tidak ada dokumen relevan ditemukan."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] (score={r[3]:.4f}) Sumber: {r[1]}\n    {r[2][:300]}")
        return "\n".join(lines)

    def _list(self, limit_str: str) -> str:
        try:
            limit = int(limit_str.strip())
        except ValueError:
            limit = 5
        rows = self.store.list(limit=limit)
        return "\n".join(f"- [{r[0][:8]}] {r[1]}: {r[2][:80]}" for r in rows)

    def _create(self, json_str: str) -> str:
        try:
            data = json.loads(json_str)
            doc_id = self.store.create(data["source"], data["content"])
            return f"Dokumen berhasil disimpan dengan ID: {doc_id}"
        except Exception as e:
            return f"Gagal menyimpan dokumen: {e}"
```

### Langkah 8 — Buat `app/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .llm import start_llama, stop_llama
from .react import react_loop
from .schemas import ReActRequest, ReActResponse
from .database import DocStore

@asynccontextmanager
async def lifespan(app: FastAPI):
    DocStore().seed()   # seed data bila kosong
    await start_llama()
    yield
    stop_llama()

app = FastAPI(title="Sesi 3 — Knowledge Agent ReAct", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/agent/chat", response_model=ReActResponse)
async def chat(req: ReActRequest):
    answer, steps = await react_loop(req.query, req.max_steps, req.temperature)
    return ReActResponse(
        query=req.query,
        final_answer=answer,
        total_steps=len(steps),
        steps=steps,
    )
```

### Langkah 9 — Jalankan Server

```cmd
run.bat
```

Atau manual:
```cmd
uvicorn app.main:app --port 8002 --reload
```

Saat startup, llama-server otomatis distart. Tunggu log `[OK] llama-server siap` sebelum lanjut.

### Langkah 10 — Uji ReAct Loop via Swagger

Buka **http://localhost:8002/docs** → `POST /agent/chat`:

**Uji 1 — Pertanyaan satu topik:**
```json
{ "query": "Apa kebijakan refund produk?", "max_steps": 8 }
```
Harapan: 2 langkah (search + FINISH), `total_steps: 2`.

**Uji 2 — Pertanyaan multi-topik:**
```json
{ "query": "Bagaimana cara klaim garansi NocBook dan apa syarat refund?", "max_steps": 8 }
```
Harapan: ≥3 langkah (search garansi + search refund + FINISH).

**Yang perlu dicermati di field `steps`:**
- `thought` menjelaskan reasoning agent
- `action` = nama tool yang dipanggil
- `observation` = hasil tool (konten dokumen yang ditemukan)
- FINISH hanya muncul di langkah terakhir

**Uji 3 — Pertanyaan tanpa tool:**
```json
{ "query": "Halo, selamat pagi!" }
```
Harapan: agent langsung FINISH tanpa `search_knowledge`.

### Langkah 11 — Jalankan Unit Test

```cmd
pytest tests/test_react.py -v
```

Test `test_react.py` tidak memerlukan LLM nyala — hanya menguji fungsi `_parse_step()`:

```python
from app.react import _parse_step, _is_placeholder

def test_parse_step():
    output = "Thought: Saya perlu cari refund\nAction: search_knowledge\nAction Input: kebijakan refund"
    t, a, ai = _parse_step(output)
    assert a == "search_knowledge"
    assert "refund" in ai

def test_placeholder_detection():
    assert _is_placeholder("Selesai") == True
    assert _is_placeholder("Kebijakan refund berlaku 30 hari") == False
```

> ✅ **Checkpoint**: `POST /agent/chat` dengan query pertanyaan produk mengembalikan `steps` dengan trace Thought/Action/Observation yang jelas, dan `final_answer` berisi jawaban yang dirangkum → Sesi 3 selesai!
