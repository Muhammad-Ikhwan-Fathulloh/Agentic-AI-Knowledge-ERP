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

---

## 🚀 Folder Implementasi Produksi (selain Notebook)

**Bersumber dari pola arsitektur [End-to-End-LLM-Serving](https://github.com/Muhammad-Ikhwan-Fathulloh/End-to-End-LLM-Serving),
kurikulum ini sekarang dilengkapi folder kode *production-ready* per-sesi (struktur identik seperti `Sesi_2` yang sudah ada):
`app/`, `tests/`, `.env`, `.gitignore`, `requirements.txt`, `run.bat` + README mini internal.**

| Sesi | Folder Implementasi | Port | Stack Penting | Referensi E2E-LLM-Serving |
|---|---|---|---|---|
| 1 | (Notebook-only) | - | DuckDB + VSS, Sentence-Transformers | — |
| **2** | **`Sesi_2/`** (sudah ada) | **8001** | FastAPI + DuckDB + Pydantic | `p1_basic_llm.py` pola REST API |
| **3** | **`Sesi_3_Knowledge_Agent_ReAct/`** | **8002** | ReAct loop + llama-server (port 8080) | `p1_basic_llm.py` pola llama-server startup |
| **4** | **`Sesi_4_Knowledge_Agent_Planner/`** | **8003** | Planner-Executor JSON Prompting + retry | — |
| **5** | **`Sesi_5_Knowledge_ERP_CRUD/`** | **8005** | CRUD Produk/Customer/Order + Stok Validasi | — |
| **6** | **`Sesi_6_Knowledge_ERP_ReAct/`** | **8006** | ERP ReAct + Human-in-the-Loop `create_order` | — |
| **7** | **`Sesi_7_Knowledge_ERP_Generate/`** | **8007** | Laporan Naratif via Qwen (Sales + Low-Stock) | `p1_basic_llm.py` pola prompt generation |
| **8** | **`Sesi_8_Orchestrator/`** | **8000** | Router + Semantic Cache (DuckDB VSS) + Feedback Loop | **`p3_cache_pgvector.py`** & **`p4_feedback_pgvector.py`** (diadaptasi ke DuckDB VSS) |

### Cara Menjalankan Full-Stack (semua service sekaligus)
Jalankan **hanya file `run.bat` di dalam folder `Sesi_8_Orchestrator/`**:
```cmd
cd Sesi_8_Orchestrator
run.bat
```
Script otomatis mem-spawn service Sesi 2 (8001) → Sesi 5 (8005) → Sesi 7 (8007) → Sesi 8 (8000).
Buka `http://localhost:8000/docs` untuk Swagger UI endpoint orchestrator utama.

### Mapping Pola End-to-End-LLM-Serving ke Kurikulum Ini
| Modul End-to-End LLM Serving | Adaptasi di Agentic-AI-Knowledge-ERP |
|---|---|
| **P1: Basic LLM (llama-server)** | Setiap sesi 3,4,6,7,8 punya `app/llm.py` yang mengelola lifecycle `llama-server.exe` (start otomatis via FastAPI `lifespan`, health check, shutdown) |
| **P2: Saka-NLP Optimization** | Bisa dipasang di pre/post processing prompt layer (belum di-hardcode agar modular) |
| **P3: Semantic Cache pgvector** | `Sesi_8_Orchestrator/app/database.py` tabel `semantic_cache` pakai **DuckDB VSS** (embedded, tanpa server DB) |
| **P4: Feedback Loop pgvector** | `Sesi_8_Orchestrator/app/database.py` tabel `interactions` + endpoint `/agent/feedback` (👍/👎) |
| **P5: RAG FAISS / P6: RAG pgvector** | Dipindah ke domain Knowledge Agent (Sesi 2+3+4): DuckDB VSS untuk vector store, Planner-Executor untuk RAG synthesis |
| `frontend/index.html` dashboard 6 tab | Lihat `README_Sesi_8.md` / folder `Sesi_8_Orchestrator/README.md` — dapat dipasang frontend statis di `Sesi_8_Orchestrator/static/` bila dibutuhkan |

---

## Dokumen Pendukung
Lihat `Materi_Agentic_Knowledge_System_8_Sesi.md` untuk penjelasan lengkap tiap sesi (tujuan, konsep, arsitektur, kode inti, latihan, deliverable) dalam satu dokumen, termasuk struktur folder proyek yang disarankan untuk deployment akhir.
