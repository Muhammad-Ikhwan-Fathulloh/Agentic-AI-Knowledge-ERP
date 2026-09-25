from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from app.config import settings
from app.schemas import DocIn, DocOut, DocSearchResult
from app.database import store, chunk_text
from app.pdf_ingest import extract_chunks_from_pdf


@asynccontextmanager
async def lifespan(app: FastAPI):
    seeded = store.seed_if_empty()
    if seeded > 0:
        print(f"[S2] Seed otomatis: {seeded} chunks FAQ + SOP dimasukkan ke knowledge.duckdb")
    print(f"[S2] DuckDB siap: {settings.duckdb_path} | Total dokumen: {store.count()}")
    yield


app = FastAPI(
    title="Sesi 2 - Knowledge Agent CRUD REST API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "app": "ok",
        "vector_backend": settings.vector_backend,
        "duckdb_path": settings.duckdb_path,
        "documents_count": store.count(),
        "embed_model": settings.embed_model,
        "embed_dim": settings.embed_dim,
    }


@app.get("/stats")
async def stats():
    rows = store.list(limit=1000)
    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r[1]] = by_source.get(r[1], 0) + 1
    return {
        "total_documents": store.count(),
        "documents_by_source": by_source,
    }


@app.post("/documents", response_model=DocOut)
def create_document(doc: DocIn):
    doc_id = store.insert(doc.source, doc.content)
    return {**doc.model_dump(), "id": doc_id}


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
    existing = store.get(doc_id)
    if not existing:
        raise HTTPException(404, "Document not found")
    store.update(doc_id, doc.source, doc.content)
    return {**doc.model_dump(), "id": doc_id}


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    existing = store.get(doc_id)
    if not existing:
        raise HTTPException(404, "Document not found")
    store.delete(doc_id)
    return {"status": "deleted", "id": doc_id}


@app.post("/documents/bulk")
def bulk_create(docs: List[DocIn]):
    ids = []
    for doc in docs:
        ids.append(store.insert(doc.source, doc.content))
    return {"inserted": len(ids), "ids": ids}


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
        if chunk.strip():
            doc_id = store.insert(source=f"{file.filename}#chunk{i}", content=chunk)
            inserted_ids.append(doc_id)

    return {
        "filename": file.filename,
        "chunks_inserted": len(inserted_ids),
        "ids": inserted_ids,
    }


@app.post("/documents/ingest-text")
async def ingest_text_chunked(doc: DocIn, chunk_size: int = 400, chunk_overlap: int = 80):
    chunks = chunk_text(doc.content, size=chunk_size, overlap=chunk_overlap)
    if not chunks:
        raise HTTPException(400, "tidak ada chunk yang bisa disimpan")
    ids = store.insert_chunks(doc.source, chunks)
    return {
        "source": doc.source,
        "total_chunks": len(chunks),
        "total_words": sum(len(c.split()) for c in chunks),
        "document_ids": ids,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)