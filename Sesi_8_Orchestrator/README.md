# Sesi 8 - Agentic AI Orchestrator (Port 8000)

## Ringkasan
**Final integration**: Satu service yang menyatukan **Knowledge Agent (Sesi 2–4)** dan **ERP Agent (Sesi 5–7)** dalam satu pintu masuk dengan:
- **LLM Router** (klasifikasikan domain) + **rule-based fallback**.
- **Semantic Cache** (DuckDB VSS) → optimasi latency & biaya seperti P3 di End-to-End-LLM-Serving.
- **Feedback Loop** (👍/👎) → evaluasi kualitas jawaban seperti P4 di End-to-End-LLM-Serving.
- **Planner mode** untuk Knowledge, **ReAct inline mode** untuk ERP.

## Arsitektur Alur
```
[User Query]
    │
    ▼
[Semantic Cache lookup]  ──► Hit ► return jawaban cepat (cached: true)
    │ Miss
    ▼
[Router LLM → domain knowledge / erp]
    │
    ├─── knowledge ──► Planner-Executor (search → answer)
    └─── erp       ──► ReAct Inline (list/check/create/report)
    │
    ▼
[Simpan ke semantic_cache]
[Simpan ke interactions log → siap untuk feedback]
    │
    ▼
[Final Answer + interaction_id]
```

## Cara Run
```cmd
run.bat
```
Otomatis menjalankan **4 service**:

## Persiapan llama.cpp & Model Lokal

Proyek ini menggunakan LLM secara lokal (Local AI). Ikuti langkah ini agar LLM bisa berjalan:

**1. Siapkan Binary llama-server**
- Download *release* terbaru dari **[GitHub llama.cpp releases](https://github.com/ggerganov/llama.cpp/releases)**.
- Ambil file `llama-server.exe` (di Windows) atau `llama-server` (di Mac/Linux).
- Letakkan binary tersebut di folder `../End-to-End LLM Serving/backend/bin/`. (Buat foldernya jika belum ada).

**2. Siapkan File Model GGUF**
📥 **[Download model GGUF dari Google Drive](https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing)**
- Letakkan file `.gguf` di folder `../End-to-End LLM Serving/models/`.
- Periksa isian `LLM_MODEL_GGUF` di `.env` Anda agar persis dengan file model yang terinstal.
| Port | Service                                       |
| ---- | --------------------------------------------- |
| 8001 | Sesi 2 Knowledge CRUD                         |
| 8005 | Sesi 5 ERP CRUD                               |
| 8007 | Sesi 7 ERP Report Generate                    |
| 8000 | **Sesi 8 Orchestrator** (endpoint utama user) |

## Endpoint
| Endpoint                    | Method | Deskripsi                                             |
| --------------------------- | ------ | ----------------------------------------------------- |
| `GET /health`               | GET    | Cek semua dependency, cache count, total interactions |
| `POST /agent/orchestrate`   | POST   | Masukkan query, dapat jawaban end-to-end              |
| `POST /agent/feedback`      | POST   | `{interaction_id, is_like}` → simpan feedback         |
| `GET /agent/stats`          | GET    | Total interactions, likes, dislikes, cache entries    |
| `GET /agent/eval-benchmark` | GET    | 10 Skenario evaluasi + checklist rubrik               |

## Struktur
```
Sesi_8_Orchestrator/
├── app/
│   ├── config.py      # Semua URL dependency, cache_threshold, etc.
│   ├── database.py    # DuckDB VSS: semantic_cache + interactions tables
│   ├── llm.py         # llama-server startup port 8088
│   ├── router.py      # LLM classifier (JSON) + rule fallback
│   ├── dispatch.py    # dispatch_knowledge (planner) + dispatch_erp (react inline)
│   ├── schemas.py
│   └── main.py        # FastAPI /agent/* endpoint
└── tests/test_router.py  # Unit test rule fallback routing
```

## Referensi ke End-to-End-LLM-Serving
| Modul End-to-End             | Ekuivalen di Sesi 8                                            |
| ---------------------------- | -------------------------------------------------------------- |
| P3 Semantic Cache (pgvector) | `semantic_cache` + VSS (DuckDB embedded)                       |
| P4 Feedback Loop (pgvector)  | `interactions` + feedback boolean                              |
| P1/P2 Basic LLM + Saka-NLP   | Dibatalkan: Sesi ini full LLM lokal tanpa external API         |
| P5/P6 RAG FAISS/pgvector     | RAG dipindah ke Knowledge Agent + Planner (dispatch_knowledge) |
