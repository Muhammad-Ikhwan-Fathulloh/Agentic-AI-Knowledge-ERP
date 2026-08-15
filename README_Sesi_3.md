# Sesi 3 — Knowledge Agent: Prompting ReAct (Qwen Lokal)

**File notebook:** `Sesi_3_Knowledge_Agent_ReAct_Prompting.ipynb`

## Tentang Sesi Ini
Di sini API dari Sesi 2 diubah dari sekadar "endpoint yang dipanggil manual" menjadi *tool* yang dipanggil otomatis oleh LLM lewat pola **ReAct** (Reason → Act → Observe). Reasoning dijalankan oleh **Qwen 2.5** lokal (GGUF, via `llama-cpp-python`) — tanpa API cloud.

## Prasyarat
- Sudah menyelesaikan Sesi 1–2.
- Paham dasar prompt engineering (instruksi ke LLM, parsing output).

## Yang Akan Dipelajari
- Struktur prompt ReAct: `Thought / Action / Action Input / Observation`.
- Kenapa model kecil (Qwen 0.5B–7B) rawan gagal format output, dan cara menangani lewat parsing yang toleran + retry.
- Tool registry: memetakan nama tool ke fungsi Python yang memanggil REST API Sesi 2.
- Cara menjalankan model GGUF secara lokal di Colab dengan `llama-cpp-python`.

## Struktur Notebook
1. Setup environment + unduh model Qwen 2.5-0.5B-Instruct (GGUF) dari Hugging Face.
2. Load model dengan `Llama()`, definisikan `qwen_llm_call()`.
3. Rekonstruksi knowledge base & API dari Sesi 1–2 (ringkas, auto-seed).
4. Prompt template ReAct (`REACT_SYSTEM`).
5. Tool executor (`call_tool`) & fungsi utama `react_loop()`.
6. **TODO 1**: tambahkan tool kedua `create_document`.
7. **TODO 2**: uji 5 pertanyaan berbeda, hitung *success rate* format.

## Cara Menjalankan
⚠️ Sel unduh model butuh koneksi internet ke Hugging Face — jalankan langsung di Google Colab (bukan sandbox terbatas). Proses unduh berjalan sekali per sesi Colab; ukuran model kecil (~0.5B, quantized) sehingga cukup ringan untuk CPU Colab gratis.

## Konsep Kunci
| Istilah | Penjelasan Singkat |
|---|---|
| ReAct | Pola reasoning iteratif: LLM berpikir, memilih aksi, mengamati hasil, ulangi hingga cukup informasi |
| GGUF | Format file model terkuantisasi untuk `llama.cpp`, ringan dijalankan di CPU |
| Guardrail | Batas jumlah langkah (`max_steps`) agar loop tidak berjalan tanpa henti |

## Output / Deliverable
- Fungsi `react_loop()` yang bisa menjawab pertanyaan dengan minimal 1 tool call.
- Log trace `Thought/Action/Observation` untuk setiap query yang diuji.

## Lanjut ke Sesi Berikutnya
Sesi 4 membandingkan pola ReAct iteratif ini dengan pola **planner-executor (structured JSON prompting)** — dua gaya memakai model Qwen yang sama, dengan trade-off kecepatan vs fleksibilitas yang berbeda.
