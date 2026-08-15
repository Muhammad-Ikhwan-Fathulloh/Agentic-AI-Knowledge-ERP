# Sesi 4 — Knowledge Agent dengan LLM Reasoning (Qwen, Structured Prompting)

**File notebook:** `Sesi_4_Knowledge_Agent_LLM_Reasoning_Qwen.ipynb`

## Tentang Sesi Ini
Sesi ini memperkenalkan pola prompting kedua di atas model Qwen yang sama: **planner-executor** berbasis JSON, sebagai alternatif ReAct iteratif dari Sesi 3. Qwen dipaksa mengeluarkan keputusan dalam format JSON ketat — cara mengemulasi *function calling* pada model kecil yang tidak punya kapabilitas itu secara native.

## Prasyarat
- Sudah menyelesaikan Sesi 1–3 (terutama paham `qwen_llm_call()` dan pola ReAct sebagai pembanding).

## Yang Akan Dipelajari
- Kenapa dan kapan pola *single-shot planner* lebih efisien dibanding loop iteratif ReAct.
- Cara memaksa & mem-parsing output JSON dari LLM lokal (`extract_json()` dengan regex + `json.loads`, termasuk strategi retry).
- Pola *planner → tool execution → final answer* sebagai dua tahap terpisah (dua kali panggilan LLM, bukan loop berkali-kali).
- Trade-off: ReAct (fleksibel, banyak langkah, lebih lambat) vs planner (cepat, satu langkah, kurang fleksibel untuk kasus kompleks).

## Struktur Notebook
1. Setup environment + load model Qwen (sama seperti Sesi 3).
2. Rekonstruksi knowledge base & API dari Sesi 1–2.
3. Penjelasan konseptual: kenapa dibutuhkan pola baru selain ReAct.
4. Prompt planner (`PLANNER_PROMPT`) + fungsi `extract_json()`.
5. Fungsi utama `qwen_reasoning_agent()` (planner + jawaban akhir).
6. **TODO 1**: tambahkan fallback rule-based saat parsing JSON gagal total.
7. **TODO 2**: bandingkan ReAct (Sesi 3) vs planner (sesi ini) — jumlah panggilan LLM, latency, kualitas jawaban.

## Cara Menjalankan
Sama seperti Sesi 3, model Qwen diunduh ulang di awal notebook (jalankan di Colab dengan internet). Tidak butuh API key eksternal apa pun.

## Konsep Kunci
| Istilah | Penjelasan Singkat |
|---|---|
| Planner-executor | Pola: satu prompt memutuskan aksi, prompt terpisah menyusun jawaban — bukan loop |
| Structured/JSON prompting | Memaksa LLM mengeluarkan output dalam skema JSON tertentu agar mudah diparsing kode |
| Function calling emulation | Cara menyimulasikan tool-calling pada model tanpa dukungan native untuk fitur tersebut |

## Output / Deliverable
- Fungsi `qwen_reasoning_agent()` yang berjalan dengan 1–2 kali panggilan LLM saja.
- Tabel perbandingan kualitatif ReAct vs planner untuk pertanyaan yang sama.

## Lanjut ke Sesi Berikutnya
Sesi 5 memulai domain baru: **Knowledge ERP** — data transaksional (produk, order, stok) yang nantinya bisa **ditulis**, bukan hanya dibaca oleh agent.
