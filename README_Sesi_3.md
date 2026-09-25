# Sesi 3 - Knowledge Agent: Prompting ReAct (Qwen Lokal)

**File notebook:** `Sesi_3_Knowledge_Agent_ReAct_Prompting.ipynb`
**Kode implementasi production-ready:** `Sesi_3_Knowledge_Agent_ReAct/` (FastAPI, port 8002)

---

## Daftar Isi
1. [Tentang Sesi Ini](#tentang-sesi-ini)
2. [Konsep ReAct Secara Mendalam](#konsep-react-secara-mendalam)
3. [Anatomi Prompt ReAct - Panduan Pembuatan](#anatomi-prompt-react--panduan-pembuatan)
4. [Alur ReAct Loop (Iteratif Reasoning-Acting)](#alur-react-loop-iteratif-reasoning-acting)
5. [Parsing & Guardrail: Tantangan Model Kecil](#parsing--guardrail-tantangan-model-kecil)
6. [Multi-Topik Reasoning: Dekomposisi Pertanyaan Gabungan](#multi-topik-reasoning-dekomposisi-pertanyaan-gabungan)
7. [Prasyarat & Yang Akan Dipelajari](#prasyarat--yang-akan-dipelajari)
8. [Struktur Notebook & Cara Menjalankan](#struktur-notebook--cara-menjalankan)
9. [Konsep Kunci & Output / Deliverable](#konsep-kunci--output--deliverable)

---

## Tentang Sesi Ini
Di sini API dari Sesi 2 diubah dari sekadar "endpoint yang dipanggil manual" menjadi *tool* yang dipanggil otomatis oleh LLM lewat pola **ReAct** (Reason → Act → Observe). Reasoning dijalankan oleh **Qwen 2.5** lokal (GGUF, via `llama-cpp-python`) - tanpa API cloud.

Ini adalah titik balik krusial dalam kurikulum: sebelumnya kode *kita* yang mengendalikan alur program (if/else, fungsi yang dipanggil secara deterministik). Mulai sesi ini, **LLM-lah yang memutuskan fungsi mana yang dipanggil, kapan dipanggil, dan dengan parameter apa**, berdasarkan bahasa natural. Pergeseran paradigma ini membawa tantangan baru: *format output LLM tidak selalu dapat diprediksi 100%*. Seluruh Sesi 3 membahas cara mengelola ketidakpastian ini agar agent tetap dapat diandalkan.

---

## Konsep ReAct Secara Mendalam

### Latar Belakang: Mengapa Tidak Cukup Chain-of-Thought (CoT) Saja?
Sebelum ReAct, teknik standard untuk meningkatkan akurasi LLM adalah **Chain-of-Thought** (CoT): meminta LLM "berpikir langkah demi langkah" sebelum mengeluarkan jawaban. CoT memang meningkatkan kemampuan penalaran matematika dan logika, tapi punya kelemahan fatal: **seluruh fakta berasal dari bobot (weights) model saja**, tidak diverifikasi ke sumber data eksternal. Hasilnya:
- Fakta lama yang berubah (misal kebijakan refund terbaru 2026) tidak bisa CoT ketahui.
- LLM rawan **halusinasi** - "mengingat" fakta yang tidak benar tapi terdengar meyakinkan.
- CoT tidak bisa *berinteraksi* dengan dunia nyata (cek database, kirim email, buat order).

ReAct memecahkan ini dengan menambahkan loop **Act → Observe** ke dalam Chain-of-Thought.

### Definisi Formal ReAct
Dari paper asli Google 2022 (*Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models"*):

> **ReAct = LLM menghasilkan jejak penalaran (thought) dan aksi spesifik (action) secara berselang-seling. Thought memandu aksi selanjutnya, sedangkan observation dari aksi memperbaiki thought berikutnya.**

Perhatikan kata **berselang-seling**: ini bukan "berpikir SEKALI baru bertindak SEKALI", melainkan **T → A → O → T' → A' → O' → …** sampai konvergen ke jawaban final.

### Filosofi "Manusia Memecahkan Masalah"
ReAct meniru cara manusia menyelesaikan masalah kompleks:
1. **T**hought (Pikir): *"Saya perlu tahu tentang garansi NocBook. Informasi ini kemungkinan ada di dokumen SOP."*
2. **A**ction (Aksi): *Membuka folder SOP → mencari file "Garansi_NocBook.pdf"*
3. **O**bserve (Amati): *Membaca 4 langkah klaim garansi di PDF.*
4. **T**hought' (Pikir lagi): *"Bagus, garansi sudah jelas. Sekarang user juga nanya refund. Saya cari dokumen refund."*
5. **A**ction': *Membuka file "Kebijakan_Refund.pdf"*
6. **O**bserve': *Membaca syarat refund.*
7. **T**hought'' (Pikir final): *"Semua info cukup. Susun jadi jawaban rapi."*
8. **FINISH** (Jawab user).

Setiap tahap memiliki jejak yang *traceable* - jika suatu saat jawaban salah, kita bisa audit: "Apakah LLM salah cari dokumen? Atau salah merangkum observation?"

### ReAct vs Paradigma Agent Lainnya
| Paradigma                           | Proses                                    | Kelebihan                                 | Kekurangan                                          | Contoh Kasus                       |
| ----------------------------------- | ----------------------------------------- | ----------------------------------------- | --------------------------------------------------- | ---------------------------------- |
| **CoT Biasa**                       | T → Jawaban                               | Cepat, 1 LLM call                         | Halusinasi, no data eksternal                       | Penalaran matematika sederhana     |
| **ReAct (Sesi 3)**                  | T→A→O→T'→…→FINISH                         | Interpretable, bisa akses tool, fleksibel | Banyak LLM call, lambat untuk FAQ                   | Investigasi bertahap, multi-topik  |
| **Planner (Sesi 4)**                | Planner (1x LLM) → Tool → Answer (1x LLM) | Cepat (hanya 2 LLM call), stabil          | Kurang fleksibel, tidak bisa multi-step investigasi | FAQ single-topik, lookup sederhana |
| **Native Function Calling (GPT-4)** | LLM memanggil tool secara built-in        | Paling stabil formatnya                   | Butuh model besar (mahal), data keluar cloud        | Production enterprise              |

> **Catatan penting:** Qwen 0.5B–7B TIDAK punya fitur native function calling seperti GPT-4. Seluruh implementasi ReAct dan Planner di kurikulum ini adalah **emulasi manual via prompt engineering + parsing regex/JSON**. Ini membuat pembelajaran jauh lebih *informatif* - peserta melihat *bagaimana* function calling bekerja di balik layar, bukan sekadar memanggil library.

---

## Anatomi Prompt ReAct - Panduan Pembuatan

Kualitas ReAct agent 90% ditentukan oleh seberapa baik Anda menulis `REACT_SYSTEM` prompt. Berikut adalah *panduan pembuatan prompt ReAct* berdasarkan implementasi di [react.py#L6-L57](file:///d:/Agentic-AI-Knowledge-ERP/Sesi_3_Knowledge_Agent_ReAct/app/react.py#L6-L57):

### Komponen Wajib Prompt ReAct (Dalam Urutan)
Buat checklist ini setiap kali Anda membangun agent ReAct baru:

1. **✅ Role & Persona Definition**
   - *"Kamu adalah agent Knowledge yang menjawab pertanyaan memakai tool."*
   - Aturan: Jangan gunakan persona yang terlalu "cerdas" (misal "ahli AI") - ini membuat LLM berhalusinasi seolah tahu semuanya. Persona yang *mengandalkan tool* justru lebih baik.

2. **✅ Tool Inventory - Daftar Eksplisit + Skema Parameter**
   ```
   - search_knowledge[query]: mencari dokumen relevan di knowledge base.
   - create_document[{"source":"...", "content":"..."}]: menyimpan dokumen baru.
   ```
   - Aturan: **Jangan pernah terlalu banyak tool** (≤ 5). Model kecil bingung jika tool > 5, apalagi dengan nama mirip.
   - Aturan: Gunakan format `nama_tool[bentuk_param]` sebagai petunjuk implisit. Ini bekerja lebih baik daripada menjelaskan parameter di paragraf.

3. **✅ Output Format Contract - Labelisasi Yang Konsisten**
   ```
   Thought: <pemikiranmu>
   Action: <nama_tool ATAU FINISH>
   Action Input: <parameter ATAU jawaban final>
   ```
   - Aturan: **Setiap field HARUS punya prefix label unik** (Thought:, Action:, Action Input:). Ini *syarat mutlak* agar regex parsing bisa bekerja.
   - Aturan: Buat labelnya **case-sensitive persis** (jangan campur `Thought:` dengan `thought:`). LLM biasanya meniru casing dari contoh.

4. **✅ Observation Protocol**
   *"Jika Action bukan FINISH, Observation akan diberikan lalu kamu lanjutkan langkah berikutnya."*
   - Aturan: Sebutkan kata `Observation` secara eksplisit. Ini memberitahu LLM bahwa "setelah Action Input, giliran SISTEM yang bicara - Anda tunggu."

5. **✅ Domain-Specific Rules (Opsional Tapi Sangat Disarankan)**
   Contoh multi-topik rule di implementasi kita:
   ```
   - Jika pertanyaan user mengandung LEBIH DARI SATU topik, kamu HARUS search_knowledge TERPISAH…
   ```
   - Aturan: Rules spesifik domain meningkatkan akurasi jauh lebih banyak daripada aturan umum. Jika agent Anda untuk "logistik", tambahkan rule "sebutkan nama kurir sebelum FINISH". Jika agent "medis", tambahkan rule "selalu sebutkan dosis obat dengan angka, bukan kata".

6. **✅ Few-Shot Examples - Minimal 3 Contoh**
   Kuantitas minimum yang terbukti bekerja untuk Qwen 0.5B–7B:
   - 1 contoh sederhana (1 topik, 1 tool call → FINISH)
   - 1 contoh kompleks (multi-topik, multi-tool call → FINISH terstruktur)
   - 1 contoh **SALAH** dengan penjelasan "ini dilarang karena …"

   Few-shot yang **SPESIFIK DOMAIN** jauh lebih efektif daripada contoh abstrak. Jangan malu menulis contoh 10–15 baris; LLM kecil *butuh* pola yang jelas.

---

## Alur ReAct Loop (Iteratif Reasoning-Acting)

Berikut *state transition diagram* untuk satu iterasi ReAct:

```
              ┌────────────────────────────────────────┐
              │           history (string)             │
              │  = REACT_SYSTEM + Pertanyaan +         │
              │    Σ (output_k + Observation_k)        │
              └───────────────┬────────────────────────┘
                              ▼
              ┌────────────────────────────────────────┐
              │    llm_complete(history,               │
              │                stop=["Observation:"])  │◀── Stop tokens:
              └───────────────┬────────────────────────┘    Qwen tidak perlu
                              ▼                             menulis Observation
                ┌──────────────────────────────┐            sendiri (bisa
                │ _parse_step(output)          │            halusinasi!)
                │ → thought, action, input     │
                └──────────────┬───────────────┘
                               ▼
                 ┌─────────────────────────────┐
                 │  action valid dan terdaftar?│
                 └──────┬────────────────┬─────┘
                        │ TIDAK          │ YA
                        ▼                 ▼
         ┌────────────────────┐   ┌───────────────────────┐
         │ observation =      │   │  action == "finish"?  │
         │  "Format tidak     │   └──────┬──────────┬─────┘
         │   valid: …"        │          │ YA       │ TIDAK
         │                    │          ▼          ▼
         │ lanjut ke step     │  ┌────────────┐ ┌─────────────────┐
         │   berikutnya       │  │ placeholder?│ │ tools.call()    │
         │ (self-healing)     │  └─┬──────┬───┘ │ → observation   │
         └────────────────────┘    │YA    │TIDAK│ history += obs  │
                                   ▼      ▼     │ lanjut step     │
                          ┌────────────┐ ┌─────┴────────────┐
                          │ retry 1x   │ │ return final_answ,│
                          │ + pesan    │ │        steps     │
                          │ perbaikan  │ └──────────────────┘
                          └─────┬──────┘
                                │
                                ▼
                     (kembali ke atas loop)
```

### Bagaimana `history` Tumbuh Setiap Iterasi (Contoh Riil)
```
Iterasi 0 (awal):
  history = REACT_SYSTEM + "Pertanyaan user: Bagaimana refund?"
             (± 2000 token)

Iterasi 1 (setelah tool call):
  history = REACT_SYSTEM + "Pertanyaan user: Bagaimana refund?"
          + "Thought: User ingin tahu refund…\n"
          + "Action: search_knowledge\n"
          + "Action Input: kebijakan refund\n\n"
          + "Observation: [1] (score=0.72…) Syarat refund: 30 hari…\n\n"
             (± 2500 token)

Iterasi 2 (FINISH):
  history = (sampai Observation terakhir)
          + "Thought: Info refund sudah cukup…\n"
          + "Action: FINISH\n"
          + "Action Input: Untuk refund, syaratnya adalah…\n\n"
             (± 2900 token)
```
**Kenapa ini penting?** Semakin banyak step, semakin panjang `history`, semakin mahal komputasinya (lama generate, lebih banyak token). Ini alasan praktis kenapa `max_steps` perlu dibatasi - bukan cuma mencegah infinite loop, tapi juga mengendalikan cost/latensi.

---

## Parsing & Guardrail: Tantangan Model Kecil

### Mengapa Model Kecil Selalu Bermasalah dengan Format?
Qwen 0.5B–7B (dan hampir semua model open-source kecil) punya 2 kelemahan mendasar terkait format output:
1. **Trained on general text, not structured output.** Model melihat jauh lebih banyak artikel/blog daripada format `Label: Value`.
2. **Attention head terbatas.** Model besar (30B+) punya cukup kapasitas untuk "selalu mengingat format rules" di tengah konteks panjang. Model kecil sering "lupa" aturan format setelah 1-2 iterasi.

### Strategi Pertahanan Bertingkat (Defense-in-Depth)
Implementasi ReAct di kurikulum ini menggunakan **5 lapisan pertahanan berurutan**:

| Tingkat                         | Mekanisme                                            | Aksi Jika Gagal                                            | Contoh yang Ditangkap                                      |
| ------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------- |
| **L1 - Prompt Design**          | Few-shot + penekanan kata WAJIB                      | Menghindari sejak awal                                     | LLM lupa Action Input                                      |
| **L2 - Stop Tokens**            | `stop=["Observation:"]`                              | Memotong output sebelum LLM halusinasi Observation sendiri | Qwen menulis "Observation: (saya pikir hasilnya adalah …)" |
| **L3 - Regex Parsing Tolerant** | 3 regex terpisah, masing-masing dengan fallback `""` | Tidak crash, lanjut dengan parsial                         | Thought hilang, tapi Action & Input ada                    |
| **L4 - Whitelist Validation**   | `action.lower() in valid_actions`                    | Kirim Observation "tool tidak dikenal", ulangi             | LLM menulis `Action: look_up` (tool tidak ada)             |
| **L5 - Content Quality**        | Placeholder detection + FINISH retry                 | Paksa 1x ulang FINISH                                      | `Action Input: Selesai` (placeholder)                      |

### Kalau 5 Lapisan Ini Masih Gagal?
Ada 2 fallback terakhir:
1. **Fallback `max_steps` habis:** Return jawaban sementara dari observation terakhir dengan tag `[Melebihi batas langkah]`. User tetap dapat informasi, bukan blank.
2. **Fallback kode Python rule-based (di luar loop):** Jika `final_answer` masih placeholder / `[Melebihi batas langkah]`, Anda bisa menambahkan layer di `main.py` yang melakukan rule-based response sederhana (misal keyword matching ke query user).

---

## Multi-Topik Reasoning: Dekomposisi Pertanyaan Gabungan

### Mengapa Ini Topik Tersendiri?
Setelah menguji Qwen 0.5B dengan 100+ pertanyaan, pola kegagalan yang **paling sering** bukan format error - tapi **premature FINISH** (selesai sebelum semua bagian pertanyaan terjawab). User bertanya 3 hal, LLM menjawab 1 hal, lalu FINISH.

Karena itu, implementasi di Sesi 3 menambahkan **3 aturan khusus multi-topik** secara eksplisit di dalam prompt, bukan di kode. Berikut penjelasan masing-masing:

#### Aturan 1: Pemisahan Query Per Topik (Bukan Gabung)
> *"Jangan gabungkan dua topik berbeda dalam satu query pencarian."*

**Alasan:** Vector search bekerja dengan cosine similarity satu vektor query → satu vektor dokumen. Jika query gabungan `garansi refund`, vektornya berada "di tengah" antara topik garansi dan refund. Hasilnya: dokumen garansi skor 0.5, dokumen refund skor 0.5 - tidak ada yang tinggi. Dua query terpisah → masing-masing dokumen dapat skor ~0.7–0.8 → jauh lebih relevan.

#### Aturan 2: Checkpoint di Thought
> *"Sebelum lanjut ke topik berikutnya, tulis di Thought apakah topik saat ini sudah cukup informasinya, dan topik apa saja yang masih belum dicari."*

**Alasan:** Ini adalah *commitment device* (alat komitmen). Jika LLM menulis secara eksplisit "topik garansi sudah, sekarang tinggal refund", probabilitas LLM benar-benar mencari refund naik ~35% (dari pengujian empiris). Sebaliknya, jika LLM hanya berpikir implisit tanpa ditulis, ia sering "lupa" topik kedua.

#### Aturan 3: Verifikasi Silang dengan list_documents
> *"Jika hasil search_knowledge terlihat terpotong (misal langkah bernomor 1-4 tapi ada indikasi masih berlanjut, atau skor relevansi rendah), gunakan list_documents untuk memverifikasi."*

**Alasan:** Scenario umum di vector search: chunk SOP_Garansi.pdf ter-split menjadi 2 chunk (A: langkah 1–3, B: langkah 4–6). Search hanya menangkap chunk A (skor tertinggi). LLM membaca nomor "1. 2. 3." dan berpikir itu selesai, padahal masih ada 4–6 di chunk B. Aturan ini membuat LLM *curiga* jika melihat pola nomor urut tanpa penutup.

---

## Prasyarat
- Sudah menyelesaikan Sesi 1–2.
- Paham dasar prompt engineering (instruksi ke LLM, parsing output).
- Paham REST API dasar (GET/POST, parameter query/body).

## Yang Akan Dipelajari
- Struktur prompt ReAct: `Thought / Action / Action Input / Observation`.
- Kenapa model kecil (Qwen 0.5B–7B) rawan gagal format output, dan cara menangani lewat parsing yang toleran + retry.
- Tool registry: memetakan nama tool ke fungsi Python yang memanggil REST API Sesi 2.
- Cara menjalankan model GGUF secara lokal di Colab dengan `llama-cpp-python`.
- **Khusus pembelajaran mendalam:**
  - Perbedaan filosofi ReAct vs Chain-of-Thought vs Native Function Calling.
  - 7 komponen wajib prompt ReAct dan urutan penulisannya.
  - Strategy defense-in-depth 5 lapisan untuk output format LLM yang tak dapat diprediksi.
  - Teknik dekomposisi multi-topik (mengatasi premature FINISH).

## Struktur Notebook
1. Setup environment + unduh model Qwen 2.5-0.5B-Instruct (GGUF) dari Hugging Face.
2. Load model dengan `Llama()`, definisikan `qwen_llm_call()`.
3. Rekonstruksi knowledge base & API dari Sesi 1–2 (ringkas, auto-seed).
4. Prompt template ReAct (`REACT_SYSTEM`) + pembedahan komponennya.
5. Tool executor (`call_tool`) & fungsi utama `react_loop()`.
6. **TODO 1**: tambahkan tool kedua `create_document`.
7. **TODO 2**: uji 5 pertanyaan berbeda, hitung *success rate* format.

## Cara Menjalankan
⚠️ Sel unduh model butuh koneksi internet ke Hugging Face - jalankan langsung di Google Colab (bukan sandbox terbatas). Proses unduh berjalan sekali per sesi Colab; ukuran model kecil (~0.5B, quantized) sehingga cukup ringan untuk CPU Colab gratis.

Untuk versi kode production (FastAPI port 8002, tanpa Colab), lihat folder `Sesi_3_Knowledge_Agent_ReAct/` dan jalankan `run.bat`.

## Konsep Kunci
| Istilah                   | Penjelasan Singkat                                                          | Penjelasan Mendalam                                                                                                                                         |
| ------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ReAct**                 | Pola reasoning iteratif: LLM berpikir → aksi → amati → ulangi               | Paradigma dari paper Google 2022. Menggabungkan CoT (penalaran) dengan kemampuan memanggil tool (aksi). Setiap langkah bergantian antara LLM dan Python.    |
| **GGUF**                  | Format file model terkuantisasi untuk `llama.cpp`, ringan dijalankan di CPU | Pengganti format GGML/GGJT. Mendukung multiple quantization (Q4_K_M adalah sweet spot: 4-bit, akurasi hampir FP16 tapi ¼ ukuran).                           |
| **Guardrail**             | Batas jumlah langkah (`max_steps`) agar loop tidak berjalan tanpa henti     | Diimplementasikan bertingkat: max_steps, whitelist action, placeholder detection, retry, dan fallback max_steps. 99% kasus tertangkap di 3 lapisan pertama. |
| **Few-Shot Prompting**    | Memberi 2–3 contoh jawaban format yang benar                                | Untuk Qwen 0.5B, contoh SALAH secara eksplisit ("ini dilarang karena X") meningkatkan akurasi format ~20% dibanding hanya contoh BENAR.                     |
| **Multi-Topik Reasoning** | Memisahkan pertanyaan gabungan menjadi beberapa pencarian terpisah          | Mengatasi premature FINISH dengan 3 teknik: query per-topik, checkpoint di Thought, dan verifikasi list_documents untuk chunk terpotong.                    |

## Output / Deliverable
- Fungsi `react_loop()` yang bisa menjawab pertanyaan dengan minimal 1 tool call.
- Log trace `Thought/Action/Observation` untuk setiap query yang diuji.
- Pemahaman kapan ReAct lebih cocok daripada planner (lanjut ke Sesi 4).

## Lanjut ke Sesi Berikutnya
Sesi 4 membandingkan pola ReAct iteratif ini dengan pola **planner-executor (structured JSON prompting)** - dua gaya memakai model Qwen yang sama, dengan trade-off kecepatan vs fleksibilitas yang berbeda.
