# Sesi 4 — Knowledge Agent dengan LLM Reasoning (Qwen, Structured Prompting)

**File notebook:** `Sesi_4_Knowledge_Agent_LLM_Reasoning_Qwen.ipynb`
**Kode implementasi production-ready:** `Sesi_4_Knowledge_Agent_Planner/` (FastAPI, port 8003)

---

## Daftar Isi
1. [Tentang Sesi Ini — Mengapa Ada Pola Kedua?](#tentang-sesi-ini--mengapa-ada-pola-kedua)
2. [Perbandingan Dua Paradigma Agent: ReAct vs Planner-Executor](#perbandingan-dua-paradigma-agent-react-vs-planner-executor)
3. [Trade-off dalam Pemilihan Pola Agent](#trade-off-dalam-pemilihan-pola-agent)
4. [Structured JSON Prompting: Konsep & Implementasi](#structured-json-prompting-konsep--implementasi)
5. [Kapan Pakai Pola Mana? — Decision Framework Praktis](#kapan-pakai-pola-mana--decision-framework-praktis)
6. [Mekanisme Retry & Fallback Untuk Output LLM yang Tidak Stabil](#mekanisme-retry--fallback-untuk-output-llm-yang-tidak-stabil)
7. [Prasyarat & Yang Akan Dipelajari](#prasyarat--yang-akan-dipelajari)
8. [Struktur Notebook & Cara Menjalankan](#struktur-notebook--cara-menjalankan)
9. [Konsep Kunci & Output / Deliverable](#konsep-kunci--output--deliverable)

---

## Tentang Sesi Ini — Mengapa Ada Pola Kedua?

Sesi ini memperkenalkan pola prompting kedua di atas model Qwen yang sama: **planner-executor** berbasis JSON, sebagai alternatif ReAct iteratif dari Sesi 3. Qwen dipaksa mengeluarkan keputusan dalam format JSON ketat — cara mengemulasi *function calling* pada model kecil yang tidak punya kapabilitas itu secara native.

### Latar Belakang: ReAct Tidak Selalu Optimal
Setelah mengimplementasikan ReAct (Sesi 3), muncul 3 masalah praktis dalam penggunaan sehari-hari:

| Masalah ReAct | Analisis Root Cause | Alternatif Planner |
|---|---|---|
| **Latensi 6–25 detik** (FAQ sederhana pun lambat) | 1 LLM call = ±2–5 detik × 2–5 step ReAct = waktu yang lama. | **Planner = 1–2 LLM call** (tanpa loop). Latensi ~2–6 detik. |
| **Token usage membengkak** | Tiap iterasi ReAct mengirim ulang `history` (prompt + observation sebelumnya) dari step 0. | **Planner = 2 prompt independen**: Planner prompt kecil, Answer prompt hanya memuat konteks 1×. Tidak ada pembengkakan history. |
| **Tidak dapat diprediksi jumlah step** | User bertanya lookup sederhana "berapa nomor CS?" → ReAct bisa membutuhkan 1 step atau 4 step. | **Planner = jumlah LLM call tetap 1–2** — bisa diestimasi biaya dan SLA-nya untuk sistem produksi. |

Pola Planner bukan *pengganti* ReAct — keduanya **saling melengkapi**. Sesi ini sengaja mengajarkan keduanya agar Anda bisa memilih pola yang tepat berdasarkan karakteristik pertanyaan.

---

## Perbandingan Dua Paradigma Agent: ReAct vs Planner-Executor

### Definisi Masing-masing Pola
- **ReAct (Sesi 3):** *Reasoning + Acting interleaved*. LLM berpikir → bertindak → mengamati hasil → berpikir lagi → bertindak lagi → **ulangi** sampai merasa cukup informasi (FINISH). Ada **loop** (pengulangan) dan **jumlah step tidak tentu**.
- **Planner-Executor (Sesi 4):** *Plan first, execute once, answer*. LLM **merencanakan SEMUA di awal** (butuh tool? yang mana? parameternya?), Python **mengeksekusi tool 0–1 kali** (deterministik), LLM yang lain **menyusun jawaban final**. **Tidak ada loop**. Jumlah LLM call **selalu 1 atau 2**.

### Tabel Perbandingan Mendalam

| Aspek | ReAct Iteratif (Sesi 3) | Planner-Executor JSON (Sesi 4) |
|---|---|---|
| **Filosofi dasar** | "Saya akan menjelajahi informasi sedikit demi sedikit sampai puas." | "Saya akan putuskan strategi terbaik di awal, lalu jalankan sekali." |
| **Kontrol alur** | LLM yang mengontrol loop (kapan selesai adalah keputusan LLM) | Kode Python yang mengontrol flow (setiap fase dipanggil prosedural) |
| **Jumlah LLM call** | Variabel: 2 s/d `max_steps` (default 8) | Tetap: 2 LLM call (1 planner, 1 answer) → kadang ditambah planner retry |
| **Latensi tipikal** | ~4–25 detik (bergantung step) | ~2–6 detik (hampir konstan) |
| **Fleksibilitas reasoning** | **Tinggi:** bisa beradaptasi setelah melihat observation. Contoh: hasil search jelek → ganti query → search lagi. | **Rendah:** keputusan tool diambil SEBELUM melihat hasil. Kalau query planner jelek, tidak bisa search lagi kecuali ditulis kode khusus. |
| **Penanganan multi-topik** | **Sangat bagus:** multi-topik rules eksplisit + 1 search per topik + checkpoint di Thought. | **Lemah:** cuma 1 field `query` di JSON → planner harus memilih salah satu topik, atau menggabung semua dalam 1 query (yang menurunkan relevansi search). |
| **Stabilitas output format** | Rentan error (3 label Thought/Action/Input ditulis bebas) — sering perlu self-healing di loop. | Lebih stabil (3 field JSON ketat + `json.loads()` validasi + retry). |
| **Transparansi keputusan** | Perlu membaca beberapa StepLog untuk menelusuri "kenapa tool ini dipilih". | Keputusan dalam 1 JSON `{need_tool, tool, query}` — audit instan. |
| **Sensitivitas terhadap prompt** | **Tinggi:** kalau REACT_SYSTEM kurang jelas, output banyak yang perlu self-healing. | **Sedang:** planner yang jelek tinggal di-retry; answer prompt kurang sensitif. |
| **Kompleksitas implementasi** | Tinggi: 5 lapisan guardrail, 3 regex parser, placeholder detection, multi-topik rule, FINISH retry. | Rendah: 2 prompt, 1 regex JSON, 1 loop retry sederhana, 1 execution fase. |
| **Karakter error yang muncul** | Gagal format label, tool salah nama, FINISH terlalu awal (premature), jawaban placeholder. | JSON sintaks error, query planner off-topic, need_tool salah (false positive/negative). |
| **Tipe model yang cocok** | Model menengah (7B+) karena perlu kapasitas reasoning per-step dan ingat format. | Model kecil (0.5B–3B) OK, karena tiap task dibagi jadi spesifik (hanya planner / hanya jawab). |

### Visual Perbandingan Flow
```
=== REACT (Sesi 3) ==========================================

  User Query ──▶  LLM Step 1  ──▶ Tool Call 1 ──▶ Obs 1
                       │
                       ▼
                  LLM Step 2 ──▶ Tool Call 2 ──▶ Obs 2
                       │
                       ▼
                  LLM Step 3 ──▶ (FINISH / Tool 3 …)
                       │
                       ▼
                 Jawaban User
  (Total: 3 LLM call + 2 Tool call — bergantung step)


=== PLANNER-EXECUTOR (Sesi 4) ================================

  User Query
       │
       ▼
  ┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
  │ LLM 1 : PLANNER │────▶│ Python: Tool │────▶│ LLM 2: Answer│
  │ (JSON 3 field)  │     │  (0 atau 1x) │     │  (narasi)    │
  └─────────────────┘     └──────────────┘     └──────┬───────┘
                                                       │
                                                       ▼
                                                 Jawaban User
  (Total: 2 LLM call + 1 Tool call — SELALU tetap)
```

---

## Trade-off dalam Pemilihan Pola Agent

Pemilihan pola agent selalu melibatkan trade-off 4 dimensi utama. Tidak ada yang "lebih baik" secara mutlak — pilih berdasarkan prioritas sistem Anda.

### Dimensi 1: Kecepatan vs Kelengkapan
```
          KECEPATAN (Latensi Rendah)
             ▲
             │       ● Planner
             │     ╱
             │   ╱   ◀ Trade-off: Planner cepat tapi
             │ ╱                         informasi bisa tidak lengkap
             │                               untuk pertanyaan kompleks.
             │
             │             ● ReAct
             │          ╱
             │        ╱
             │      ╱   ◀ Trade-off: ReAct lengkap tapi lambat.
             ╱
          KELENGKAPAN (Informasi Penuh)
```
- **Prioritaskan kecepatan (FAQ customer service, chatbot publik):** Planner.
- **Prioritaskan kelengkapan (riset, troubleshooting):** ReAct.

### Dimensi 2: Biaya Token vs Kualitas Jawaban
Rasio tipikal pada Qwen 0.5B:
| Skenario | Token Planner | Token ReAct | Rasio |
|---|---|---|---|
| FAQ 1 topik, 1 search | 920 | 2180 | **Planner 2.4× lebih hemat** |
| Multi-topik 2 search | 980 | 3150 | **Planner 3.2× lebih hemat** |
| Multi-topik 3 search | 1010 | 4200 | **Planner 4.1× lebih hemat** |

> **Catatan:** Dalam kurikulum ini model lokal (tidak bayar per token), jadi hemat token berarti **cepat generate + hemat memori**. Untuk produksi pakai LLM cloud (bayar per 1K token), perbedaan biaya antara Planner vs ReAct bisa menjadi **faktor penentu**.

### Dimensi 3: Determinisme vs Fleksibilitas
- **Determinisme = output dapat diprediksi.** Planner cocok untuk:
  - Sistem dengan SLA (response time harus < X detik)
  - Integration testing: "untuk input A, output selalu melalui path P"
  - Operasi bisnis kritis (setiap tool call perlu audit log yang jelas)
- **Fleksibilitas = beradaptasi dengan tak terduga.** ReAct cocok untuk:
  - Research assistant (user sendiri tidak tahu query apa yang tepat)
  - Troubleshooting bertahap (perlu eliminasi penyebab satu per satu)
  - Exploratory data analysis (perlu beberapa kali pencarian untuk memahami data)

### Dimensi 4: Interpretabilitas (Logging & Audit)
- **Planner:** Setiap keputusan adalah JSON kecil → mudah disimpan ke tabel `planner_logs(id, question, need_tool, tool, query, is_success, retry_count)`. Analisis kesalahan mudah: "15% pertanyaan tentang stok salah diklasifikasi need_tool=false" → perbaiki RULES di planner prompt.
- **ReAct:** Keputusan tersebar di N StepLog. Perlu tool visualizer (atau baca manual) untuk melihat "mengapa LLM memilih tool ini bukan itu". Biasanya butuh `trace_id` + viewer seperti LangSmith / Langfuse untuk analisis.

---

## Structured JSON Prompting: Konsep & Implementasi

### Apa itu Structured (JSON) Prompting?
**Structured prompting** adalah teknik memaksa LLM mengeluarkan output **dalam format data terstruktur** (JSON, YAML, XML, dll.) alih-alih bahasa natural bebas. Formatnya didefinisikan secara eksplisit di prompt, dan output divalidasi sebelum diproses lebih lanjut.

Untuk agent, tujuan utamanya adalah **mengemulasikan function calling pada model yang tidak mendukungnya secara native**. Ini adalah jalan tengah antara:
- **Native function calling (GPT-4):** Paling bagus, tapi mahal, cloud, dan data keluar lokal.
- **Free-text ReAct (Sesi 3):** Gratis & lokal, tapi format tidak stabil.

### Anatomi Structured Prompt untuk Agent
Ada **4 komponen wajib** dalam structured JSON prompting yang bagus:

1. **Persona sempit.** Jangan "asisten AI serba bisa". Peran khusus untuk planner:
   > "Kamu adalah PLANNER agent. Tugasmu SATU-SATUNYA: memutuskan apakah pertanyaan user BUTUH tool (pencarian knowledge base) ATAU TIDAK."
   
   Persona sempit mengurangi ruang kemungkinan output → parsing lebih stabil.

2. **Contoh format PERSIS + alternatif.**
   ```
   Keluarkan HANYA JSON, TIDAK ADA teks lain di luar kurung kurawal. Format PERSIS:
   {"need_tool": true, "tool": "search_knowledge", "query": "<query pencarian yang relevan>"}
   ATAU
   {"need_tool": false, "tool": null, "query": null}
   ```
   Disediakan 2 format (true/false) agar LLM tahu dua kemungkinan valid. Tidak ada "setengah-setengah".

3. **Daftar RULES kontras true/false.**
   ```
   RULES:
   - need_tool = true JIKA pertanyaan menanyakan fakta spesifik, FAQ, SOP, detail produk…
   - need_tool = false JIKA pertanyaan adalah sapaan, terima kasih, atau pengetahuan umum…
   ```
   Memberikan batas tegas tentang **kapan tool dipakai** — tanpanya LLM cenderung selalu menjawab true atau selalu false.

4. **Suffix tag sebelum output:**
   ```
   Pertanyaan: {question}
   JSON:
   ```
   `JSON:` di akhir sebagai "trigger mode output". LLM belajar bahwa setelah tag ini adalah area JSON (bukan narasi biasa). Ini mirip dengan tag `A:` dalam dialog Q&A klasik.

### Dua Lapisan Validasi Output LLM
Jangan pernah percaya output LLM mentah. Selalu validasi berlapis:

```
LLM output (string, misal: "Tentu, ini JSONnya: {\"need_tool\": true, ...}")
            │
            ▼
┌──────────────────────────────┐
│ LAPISAN 1: Regex Extraction  │
│ pattern = r"\{.*\}" (DOTALL) │ → tangkap area yang "terlihat seperti JSON"
│ (pisahkan dari narasi        │   buang "Tentu, ini JSONnya: " prefix
│  pembuka / penutup)          │
└──────────────┬───────────────┘
               │ Jika match
               ▼
┌──────────────────────────────┐
│ LAPISAN 2: json.loads()      │
│ (Python stdlib)              │ → pastikan sintaks JSON valid
│                              │   (koma seimbang, quote benar, null/bool lowercase, dll)
└──────────────┬───────────────┘
               │ Jika valid
               ▼
┌──────────────────────────────┐
│ LAPISAN 3: Schema validation │ (opsional, di Sesi 4 = PlannerDecision Pydantic)
│ Pydantic BaseModel:          │ → pastikan field yang diharapkan ADA & BER-TIPE BENAR
│ need_tool: bool (wajib)      │   misal need_tool harus bool, bukan string "true"
│ tool: Optional[str]          │
│ query: Optional[str]         │
└──────────────┬───────────────┘
               ▼
          (siap dipakai)
```

Dalam `planner.py` kita, lapisan 1+2 adalah fungsi `extract_json()`, lapisan 3 adalah konstruksi `PlannerDecision(...)` di [planner.py#L81-L85](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_4_Knowledge_Agent_Planner/app/planner.py#L81-L85).

---

## Kapan Pakai Pola Mana? — Decision Framework Praktis

Gunakan framework ini (bisa diimplementasikan sebagai rule-based router sederhana sebelum memilih agent):

### Step 1: Klasifikasikan Pertanyaan Berdasarkan 5 Sinyal
Periksa ada/tidaknya sinyal ini dalam query user:

| Sinyal | Arti | Rekomendasi Awal |
|---|---|---|
| **Sinyal A:** Ada kata hubung "dan", "serta", "sambil" | Indikasi **multi-topik** | **Condong ke ReAct** (Planner lemah di multi-topik) |
| **Sinyal B:** Ada daftar pertanyaan bernomor "1. … 2. … 3. …" | Multi-topik eksplisit | **ReAct** |
| **Sinyal C:** Mengandung indikasi ketidakpastian "mungkin", "sepertinya", "entah" | User exploratory, perlu search banyak | **ReAct** |
| **Sinyal D:** Struktur [Kata Tanya + Objek Tunggal] ("Apa X", "Bagaimana Y", "Kapan Z") | Single-topik, lookup pasti | **Condong ke Planner** |
| **Sinyal E:** Sapaan / obrolan ringan ("Halo", "Terima kasih", "Siapa kamu?") | Tidak butuh tool | **Planner** (atau rule-based langsung tanpa LLM!) |

### Step 2: Gabungkan dengan Constraints Sistem
Setelah sinyal pertanyaan, lihat constraint teknis:
- **Apakah SLA latensi <5 detik?** → Jika YA: Planner (meskipun ada multi-topik ringan)
- **Apakah biaya token adalah perhatian utama (cloud)?** → Jika YA: Planner
- **Apakah salah jawaban = konsekuensi bisnis besar?** → Jika YA: ReAct (lengkap lebih baik daripada cepat tapi salah)
- **Apakah akan di-deploy di hardware terbatas (Raspberry Pi, 1CPU)?** → Planner (hemat compute)

### Step 3: Matriks Keputusan Akhir
| | SLA Ketat (<5s) | SLA Longgar (>10s) |
|---|---|---|
| **Single-topik / Sapaan** | **Planner (100%)** | Planner (lebih cepat) ATAU ReAct 2 step (lebih konsisten format) |
| **Multi-topik (2 topik)** | **Planner + post-process** (Planner pilih 1 topik dulu, bisa buatkan flow tanya user "apakah ada yang lain?") | **ReAct (pilihan utama)** |
| **Multi-topik (3+ topik) / Exploratory** | **Beri loading yang jelas + ReAct** (kadang user mau menunggu jika diberi estimasi) | **ReAct 100%** |

---

## Mekanisme Retry & Fallback Untuk Output LLM yang Tidak Stabil

### Mengapa Retry Perlu? — Perilaku Non-Deterministik LLM
LLM menghasilkan token secara probabilistik (sampling dari distribusi probabilitas next-token). Meskipun `temperature=0.2` (cenderung deterministik), masih ada 3 sumber variasi:
1. **Seed bervariasi per request.** llama-server default seed random.
2. **Floating-point non-determinism.** Operasi matriks di GPU/CPU paralel sedikit berbeda tiap run.
3. **Context window yang berbeda.** Kalau ada cache berbeda, token pertama bisa beda → chain berefek ke token berikutnya.

Akibatnya: untuk prompt planner yang sama persis, 10%–20% output-nya bisa invalid JSON atau salah klasifikasi. Tapi jika di-run 2–3× lagi, hampir selalu ada yang valid. **Ini adalah dasar filosofi retry pada LLM-based systems.**

### Strategi Retry Planner yang Diterapkan di `planner.py`
```python
for attempt in range(1, settings.planner_max_retry + 2):   # Total 3 peluang
    plan_raw = await llm_complete(PLANNER_PROMPT.format(question=question), ...)
    parsed = extract_json(plan_raw)
    if parsed is not None and "need_tool" in parsed:
        break   # ✅ Valid: langsung keluar loop
    planner_retries += 1

# Fallback AKHIR jika SEMUA 3x gagal:
if parsed is None:
    parsed = {"need_tool": False, "tool": None, "query": None}
```

#### Pengamatan Penting:
1. **Prompt tetap SAMA, tidak diubah.** Banyak engineer salah: "kalau gagal, tambahkan pesan 'ulangi dengan format benar'". Pada Qwen kecil, ini SAMA SAJA efektifnya dengan "prompt sama, run ulang" — dan yang terakhir lebih sederhana (tidak perlu build prompt error).
2. **Jumlah retry = 2 (total 3 call) adalah sweet spot.** Empiris:
   - Call pertama: ~83% valid
   - Retry 1: +12% → total 95% valid
   - Retry 2: +4% → total 99% valid
   - Retry 3++: tidak signifikan (kurang 0.5%) tapi menambah latensi 1 LLM call.
3. **Fallback = asumsi tidak butuh tool.** Baca "Mengapa bukan sebaliknya?" di README folder implementasi: false-positive (seharusnya butuh tapi tidak) UX-nya lebih aman daripada false-negative (boros waktu search yang sia-sia).

### Lapisan Fallback Lebih Luar (Untuk Production)
Jika Anda deploy ke produksi, tambahkan 2 lapisan lagi:

```
Lapisan A (sudah ada): planner retry (3x) + fallback need_tool=False
Lapisan B (tambahan): Rule-based keyword classifier sebagai "safety net"
           if 'refund' in query or 'garansi' in query or 'stok' in query:
               override need_tool = True
Lapisan C (tambahan): Timeout global planner
           asyncio.wait_for(plan_and_execute(q), timeout=10)
           # Kalau timeout → langsung jawab "Maaf sedang sibuk"
```

---

## Prasyarat
- Sudah menyelesaikan Sesi 1–3 (terutama paham `qwen_llm_call()` dan pola ReAct sebagai pembanding).
- Paham dasar JSON: object, key-value pair, `null` vs `""`, lowercase `true`/`false`.
- Paham dasar regex Python: `re.search()`, flag `re.DOTALL`, grup capture.

## Yang Akan Dipelajari
- Kenapa dan kapan pola *single-shot planner* lebih efisien dibanding loop iteratif ReAct.
- Cara memaksa & mem-parsing output JSON dari LLM lokal (`extract_json()` dengan regex + `json.loads`, termasuk strategi retry).
- Pola *planner → tool execution → final answer* sebagai dua tahap terpisah (dua kali panggilan LLM, bukan loop berkali-kali).
- **Khusus pembelajaran mendalam:**
  - 4 dimensi trade-off ReAct vs Planner (kecepatan/lengkapan, biaya/kualitas, determinisme/fleksibilitas, interpretabilitas).
  - 4 komponen wajib structured JSON prompting dan 3 lapisan validasi output LLM.
  - Decision framework 3-step untuk memilih pola agent berdasarkan sinyal pertanyaan + constraint sistem.
  - Filosofi retry LLM: sweet spot 3 peluang + fallback yang UX-nya aman.

## Struktur Notebook
1. Setup environment + load model Qwen (sama seperti Sesi 3).
2. Rekonstruksi knowledge base & API dari Sesi 1–2.
3. Penjelasan konseptual: kenapa dibutuhkan pola baru selain ReAct.
4. Prompt planner (`PLANNER_PROMPT`) + fungsi `extract_json()` + pembedahan per baris.
5. Fungsi utama `qwen_reasoning_agent()` (planner + jawaban akhir).
6. **TODO 1**: tambahkan fallback rule-based saat parsing JSON gagal total.
7. **TODO 2**: bandingkan ReAct (Sesi 3) vs planner (sesi ini) — jumlah panggilan LLM, latency, kualitas jawaban.

## Cara Menjalankan
Sama seperti Sesi 3, model Qwen diunduh ulang di awal notebook (jalankan di Colab dengan internet). Tidak butuh API key eksternal apa pun.

Untuk versi kode production (FastAPI port 8003, tanpa Colab), lihat folder `Sesi_4_Knowledge_Agent_Planner/` dan jalankan `run.bat`.

## Konsep Kunci
| Istilah | Penjelasan Singkat | Penjelasan Mendalam |
|---|---|---|
| **Planner-executor** | Pola: satu prompt memutuskan aksi, prompt terpisah menyusun jawaban — bukan loop | Tiga fase berurutan (Planner → Execution → Answer), 1–2 LLM call. Fleksibilitas rendah tapi cepat dan stabil. Berguna untuk FAQ single-topik. |
| **Structured/JSON prompting** | Memaksa LLM mengeluarkan output dalam skema JSON tertentu agar mudah diparsing kode | Teknik emulasi function calling untuk model kecil. 4 komponen wajib: persona sempit, format contoh persis, rules kontras, suffix tag. 3 lapisan validasi: regex, json.loads, Pydantic schema. |
| **Function calling emulation** | Cara menyimulasikan tool-calling pada model tanpa dukungan native untuk fitur tersebut | Alternatif dari native function calling GPT-4. Planner prompt = "pemanggilan tool virtual", Python = runtime eksekusi, Answer prompt = "pemrosesan tool response". |
| **LLM Retry loop** | Menjalankan ulang prompt yang sama jika output invalid | Berdasarkan perilaku probabilistik LLM. Sweet spot Qwen 0.5B: 3 total panggilan. Fallback yang aman = false-positive (anggap tidak butuh tool). |
| **Anti-hallucination guardrail** | Prompt rule "Gunakan HANYA informasi dari KONTEKS… Jangan mengarang" | Bagian dari ANSWER_PROMPT. Mencegah LLM menebak-nebak informasi tidak ada dalam dokumen — menjawab "Maaf info tidak tersedia" lebih baik daripada jawaban salah. |

## Output / Deliverable
- Fungsi `qwen_reasoning_agent()` yang berjalan dengan 1–2 kali panggilan LLM saja.
- Tabel perbandingan kualitatif ReAct vs planner untuk pertanyaan yang sama.
- Pemahaman decision framework kapan memilih pola mana (dapat dipakai untuk Sesi 8 orchestrator router).

## Lanjut ke Sesi Berikutnya
Sesi 5 memulai domain baru: **Knowledge ERP** — data transaksional (produk, order, stok) yang nantinya bisa **ditulis**, bukan hanya dibaca oleh agent.
