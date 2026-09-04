# Sesi 2 — Knowledge Agent: CRUD REST API (Port 8001)

**Notebook referensi:** `Sesi_2_Knowledge_Agent_CRUD_API.ipynb`
**Penjelasan mendalam:** `../README_Sesi_2.md`

## Tentang Sesi Ini

Membungkus tabel `documents` (DuckDB + VSS dari Sesi 1) menjadi **REST API penuh** dengan FastAPI, lengkap dengan:
- CRUD individual dokumen (`POST/GET/PUT/DELETE /documents/{id}`)
- Pagination list (`GET /documents`)
- **Semantic search** (`GET /documents/search?q=...`) — memakai embedding + `array_distance` DuckDB VSS
- Bulk insert (`POST /documents/bulk`)
- **Upload PDF otomatis** di-chunk & di-embed (`POST /documents/upload-pdf`)
- Ingest teks panjang dengan chunking kustom (`POST /documents/ingest-text`)
- Seed otomatis 8 contoh FAQ + SOP ketika DB kosong
- Health check (`/health`) & statistik sumber (`/stats`)
- CORS middleware siap dipanggil frontend / agent lain

## Prasyarat

- Python 3.10+ (tested 3.11)
- Tidak perlu GPU / server DB — DuckDB embedded.

## Struktur Folder

```
Sesi_2/
├── app/
│   ├── __init__.py
│   ├── config.py          pydantic-settings baca .env
│   ├── schemas.py         Pydantic DocIn / DocOut / DocSearchResult
│   ├── embeddings.py      Sentence-Transformer encode() wrapper
│   ├── database.py        DuckDB VSS + DocStore (CRUD + search + seed + chunk)
│   ├── pdf_ingest.py      Extract & chunk PDF (pypdf)
│   └── main.py            FastAPI entrypoint: CORS, lifespan, semua endpoint
├── tests/
│   ├── test_documents.py  CRUD + search + bulk + ingest-text (pytest + TestClient)
│   └── test_pdf_upload.py Validasi Content-Type & PDF kosong
├── .env                   Default: DuckDB + port 8001
├── .gitignore
├── requirements.txt
└── run.bat                Auto venv → install → uvicorn --reload port 8001
```

## Cara Menjalankan

```cmd
cd Sesi_2
run.bat
```

Script akan:
1. Buat `.venv` kalau belum ada → aktifkan.
2. `pip install -r requirements.txt`
3. Start `uvicorn app.main:app --port 8001 --reload`

Buka **Swagger UI:** `http://localhost:8001/docs`

## Daftar Endpoint

| Method | Path | Deskripsi |
|---|---|---|
| GET | `/health` | Status service: jumlah dokumen, embed model, path DB |
| GET | `/stats` | Total dokumen + jumlah per source |
| POST | `/documents` | Insert satu dokumen (auto-embed) |
| GET | `/documents` | List dokumen (`?limit=&offset=`) |
| GET | `/documents/search` | Semantic search (`?q=&k=`) |
| GET | `/documents/{id}` | Get by ID |
| PUT | `/documents/{id}` | Update (re-embed otomatis) |
| DELETE | `/documents/{id}` | Hapus by ID |
| POST | `/documents/bulk` | Insert banyak dokumen sekaligus |
| POST | `/documents/upload-pdf` | Upload file PDF → extract → chunk → embed |
| POST | `/documents/ingest-text` | Teks panjang → chunking kustom → simpan multi-row |

## Seed Data Otomatis

Jika `knowledge.duckdb` kosong (atau baru dibuat), saat startup otomatis disisipkan 8 contoh (dengan chunking 400 kata / overlap 80):
- FAQ garansi NocBook, FAQ waterproof NocMouse
- FAQ pengiriman luar Jawa, FAQ metode pembayaran, FAQ refund
- SOP Klaim Garansi NocBook, SOP Pengembalian Barang
- Artikel Teknologi RAM DDR4 NocMem

## Uji Otomatis (pytest)

```cmd
cd Sesi_2
.venv\Scripts\activate
pytest tests/ -v
```

Test **tidak membutuhkan LLM nyala** (hanya menguji parser, CRUD, fallback, validasi).

## Hubungan dengan Sesi Lain

- Sesi **2 ini adalah "tool provider" untuk agent di Sesi 3 (ReAct) dan Sesi 4 (Planner)** — kedua sesi itu akan memanggil `http://localhost:8001/documents/search` & `/documents` sebagai *Knowledge Base*.
- Port 8001 juga digunakan oleh Sesi 8 (Orchestrator) ketika melakukan dispatch ke domain `knowledge`.
