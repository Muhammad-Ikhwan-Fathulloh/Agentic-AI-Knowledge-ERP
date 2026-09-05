# Sesi 3 — Knowledge Agent ReAct (Port 8002)

## Ringkasan
Mengimplementasikan **loop ReAct (Reason-Act)** manual dengan LLM lokal Qwen. Agent dapat:
- Mencari dokumen relevan via `search_knowledge` (memanggil API Sesi 2).
- Menyimpan dokumen baru via `create_document`.
- Melihat daftar dokumen via `list_documents`.
- Setiap langkah menghasilkan trace `Thought → Action → Action Input → Observation`.

## Prasyarat
- Folder `../End-to-End LLM Serving/models/` berisi file GGUF Qwen (contoh: `qwen2.5-0.5b-instruct-q4_k_m.gguf`).
- Binary `llama-server` ada di `../End-to-End LLM Serving/backend/bin/`.
- **Sesi 2 tidak perlu jalan** — knowledge base dikelola lokal di folder ini (`knowledge.duckdb`).

## Download Model Qwen
📥 **[Download model GGUF dari Google Drive](https://drive.google.com/drive/folders/16eYzbAx7KOnawHqmnMD6tjshSSCmp6sX?usp=sharing)**

Setelah download, letakkan file `.gguf` di folder `../End-to-End LLM Serving/models/`.

## Knowledge Base Lokal (dari Sesi 2)
Data FAQ & SOP dari Sesi 2 sudah di-embed langsung ke Sesi 3:
- `app/database.py` — DocStore + seed data (FAQ NocBook, NocMouse, Shipping, Pembayaran, Refund, SOP Garansi, SOP Return, RAM DDR4)
- `app/embeddings.py` — wrapper SentenceTransformer
- Data di-seed otomatis ke `knowledge.duckdb` saat pertama kali startup

Mode sumber data bisa dikontrol via `.env`:
| `USE_LOCAL_DB` | Sumber data |
|---|---|
| `true` (default) | DuckDB lokal Sesi 3 — mandiri, tidak butuh Sesi 2 |
| `false` | REST API Sesi 2 port 8001 — butuh Sesi 2 jalan |

## Cara Run
```cmd
run.bat
```
Atau manual:
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8002 --reload
```

## Endpoint
| Endpoint | Method | Deskripsi |
|---|---|---|
| `GET /health` | GET | Cek app, llama-server, dan koneksi Knowledge API |
| `POST /agent/chat` | POST | Input `{query, max_steps, temperature}` → jawaban ReAct + trace langkah |

## Struktur File
```
Sesi_3_Knowledge_Agent_ReAct/
├── app/
│   ├── config.py       # Settingan port, LLM, API via pydantic-settings
│   ├── schemas.py      # Pydantic: DocIn/DocOut/DocSearchResult + ReActRequest/ReActResponse + StepLog
│   ├── embeddings.py   # SentenceTransformer wrapper (dari Sesi 2)
│   ├── database.py     # DocStore + SEED_DATA FAQ & SOP (dari Sesi 2)
│   ├── llm.py          # Startup llama-server + wrapper llm_complete (async)
│   ├── tools.py        # Tool registry — dual-mode: local DB / HTTP API Sesi 2
│   ├── react.py        # ReAct loop + prompt template + parser Thought/Action/Action Input
│   └── main.py         # FastAPI entrypoint + /documents CRUD + /agent/chat
├── knowledge.duckdb    # Knowledge base lokal (auto-created saat startup)
├── tests/test_react.py # Unit test parser ReAct step (TANPA butuh LLM)
├── .env                # Override settingan default (mis. USE_LOCAL_DB=false)
└── run.bat             # Jalankan Sesi 3 langsung (tanpa perlu spawn Sesi 2)
```

## Uji Manual (via Swagger /docs)
1. Buka `http://localhost:8002/docs`.
2. Coba `POST /agent/chat` dengan query: `Apa kebijakan refund produk?`.
3. Perhatikan field `steps` — setiap step menunjukkan trace Thought/Action/Observation.
