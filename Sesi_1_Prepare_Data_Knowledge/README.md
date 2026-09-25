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

| Method | Path           | Deskripsi                                                       |
| ------ | -------------- | --------------------------------------------------------------- |
| GET    | `/health`      | Status service: jumlah dokumen, embed model, path DB, embed_dim |
| GET    | `/stats`       | Total chunk + jumlah per source + setting chunk size/overlap    |
| POST   | `/ingest/text` | Simpan teks → chunking otomatis (bisa custom size/overlap)      |
| POST   | `/ingest/file` | Upload PDF / TXT / Markdown → ekstrak → chunk → embed → simpan  |
| POST   | `/search`      | Semantic search top-k (body JSON: `q` + `k`)                    |
| GET    | `/documents`   | Lihat semua chunk terbaru (`?limit=`)                           |
| DELETE | `/documents`   | Reset DB: hapus SEMUA chunk (opsional pembersihan)              |

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

---

## 🛠️ Hands-On: Cara Membuat Proyek Ini dari Nol

Ikuti langkah demi langkah berikut untuk membangun ulang Sesi 1 dari awal.

### Langkah 1 — Buat Struktur Folder

```cmd
mkdir Sesi_1_Prepare_Data_Knowledge
cd Sesi_1_Prepare_Data_Knowledge
mkdir app tests
```

### Langkah 2 — Buat Virtual Environment & Install Dependensi

```cmd
python -m venv .venv
.venv\Scripts\activate
```

Buat file `requirements.txt`:

```
fastapi
uvicorn[standard]
pydantic
pydantic-settings
python-dotenv
duckdb
sentence-transformers
httpx
pytest
pypdf
python-multipart
```

Lalu install:

```cmd
pip install -r requirements.txt
```

### Langkah 3 — Buat File Konfigurasi `.env`

```env
EMBED_MODEL=all-MiniLM-L6-v2
EMBED_DIM=384
DUCKDB_PATH=./knowledge.duckdb
CHUNK_SIZE=400
CHUNK_OVERLAP=80
APP_PORT=8000
```

### Langkah 4 — Buat `app/config.py`

Buat file `app/config.py` untuk membaca `.env` via `pydantic-settings`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    duckdb_path: str = "./knowledge.duckdb"
    chunk_size: int = 400
    chunk_overlap: int = 80
    app_port: int = 8000

    class Config:
        env_file = ".env"

settings = Settings()
```

### Langkah 5 — Buat `app/schemas.py`

Definisikan request/response model Pydantic:

```python
from pydantic import BaseModel
from typing import Optional

class IngestTextRequest(BaseModel):
    source: str
    content: str
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None

class SearchRequest(BaseModel):
    q: str
    k: int = 3
```

### Langkah 6 — Buat `app/database.py`

Inilah inti proyek — modul yang mengelola DuckDB + VSS:

```python
import duckdb, uuid
from sentence_transformers import SentenceTransformer
from .config import settings

_model = SentenceTransformer(settings.embed_model)

def get_conn():
    conn = duckdb.connect(settings.duckdb_path)
    conn.execute("INSTALL vss; LOAD vss;")
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id VARCHAR PRIMARY KEY,
            source VARCHAR,
            content TEXT,
            embedding FLOAT[384],
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_emb ON documents
        USING HNSW (embedding) WITH (metric='cosine')
    """)
    conn.close()

def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i:i+size]))
        i += size - overlap
    return chunks

def encode(text: str) -> list[float]:
    return _model.encode(text).tolist()

def insert_chunks(source: str, content: str,
                  chunk_size: int = None, chunk_overlap: int = None):
    sz = chunk_size or settings.chunk_size
    ov = chunk_overlap or settings.chunk_overlap
    chunks = chunk_text(content, sz, ov)
    conn = get_conn()
    for c in chunks:
        conn.execute(
            "INSERT INTO documents(id,source,content,embedding) VALUES(?,?,?,?)",
            [str(uuid.uuid4()), source, c, encode(c)]
        )
    conn.close()
    return len(chunks)

def search(query: str, k: int = 3):
    conn = get_conn()
    emb = encode(query)
    rows = conn.execute("""
        SELECT id, source, content,
               array_distance(embedding, ?::FLOAT[384]) AS score
        FROM documents
        ORDER BY score ASC LIMIT ?
    """, [emb, k]).fetchall()
    conn.close()
    return [{"id": r[0], "source": r[1], "content": r[2], "score": r[3]}
            for r in rows]

def count_docs():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    return n

def get_all(limit: int = 50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id,source,content,created_at FROM documents ORDER BY created_at DESC LIMIT ?",
        [limit]
    ).fetchall()
    conn.close()
    return [{"id":r[0],"source":r[1],"content":r[2],"created_at":str(r[3])} for r in rows]

def delete_all():
    conn = get_conn()
    conn.execute("DELETE FROM documents")
    conn.close()
```

### Langkah 7 — Buat `app/ingest.py`

Modul untuk mengekstrak teks dari PDF, TXT, dan Markdown:

```python
import io
from pypdf import PdfReader

def extract_text(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    # TXT / MD — decode langsung
    return content.decode("utf-8", errors="ignore")
```

### Langkah 8 — Buat `app/seed_samples.py`

Data contoh 8 FAQ/SOP yang otomatis di-seed saat DB kosong:

```python
SAMPLES = [
    {"source": "FAQ_Garansi_NocBook",
     "content": "NocBook mendapat garansi resmi 1 tahun untuk kerusakan pabrik..."},
    {"source": "FAQ_Refund",
     "content": "Kebijakan refund: pengajuan max 30 hari sejak terima barang..."},
    # tambahkan 6 data lain sesuai kebutuhan
]
```

### Langkah 9 — Buat `app/main.py`

FastAPI entrypoint lengkap dengan seluruh endpoint:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from .database import init_db, insert_chunks, search, count_docs, get_all, delete_all
from .ingest import extract_text
from .schemas import IngestTextRequest, SearchRequest
from .seed_samples import SAMPLES

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if count_docs() == 0:          # seed otomatis bila DB kosong
        for s in SAMPLES:
            insert_chunks(s["source"], s["content"])
    yield

app = FastAPI(title="Sesi 1 — Knowledge Vector DB", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok", "documents_count": count_docs()}

@app.get("/stats")
def stats():
    return {"total_chunks": count_docs()}

@app.post("/ingest/text")
def ingest_text(req: IngestTextRequest):
    n = insert_chunks(req.source, req.content, req.chunk_size, req.chunk_overlap)
    return {"chunks_created": n}

@app.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    raw = await file.read()
    text = extract_text(file.filename, raw)
    if not text.strip():
        raise HTTPException(400, "Tidak ada teks yang bisa diekstrak")
    n = insert_chunks(file.filename, text)
    return {"filename": file.filename, "chunks_created": n}

@app.post("/search")
def search_docs(req: SearchRequest):
    return search(req.q, req.k)

@app.get("/documents")
def list_docs(limit: int = 50):
    return get_all(limit)

@app.delete("/documents")
def reset_db():
    delete_all()
    return {"message": "Semua chunk dihapus"}
```

### Langkah 10 — Jalankan Server

```cmd
uvicorn app.main:app --port 8000 --reload
```

Buka di browser: **http://localhost:8000/docs**

### Langkah 11 — Uji Coba via Swagger

1. **`GET /health`** → pastikan `documents_count >= 8` (seed otomatis berhasil)

2. **`POST /ingest/text`** → tambah dokumen baru:
   ```json
   {
     "source": "Panduan_Pengiriman",
     "content": "Pengiriman ke seluruh Indonesia menggunakan JNE, SiCepat, dan Anteraja. Gratis ongkir untuk pembelian di atas Rp 200.000."
   }
   ```

3. **`POST /search`** → cari dokumen relevan:
   ```json
   { "q": "bagaimana cara pengiriman?", "k": 3 }
   ```
   Pastikan dokumen `Panduan_Pengiriman` muncul di hasil teratas.

4. **`POST /ingest/file`** → upload PDF via form-data di Swagger, lalu cari isinya.

5. **`GET /stats`** → lihat total chunk yang tersimpan.

### Langkah 12 — Buat `run.bat` untuk Kemudahan

```bat
@echo off
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

### Langkah 13 — Tulis Unit Test (Opsional)

Buat `tests/test_ingest.py`:

```python
from app.database import chunk_text, encode

def test_chunk_basic():
    text = " ".join([f"kata{i}" for i in range(500)])
    chunks = chunk_text(text, size=400, overlap=80)
    assert len(chunks) >= 2           # harus lebih dari 1 chunk
    assert len(chunks[0].split()) == 400

def test_embed_dim():
    vec = encode("Halo, apa kabar?")
    assert len(vec) == 384            # dimensi all-MiniLM-L6-v2
```

Jalankan:

```cmd
pytest tests/ -v
```

> ✅ **Checkpoint**: Semua test hijau + server jalan di port 8000 + `/health` mengembalikan `documents_count >= 8` → Sesi 1 selesai!
