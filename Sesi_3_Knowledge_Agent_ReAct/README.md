# Sesi 3 — Knowledge Agent ReAct (Port 8002)

## Ringkasan
Mengimplementasikan **loop ReAct (Reason-Act)** manual dengan LLM lokal Qwen. Agent dapat:
- Mencari dokumen relevan via `search_knowledge` (memanggil API Sesi 2).
- Menyimpan dokumen baru via `create_document`.
- Melihat daftar dokumen via `list_documents`.
- Setiap langkah menghasilkan trace `Thought → Action → Action Input → Observation`.

## Prasyarat
- Service **Sesi 2 (Knowledge Agent CRUD API, Port 8001)** sudah jalan (otomatis di-spawn oleh `run.bat`).
- Folder `../End-to-End LLM Serving/models/` berisi file GGUF Qwen (contoh: `qwen2.5-0.5b-instruct-q4_k_m.gguf`).
- Binary `llama-server` ada di `../End-to-End LLM Serving/backend/bin/`.

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
│   ├── schemas.py      # Pydantic ReActRequest / ReActResponse + StepLog
│   ├── llm.py          # Startup llama-server + wrapper llm_complete (async)
│   ├── tools.py        # Tool registry (search_knowledge, list_documents, create_document)
│   ├── react.py        # ReAct loop + prompt template + parser Thought/Action/Action Input
│   └── main.py         # FastAPI entrypoint
├── tests/test_react.py # Unit test parser ReAct step (TANPA butuh LLM)
├── .env                # Override settingan default
└── run.bat             # Spawn Sesi 2 + Sesi 3 sekaligus
```

## Uji Manual (via Swagger /docs)
1. Buka `http://localhost:8002/docs`.
2. Coba `POST /agent/chat` dengan query: `Apa kebijakan refund produk?`.
3. Perhatikan field `steps` — setiap step menunjukkan trace Thought/Action/Observation.
