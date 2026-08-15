# README Index — Agentic Knowledge System (8 Sesi)

Kurikulum: **FastAPI + DuckDB + Qwen (Local, tanpa LLM cloud)**
Referensi: [End-to-End-LLM-Serving](https://github.com/Muhammad-Ikhwan-Fathulloh/End-to-End-LLM-Serving)

Setiap sesi punya notebook Colab (`.ipynb`) dan README penjelasan masing-masing (`README_Sesi_X.md`). Ringkasan urutan belajar:

| Sesi | Judul | Notebook | README |
|---|---|---|---|
| 1 | Prepare Data Knowledge & Create Vector DB | `Sesi_1_Prepare_Data_Knowledge_VectorDB.ipynb` | `README_Sesi_1.md` |
| 2 | Knowledge Agent: CRUD REST API | `Sesi_2_Knowledge_Agent_CRUD_API.ipynb` | `README_Sesi_2.md` |
| 3 | Knowledge Agent: Prompting ReAct (Qwen Lokal) | `Sesi_3_Knowledge_Agent_ReAct_Prompting.ipynb` | `README_Sesi_3.md` |
| 4 | Knowledge Agent dengan LLM Reasoning (Qwen, Structured Prompting) | `Sesi_4_Knowledge_Agent_LLM_Reasoning_Qwen.ipynb` | `README_Sesi_4.md` |
| 5 | Knowledge ERP: CRUD REST API | `Sesi_5_Knowledge_ERP_CRUD_API.ipynb` | `README_Sesi_5.md` |
| 6 | Knowledge ERP: Prompting ReAct | `Sesi_6_Knowledge_ERP_ReAct_Prompting.ipynb` | `README_Sesi_6.md` |
| 7 | Knowledge ERP dengan LLM Generate (Qwen) | `Sesi_7_Knowledge_ERP_LLM_Generate_Qwen.ipynb` | `README_Sesi_7.md` |
| 8 | Finalize Agentic AI (Orchestrator, Full Qwen Lokal) | `Sesi_8_Finalize_Agentic_AI_Orchestrator.ipynb` | `README_Sesi_8.md` |

## Dua Domain Paralel

- **Knowledge Agent** (Sesi 1–4): basis pengetahuan bebas (dokumen, FAQ, artikel) + RAG.
- **Knowledge ERP** (Sesi 5–7): data transaksional/bisnis (produk, stok, order) + agent aksi.
- **Sesi 8**: menggabungkan keduanya jadi satu orchestrator.

## Pola Prompting yang Dipelajari

| Pola | Diperkenalkan di | Karakteristik |
|---|---|---|
| ReAct (iteratif) | Sesi 3, 6 | Loop `Thought/Action/Observation`, fleksibel untuk tugas multi-langkah, lebih lambat |
| Structured/JSON (planner-executor) | Sesi 4, 7, 8 | Satu-dua kali panggilan LLM, lebih cepat, cocok tugas satu langkah/generasi teks |

## Stack Teknis
- **FastAPI** — REST API & tool-serving layer
- **DuckDB** — penyimpanan data + vector search (ekstensi `vss`)
- **Qwen 2.5 (GGUF via llama-cpp-python)** — satu-satunya LLM, dijalankan lokal
- **Sentence-Transformers** — embedding dokumen

## Cara Pakai
1. Kerjakan notebook secara berurutan Sesi 1 → 8 di Google Colab.
2. Baca README masing-masing sesi sebelum membuka notebook untuk konteks tujuan & konsep kunci.
3. Setiap notebook punya sel bertanda **🔨 TODO** yang wajib dilengkapi peserta, dengan solusi contoh di sel setelahnya.
4. Model Qwen (GGUF) diunduh otomatis di Sesi 3, 4, 6, 7, 8 — pastikan dijalankan di Colab dengan koneksi internet aktif ke Hugging Face.
5. Tidak ada API key yang dibutuhkan di seluruh kurikulum ini.

## Dokumen Pendukung
Lihat `Materi_Agentic_Knowledge_System_8_Sesi.md` untuk penjelasan lengkap tiap sesi (tujuan, konsep, arsitektur, kode inti, latihan, deliverable) dalam satu dokumen, termasuk struktur folder proyek yang disarankan untuk deployment akhir.
