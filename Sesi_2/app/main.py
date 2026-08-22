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