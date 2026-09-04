# Sesi 1 — Prepare Data Knowledge & Create Vector DB (Port 8000)

**Notebook referensi:** `../Sesi_1_Prepare_Data_Knowledge_VectorDB.ipynb`
**Penjelasan mendalam:** `../README_Sesi_1.md`

## Tentang Sesi Ini
Membangun **pipeline data RAG end-to-end**:  
`Load dokumen (PDF/TXT/Markdown) → Cleaning → Chunking (overlap) → Embedding (Sentence-Transformers) → Simpan ke DuckDB VSS`

Service ini juga menyediakan **API ingest + search** standalone, serta **seed data contoh otomatis**
(8 FAQ + SOP toko online NocStore) bila database kosong.

## Prasyarat
- Python 3.10+ (tested 3.11)
- Tidak perlu GPU — model embedding all-MiniLM-L6-v2 berjalan di CPU dengan baik.

## Pipeline
```
[PDF / TXT / Markdown / Teks Manual]
        │  app/ingest.py
        ▼
   [Ekstrak Teks Mentah]
        │
        ▼  app/database.py :: chunk_text()
   [Chunking: 400 kata / chunk, overlap 80 kata]
        │
        ▼  Sentence-Transformers all-MiniLM-L6-v2 (384-dim)
   [Embedding per-chunk]
        │
        ▼  DuckDB + ekstensi VSS + HNSW index
   [Penyimpanan Tabel documents(id, source, content, embedding, created_at)]
```

## Cara Run
```cmd
run.bat
```
Atau manual:
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

## Daftar Endpoint

| Method | Path | Deskripsi |
|---|---|---|
| GET | `/health` | Status service: jumlah dokumen, embed model, path DB, embed_dim |
| GET | `/stats` | Total chunk + jumlah per source + setting chunk size/overlap |
| POST | `/ingest/text` | Simpan teks → chunking otomatis (bisa custom size/overlap) |
| POST | `/ingest/file` | Upload PDF / TXT / Markdown → ekstrak → chunk → embed → simpan |
| POST | `/search` | Semantic search top-k (body JSON: `q` + `k`) |
| GET | `/documents` | Lihat semua chunk terbaru (`?limit=`) |
| DELETE | `/documents` | Reset DB: hapus SEMUA chunk (opsional pembersihan) |

## Uji Manual via `/docs`
1. Buka `http://localhost:8000/docs`.
2. `GET /health` → pastikan `documents_count >= 8` (seed 8 FAQ/SOP).
3. `POST /search` → body: `{"q":"bagaimana refund?","k":3}` → pastikan top-1 adalah chunk FAQ_Refund.
4. `POST /ingest/text` → tambahkan artikel sendiri → cek lagi via `GET /stats`.

## Struktur File
```
Sesi_1_Prepare_Data_Knowledge/
├── app/
│   ├── config.py        # Setting embed model, chunk size, duckdb path
│   ├── schemas.py       # Pydantic request/response
│   ├── database.py      # init_db, chunk_text, encode, insert_chunks, search
│   ├── ingest.py        # extract text dari PDF / TXT / MD
│   ├── seed_samples.py  # CLI seed opsional (selain auto-seed di lifespan)
│   └── main.py          # FastAPI + seed FAQ otomatis di lifespan
├── tests/test_ingest.py # Unit test chunking + embedding dimension
├── .env
└── run.bat
```

## Tugas Eksplorasi
1. **Bandingkan chunk size**: upload PDF yang sama dengan `chunk_size=200` vs `800`, bandingkan hasil search untuk query yang sama.
2. **Similarity search manual**: Jalankan SQL berikut di DuckDB:
   ```sql
   SELECT source, left(content, 80),
          array_distance(embedding, (SELECT embedding FROM documents LIMIT 1)) AS dist
   FROM documents ORDER BY dist ASC LIMIT 5;
   ```
3. **Optimasi overlap**: Ubah `CHUNK_OVERLAP` dari 80 → 200, apa pengaruhnya terhadap retrieval konteks panjang?

## Uji Otomatis (pytest)

```cmd
cd Sesi_1_Prepare_Data_Knowledge
.venv\Scripts\activate
pytest tests/ -v
```

Test **tidak membutuhkan LLM nyala** (hanya menguji chunking logic + dimensi embedding output).

## Hubungan dengan Sesi Lain

- **Sesi 1 → Sesi 2:** Output file `knowledge.duckdb` dari Sesi 1 dapat langsung dipakai Sesi 2 (CRUD REST API) karena kedua sesi pakai skema tabel `documents` identik.
- **Catatan concurrency DuckDB:** Karena DuckDB adalah file embedded single-writer, jalankan **hanya salah satu** Sesi 1 atau Sesi 2 pada satu `knowledge.duckdb` pada waktu bersamaan (atau set `DUCKDB_PATH` berbeda di `.env` masing-masing jika ingin DB terpisah).
- **Sesi 3 & Sesi 4 (Knowledge Agent):** akan memanggil endpoint `search` milik Sesi 2 (port 8001) sebagai tool RAG — jadi Sesi 1 & 2 sama-sama fondasi untuk agent reasoning.
