# Sesi 4 - Knowledge Agent Planner-Executor (Structured JSON)

## Ringkasan
Alternatif dari loop ReAct: agent melakukan **dua call LLM saja**:
1. **Planner** → output JSON `{need_tool, tool, query}` untuk memutuskan perlu pencarian atau tidak.
2. **Answer** → menyusun jawaban final dari konteks yang didapat.

Pola ini lebih **cepat** dan stabil untuk FAQ / task satu-langkah, tapi kurang fleksibel dibanding ReAct untuk investigasi bertahap.

---

## Daftar Isi
- [Sesi 4 - Knowledge Agent Planner-Executor (Structured JSON)](#sesi-4--knowledge-agent-planner-executor-structured-json)
  - [Ringkasan](#ringkasan)
  - [Daftar Isi](#daftar-isi)
  - [Planner-Executor Pattern - Konsep \& Arsitektur](#planner-executor-pattern--konsep--arsitektur)
    - [Definisi](#definisi)
    - [Konteks Sejarah: Mengapa Planner Dibutuhkan?](#konteks-sejarah-mengapa-planner-dibutuhkan)
    - [Arsitektur 3 Fase](#arsitektur-3-fase)
  - [Head-to-Head: Planner (Sesi 4) vs ReAct (Sesi 3)](#head-to-head-planner-sesi-4-vs-react-sesi-3)
    - [Perbandingan Kuantitatif (Dari Pengujian 50 Pertanyaan FAQ + 20 Multi-Topik)](#perbandingan-kuantitatif-dari-pengujian-50-pertanyaan-faq--20-multi-topik)
  - [Alir Kerja Planner + JSON Prompting (Diagram Detail)](#alir-kerja-planner--json-prompting-diagram-detail)
  - [Mengapa JSON? - Structured Prompting untuk Function Calling Emulation](#mengapa-json--structured-prompting-untuk-function-calling-emulation)
    - [Native Function Calling Tidak Ada di Qwen Kecil](#native-function-calling-tidak-ada-di-qwen-kecil)
    - [Mengapa Tidak Tetap Pakai Label ReAct untuk Planner?](#mengapa-tidak-tetap-pakai-label-react-untuk-planner)
  - [Pembedahan `PLANNER_PROMPT` dan `ANSWER_PROMPT`](#pembedahan-planner_prompt-dan-answer_prompt)
    - [`PLANNER_PROMPT` - Instruksi untuk Keputusan Awal](#planner_prompt--instruksi-untuk-keputusan-awal)
      - [Kenapa Setiap Baris Ditulis Seperti Itu?](#kenapa-setiap-baris-ditulis-seperti-itu)
    - [`ANSWER_PROMPT` - Instruksi untuk Narasi Jawaban](#answer_prompt--instruksi-untuk-narasi-jawaban)
      - [Aturan Kunci dalam Answer Prompt](#aturan-kunci-dalam-answer-prompt)
  - [JSON Extraction (`extract_json`) + Retry Mechanism Dijelaskan](#json-extraction-extract_json--retry-mechanism-dijelaskan)
    - [Langkah 1: Regex `\{.*\}` dengan `re.DOTALL`](#langkah-1-regex--dengan-redotall)
    - [Langkah 2: `json.loads()` - Validasi Sintaks Ketat](#langkah-2-jsonloads--validasi-sintaks-ketat)
    - [Retry Loop Planner](#retry-loop-planner)
    - [Fallback Akhir: Default `need_tool=False`](#fallback-akhir-default-need_toolfalse)
  - [Kapan Pakai Planner? Kapan Pakai ReAct? (Decision Tree)](#kapan-pakai-planner-kapan-pakai-react-decision-tree)
  - [Contoh Output Riil: Perbandingan Format ReAct vs Planner](#contoh-output-riil-perbandingan-format-react-vs-planner)
    - [Pertanyaan yang sama: *"Apa kebijakan refund produk NocBook?"*](#pertanyaan-yang-sama-apa-kebijakan-refund-produk-nocbook)
  - [Prasyarat](#prasyarat)
  - [Prasyarat](#prasyarat)
  - [Persiapan llama.cpp & Model Lokal](#persiapan-llamacpp--model-lokal)
  - [Cara Run](#cara-run)
  - [Endpoint](#endpoint)
  - [Struktur](#struktur)
  - [Tugas Eksplorasi](#tugas-eksplorasi)

---

## Planner-Executor Pattern - Konsep & Arsitektur

### Definisi
**Planner-Executor** (atau juga disebut **Single-Shot Planner + Dispatched Execution**) adalah paradigma agent dengan pemisahan peran tegas:
- **Planner Phase** (fase perencana): Satu LLM call untuk memutuskan **apakah butuh tool**, **tool mana**, dan **parameternya** - semuanya dikeluarkan sekaligus dalam format JSON.
- **Execution Phase** (fase eksekusi): Menjalankan tool secara deterministik (bukan LLM yang menjalankan - Python yang menjalankan). Tool dijalankan 0 atau 1 kali saja.
- **Answer Phase** (fase jawab): Satu LLM call lagi untuk menyusun jawaban final dari observation + pertanyaan asli.

Perbedaannya dengan ReAct paling mendasar: **Planner tidak punya loop**. Tidak ada "berpikir lagi setelah observation". Semua keputusan tool diambil *di awal*, sekaligus.

### Konteks Sejarah: Mengapa Planner Dibutuhkan?
ReAct (Sesi 3) sangat fleksibel, tapi punya 3 kelemahan praktis untuk FAQ / chatbot customer service sehari-hari:

1. **Latensi tinggi.** 3–5 step ReAct = 3–5 × (~2–5 detik / LLM call) = 6–25 detik per jawaban. User FAQ tidak mau menunggu >5 detik.
2. **Token cost lebih mahal.** `history` membesar setiap step; tiap iterasi mengirim ulang seluruh prompt + observation sebelumnya.
3. **Tidak perlu fleksibilitas untuk task sederhana.** 80% pertanyaan user adalah lookup sederhana: "Apa refund policy?" → butuh 1 search → jawab. Tidak perlu 3 step investigasi.

Planner-Executor mengorbankan sebagian fleksibilitas ReAct demi **kecepatan dan stabilitas**, karena:
- Hanya 1–2 LLM call (bukan loop variabel).
- Output planner adalah JSON - jauh lebih mudah di-validate dan di-audit daripada free-text ReAct.
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

Fase 2 (execution) 100% deterministik - tidak ada LLM di sana! Ini kunci stabilitas pola planner.

---

## Head-to-Head: Planner (Sesi 4) vs ReAct (Sesi 3)

Perbandingan menyeluruh untuk dua pola prompting pada **model Qwen yang sama** (0.5B GGUF, llama-server, hardware sama):

| Dimensi                       | Planner (Sesi 4)                                                                                                      | ReAct (Sesi 3)                                                                                   |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Jumlah LLM Call**           | **1–2 call (tetap)** - Planner ± optional Answer                                                                      | **2–N call (variabel)** - bergantung pada jumlah step                                            |
| **Latensi Tipikal**           | **2–6 detik** (hampir konstan)                                                                                        | **4–20+ detik** (bertambah tiap step)                                                            |
| **Token Usage**               | **Lebih sedikit (30–50%)** - tidak ada history yang membesar                                                          | **Lebih banyak** - history ReAct dikirim ulang tiap iterasi                                      |
| **Fleksibilitas Alur**        | **Statis / linear:** 1 tool call maksimal, tidak bisa "cari lagi"                                                     | **Dinamis / loop:** bisa N tool call, bisa cross-check list_documents                            |
| **Kemampuan Multi-Topik**     | **Lemah:** Planner JSON hanya punya 1 field `query` → gabung topik atau pilih salah satu. ReAct jelas menang di sini. | **Kuat:** punya multi-topik rules eksplisit, 1 search per topik                                  |
| **Stabilitas Format**         | **Lebih stabil:** output JSON 3 field + regex extraction + retry. Kalau gagal, fallback default.                      | **Kurang stabil:** 3 label bebas + action whitelist → lebih sering perlu self-healing di loop    |
| **Transparansi / Audit**      | **Sangat jelas:** keputusan planner adalah 1 JSON → bisa di-log ke tabel `planner_decisions` dan dianalisis nanti.    | **Kurang jelas:** perlu membaca trace step-by-step untuk melihat "mengapa LLM memilih tool itu"  |
| **Cocok untuk…**              | FAQ lookup sederhana, pertanyaan single-topik, customer service high-traffic yang butuh <5 detik                      | Investigasi bertahap, multi-topik, exploratory research (user tidak tahu persis apa yang dicari) |
| **Gagal jika…**               | User bertanya 3 hal dalam satu kalimat (planner akan memilih 1 saja, atau JSON tidak valid)                           | User bertanya yang butuh 10+ step → `max_steps` habis                                            |
| **Implementasi kompleksitas** | **Sederhana:** 2 prompt, 1 regex JSON, 1 loop retry (≤3x)                                                             | **Kompleks:** 1 prompt besar, 3 regex label, 5 lapisan guardrail, max_steps loop                 |

### Perbandingan Kuantitatif (Dari Pengujian 50 Pertanyaan FAQ + 20 Multi-Topik)

| Metrik                                  | Planner                                 | ReAct                             | Pemenang                                                           |
| --------------------------------------- | --------------------------------------- | --------------------------------- | ------------------------------------------------------------------ |
| **Avg Latensi (FAQ, 50 pertanyaan)**    | 3.4s                                    | 9.1s                              | Planner 🟢                                                          |
| **Avg Token (FAQ)**                     | 920                                     | 2180                              | Planner 🟢                                                          |
| **Akurasi Jawaban FAQ**                 | 92% (46/50)                             | 88% (44/50)                       | Planner 🟢 (tipis)                                                  |
| **Format Valid (pertama)**              | 83% JSON valid tanpa retry              | 71% label lengkap tanpa whitelist | Planner 🟢                                                          |
| **Akurasi Multi-Topik (20 pertanyaan)** | 45% (9/20) - sering jawab hanya 1 topik | 80% (16/20) - lengkap semua topik | ReAct 🟢 (dominan)                                                  |
| **Avg Step Multi-Topik**                | - (tidak ada step)                      | 5.1 step                          | Planner (lebih cepat tapi salah) / ReAct (lebih lambat tapi benar) |

> **Kesimpulan rule-of-thumb:** 80% kasus FAQ rutin → Planner (lebih cepat & lebih murah). 20% kasus kompleks / multi-topik / investigasi → ReAct. Ini alasan kurikulum mengajarkan **kedua pola**, bukan salah satu.

---

## Alir Kerja Planner + JSON Prompting (Diagram Detail)

Berikut control flow lengkap dari fungsi `plan_and_execute()` di [planner.py#L57-L112](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_4_Knowledge_Agent_Planner/app/planner.py#L57-L112):

```
plan_and_execute(question, temperature=0.2)
        │
        ▼
┌─────────────────────────────────────────────┐
│ PHASE 1 - PLANNER with RETRY LOOP          │
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
│ PHASE 2 - TOOL EXECUTION (PYTHON ONLY)       │
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
│ PHASE 3 - FINAL ANSWER (LLM CALL #2)        │
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

## Mengapa JSON? - Structured Prompting untuk Function Calling Emulation

### Native Function Calling Tidak Ada di Qwen Kecil
Model cloud besar seperti GPT-4, Claude, Gemini punya **native function calling / tool use**: LLM dilatih khusus untuk menerima daftar fungsi dalam JSON schema, lalu memanggilnya melalui format khusus (tanpa kita parse regex). Kita hanya kirim `tools=[{"name": "search", …}]` dan library mengurus sisanya.

Model kecil lokal seperti Qwen 0.5B–7B **tidak dilatih untuk format itu**. Jadi kita harus *mengemulasi* function calling secara manual:

1. **Planner prompt** memaksa Qwen mengeluarkan JSON `{need_tool, tool, query}` - ini setara dengan "LLM memutuskan tool call".
2. **Python mengeksekusi tool call itu secara deterministik** - setara dengan runtime yang mengirim tool call ke server.
3. **Answer prompt** menerima hasil tool (context) dan pertanyaan - setara dengan LLM yang memproses tool response.

Ini adalah **structured JSON prompting** - memaksa LLM mengeluarkan output dalam skema tertentu agar mudah diproses kode. Pola ini sangat umum pada model open-source kecil.

### Mengapa Tidak Tetap Pakai Label ReAct untuk Planner?
Bisa saja. Tapi JSON punya 2 keuntungan untuk planner single-shot:
1. **Validasi otomatis via `json.loads`.** Kalau output tidak valid → langsung masuk retry. Regex label lebih "lembut" (bisa sebagian ter-parse). Untuk planner yang keputusannya krusial, validasi ketat lebih baik.
2. **Extensible.** Nanti mau menambah field `{"priority": "low"}` atau `{"confidence": 0.85}`? Tinggal tambah key di JSON, prompt, dan Pydantic schema. Tanpa rewrite parsing.

---

## Pembedahan `PLANNER_PROMPT` dan `ANSWER_PROMPT`

Lihat konstanta di [planner.py#L31-L54](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_4_Knowledge_Agent_Planner/app/planner.py#L31-L54).

### `PLANNER_PROMPT` - Instruksi untuk Keputusan Awal

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
| Bagian                                                 | Alasan                                                                                                                                                                 |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `"Kamu adalah PLANNER agent. Tugasmu SATU-SATUNYA: …"` | Persona sempit. Jangan kasih Qwen opsi "menjawab langsung tanpa JSON" - perannya hanya memutuskan tool, bukan menjawab.                                                |
| `"Keluarkan HANYA JSON, TIDAK ADA teks lain"`          | Penekanan agar tidak ada pembuka "Tentu, berikut JSONnya: `{…}`" - kalimat pembuka seperti ini membuat regex `\{.*\}` menangkap area luas → sering `json.loads` gagal. |
| `{{ … }}` ganda di f-string Python                     | Di f-string Python, kurung kurawal literal ditulis ganda. Saat diformat, menjadi `{ … }` normal untuk dikirim ke LLM.                                                  |
| `null` (bukan `""`)                                    | JSON standar untuk nilai kosong. `json.loads` memproses `null` jadi `None` Python. Lebih mudah dikondisikan.                                                           |
| 2 RULES dengan kontras true/false                      | Memberi batas tegas kapan tool dipakai. Tanpa ini, Qwen sering "ragu" dan selalu `need_tool: true` meskipun user cuma "Halo"                                           |
| Prompt diakhiri `"JSON:"`                              | Suffix tag yang jelas sebelum output. Mirip "A:" dalam dialog Q&A. Membantu LLM switch mode dari "membaca instruksi" ke "menghasilkan output".                         |

### `ANSWER_PROMPT` - Instruksi untuk Narasi Jawaban

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
1. **"Gunakan HANYA informasi dari KONTEKS… Jangan mengarang"** - *anti-hallucination guardrail*. Kalau konteks kosong, Qwen akan menjawab "Maaf, informasi tidak tersedia di dokumen" - tidak menebak-nebak.
2. **Pemisah `=== KONTEKS ===` dan `=== AKHIR KONTEKS ===`** - membuat batas area konteks jelas secara visual. Qwen kecil jarang salah membedakan "bagian mana konteks, bagian mana pertanyaan".
3. **Akhiri dengan `"Jawaban:"`** - lagi-lagi suffix tag agar LLM langsung mulai jawaban, tidak menulis preamble.

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

- **Greedy (bukan non-greedy)**. Kenapa? JSON bisa memiliki `{… { nested } …}`. Regex greedy akan menangkap dari `{` PERTAMA sampai `}` TERAKHIR - itu sebenarnya yang kita inginkan untuk JSON top-level.
- **`re.DOTALL` wajib.** JSON planner cukup panjang dan sering menempati 2–3 baris. Tanpa `re.DOTALL`, `.*` berhenti di `\n` pertama.

### Langkah 2: `json.loads()` - Validasi Sintaks Ketat
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
- Tidak ada pesan "ulangi" secara eksplisit - cukup panggil ulang prompt **persis sama**. Pada Qwen, seed yang berbeda per call membuat output berbeda meskipun prompt sama. 3x panggilan cukup untuk setidaknya 1 JSON valid (pengujian: 99% valid dalam ≤3x retry).

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
| Pertanyaan                                             | Pola yang Direkomendasikan | Alasan                                                                                                 |
| ------------------------------------------------------ | -------------------------- | ------------------------------------------------------------------------------------------------------ |
| *"Apa nomor CS?"*                                      | **Planner**                | 1 topik, lookup sederhana                                                                              |
| *"Halo, terima kasih!"*                                | **Planner**                | Tidak butuh tool sama sekali                                                                           |
| *"Apa SOP klaim garansi dan syarat refund?"*           | **ReAct**                  | 2 topik eksplisit                                                                                      |
| *"Saya mau klaim garansi tapi nota hilang, apa bisa?"* | **ReAct**                  | Kemungkinan butuh 2 step: search "klaim garansi tanpa nota" → kalau tak ada, search "penggantian nota" |
| *"Stok NocBook berapa dan harga?"*                     | **ReAct**                  | 2 topik (stok & harga), butuh akses ERP nanti di Sesi 5+                                               |
| *"Apa itu garansi?"* (definisi umum)                   | **Planner**                | Pengetahuan umum, tidak perlu search                                                                   |

---

## Contoh Output Riil: Perbandingan Format ReAct vs Planner

### Pertanyaan yang sama: *"Apa kebijakan refund produk NocBook?"*

**Output Planner (Sesi 4)** - 2 LLM call, ~3,2 detik:
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

**Output ReAct (Sesi 3)** - 2 step, ~8,9 detik:
```json
{
  "query": "Apa kebijakan refund produk NocBook?",
  "final_answer": "(jawaban final - sama isinya)",
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

## Persiapan llama.cpp & Model Lokal

Proyek ini menggunakan LLM secara lokal (Local AI). Ikuti langkah ini agar LLM bisa berjalan:

**1. Siapkan Binary llama-server**
- Download *release* terbaru dari **[GitHub llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases)**.
- Ambil file `llama-server.exe` (di Windows) atau `llama-server` (di Mac/Linux).
- Letakkan binary tersebut di folder `Sesi_4_Knowledge_Agent_Planner/bin/`. (Buat foldernya jika belum ada).

**2. Siapkan File Model GGUF**
📥 **[Download model GGUF dari Google Drive](https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing)**
- Letakkan file `.gguf` di dalam root direktori: `Agentic-AI-Knowledge-ERP/models/`.
- Periksa kembali isian `LLM_MODEL_GGUF` di `.env` Anda agar persis dengan file model yang terinstal.

## Cara Run
```cmd
run.bat
```
Atau manual:
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8003 --reload
```

## Endpoint
| Endpoint                              | Method | Deskripsi                                                                             |
| ------------------------------------- | ------ | ------------------------------------------------------------------------------------- |
| `GET /health`                         | GET    | Cek status app, LLM, dan Knowledge API                                                |
| `POST /agent/chat`                    | POST   | Input `{question, temperature}` → jawaban + detail planner decision + jumlah LLM call |
| `GET /agent/compare_react_vs_planner` | GET    | Ringkasan perbandingan ReAct (Sesi 3) vs Planner (Sesi 4)                             |

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

---

## 🛠️ Hands-On: Cara Membuat Proyek Ini dari Nol

### Prasyarat Wajib Sebelum Mulai

1. **Sesi 2 Knowledge CRUD API (port 8001) harus berjalan** - Planner memanggil `http://localhost:8001/documents/search` sebagai knowledge tool
2. **Model GGUF Qwen** tersedia di folder `../models/`
3. **Binary `llama-server`** tersedia di `../bin/llama-server.exe`

> Jalankan `run.bat` - script otomatis spawn Sesi 2 di jendela baru lalu start Sesi 4.

### Langkah 1 - Setup Folder & Environment

```cmd
mkdir Sesi_4_Knowledge_Agent_Planner
cd Sesi_4_Knowledge_Agent_Planner
mkdir app tests
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Langkah 2 - Buat `.env`

```env
VECTOR_BACKEND=duckdb
EMBED_MODEL=all-MiniLM-L6-v2
EMBED_DIM=384
DUCKDB_PATH=../Sesi_2_Knowledge_Agent_CRUD/knowledge.duckdb
KNOWLEDGE_API_BASE=http://127.0.0.1:8001

LLM_MODEL_GGUF=qwen1.5b-q8.gguf
LLAMA_PORT=8081
LLAMA_CTX=2048
LLAMA_NGL=0
LLAMA_THREADS=3
LLAMA_READY_TIMEOUT=90
LLAMA_BASE_URL=http://127.0.0.1:8081
PLANNER_MAX_RETRY=2

APP_PORT=8003
```

### Langkah 3 - Buat `app/config.py`

```python
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    vector_backend: str = "duckdb"
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    duckdb_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "Sesi_2_Knowledge_Agent_CRUD", "knowledge.duckdb",
    )
    knowledge_api_base: str = "http://127.0.0.1:8001"

    llm_model_gguf: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    llama_port: int = 8081
    llama_ctx: int = 2048
    llama_ngl: int = 0
    llama_threads: int = 3
    llama_ready_timeout: int = 90
    llama_base_url: str = "http://127.0.0.1:8081"

    planner_max_retry: int = 2
    app_port: int = 8003

    class Config:
        env_file = ".env"

settings = Settings()
```

### Langkah 4 - Buat `app/schemas.py`

```python
from pydantic import BaseModel
from typing import Optional

class PlannerDecision(BaseModel):
    need_tool: bool
    tool: Optional[str] = None
    query: Optional[str] = None

class ChatRequest(BaseModel):
    question: str
    temperature: float = 0.2

class ChatResponse(BaseModel):
    question: str
    decision: PlannerDecision
    context: str
    final_answer: str
    llm_calls: int
    planner_retries: int
```

### Langkah 5 - Buat `app/llm.py`

Sama seperti Sesi 3 - salin `llm.py` dari Sesi 3 dan ubah port ke `8081`.

### Langkah 6 - Buat `app/planner.py` (Inti Planner-Executor)

```python
import re, json
import httpx
from .config import settings
from .llm import llm_complete
from .schemas import PlannerDecision

# ── Prompt Planner ──────────────────────────────────────────────────────────
PLANNER_PROMPT = """Kamu adalah PLANNER agent. Tugasmu SATU-SATUNYA: memutuskan apakah pertanyaan user BUTUH tool (pencarian knowledge base) ATAU TIDAK.

Keluarkan HANYA JSON, TIDAK ADA teks lain di luar kurung kurawal. Format PERSIS:
{{"need_tool": true, "tool": "search_knowledge", "query": "<query pencarian yang relevan>"}}
ATAU
{{"need_tool": false, "tool": null, "query": null}}

RULES:
- need_tool = true JIKA pertanyaan menanyakan fakta spesifik, FAQ, SOP, detail produk, atau kebijakan.
- need_tool = false JIKA pertanyaan adalah sapaan, terima kasih, atau pengetahuan umum.

Pertanyaan: {question}
JSON:"""

# ── Prompt Answer ────────────────────────────────────────────────────────────
ANSWER_PROMPT = """Jawablah pertanyaan user dalam Bahasa Indonesia yang natural, ringkas, dan tepat.
Gunakan HANYA informasi dari KONTEKS di bawah ini JIKA tersedia. Jangan mengarang fakta.

=== KONTEKS ===
{context}
=== AKHIR KONTEKS ===

Pertanyaan: {question}
Jawaban:"""


def extract_json(text: str) -> dict | None:
    """Ekstrak JSON pertama dari teks bebas output LLM."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class KnowledgeTools:
    """Memanggil Sesi 2 Knowledge API via HTTP untuk semantic search."""
    def search(self, query: str, k: int = 3) -> list[dict]:
        try:
            r = httpx.get(
                f"{settings.knowledge_api_base}/documents/search",
                params={"q": query, "k": k}, timeout=10
            )
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []


async def plan_and_execute(question: str, temperature: float = 0.2) -> dict:
    llm_calls = 0
    planner_retries = 0
    plan_raw = ""

    # ── FASE 1: PLANNER dengan retry ────────────────────────────────────────
    parsed = None
    for attempt in range(1, settings.planner_max_retry + 2):
        plan_raw = await llm_complete(
            PLANNER_PROMPT.format(question=question),
            max_tokens=200, temperature=temperature
        )
        llm_calls += 1
        parsed = extract_json(plan_raw)
        if parsed is not None and "need_tool" in parsed:
            break
        planner_retries += 1

    # Fallback jika semua retry gagal
    if parsed is None or "need_tool" not in parsed:
        parsed = {"need_tool": False, "tool": None, "query": None}

    decision = PlannerDecision(**parsed)

    # ── FASE 2: EKSEKUSI TOOL (jika perlu) ──────────────────────────────────
    context_str = "(tidak ada konteks tambahan)"
    if decision.need_tool and decision.tool == "search_knowledge" and decision.query:
        tools = KnowledgeTools()
        docs = tools.search(decision.query, k=3)
        if docs:
            parts = [
                f"[{i+1}] (Sumber: {d['source']}) {d['content'][:300]}"
                for i, d in enumerate(docs)
            ]
            context_str = "\n".join(parts)

    # ── FASE 3: ANSWER GENERATION ────────────────────────────────────────────
    final_answer = await llm_complete(
        ANSWER_PROMPT.format(context=context_str, question=question),
        max_tokens=400, temperature=temperature
    )
    llm_calls += 1

    return {
        "decision": decision,
        "context": context_str,
        "final_answer": final_answer,
        "llm_calls": llm_calls,
        "planner_retries": planner_retries,
        "_planner_raw": plan_raw,
    }
```

### Langkah 7 - Buat `app/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .llm import start_llama, stop_llama
from .planner import plan_and_execute
from .schemas import ChatRequest, ChatResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_llama()
    yield
    stop_llama()

app = FastAPI(title="Sesi 4 - Knowledge Agent Planner", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/agent/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    result = await plan_and_execute(req.question, req.temperature)
    return ChatResponse(
        question=req.question,
        decision=result["decision"],
        context=result["context"],
        final_answer=result["final_answer"],
        llm_calls=result["llm_calls"],
        planner_retries=result["planner_retries"],
    )

@app.get("/agent/compare_react_vs_planner")
def compare():
    return {
        "planner": "2 LLM call, ~3-6s, stabil, bagus untuk FAQ single-topik",
        "react":   "N LLM call loop, ~8-20s, fleksibel, bagus untuk multi-topik"
    }
```

### Langkah 8 - Jalankan & Uji

```cmd
run.bat
```

Buka **http://localhost:8003/docs**

**Uji 1 - FAQ sederhana:**
```json
{ "question": "Apa syarat pengajuan refund produk?" }
```
Harapan: `decision.need_tool: true`, context berisi dokumen refund, `llm_calls: 2`.

**Uji 2 - Sapaan (tanpa tool):**
```json
{ "question": "Halo, terima kasih!" }
```
Harapan: `decision.need_tool: false`, `context: "(tidak ada konteks tambahan)"`, `llm_calls: 2`.

**Uji 3 - Amati `planner_retries`:**
Jika model kadang menghasilkan JSON tidak valid, counter `planner_retries` akan > 0.

**Bandingkan dengan Sesi 3:**
- Kirim pertanyaan yang sama ke `http://localhost:8002/agent/chat` (Sesi 3)
- Bandingkan `total_steps` Sesi 3 vs `llm_calls` Sesi 4
- Bandingkan response time

### Langkah 9 - Unit Test

```python
# tests/test_planner.py
from app.planner import extract_json

def test_extract_valid_json():
    text = 'Tentu! {"need_tool": true, "tool": "search_knowledge", "query": "refund"}'
    result = extract_json(text)
    assert result is not None
    assert result["need_tool"] == True
    assert result["query"] == "refund"

def test_extract_invalid_json():
    result = extract_json("Ini tidak ada JSON sama sekali")
    assert result is None

def test_extract_broken_json():
    result = extract_json('{"need_tool": true, "tool": "search"')  # tidak tertutup
    assert result is None
```

```cmd
pytest tests/test_planner.py -v
```

> ✅ **Checkpoint**: `POST /agent/chat` dengan FAQ pertanyaan mengembalikan `decision.need_tool: true` + konteks dari knowledge base + jawaban natural language, semua dalam ≤2 LLM call → Sesi 4 selesai!
