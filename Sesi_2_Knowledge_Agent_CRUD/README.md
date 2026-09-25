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

| Method | Path                     | Deskripsi                                            |
| ------ | ------------------------ | ---------------------------------------------------- |
| GET    | `/health`                | Status service: jumlah dokumen, embed model, path DB |
| GET    | `/stats`                 | Total dokumen + jumlah per source                    |
| POST   | `/documents`             | Insert satu dokumen (auto-embed)                     |
| GET    | `/documents`             | List dokumen (`?limit=&offset=`)                     |
| GET    | `/documents/search`      | Semantic search (`?q=&k=`)                           |
| GET    | `/documents/{id}`        | Get by ID                                            |
| PUT    | `/documents/{id}`        | Update (re-embed otomatis)                           |
| DELETE | `/documents/{id}`        | Hapus by ID                                          |
| POST   | `/documents/bulk`        | Insert banyak dokumen sekaligus                      |
| POST   | `/documents/upload-pdf`  | Upload file PDF → extract → chunk → embed            |
| POST   | `/documents/ingest-text` | Teks panjang → chunking kustom → simpan multi-row    |

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

---

## 🛠️ Hands-On: Cara Membuat Proyek Ini dari Nol

### Langkah 1 — Setup Folder & Environment

```cmd
mkdir Sesi_2_Knowledge_Agent_CRUD
cd Sesi_2_Knowledge_Agent_CRUD
mkdir app tests
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Isi `requirements.txt` sama dengan Sesi 1 (tambahkan `python-multipart`).

### Langkah 2 — Buat `.env`

```env
VECTOR_BACKEND=duckdb
EMBED_MODEL=all-MiniLM-L6-v2
EMBED_DIM=384
DUCKDB_PATH=./knowledge.duckdb
APP_PORT=8001
```

### Langkah 3 — Buat `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    vector_backend: str = "duckdb"
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    duckdb_path: str = "./knowledge.duckdb"
    app_port: int = 8001

    class Config:
        env_file = ".env"

settings = Settings()
```

### Langkah 4 — Buat `app/embeddings.py`

Wrapper tipis di atas SentenceTransformer agar mudah diganti model lain:

```python
from sentence_transformers import SentenceTransformer
from .config import settings

_model = SentenceTransformer(settings.embed_model)

def encode(text: str) -> list[float]:
    return _model.encode(text).tolist()
```

### Langkah 5 — Buat `app/database.py`

`DocStore` adalah class utama yang membungkus semua operasi DuckDB:

```python
import duckdb, uuid
from .config import settings
from .embeddings import encode

SEED_DATA = [
    {"source": "FAQ_Garansi",  "content": "Garansi resmi 1 tahun untuk kerusakan pabrik..."},
    {"source": "FAQ_Refund",   "content": "Ajukan refund max 30 hari setelah terima barang..."},
    # + 6 data lain
]

class DocStore:
    def __init__(self):
        self.path = settings.duckdb_path
        self._init()

    def _conn(self):
        c = duckdb.connect(self.path)
        c.execute("INSTALL vss; LOAD vss;")
        return c

    def _init(self):
        c = self._conn()
        c.execute("""
            CREATE TABLE IF NOT EXISTS documents(
                id VARCHAR PRIMARY KEY,
                source VARCHAR,
                content TEXT,
                embedding FLOAT[384],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS hnsw_idx ON documents
            USING HNSW(embedding) WITH (metric='cosine')
        """)
        c.close()

    def seed(self):
        if self.count() == 0:
            for d in SEED_DATA:
                self.create(d["source"], d["content"])

    def count(self) -> int:
        c = self._conn()
        n = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        c.close(); return n

    def create(self, source: str, content: str) -> str:
        doc_id = str(uuid.uuid4())
        c = self._conn()
        c.execute("INSERT INTO documents VALUES(?,?,?,?)",
                  [doc_id, source, content, encode(content)])
        c.close()
        return doc_id

    def get(self, doc_id: str):
        c = self._conn()
        r = c.execute("SELECT * FROM documents WHERE id=?", [doc_id]).fetchone()
        c.close()
        return r

    def update(self, doc_id: str, source: str, content: str):
        c = self._conn()
        c.execute("UPDATE documents SET source=?,content=?,embedding=? WHERE id=?",
                  [source, content, encode(content), doc_id])
        c.close()

    def delete(self, doc_id: str):
        c = self._conn()
        c.execute("DELETE FROM documents WHERE id=?", [doc_id])
        c.close()

    def list(self, limit=20, offset=0):
        c = self._conn()
        rows = c.execute(
            "SELECT id,source,content,created_at FROM documents LIMIT ? OFFSET ?",
            [limit, offset]
        ).fetchall()
        c.close()
        return rows

    def search(self, query: str, k: int = 3):
        emb = encode(query)
        c = self._conn()
        rows = c.execute("""
            SELECT id, source, content,
                   array_distance(embedding, ?::FLOAT[384]) AS score
            FROM documents ORDER BY score ASC LIMIT ?
        """, [emb, k]).fetchall()
        c.close()
        return rows

    def bulk_create(self, items: list) -> int:
        for item in items:
            self.create(item["source"], item["content"])
        return len(items)

    def chunk_and_insert(self, source: str, content: str,
                         chunk_size=400, overlap=80) -> int:
        words = content.split()
        chunks, i = [], 0
        while i < len(words):
            chunk = " ".join(words[i:i+chunk_size])
            self.create(source, chunk)
            chunks.append(chunk)
            i += chunk_size - overlap
        return len(chunks)
```

### Langkah 6 — Buat `app/pdf_ingest.py`

```python
import io
from pypdf import PdfReader

def extract_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
```

### Langkah 7 — Buat `app/schemas.py`

```python
from pydantic import BaseModel
from typing import Optional

class DocIn(BaseModel):
    source: str
    content: str

class DocOut(BaseModel):
    id: str
    source: str
    content: str

class DocSearchResult(DocOut):
    score: float

class BulkDocIn(BaseModel):
    documents: list[DocIn]

class IngestTextIn(BaseModel):
    source: str
    content: str
    chunk_size: Optional[int] = 400
    chunk_overlap: Optional[int] = 80
```

### Langkah 8 — Buat `app/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .database import DocStore
from .pdf_ingest import extract_pdf
from .schemas import DocIn, BulkDocIn, IngestTextIn

store = DocStore()

@asynccontextmanager
async def lifespan(app: FastAPI):
    store.seed()   # seed 8 contoh bila kosong
    yield

app = FastAPI(title="Sesi 2 — Knowledge CRUD API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok", "total_documents": store.count()}

@app.get("/stats")
def stats():
    return {"total_documents": store.count()}

@app.post("/documents")
def create(doc: DocIn):
    doc_id = store.create(doc.source, doc.content)
    return {"id": doc_id, "message": "Dokumen berhasil disimpan"}

@app.get("/documents")
def list_docs(limit: int = 20, offset: int = 0):
    rows = store.list(limit, offset)
    return [{"id": r[0], "source": r[1], "content": r[2]} for r in rows]

@app.get("/documents/search")
def search(q: str = Query(...), k: int = 3):
    rows = store.search(q, k)
    return [{"id": r[0], "source": r[1], "content": r[2], "score": r[3]}
            for r in rows]

@app.get("/documents/{doc_id}")
def get_doc(doc_id: str):
    r = store.get(doc_id)
    if not r:
        raise HTTPException(404, "Dokumen tidak ditemukan")
    return {"id": r[0], "source": r[1], "content": r[2]}

@app.put("/documents/{doc_id}")
def update_doc(doc_id: str, doc: DocIn):
    store.update(doc_id, doc.source, doc.content)
    return {"message": "Diperbarui"}

@app.delete("/documents/{doc_id}")
def delete_doc(doc_id: str):
    store.delete(doc_id)
    return {"message": "Dihapus"}

@app.post("/documents/bulk")
def bulk_insert(payload: BulkDocIn):
    n = store.bulk_create([d.dict() for d in payload.documents])
    return {"inserted": n}

@app.post("/documents/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    raw = await file.read()
    text = extract_pdf(raw)
    if not text.strip():
        raise HTTPException(400, "PDF kosong atau tidak bisa dibaca")
    n = store.chunk_and_insert(file.filename, text)
    return {"filename": file.filename, "chunks": n}

@app.post("/documents/ingest-text")
def ingest_text(req: IngestTextIn):
    n = store.chunk_and_insert(req.source, req.content,
                                req.chunk_size, req.chunk_overlap)
    return {"chunks_created": n}
```

### Langkah 9 — Jalankan & Uji

```cmd
uvicorn app.main:app --port 8001 --reload
```

**Buka:** http://localhost:8001/docs

**Uji step-by-step via Swagger:**

1. **`GET /health`** → pastikan `total_documents >= 8`
2. **`POST /documents`** → insert dokumen baru:
   ```json
   { "source": "Tutorial_DuckDB", "content": "DuckDB adalah database analitik embedded yang sangat cepat." }
   ```
3. **`GET /documents/search?q=database+embedded&k=3`** → pastikan dokumen tutorial muncul
4. Salin `id` dari step 2
5. **`GET /documents/{id}`** → ambil dokumen spesifik
6. **`PUT /documents/{id}`** → update konten dokumen
7. **`POST /documents/ingest-text`** → masukkan teks panjang dengan chunking:
   ```json
   {
     "source": "Artikel_Panjang",
     "content": "Lorem ipsum... (teks panjang 1000+ kata)",
     "chunk_size": 200,
     "chunk_overlap": 40
   }
   ```
8. **`GET /stats`** → lihat total dokumen bertambah
9. **`DELETE /documents/{id}`** → hapus dokumen tadi

### Langkah 10 — Unit Test

Buat `tests/test_documents.py`:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["total_documents"] >= 8

def test_crud():
    # Create
    r = client.post("/documents", json={"source":"Test","content":"Halo dunia"})
    assert r.status_code == 200
    doc_id = r.json()["id"]

    # Get
    r = client.get(f"/documents/{doc_id}")
    assert r.json()["content"] == "Halo dunia"

    # Update
    client.put(f"/documents/{doc_id}",
               json={"source":"Test","content":"Konten baru"})
    r = client.get(f"/documents/{doc_id}")
    assert r.json()["content"] == "Konten baru"

    # Delete
    client.delete(f"/documents/{doc_id}")
    r = client.get(f"/documents/{doc_id}")
    assert r.status_code == 404

def test_search():
    r = client.get("/documents/search?q=garansi&k=2")
    assert r.status_code == 200
    assert len(r.json()) <= 2
```

```cmd
pytest tests/ -v
```

> ✅ **Checkpoint**: Server jalan di port 8001, CRUD berjalan, dan `GET /documents/search` mengembalikan hasil semantik yang relevan → Sesi 2 selesai dan siap jadi tool untuk Sesi 3 & 4!
