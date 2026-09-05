"""
Sesi 3 — Knowledge Agent dengan ReAct Prompting (Port 8002)
============================================================
FastAPI yang membungkus ReAct loop + tools + llama-server.

Knowledge base (DuckDB) dikelola lokal — tidak perlu Sesi 2 jalan
secara terpisah. Data seed FAQ & SOP diambil langsung dari database.py.

Cara run:
    cd Sesi_3_Knowledge_Agent_ReAct
    pip install -r requirements.txt
    uvicorn app.main:app --port 8002 --reload
"""
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm import lifespan as llm_lifespan, state
from app.schemas import ReActRequest, ReActResponse
from app.react import react_loop
from app.database import store
from app.schemas import DocIn, DocOut, DocSearchResult


# ---------------------------------------------------------------------------
# Lifespan: seed knowledge base + start llama-server
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Seed knowledge base dari Sesi 2 jika masih kosong
    seeded = store.seed_if_empty()
    if seeded > 0:
        print(f"[S3] Seed otomatis: {seeded} chunks knowledge dimasukkan ke DuckDB lokal")
    print(f"[S3] DuckDB siap: {settings.duckdb_path} | Total dokumen: {store.count()}")

    # 2. Start llama-server (delegasi ke llm.py lifespan)
    async with llm_lifespan(app):
        yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Sesi 3 — Knowledge Agent ReAct",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    process = state.get("process")
    alive = process is not None and process.poll() is None
    return {
        "app": "ok",
        "llama_server_alive": alive,
        "llama_server_ready": state.get("ready", False),
        "knowledge_source": "local_duckdb" if settings.use_local_db else settings.knowledge_api_base,
        "documents_count": store.count(),
        "duckdb_path": settings.duckdb_path,
    }


# ---------------------------------------------------------------------------
# ReAct agent endpoint
# ---------------------------------------------------------------------------
@app.post("/agent/chat", response_model=ReActResponse)
async def chat(req: ReActRequest):
    answer, steps = await react_loop(
        query=req.query,
        max_steps=req.max_steps,
        temperature=req.temperature,
    )
    return ReActResponse(
        query=req.query,
        final_answer=answer,
        steps=steps,
        total_steps=len(steps),
        domain="knowledge",
    )


# ---------------------------------------------------------------------------
# Knowledge CRUD endpoints (kompatibel dengan Sesi 2 — port 8001)
# Memungkinkan Sesi 4+ memanggil Sesi 3 sebagai pengganti Sesi 2.
# ---------------------------------------------------------------------------
@app.get("/documents/search", response_model=List[DocSearchResult])
def search_documents(q: str, k: int = 5):
    rows = store.search(q, k)
    return [{"id": r[0], "source": r[1], "content": r[2], "score": r[3]} for r in rows]


@app.get("/documents", response_model=List[DocOut])
def list_documents(limit: int = 20, offset: int = 0):
    rows = store.list(limit, offset)
    return [{"id": r[0], "source": r[1], "content": r[2]} for r in rows]


@app.post("/documents", response_model=DocOut)
def create_document(doc: DocIn):
    doc_id = store.insert(doc.source, doc.content)
    return {**doc.model_dump(), "id": doc_id}


@app.get("/documents/{doc_id}", response_model=DocOut)
def get_document(doc_id: str):
    row = store.get(doc_id)
    if not row:
        raise HTTPException(404, "Document not found")
    return {"id": row[0], "source": row[1], "content": row[2]}


@app.put("/documents/{doc_id}", response_model=DocOut)
def update_document(doc_id: str, doc: DocIn):
    if not store.get(doc_id):
        raise HTTPException(404, "Document not found")
    store.update(doc_id, doc.source, doc.content)
    return {**doc.model_dump(), "id": doc_id}


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    if not store.get(doc_id):
        raise HTTPException(404, "Document not found")
    store.delete(doc_id)
    return {"status": "deleted", "id": doc_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
