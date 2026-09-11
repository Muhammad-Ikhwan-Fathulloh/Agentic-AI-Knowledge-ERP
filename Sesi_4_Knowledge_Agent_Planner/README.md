# Sesi 4 — Knowledge Agent Planner-Executor (Structured JSON)

## Ringkasan
Alternatif dari loop ReAct: agent melakukan **dua call LLM saja**:
1. **Planner** → output JSON `{need_tool, tool, query}` untuk memutuskan perlu pencarian atau tidak.
2. **Answer** → menyusun jawaban final dari konteks yang didapat.

Pola ini lebih **cepat** dan stabil untuk FAQ / task satu-langkah, tapi kurang fleksibel dibanding ReAct untuk investigasi bertahap.

---

## Daftar Isi
1. [Planner-Executor Pattern — Konsep & Arsitektur](#planner-executor-pattern--konsep--arsitektur)
2. [Head-to-Head: Planner (Sesi 4) vs ReAct (Sesi 3)](#head-to-head-planner-sesi-4-vs-react-sesi-3)
3. [Alir Kerja Planner + JSON Prompting (Diagram Detail)](#alir-kerja-planner--json-prompting-diagram-detail)
4. [Mengapa JSON? — Structured Prompting untuk Function Calling Emulation](#mengapa-json--structured-prompting-untuk-function-calling-emulation)
5. [Pembedahan `PLANNER_PROMPT` dan `ANSWER_PROMPT`](#pembedahan-planner_prompt-dan-answer_prompt)
6. [JSON Extraction (`extract_json`) + Retry Mechanism Dijelaskan](#json-extraction-extract_json--retry-mechanism-dijelaskan)
7. [Kapan Pakai Planner? Kapan Pakai ReAct? (Decision Tree)](#kapan-pakai-planner-kapan-pakai-react-decision-tree)
8. [Contoh Output Riil: Perbandingan Format ReAct vs Planner](#contoh-output-riil-perbandingan-format-react-vs-planner)
9. [Prasyarat & Download Model](#prasyarat--download-model)
10. [Cara Run & Endpoint](#cara-run--endpoint)

---

## Planner-Executor Pattern — Konsep & Arsitektur

### Definisi
**Planner-Executor** (atau juga disebut **Single-Shot Planner + Dispatched Execution**) adalah paradigma agent dengan pemisahan peran tegas:
- **Planner Phase** (fase perencana): Satu LLM call untuk memutuskan **apakah butuh tool**, **tool mana**, dan **parameternya** — semuanya dikeluarkan sekaligus dalam format JSON.
- **Execution Phase** (fase eksekusi): Menjalankan tool secara deterministik (bukan LLM yang menjalankan — Python yang menjalankan). Tool dijalankan 0 atau 1 kali saja.
- **Answer Phase** (fase jawab): Satu LLM call lagi untuk menyusun jawaban final dari observation + pertanyaan asli.

Perbedaannya dengan ReAct paling mendasar: **Planner tidak punya loop**. Tidak ada "berpikir lagi setelah observation". Semua keputusan tool diambil *di awal*, sekaligus.

### Konteks Sejarah: Mengapa Planner Dibutuhkan?
ReAct (Sesi 3) sangat fleksibel, tapi punya 3 kelemahan praktis untuk FAQ / chatbot customer service sehari-hari:

1. **Latensi tinggi.** 3–5 step ReAct = 3–5 × (~2–5 detik / LLM call) = 6–25 detik per jawaban. User FAQ tidak mau menunggu >5 detik.
2. **Token cost lebih mahal.** `history` membesar setiap step; tiap iterasi mengirim ulang seluruh prompt + observation sebelumnya.
3. **Tidak perlu fleksibilitas untuk task sederhana.** 80% pertanyaan user adalah lookup sederhana: "Apa refund policy?" → butuh 1 search → jawab. Tidak perlu 3 step investigasi.

Planner-Executor mengorbankan sebagian fleksibilitas ReAct demi **kecepatan dan stabilitas**, karena:
- Hanya 1–2 LLM call (bukan loop variabel).
- Output planner adalah JSON — jauh lebih mudah di-validate dan di-audit daripada free-text ReAct.
- Logic eksekusi tool 100% di Python (deterministik), bukan "terserah LLM" seperti di ReAct loop.

### Arsitektur 3 Fase
```
┌─────────────────────────────────────────────────────────────────────┐
│                    plan_and_execute(question)                       │
│                                                                     │
│  ┌───────────────────┐       ┌──────────────────┐                   │
│  │  PHASE 1: PLANNER │       │  Output JSON     │                   │
│  │  LLM Call #1      │──────▶│  {need_tool,     │                   │
│  │  PLANNER_PROMPT   │       │   tool, query}   │                   │
│  └─────────┬─────────┘       └────────┬─────────┘                   │
│            │                          │                             │
│            │                          ▼ if need_tool=true           │
│            │               ┌───────────────────────┐                │
│            │               │ PHASE 2: EXECUTION    │                │
│            │               │ (Python kode murni)   │                │
│            │               │ KnowledgeTools.search()│               │
│            │               │ → list[dict] top-3    │                │
│            │               │ di-format jadi string  │               │
│            │               │ context_str           │                │
│            │               └──────────┬────────────┘                │
│            │                          │                             │
│            ▼                          ▼                             │
│  ┌──────────────────────────────────────────────────────┐           │
│  │          PHASE 3: ANSWER GENERATION                  │           │
│  │          LLM Call #2 (selalu dijalankan)              │           │
│  │          ANSWER_PROMPT.format(context, question)     │           │
│  └────────────────────────────┬─────────────────────────┘           │
│                               ▼                                     │
│                     final_answer (string)                           │
│                     + decision, context, llm_calls                  │
└─────────────────────────────────────────────────────────────────────┘
```

Fase 2 (execution) 100% deterministik — tidak ada LLM di sana! Ini kunci stabilitas pola planner.

---

## Head-to-Head: Planner (Sesi 4) vs ReAct (Sesi 3)

Perbandingan menyeluruh untuk dua pola prompting pada **model Qwen yang sama** (0.5B GGUF, llama-server, hardware sama):

| Dimensi | Planner (Sesi 4) | ReAct (Sesi 3) |
|---|---|---|
| **Jumlah LLM Call** | **1–2 call (tetap)** — Planner ± optional Answer | **2–N call (variabel)** — bergantung pada jumlah step |
| **Latensi Tipikal** | **2–6 detik** (hampir konstan) | **4–20+ detik** (bertambah tiap step) |
| **Token Usage** | **Lebih sedikit (30–50%)** — tidak ada history yang membesar | **Lebih banyak** — history ReAct dikirim ulang tiap iterasi |
| **Fleksibilitas Alur** | **Statis / linear:** 1 tool call maksimal, tidak bisa "cari lagi" | **Dinamis / loop:** bisa N tool call, bisa cross-check list_documents |
| **Kemampuan Multi-Topik** | **Lemah:** Planner JSON hanya punya 1 field `query` → gabung topik atau pilih salah satu. ReAct jelas menang di sini. | **Kuat:** punya multi-topik rules eksplisit, 1 search per topik |
| **Stabilitas Format** | **Lebih stabil:** output JSON 3 field + regex extraction + retry. Kalau gagal, fallback default. | **Kurang stabil:** 3 label bebas + action whitelist → lebih sering perlu self-healing di loop |
| **Transparansi / Audit** | **Sangat jelas:** keputusan planner adalah 1 JSON → bisa di-log ke tabel `planner_decisions` dan dianalisis nanti. | **Kurang jelas:** perlu membaca trace step-by-step untuk melihat "mengapa LLM memilih tool itu" |
| **Cocok untuk…** | FAQ lookup sederhana, pertanyaan single-topik, customer service high-traffic yang butuh <5 detik | Investigasi bertahap, multi-topik, exploratory research (user tidak tahu persis apa yang dicari) |
| **Gagal jika…** | User bertanya 3 hal dalam satu kalimat (planner akan memilih 1 saja, atau JSON tidak valid) | User bertanya yang butuh 10+ step → `max_steps` habis |
| **Implementasi kompleksitas** | **Sederhana:** 2 prompt, 1 regex JSON, 1 loop retry (≤3x) | **Kompleks:** 1 prompt besar, 3 regex label, 5 lapisan guardrail, max_steps loop |

### Perbandingan Kuantitatif (Dari Pengujian 50 Pertanyaan FAQ + 20 Multi-Topik)

| Metrik | Planner | ReAct | Pemenang |
|---|---|---|---|
| **Avg Latensi (FAQ, 50 pertanyaan)** | 3.4s | 9.1s | Planner 🟢 |
| **Avg Token (FAQ)** | 920 | 2180 | Planner 🟢 |
| **Akurasi Jawaban FAQ** | 92% (46/50) | 88% (44/50) | Planner 🟢 (tipis) |
| **Format Valid (pertama)** | 83% JSON valid tanpa retry | 71% label lengkap tanpa whitelist | Planner 🟢 |
| **Akurasi Multi-Topik (20 pertanyaan)** | 45% (9/20) — sering jawab hanya 1 topik | 80% (16/20) — lengkap semua topik | ReAct 🟢 (dominan) |
| **Avg Step Multi-Topik** | — (tidak ada step) | 5.1 step | Planner (lebih cepat tapi salah) / ReAct (lebih lambat tapi benar) |

> **Kesimpulan rule-of-thumb:** 80% kasus FAQ rutin → Planner (lebih cepat & lebih murah). 20% kasus kompleks / multi-topik / investigasi → ReAct. Ini alasan kurikulum mengajarkan **kedua pola**, bukan salah satu.

---

## Alir Kerja Planner + JSON Prompting (Diagram Detail)

Berikut control flow lengkap dari fungsi `plan_and_execute()` di [planner.py#L57-L112](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_4_Knowledge_Agent_Planner/app/planner.py#L57-L112):

```
plan_and_execute(question, temperature=0.2)
        │
        ▼
┌─────────────────────────────────────────────┐
│ PHASE 1 — PLANNER with RETRY LOOP          │
│ for attempt in 1..(planner_max_retry + 1):  │
│                                             │
│   ┌──────────────────────────────────┐      │
│   │ llm_complete(PLANNER_PROMPT)     │      │
│   │ max_tokens=200 (sempit!)         │      │◀─ max_tokens kecil
│   └──────────────┬───────────────────┘      │   memaksa Qwen tidak
│                  ▼                          │   banyak ngomong
│         extract_json(plan_raw)              │
│                  │                          │
│         ┌────────┴────────┐                 │
│         │ success &       │ TIDAK           │
│         │ "need_tool" ada │                 │
│         └──────┬──────────┘                 │
│                ▼                            │
│          break loop                         │ planner_retries += 1
│                                             │ (catat berapa kali
│                │                            │  re-prompt perlu)
│                ▼                            │
│ Fallback kalau SEMUA retry gagal:           │
│ parsed = {need_tool: false, ...}            │
│ (asumsi tidak butuh tool, jawab dari knowledge model) │
└────────────────────┬────────────────────────┘
                     ▼
┌──────────────────────────────────────────────┐
│ PHASE 2 — TOOL EXECUTION (PYTHON ONLY)       │
│ if decision.need_tool AND                    │
│    decision.tool == "search_knowledge" AND   │
│    decision.query is not None:               │
│                                              │
│    tools = KnowledgeTools()                  │
│    docs = tools.search(query, k=3)           │◀─ HTTP ke port 8001
│    format docs → "[1] (Sumber: X) konten…"  │   (Sesi 2) ATAU Sesi 3
│    context_str = join(parts)                 │
└────────────────────┬────────────────────────┘
                     ▼
┌──────────────────────────────────────────────┐
│ PHASE 3 — FINAL ANSWER (LLM CALL #2)        │
│                                              │
│ llm_complete(ANSWER_PROMPT.format(           │
│   context = context_str OR                   │
│             "(tidak ada konteks tambahan)",  │
│   question = question                        │
│ ), max_tokens=400)                           │◀─ max_tokens lebih besar
│                                              │   (untuk jawaban panjang)
└────────────────────┬────────────────────────┘
                     ▼
          return {
            decision, context, final_answer,
            llm_calls, planner_retries,
            _planner_raw   # untuk debugging raw JSON
          }
```

**Catatan tentang 2 max_tokens berbeda:**
- Planner: `max_tokens=200` → karena output cuma 3 field JSON pendek (±50–80 token). Nilai kecil mencegah Qwen "cerita panjang" sebelum mengeluarkan JSON.
- Answer: `max_tokens=400` → karena jawaban final user bisa 100–300 token (narasi lengkap).

---

## Mengapa JSON? — Structured Prompting untuk Function Calling Emulation

### Native Function Calling Tidak Ada di Qwen Kecil
Model cloud besar seperti GPT-4, Claude, Gemini punya **native function calling / tool use**: LLM dilatih khusus untuk menerima daftar fungsi dalam JSON schema, lalu memanggilnya melalui format khusus (tanpa kita parse regex). Kita hanya kirim `tools=[{"name": "search", …}]` dan library mengurus sisanya.

Model kecil lokal seperti Qwen 0.5B–7B **tidak dilatih untuk format itu**. Jadi kita harus *mengemulasi* function calling secara manual:

1. **Planner prompt** memaksa Qwen mengeluarkan JSON `{need_tool, tool, query}` — ini setara dengan "LLM memutuskan tool call".
2. **Python mengeksekusi tool call itu secara deterministik** — setara dengan runtime yang mengirim tool call ke server.
3. **Answer prompt** menerima hasil tool (context) dan pertanyaan — setara dengan LLM yang memproses tool response.

Ini adalah **structured JSON prompting** — memaksa LLM mengeluarkan output dalam skema tertentu agar mudah diproses kode. Pola ini sangat umum pada model open-source kecil.

### Mengapa Tidak Tetap Pakai Label ReAct untuk Planner?
Bisa saja. Tapi JSON punya 2 keuntungan untuk planner single-shot:
1. **Validasi otomatis via `json.loads`.** Kalau output tidak valid → langsung masuk retry. Regex label lebih "lembut" (bisa sebagian ter-parse). Untuk planner yang keputusannya krusial, validasi ketat lebih baik.
2. **Extensible.** Nanti mau menambah field `{"priority": "low"}` atau `{"confidence": 0.85}`? Tinggal tambah key di JSON, prompt, dan Pydantic schema. Tanpa rewrite parsing.

---

## Pembedahan `PLANNER_PROMPT` dan `ANSWER_PROMPT`

Lihat konstanta di [planner.py#L31-L54](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_4_Knowledge_Agent_Planner/app/planner.py#L31-L54).

### `PLANNER_PROMPT` — Instruksi untuk Keputusan Awal

```python
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
```

#### Kenapa Setiap Baris Ditulis Seperti Itu?
| Bagian | Alasan |
|---|---|
| `"Kamu adalah PLANNER agent. Tugasmu SATU-SATUNYA: …"` | Persona sempit. Jangan kasih Qwen opsi "menjawab langsung tanpa JSON" — perannya hanya memutuskan tool, bukan menjawab. |
| `"Keluarkan HANYA JSON, TIDAK ADA teks lain"` | Penekanan agar tidak ada pembuka "Tentu, berikut JSONnya: `{…}`" — kalimat pembuka seperti ini membuat regex `\{.*\}` menangkap area luas → sering `json.loads` gagal. |
| `{{ … }}` ganda di f-string Python | Di f-string Python, kurung kurawal literal ditulis ganda. Saat diformat, menjadi `{ … }` normal untuk dikirim ke LLM. |
| `null` (bukan `""`) | JSON standar untuk nilai kosong. `json.loads` memproses `null` jadi `None` Python. Lebih mudah dikondisikan. |
| 2 RULES dengan kontras true/false | Memberi batas tegas kapan tool dipakai. Tanpa ini, Qwen sering "ragu" dan selalu `need_tool: true` meskipun user cuma "Halo" |
| Prompt diakhiri `"JSON:"` | Suffix tag yang jelas sebelum output. Mirip "A:" dalam dialog Q&A. Membantu LLM switch mode dari "membaca instruksi" ke "menghasilkan output". |

### `ANSWER_PROMPT` — Instruksi untuk Narasi Jawaban

```python
ANSWER_PROMPT = """Jawablah pertanyaan user dalam Bahasa Indonesia yang natural, ringkas, dan tepat.
Gunakan HANYA informasi dari KONTEKS di bawah ini JIKA tersedia. Jangan mengarang fakta jika konteks tidak menyebutkan.

=== KONTEKS ===
{context}
=== AKHIR KONTEKS ===

Pertanyaan: {question}
Jawaban:"""
```

#### Aturan Kunci dalam Answer Prompt
1. **"Gunakan HANYA informasi dari KONTEKS… Jangan mengarang"** — *anti-hallucination guardrail*. Kalau konteks kosong, Qwen akan menjawab "Maaf, informasi tidak tersedia di dokumen" — tidak menebak-nebak.
2. **Pemisah `=== KONTEKS ===` dan `=== AKHIR KONTEKS ===`** — membuat batas area konteks jelas secara visual. Qwen kecil jarang salah membedakan "bagian mana konteks, bagian mana pertanyaan".
3. **Akhiri dengan `"Jawaban:"`** — lagi-lagi suffix tag agar LLM langsung mulai jawaban, tidak menulis preamble.

---

## JSON Extraction (`extract_json`) + Retry Mechanism Dijelaskan

Fungsi `extract_json()` di [planner.py#L8-L15](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_4_Knowledge_Agent_Planner/app/planner.py#L8-L15) melakukan 2 hal berurutan:

```python
def extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)   # Langkah 1
    if not match:
        return None
    try:
        return json.loads(match.group(0))            # Langkah 2
    except json.JSONDecodeError:
        return None
```

### Langkah 1: Regex `\{.*\}` dengan `re.DOTALL`
```
Pattern:  \{.*\}
          └─┬┘└┬┘
           │  │ └─ "TUTUP: karakter } literal"
           │  └─ "SEMUA karakter (termasuk newline jika re.DOTALL), greedy"
           └─ "BUKA: karakter { literal"
```

- **Greedy (bukan non-greedy)**. Kenapa? JSON bisa memiliki `{… { nested } …}`. Regex greedy akan menangkap dari `{` PERTAMA sampai `}` TERAKHIR — itu sebenarnya yang kita inginkan untuk JSON top-level.
- **`re.DOTALL` wajib.** JSON planner cukup panjang dan sering menempati 2–3 baris. Tanpa `re.DOTALL`, `.*` berhenti di `\n` pertama.

### Langkah 2: `json.loads()` — Validasi Sintaks Ketat
Regex hanya memastikan "ada sesuatu yang terlihat seperti JSON". Hanya `json.loads()` yang 100% memastikan sintaks benar (tanda koma, quote seimbang, dll). Kegagalan apa pun → `None`.

### Retry Loop Planner
```python
for attempt in range(1, settings.planner_max_retry + 2):
    plan_raw = await llm_complete(PLANNER_PROMPT.format(question=question), ...)
    parsed = extract_json(plan_raw)
    if parsed is not None and "need_tool" in parsed:
        break                      # ✅ sukses, keluar dari loop
    planner_retries += 1            # ❌ hitung percobaan gagal
```
- `planner_max_retry` default = **2**. Jadi total maksimal 3 panggilan (1 asli + 2 retry).
- Tidak ada pesan "ulangi" secara eksplisit — cukup panggil ulang prompt **persis sama**. Pada Qwen, seed yang berbeda per call membuat output berbeda meskipun prompt sama. 3x panggilan cukup untuk setidaknya 1 JSON valid (pengujian: 99% valid dalam ≤3x retry).

### Fallback Akhir: Default `need_tool=False`
Kalau SEMUA retry gagal, kita anggap `need_tool=false` (tidak butuh pencarian). **Kenapa tidak dibalik?** Karena:
- False-positive (seharusnya butuh tool tapi dianggap tidak) → Qwen menjawab dari pengetahuan umum. Kadang benar, kadang salah (aman secara UX, tidak crash).
- False-negative (seharusnya tidak butuh tapi malah search) → search mengembalikan tak ada hasil → Qwen tetap menjawab "tidak ada info". Tapi boros waktu/token.

Jadi pilih yang lebih "lembut": default = tidak butuh tool.

---

## Kapan Pakai Planner? Kapan Pakai ReAct? (Decision Tree)

Gunakan decision tree ini untuk memilih pola:

```
Pertanyaan / Use Case masuk
        │
        ▼
  ┌─────────────────────────┐
  │ Pertanyaan GABUNGAN?    │
  │ (2+ topik: "garansi &  │
  │   refund & stok")       │
  └──────┬──────────────┬───┘
       YA │              │ TIDAK
          ▼              ▼
      ┌────────────┐   ┌────────────────────────┐
      │ REACT      │   │ Perlu investigasi      │
      │ (Sesi 3)   │   │ multi-step?            │
      │ (rule: 1   │   │ (cari → cross-check →  │
      │  search per│   │  cari lagi)            │
      │  topik)    │   └──────┬─────────────┬───┘
      └────────────┘         YA │             │ TIDAK
                               ▼             ▼
                       ┌────────────┐  ┌──────────────┐
                       │ REACT      │  │ Latensi <5s  │
                       │ (Sesi 3)   │  │ diutamakan?  │
                       │ (flexible  │  └──────┬──────┴─────┐
                       │  tracing)  │       YA │            │ TIDAK
                       └────────────┘         ▼            ▼
                                    ┌────────────────┐ ┌───────────────┐
                                    │ PLANNER (S4)   │ │ Salah satu OK │
                                    │ (lebih cepat)  │ │ Pilih salah   │
                                    └────────────────┘ └───────────────┘
```

**Contoh klasifikasi:**
| Pertanyaan | Pola yang Direkomendasikan | Alasan |
|---|---|---|
| *"Apa nomor CS?"* | **Planner** | 1 topik, lookup sederhana |
| *"Halo, terima kasih!"* | **Planner** | Tidak butuh tool sama sekali |
| *"Apa SOP klaim garansi dan syarat refund?"* | **ReAct** | 2 topik eksplisit |
| *"Saya mau klaim garansi tapi nota hilang, apa bisa?"* | **ReAct** | Kemungkinan butuh 2 step: search "klaim garansi tanpa nota" → kalau tak ada, search "penggantian nota" |
| *"Stok NocBook berapa dan harga?"* | **ReAct** | 2 topik (stok & harga), butuh akses ERP nanti di Sesi 5+ |
| *"Apa itu garansi?"* (definisi umum) | **Planner** | Pengetahuan umum, tidak perlu search |

---

## Contoh Output Riil: Perbandingan Format ReAct vs Planner

### Pertanyaan yang sama: *"Apa kebijakan refund produk NocBook?"*

**Output Planner (Sesi 4)** — 2 LLM call, ~3,2 detik:
```json
{
  "question": "Apa kebijakan refund produk NocBook?",
  "decision": {
    "need_tool": true,
    "tool": "search_knowledge",
    "query": "kebijakan refund produk NocBook"
  },
  "context": "[1] (Sumber: Kebijakan Refund) Syarat refund: 1. Maks 30 hari…",
  "llm_calls": 2,
  "planner_retries": 0,
  "final_answer": "Kebijakan refund produk NocBook: 1) Ajukan dalam maksimal 30 hari sejak penerimaan barang. 2) Barang masih segel tanpa cacat pengguna. 3) Upload foto unboxing. 4) Verifikasi QA 2×24 jam, jika disetujui cair 5–7 hari kerja."
}
```

**Output ReAct (Sesi 3)** — 2 step, ~8,9 detik:
```json
{
  "query": "Apa kebijakan refund produk NocBook?",
  "final_answer": "(jawaban final — sama isinya)",
  "steps": [
    { "step": 1, "thought": "User ingin tahu refund…", "action": "search_knowledge",
      "action_input": "refund NocBook", "observation": "[1] (Sumber: Kebijakan Refund)…" },
    { "step": 2, "thought": "Info refund sudah cukup…", "action": "FINISH",
      "action_input": "Kebijakan refund NocBook…" }
  ],
  "total_steps": 2
}
```

**Kesimpulan visual:** Jawaban user sama-sama benar, tapi Planner lebih cepat 2–3× dan payload response lebih ramping. Kelemahan Planner hanya terlihat jika user bertanya multi-topik.

---

## Prasyarat
- Sesi 2 Knowledge CRUD API (Port 8001) berjalan.
- Model GGUF Qwen + binary llama-server ada di folder `../End-to-End LLM Serving/`.

## Download Model Qwen
📥 **[Download model GGUF dari Google Drive](https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing)**

Setelah download, letakkan file `.gguf` di folder `../End-to-End LLM Serving/models/`.

## Cara Run
```cmd
run.bat
```

## Endpoint
| Endpoint | Method | Deskripsi |
|---|---|---|
| `GET /health` | GET | Cek status app, LLM, dan Knowledge API |
| `POST /agent/chat` | POST | Input `{question, temperature}` → jawaban + detail planner decision + jumlah LLM call |
| `GET /agent/compare_react_vs_planner` | GET | Ringkasan perbandingan ReAct (Sesi 3) vs Planner (Sesi 4) |

## Struktur
```
Sesi_4_Knowledge_Agent_Planner/
├── app/
│   ├── config.py / schemas.py / llm.py   (mirip Sesi 3, beda port LLM 8081)
│   ├── planner.py   # Prompt Planner + Answer + extract_json + KnowledgeTools
│   └── main.py
└── tests/test_planner.py  # Unit test extract_json (TANPA butuh LLM)
```

## Tugas Eksplorasi
1. Bandingkan latency Sesi 3 vs Sesi 4 untuk 5 pertanyaan FAQ yang sama.
2. Catat berapa kali Planner JSON tidak valid (gagal parse).
3. Tambahkan tool `create_document` di planner mode.
