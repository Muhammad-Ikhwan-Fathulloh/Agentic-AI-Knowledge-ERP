# Sesi 8 — Finalize Agentic AI (Orchestrator, Full Qwen Lokal)

**File notebook:** `Sesi_8_Finalize_Agentic_AI_Orchestrator.ipynb`

## Tentang Sesi Ini
Sesi penutup: **Knowledge Agent** (Sesi 1–4) dan **Knowledge ERP** (Sesi 5–7) digabung menjadi satu **orchestrator agent** yang otomatis merutekan pertanyaan user ke domain yang tepat — seluruhnya di atas satu model Qwen lokal, dengan dua pola prompting yang sudah dipelajari (ReAct & structured/planner).

## Prasyarat
- Sudah menyelesaikan Sesi 1–7 secara berurutan (sesi ini merangkum & menggabungkan semuanya).

## Yang Akan Dipelajari
- Desain **router/orchestrator agent**: menentukan pertanyaan harus dijawab Knowledge Agent (informasi/dokumen) atau Knowledge ERP (data transaksional/aksi).
- Menggabungkan router (structured JSON prompting, pola Sesi 4) dengan tool-selection per domain dalam satu alur `orchestrate()`.
- Evaluasi end-to-end: akurasi routing, latency, dan cara menyusun tabel evaluasi untuk laporan.
- Checklist finalisasi proyek untuk deployment (Docker Compose, `.duckdb` persisten, endpoint `/health`, dsb).

## Struktur Notebook
1. Setup environment + load model Qwen.
2. Rekonstruksi kedua knowledge base (Knowledge Agent + Knowledge ERP) secara ringkas.
3. Router berbasis Qwen (`route_query`) — menentukan domain `knowledge` atau `erp`, dengan fallback rule-based jika parsing JSON gagal.
4. Tool-selection per domain (`TOOL_PROMPT`, `TOOL_DESC`) & fungsi utama `orchestrate()`.
5. **TODO 1**: tambahkan tool `create_order` ke domain ERP lengkap dengan guardrail konfirmasi (pola Sesi 6).
6. Evaluasi end-to-end dengan tabel hasil (`pandas.DataFrame`).
7. **TODO 2**: lengkapi 10 skenario evaluasi, hitung akurasi routing.
8. Checklist finalisasi proyek (deployment, dokumentasi, dsb).

## Cara Menjalankan
Model Qwen diunduh ulang di awal notebook (jalankan di Colab). Notebook ini merekonstruksi ulang kedua database (`knowledge.duckdb`, `erp.duckdb`) secara ringkas agar bisa dijalankan berdiri sendiri tanpa harus membuka 7 notebook sebelumnya.

## Konsep Kunci
| Istilah | Penjelasan Singkat |
|---|---|
| Orchestrator / router agent | Agent lapisan atas yang memutuskan sub-agent/domain mana yang menangani query |
| Domain routing accuracy | Metrik: berapa persen query dirutekan ke domain yang benar |
| End-to-end evaluation | Uji sistem secara keseluruhan (bukan cuma satu komponen) dengan skenario nyata |

## Output / Deliverable
- Fungsi `orchestrate()` yang menjawab kombinasi pertanyaan knowledge + ERP secara otomatis.
- Tabel evaluasi 10 skenario (hasil TODO 2) sebagai laporan akhir proyek.
- Checklist siap-deploy untuk lanjut ke Docker Compose (lihat dokumen materi utama untuk struktur folder lengkap).

## Proyek Selesai 🎉
Seluruh kurikulum (Sesi 1–8) sudah membentuk sistem agentic knowledge lengkap: dari persiapan data, REST API, dua pola prompting (ReAct & structured), generative reporting, hingga orchestrator — semuanya berjalan di atas satu model Qwen lokal tanpa dependensi ke LLM cloud.
