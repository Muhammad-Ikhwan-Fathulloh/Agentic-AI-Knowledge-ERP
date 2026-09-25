# Setup Lokal - Knowledge Agent: CRUD REST API (FastAPI + Uvicorn + DuckDB + pgvector)

**Referensi:** `Sesi_2_Knowledge_Agent_CRUD_API.ipynb`
**Bedanya dengan versi Colab:** notebook ini jalan di memori (`TestClient`), versi ini jalan sebagai **server sungguhan** di mesin lokal (`uvicorn`), dan menambahkan opsi backend vector store kedua - **PostgreSQL + pgvector** - di samping DuckDB.

## Tentang Panduan Ini
Sesi 1–2 (versi Colab) membangun API di dalam satu notebook. Di lokal, kita pecah jadi beberapa file (`main.py`, `database.py`, `schemas.py`) supaya bisa dijalankan sebagai service beneran dengan `uvicorn`, dan bisa dipanggil dari luar (termasuk oleh agent di Sesi 3–4) tanpa Colab/ngrok.

Backend penyimpanan dibuat **pluggable** lewat satu env var (`VECTOR_BACKEND`), jadi kode endpoint CRUD tidak berubah walau kamu ganti dari DuckDB ke pgvector.

## Prasyarat
- Python 3.10+ terpasang lokal.
- (Opsional, kalau mau pakai pgvector) Docker & Docker Compose, atau PostgreSQL 14+ yang sudah bisa install extension.
- Familiar dengan isi `Sesi_2_Knowledge_Agent_CRUD_API.ipynb` (skema `documents`, endpoint CRUD, `/documents/search`).

## Struktur Project
```
knowledge-agent-api/
├── .env
├── .env.example
├── requirements.txt
├── docker-compose.yml        # hanya untuk backend pgvector
├── app/
│   ├── __init__.py
│   ├── main.py                # entrypoint FastAPI, semua endpoint
│   ├── config.py               # baca .env
│   ├── database.py             # koneksi DuckDB / Postgres+pgvector
│   ├── schemas.py               # Pydantic models
│   ├── embeddings.py           # load sentence-transformers
│   └── pdf_ingest.py            # extract & chunk teks dari PDF
└── tests/
    ├── test_documents.py       # pytest + TestClient
    └── test_pdf_upload.py       # pytest untuk endpoint upload PDF
```

---

## Step 1 - Setup Virtual Environment

```bash
mkdir knowledge-agent-api && cd knowledge-agent-api
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
.venv\Scripts\activate
```

## Step 2 - `requirements.txt`

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
pydantic-settings==2.5.2
python-dotenv==1.0.1
duckdb==1.1.1
sentence-transformers==3.1.1
httpx==0.27.2
pytest==8.3.3
pypdf==5.0.1
python-multipart==0.0.12   # wajib, dipakai FastAPI untuk terima file upload (UploadFile)

# hanya dipakai kalau VECTOR_BACKEND=pgvector
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
pgvector==0.3.5
```

```txt
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

# hanya dipakai kalau VECTOR_BACKEND=pgvector
sqlalchemy
psycopg2-binary
pgvector
```

```bash
pip install -r requirements.txt
```

## Step 3 - Konfigurasi `.env`

```bash
# .env.example
VECTOR_BACKEND=duckdb          # duckdb | pgvector
EMBED_MODEL=all-MiniLM-L6-v2
EMBED_DIM=384

# dipakai hanya jika VECTOR_BACKEND=duckdb
DUCKDB_PATH=knowledge.duckdb

# dipakai hanya jika VECTOR_BACKEND=pgvector (harus konsisten dengan docker-compose.yml)
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=mydatabase
POSTGRES_PORT=5432
PGWEB_PORT=8081
POSTGRES_URL=postgresql+psycopg2://user:password@localhost:5432/mydatabase
```

> `POSTGRES_URL` dipakai oleh `app/database.py` (koneksi dari FastAPI ke Postgres), sedangkan `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`/`POSTGRES_PORT`/`PGWEB_PORT` dipakai oleh `docker-compose.yml` (Step 8). Pastikan kredensialnya sama di kedua tempat - kalau kamu ubah `POSTGRES_PASSWORD` di `.env`, `POSTGRES_URL` juga harus diupdate manual (`pydantic-settings` tidak otomatis merangkai keduanya).

```bash
cp .env.example .env
```

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    vector_backend: str = "duckdb"
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    duckdb_path: str = "knowledge.duckdb"
    postgres_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/knowledge"

    class Config:
        env_file = ".env"

settings = Settings()
```

## Step 4 - Model Embedding (sama seperti Sesi 1/2)

```python
# app/embeddings.py
from sentence_transformers import SentenceTransformer
from app.config import settings

embed_model = SentenceTransformer(settings.embed_model)

def encode(text: str) -> list[float]:
    return embed_model.encode(text).tolist()
```

## Step 5 - Layer Database (pluggable: DuckDB ↔ pgvector)

Ini bagian utama bedanya dari notebook: satu modul `database.py` menyediakan fungsi yang sama (`insert_document`, `get_document`, `list_documents`, `update_document`, `delete_document`, `search_documents`) apapun backend-nya, supaya `main.py` tidak perlu tahu perbedaannya.

### 5a. DuckDB (default, sama seperti Sesi 1–2)

```python
# app/database.py (bagian DuckDB)
import duckdb, uuid
from app.config import settings

def init_duckdb():
    con = duckdb.connect(settings.duckdb_path)
    con.execute("INSTALL vss; LOAD vss;")
    con.execute(f"""
    CREATE TABLE IF NOT EXISTS documents (
        id VARCHAR PRIMARY KEY, source VARCHAR, content TEXT,
        embedding FLOAT[{settings.embed_dim}],
        created_at TIMESTAMP DEFAULT current_timestamp
    );
    """)
    return con
```

### 5b. PostgreSQL + pgvector (backend baru untuk lokal)

pgvector cocok kalau API ini nantinya dipakai lebih dari satu proses/service sekaligus (DuckDB adalah file lokal single-process, sedangkan Postgres bisa diakses banyak client bersamaan - relevan kalau Sesi 3–4 nanti jalan sebagai service terpisah).

```python
# app/database.py (bagian pgvector)
from sqlalchemy import create_engine, text
from app.config import settings

def init_pgvector():
    engine = create_engine(settings.postgres_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source TEXT,
                content TEXT,
                embedding vector({settings.embed_dim}),
                created_at TIMESTAMPTZ DEFAULT now()
            );
        """))
        # index approx-nearest-neighbor, mirip peran vss di DuckDB
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx
            ON documents USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """))
    return engine
```

### 5c. Fungsi CRUD generik (dipanggil endpoint, tidak peduli backend)

```python
# app/database.py (lanjutan)
import uuid
from sqlalchemy import text as sql_text
from app.embeddings import encode
from app.config import settings

class DocStore:
    def __init__(self):
        if settings.vector_backend == "duckdb":
            self.backend = "duckdb"
            self.con = init_duckdb()
        else:
            self.backend = "pgvector"
            self.engine = init_pgvector()

    def insert(self, source: str, content: str) -> str:
        doc_id = str(uuid.uuid4())
        emb = encode(content)
        if self.backend == "duckdb":
            self.con.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, current_timestamp)",
                [doc_id, source, content, emb],
            )
        else:
            with self.engine.begin() as conn:
                conn.execute(sql_text("""
                    INSERT INTO documents (id, source, content, embedding)
                    VALUES (:id, :source, :content, :embedding)
                """), {"id": doc_id, "source": source, "content": content, "embedding": emb})
        return doc_id

    def get(self, doc_id: str):
        if self.backend == "duckdb":
            row = self.con.execute(
                "SELECT id, source, content FROM documents WHERE id=?", [doc_id]
            ).fetchone()
        else:
            with self.engine.begin() as conn:
                row = conn.execute(sql_text(
                    "SELECT id, source, content FROM documents WHERE id=:id"
                ), {"id": doc_id}).fetchone()
        return row

    def list(self, limit: int = 20, offset: int = 0):
        if self.backend == "duckdb":
            return self.con.execute(
                "SELECT id, source, content FROM documents LIMIT ? OFFSET ?",
                [limit, offset],
            ).fetchall()
        with self.engine.begin() as conn:
            return conn.execute(sql_text(
                "SELECT id, source, content FROM documents LIMIT :limit OFFSET :offset"
            ), {"limit": limit, "offset": offset}).fetchall()

    def update(self, doc_id: str, source: str, content: str):
        emb = encode(content)
        if self.backend == "duckdb":
            self.con.execute(
                "UPDATE documents SET content=?, source=?, embedding=? WHERE id=?",
                [content, source, emb, doc_id],
            )
        else:
            with self.engine.begin() as conn:
                conn.execute(sql_text("""
                    UPDATE documents SET content=:content, source=:source, embedding=:embedding
                    WHERE id=:id
                """), {"content": content, "source": source, "embedding": emb, "id": doc_id})

    def delete(self, doc_id: str):
        if self.backend == "duckdb":
            self.con.execute("DELETE FROM documents WHERE id=?", [doc_id])
        else:
            with self.engine.begin() as conn:
                conn.execute(sql_text("DELETE FROM documents WHERE id=:id"), {"id": doc_id})

    def search(self, query: str, k: int = 5):
        q_emb = encode(query)
        if self.backend == "duckdb":
            return self.con.execute(f"""
                SELECT id, source, content, array_distance(embedding, ?::FLOAT[{settings.embed_dim}]) AS dist
                FROM documents ORDER BY dist ASC LIMIT ?
            """, [q_emb, k]).fetchall()
        with self.engine.begin() as conn:
            return conn.execute(sql_text("""
                SELECT id, source, content, embedding <=> :q_emb AS dist
                FROM documents ORDER BY dist ASC LIMIT :k
            """), {"q_emb": q_emb, "k": k}).fetchall()

store = DocStore()
```

> **Catatan:** `array_distance` (DuckDB vss) dan operator `<=>` (pgvector, cosine distance) melakukan hal yang konsep-nya sama seperti `search_documents` di notebook Sesi 2 - cuma sintaksnya beda per backend, makanya dibungkus di `DocStore.search`.

## Step 6 - Pydantic Schemas (sama seperti Sesi 2)

```python
# app/schemas.py
from pydantic import BaseModel
from typing import List

class DocIn(BaseModel):
    source: str
    content: str

class DocOut(DocIn):
    id: str

class DocSearchResult(DocOut):
    score: float
```

## Step 7 - `main.py`: Endpoint CRUD + Search + Bulk

Endpoint dan logikanya identik dengan `Sesi_2_Knowledge_Agent_CRUD_API.ipynb` (termasuk solusi TODO 1 `/documents/bulk`), hanya sumber datanya sekarang lewat `store` (bisa DuckDB atau pgvector).

```python
# app/main.py
from fastapi import FastAPI, HTTPException
from typing import List
from app.schemas import DocIn, DocOut, DocSearchResult
from app.database import store

app = FastAPI(title="Knowledge Agent API")

@app.post("/documents", response_model=DocOut)
def create_document(doc: DocIn):
    doc_id = store.insert(doc.source, doc.content)
    return {**doc.dict(), "id": doc_id}

@app.get("/documents", response_model=List[DocOut])
def list_documents(limit: int = 20, offset: int = 0):
    rows = store.list(limit, offset)
    return [{"id": r[0], "source": r[1], "content": r[2]} for r in rows]

@app.get("/documents/search", response_model=List[DocSearchResult])
def search_documents(q: str, k: int = 5):
    rows = store.search(q, k)
    return [{"id": r[0], "source": r[1], "content": r[2], "score": r[3]} for r in rows]

@app.get("/documents/{doc_id}", response_model=DocOut)
def get_document(doc_id: str):
    row = store.get(doc_id)
    if not row:
        raise HTTPException(404, "Document not found")
    return {"id": row[0], "source": row[1], "content": row[2]}

@app.put("/documents/{doc_id}", response_model=DocOut)
def update_document(doc_id: str, doc: DocIn):
    store.update(doc_id, doc.source, doc.content)
    return {**doc.dict(), "id": doc_id}

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    store.delete(doc_id)
    return {"status": "deleted", "id": doc_id}

@app.post("/documents/bulk")
def bulk_create(docs: List[DocIn]):
    for doc in docs:
        create_document(doc)
    return {"inserted": len(docs)}
```

## Step 8 - Upload PDF sebagai Dokumen

Selain `POST /documents` (teks manual) dan `/documents/bulk` (array JSON), tambahkan endpoint upload file PDF: teks di-extract per halaman, tiap halaman/chunk di-*embed* dan disimpan sebagai baris `documents` sendiri - jadi langsung bisa dicari lewat `/documents/search`.

### 8a. Modul extract & chunk PDF

```python
# app/pdf_ingest.py
from pypdf import PdfReader
import io

def extract_chunks_from_pdf(file_bytes: bytes, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """
    Baca PDF dari bytes, gabungkan semua teks, lalu pecah jadi chunk
    ber-overlap (biar konteks antar-chunk tidak putus, sama seperti
    strategi chunking di Sesi 1).
    """
    reader = PdfReader(io.BytesIO(file_bytes))
    full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    full_text = full_text.strip()

    if not full_text:
        return []

    chunks = []
    start = 0
    while start < len(full_text):
        end = start + chunk_size
        chunks.append(full_text[start:end])
        start = end - overlap  # mundur sedikit supaya overlap
    return chunks
```

### 8b. Endpoint `POST /documents/upload-pdf`

```python
# app/main.py (tambahan)
from fastapi import UploadFile, File
from app.pdf_ingest import extract_chunks_from_pdf

@app.post("/documents/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "File harus berformat PDF")

    file_bytes = await file.read()
    chunks = extract_chunks_from_pdf(file_bytes)

    if not chunks:
        raise HTTPException(422, "Tidak ada teks yang bisa diekstrak dari PDF ini (kemungkinan hasil scan/gambar)")

    inserted_ids = []
    for i, chunk in enumerate(chunks):
        doc_id = store.insert(source=f"{file.filename}#chunk{i}", content=chunk)
        inserted_ids.append(doc_id)

    return {
        "filename": file.filename,
        "chunks_inserted": len(inserted_ids),
        "ids": inserted_ids,
    }
```

> Kalau PDF-nya hasil scan (gambar, bukan teks selectable), `extract_text()` akan balikin string kosong per halaman - di kasus itu perlu OCR (di luar cakupan panduan ini; lihat skill `pdf-reading` kalau butuh OCR).

### 8c. Uji upload PDF lewat curl

```bash
curl -X POST http://localhost:8000/documents/upload-pdf \
  -F "file=@/path/ke/dokumen.pdf"
```

Atau lewat Swagger UI di `http://localhost:8000/docs` - endpoint `/documents/upload-pdf` otomatis muncul dengan tombol pilih file, karena FastAPI generate form upload dari tipe `UploadFile`.

### 8d. (Opsional) Uji dengan pytest

```python
# tests/test_pdf_upload.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_upload_pdf():
    with open("tests/sample.pdf", "rb") as f:
        resp = client.post(
            "/documents/upload-pdf",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 200
    assert resp.json()["chunks_inserted"] > 0
```

## Step 9 - (Opsional) Docker Compose untuk PostgreSQL + pgvector

Kalau `VECTOR_BACKEND=pgvector`, jalankan Postgres lokal via image resmi pgvector (sudah include extension, tinggal `CREATE EXTENSION`). Ditambah `pgweb` sebagai UI ringan buat inspect tabel `documents` dari browser tanpa perlu psql.

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16-trixie
    container_name: pgvector_db
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
      POSTGRES_DB: ${POSTGRES_DB:-mydatabase}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-user} -d ${POSTGRES_DB:-mydatabase}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
  pgweb:
    image: sosedoff/pgweb:latest
    container_name: pgweb_ui
    ports:
      - "${PGWEB_PORT:-8081}:8081"
    environment:
      DATABASE_URL: postgres://${POSTGRES_USER:-user}:${POSTGRES_PASSWORD:-password}@db:5432/${POSTGRES_DB:-mydatabase}?sslmode=disable
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
volumes:
  pgdata:
```

```bash
docker compose up -d
```

Setelah `db` berstatus `healthy`, dua service siap dipakai:

| Service                  | URL / Akses                            | Kegunaan                                       |
| ------------------------ | -------------------------------------- | ---------------------------------------------- |
| `db` (Postgres+pgvector) | `localhost:${POSTGRES_PORT:-5432}`     | dipakai `app/database.py` lewat `POSTGRES_URL` |
| `pgweb`                  | `http://localhost:${PGWEB_PORT:-8081}` | UI browser untuk lihat/query tabel `documents` |

> Karena `pgweb` punya `depends_on: db: condition: service_healthy`, dia otomatis menunggu Postgres benar-benar siap (`pg_isready`) sebelum jalan - tidak perlu retry manual.

## Step 10 - Menjalankan Server dengan Uvicorn

```bash
# backend DuckDB (default, tidak perlu Docker)
uvicorn app.main:app --reload --port 8000

# atau, kalau pakai pgvector: pastikan docker compose sudah up,
# lalu set VECTOR_BACKEND=pgvector di .env sebelum menjalankan
uvicorn app.main:app --reload --port 8000
```

Server jalan di `http://localhost:8000`, dokumentasi otomatis (Swagger UI) tersedia di `http://localhost:8000/docs`.

## Step 11 - Uji API dari Terminal

```bash
# create
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"source": "manual.txt", "content": "Jam operasional toko 09.00-21.00 setiap hari."}'

# search
curl "http://localhost:8000/documents/search?q=jam%20buka%20toko&k=3"

# bulk
curl -X POST http://localhost:8000/documents/bulk \
  -H "Content-Type: application/json" \
  -d '[{"source":"a.txt","content":"Isi A"},{"source":"b.txt","content":"Isi B"}]'
```

## Step 12 - Uji Otomatis dengan `pytest` (pengganti `TestClient` manual di Colab)

```python
# tests/test_documents.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_and_search():
    resp = client.post("/documents", json={"source": "test.txt", "content": "Kebijakan cuti karyawan"})
    assert resp.status_code == 200
    assert "id" in resp.json()

    resp = client.get("/documents/search", params={"q": "cuti karyawan", "k": 3})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
```

```bash
pytest tests/ -v
```

---

## Perbandingan Backend: DuckDB vs pgvector

| Aspek            | DuckDB + vss                                | PostgreSQL + pgvector                                                         |
| ---------------- | ------------------------------------------- | ----------------------------------------------------------------------------- |
| Setup            | Zero-setup, file lokal                      | Perlu server Postgres (Docker/manual)                                         |
| Concurrency      | Cocok single-process                        | Cocok multi-client / multi-service                                            |
| Cocok untuk      | Development, notebook, prototipe (Sesi 1–2) | Deployment nyata, dipanggil banyak service (Sesi 3–4 sebagai server terpisah) |
| Index similarity | `array_distance` + extension `vss`          | Operator `<=>` + index `ivfflat`/`hnsw`                                       |
| Portabilitas     | Satu file `.duckdb`, gampang dipindah       | Butuh dump/restore Postgres                                                   |

## Ringkasan
- Struktur project dipecah dari satu notebook jadi `app/` modular: `config.py`, `embeddings.py`, `database.py`, `schemas.py`, `pdf_ingest.py`, `main.py`.
- Layer `DocStore` membuat endpoint CRUD **backend-agnostic** - tinggal ganti `VECTOR_BACKEND` di `.env` untuk pindah dari DuckDB ke pgvector tanpa ubah `main.py`.
- Endpoint dan perilaku (termasuk solusi TODO 1 `/documents/bulk`) tetap identik dengan `Sesi_2_Knowledge_Agent_CRUD_API.ipynb`, jadi tetap bisa dipakai sebagai referensi pola *tool* untuk agent ReAct di Sesi 3–4 - kali ini lewat `http://localhost:8000` sungguhan, bukan `TestClient` di memori Colab.
- Sumber dokumen sekarang ada tiga jalur: teks manual (`POST /documents`), array JSON (`POST /documents/bulk`), dan file PDF (`POST /documents/upload-pdf`) - ketiganya berakhir lewat fungsi `store.insert()` yang sama, jadi tetap konsisten di-embed dan bisa langsung dicari lewat `/documents/search`.
