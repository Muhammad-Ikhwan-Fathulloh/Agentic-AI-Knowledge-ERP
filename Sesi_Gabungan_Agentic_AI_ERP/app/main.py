"""
Agentic AI ERP v2.0 — DUA KNOWLEDGE BASE (SOP + ERP) + Agentic Routing
======================================================================
Arsitektur Agentic:
  USER QUERY
    └─> STEP 1 : Cari SOP KB dahulu (pahami prosedur)
    └─> STEP 2 : LLM/Router baca SOP → putuskan ACTION ERP
    └─> STEP 3 : Jalankan action ERP (lookup produk, cek stok, dll)
    └─> STEP 4 : Gabung SOP + data ERP → LLM jawaban FINAL

Modul lengkap:
  1a. KB SOP        : Ingest + Search SOP, prosedur, aturan bisnis
  1b. KB ERP Docs   : Ingest + Search spesifikasi produk, katalog, supplier
  2.  ERP System    : CRUD Products, Customers, Orders + Reports
  3.  AI Generator  : Narrative Sales / Low-Stock + Agentic SOP→ERP QA

Port default: 8080
"""
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.llm import lifespan_llm, state
from app.ingest import extract_text_from_file
from app.database import (
    init_db, close_db,
    chunk_text,
    sop_insert_chunks, sop_search, sop_count, sop_list_all, sop_delete_all,
    erpdoc_insert_chunks, erpdoc_search, erpdoc_count, erpdoc_list_all, erpdoc_delete_all,
    k_insert_chunks, k_search, k_count, k_list_all, k_delete_all,
    p_insert, p_list, p_get, p_update, p_delete, p_count,
    c_insert, c_list, c_get, c_count,
    o_create, o_get, o_list, o_set_status, o_count,
    report_sales, report_low_stock,
)
from app.schemas import (
    IngestTextRequest, SearchRequest, ChunkInfoResponse, SearchResult,
    ProductIn, ProductOut, CustomerIn, CustomerOut, OrderIn,
    SalesReportRequest, LowStockReportRequest, GeneratedReport,
    AgenticResponse,
)
from app.generators import (
    generate_sales_report, generate_low_stock_report, answer_with_knowledge,
    agentic_sop_erp_qa,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(f"[AgenticAI-ERP v2] DuckDB siap: {settings.duckdb_path}")
    print(f"[AgenticAI-ERP v2]   SOP KB chunks      : {sop_count()}")
    print(f"[AgenticAI-ERP v2]   ERP Docs KB chunks : {erpdoc_count()}")
    print(f"[AgenticAI-ERP v2]   Products           : {p_count()}")
    print(f"[AgenticAI-ERP v2]   Customers          : {c_count()}")
    print(f"[AgenticAI-ERP v2]   Orders             : {o_count()}")
    async with lifespan_llm(app):
        yield
    close_db()
    print("[AgenticAI-ERP v2] DuckDB ditutup.")


app = FastAPI(
    title="Agentic AI ERP v2 — Dual Knowledge Base + SOP→ERP Agentic Router",
    version="2.0.0",
    description=(
        "Dual Knowledge Base (SOP + ERP Docs) dengan Agentic Router: "
        "LLM membaca SOP terlebih dahulu, memutuskan action ERP yang tepat, "
        "menjalankan query, lalu menyusun jawaban final. "
        "Gabungan Sesi 1 (Knowledge Vector DB) + Sesi 7 (ERP + LLM Generate)."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
_INDEX_HTML = os.path.join(_FRONTEND_DIR, "index.html")

if os.path.isdir(_FRONTEND_DIR):
    app.mount("/static-frontend", StaticFiles(directory=_FRONTEND_DIR), name="frontend_static")


@app.get("/frontend", tags=["System"])
@app.get("/ui", tags=["System"])
@app.get("/dashboard", tags=["System"])
async def frontend_index():
    """
    Halaman frontend HTML (Bootstrap 5 + Vanilla JS) untuk Agentic AI ERP v2.
    Alternatif: /ui atau /dashboard.
    Jika file tidak ditemukan → buka langsung `frontend/index.html` di browser.
    """
    if not os.path.isfile(_INDEX_HTML):
        raise HTTPException(404, "frontend/index.html tidak ditemukan. Buka file secara langsung di browser.")
    return FileResponse(_INDEX_HTML, media_type="text/html")


# ======================================================================
# 1. GLOBAL HEALTH & STATS
# ======================================================================
@app.get("/health", tags=["System"])
async def health():
    p = state.get("process")
    return {
        "app": "ok",
        "version": "2.0.0 (Dual KB + Agentic SOP→ERP)",
        "duckdb": settings.duckdb_path,
        "app_port": settings.app_port,
        "embed_model": settings.embed_model,
        "embed_dim": settings.embed_dim,
        "counts": {
            "kb_sop_chunks": sop_count(),
            "kb_erp_docs_chunks": erpdoc_count(),
            "products": p_count(),
            "customers": c_count(),
            "orders": o_count(),
        },
        "llm": {
            "llama_alive": p is not None and p.poll() is None,
            "llama_ready": state.get("ready", False),
            "base_url": settings.llama_base_url,
        },
    }


@app.get("/stats", tags=["System"])
async def stats():
    sop_rows = sop_list_all(limit=500)
    erpdoc_rows = erpdoc_list_all(limit=500)
    by_source_sop: dict[str, int] = {}
    for r in sop_rows:
        by_source_sop[r[1]] = by_source_sop.get(r[1], 0) + 1
    by_source_erp: dict[str, int] = {}
    for r in erpdoc_rows:
        by_source_erp[r[1]] = by_source_erp.get(r[1], 0) + 1

    all_products = p_list()
    total_stock_value = sum(p[2] * p[3] for p in all_products)

    return {
        "knowledge_bases": {
            "kb_sop": {
                "total_chunks": sop_count(),
                "description": "Standar Operasional Prosedur (SOP), aturan bisnis, FAQ prosedural",
                "chunking": {"size": settings.chunk_size, "overlap": settings.chunk_overlap},
                "chunks_by_source": by_source_sop,
            },
            "kb_erp_docs": {
                "total_chunks": erpdoc_count(),
                "description": "Spesifikasi produk, katalog, supplier info, master data pendukung ERP",
                "chunking": {"size": settings.chunk_size, "overlap": settings.chunk_overlap},
                "chunks_by_source": by_source_erp,
            },
        },
        "erp": {
            "products_total": len(all_products),
            "customers_total": c_count(),
            "orders_total": o_count(),
            "total_stock_value_idr": total_stock_value,
        },
        "agentic_router": {
            "supported_actions": [
                "lookup_product (cari produk by keyword)",
                "check_low_stock (stok <= threshold)",
                "check_sales_report (laporan penjualan N hari)",
                "lookup_customer (data customer)",
                "lookup_order (detail order by id)",
                "lookup_erp_knowledge (cari KB ERP docs)",
                "no_erp_needed (jawab dari SOP saja)",
            ],
        },
        "generator_defaults": {
            "report_days": settings.default_report_days,
            "low_stock_threshold": settings.low_stock_threshold,
        },
    }


# ======================================================================
# 2a. KNOWLEDGE BASE #1 : SOP (Standar Operasional Prosedur)
# ======================================================================
@app.post("/sop/ingest/text", response_model=ChunkInfoResponse, tags=["KB #1 — SOP"])
async def sop_ingest_text(req: IngestTextRequest):
    """Ingest dokumen SOP, prosedur, FAQ prosedural ke KB #1."""
    if not req.content.strip():
        raise HTTPException(400, "content kosong")
    chunks = chunk_text(
        req.content,
        size=req.chunk_size or settings.chunk_size,
        overlap=req.chunk_overlap or settings.chunk_overlap,
    )
    if not chunks:
        raise HTTPException(400, "tidak ada chunk yang bisa disimpan")
    ids = sop_insert_chunks(req.source, chunks)
    return ChunkInfoResponse(
        source=req.source,
        total_chunks=len(chunks),
        total_words=sum(len(c.split()) for c in chunks),
        document_ids=ids,
    )


@app.post("/sop/ingest/file", response_model=ChunkInfoResponse, tags=["KB #1 — SOP"])
async def sop_ingest_file(file: UploadFile = File(...)):
    """Upload file SOP (PDF/TXT/MD) ke KB #1."""
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(400, "file kosong")
    source, text = extract_text_from_file(raw, file.filename or "sop_unknown")
    if not text:
        raise HTTPException(400, "tidak bisa ekstrak teks (PDF scan/image tidak didukung)")
    chunks = chunk_text(text)
    ids = sop_insert_chunks(source, chunks)
    return ChunkInfoResponse(
        source=source,
        total_chunks=len(chunks),
        total_words=sum(len(c.split()) for c in chunks),
        document_ids=ids,
    )


@app.post("/sop/search", response_model=list[SearchResult], tags=["KB #1 — SOP"])
async def sop_search_endpoint(req: SearchRequest):
    """Semantic search HANYA di KB SOP (prosedur & aturan)."""
    rows = sop_search(req.q, req.k)
    return [
        {"id": r[0], "source": r[1], "content": r[2], "score": r[3]}
        for r in rows
    ]


@app.get("/sop/documents", tags=["KB #1 — SOP"])
async def sop_list_documents(limit: int = 100):
    """Lihat semua dokumen di KB SOP."""
    rows = sop_list_all(limit)
    return [
        {"id": r[0], "source": r[1], "content": r[2]}
        for r in rows
    ]


@app.delete("/sop/documents", tags=["KB #1 — SOP"])
async def sop_reset_documents():
    deleted = sop_delete_all()
    return {"status": "sop_reset_done", "deleted_chunks": deleted}


# ======================================================================
# 2b. KNOWLEDGE BASE #2 : ERP DOCS (Spesifikasi, supplier, master data)
# ======================================================================
@app.post("/erp-docs/ingest/text", response_model=ChunkInfoResponse, tags=["KB #2 — ERP Docs"])
async def erpdoc_ingest_text(req: IngestTextRequest):
    """Ingest dokumen ERP (spesifikasi produk, supplier info, dsb) ke KB #2."""
    if not req.content.strip():
        raise HTTPException(400, "content kosong")
    chunks = chunk_text(
        req.content,
        size=req.chunk_size or settings.chunk_size,
        overlap=req.chunk_overlap or settings.chunk_overlap,
    )
    if not chunks:
        raise HTTPException(400, "tidak ada chunk yang bisa disimpan")
    ids = erpdoc_insert_chunks(req.source, chunks)
    return ChunkInfoResponse(
        source=req.source,
        total_chunks=len(chunks),
        total_words=sum(len(c.split()) for c in chunks),
        document_ids=ids,
    )


@app.post("/erp-docs/ingest/file", response_model=ChunkInfoResponse, tags=["KB #2 — ERP Docs"])
async def erpdoc_ingest_file(file: UploadFile = File(...)):
    """Upload file ERP Docs ke KB #2."""
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(400, "file kosong")
    source, text = extract_text_from_file(raw, file.filename or "erp_unknown")
    if not text:
        raise HTTPException(400, "tidak bisa ekstrak teks")
    chunks = chunk_text(text)
    ids = erpdoc_insert_chunks(source, chunks)
    return ChunkInfoResponse(
        source=source,
        total_chunks=len(chunks),
        total_words=sum(len(c.split()) for c in chunks),
        document_ids=ids,
    )


@app.post("/erp-docs/search", response_model=list[SearchResult], tags=["KB #2 — ERP Docs"])
async def erpdoc_search_endpoint(req: SearchRequest):
    """Semantic search HANYA di KB ERP Docs (spesifikasi produk, supplier, dll)."""
    rows = erpdoc_search(req.q, req.k)
    return [
        {"id": r[0], "source": r[1], "content": r[2], "score": r[3]}
        for r in rows
    ]


@app.get("/erp-docs/documents", tags=["KB #2 — ERP Docs"])
async def erpdoc_list_documents(limit: int = 100):
    rows = erpdoc_list_all(limit)
    return [
        {"id": r[0], "source": r[1], "content": r[2]}
        for r in rows
    ]


@app.delete("/erp-docs/documents", tags=["KB #2 — ERP Docs"])
async def erpdoc_reset_documents():
    deleted = erpdoc_delete_all()
    return {"status": "erp_docs_reset_done", "deleted_chunks": deleted}


# ======================================================================
# 2c. LEGACY / MERGED Knowledge Endpoints (backward compat)
# ======================================================================
@app.post("/ingest/text", response_model=ChunkInfoResponse, tags=["Knowledge (Legacy — Merge)"])
async def ingest_text(req: IngestTextRequest):
    if not req.content.strip():
        raise HTTPException(400, "content kosong")
    chunks = chunk_text(
        req.content,
        size=req.chunk_size or settings.chunk_size,
        overlap=req.chunk_overlap or settings.chunk_overlap,
    )
    if not chunks:
        raise HTTPException(400, "tidak ada chunk yang bisa disimpan")
    ids = k_insert_chunks(req.source, chunks)
    return ChunkInfoResponse(
        source=req.source,
        total_chunks=len(chunks),
        total_words=sum(len(c.split()) for c in chunks),
        document_ids=ids,
    )


@app.post("/ingest/file", response_model=ChunkInfoResponse, tags=["Knowledge (Legacy — Merge)"])
async def ingest_file(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(400, "file kosong")
    source, text = extract_text_from_file(raw, file.filename or "unknown")
    if not text:
        raise HTTPException(400, "tidak bisa ekstrak teks (PDF scan tidak didukung)")
    chunks = chunk_text(text)
    ids = k_insert_chunks(source, chunks)
    return ChunkInfoResponse(
        source=source,
        total_chunks=len(chunks),
        total_words=sum(len(c.split()) for c in chunks),
        document_ids=ids,
    )


@app.post("/search", response_model=list[SearchResult], tags=["Knowledge (Legacy — Merge)"])
async def search(req: SearchRequest):
    """Merge search: SOP + ERP Docs sekaligus, diurutkan by score."""
    rows = k_search(req.q, req.k)
    return [
        {"id": r[0], "source": r[1], "content": r[2], "score": r[3]}
        for r in rows
    ]


@app.get("/documents", tags=["Knowledge (Legacy — Merge)"])
async def list_documents(limit: int = 100):
    rows = k_list_all(limit)
    return [
        {"id": r[0], "source": r[1], "content": r[2]}
        for r in rows
    ]


@app.delete("/documents", tags=["Knowledge (Legacy — Merge)"])
async def reset_documents():
    deleted = k_delete_all()
    return {"status": "reset_done", "deleted_chunks": deleted}


# ======================================================================
# 3. ERP SYSTEM (Sesi 5 - CRUD + Reports)
# ======================================================================
@app.post("/products", response_model=ProductOut, tags=["ERP — Products"])
def create_product(p: ProductIn):
    pid = p_insert(p.name, p.price, p.stock)
    return {"id": pid, "name": p.name, "price": p.price, "stock": p.stock}


@app.get("/products", response_model=List[ProductOut], tags=["ERP — Products"])
def list_products(name: Optional[str] = None):
    rows = p_list(name)
    return [{"id": r[0], "name": r[1], "price": r[2], "stock": r[3]} for r in rows]


@app.get("/products/{pid}", response_model=ProductOut, tags=["ERP — Products"])
def get_product(pid: str):
    r = p_get(pid)
    if not r:
        raise HTTPException(404, "Product not found")
    return {"id": r[0], "name": r[1], "price": r[2], "stock": r[3]}


@app.put("/products/{pid}", response_model=ProductOut, tags=["ERP — Products"])
def update_product(pid: str, p: ProductIn):
    if not p_get(pid):
        raise HTTPException(404, "Product not found")
    p_update(pid, p.name, p.price, p.stock)
    return {"id": pid, "name": p.name, "price": p.price, "stock": p.stock}


@app.delete("/products/{pid}", tags=["ERP — Products"])
def delete_product(pid: str):
    p_delete(pid)
    return {"status": "deleted", "id": pid}


@app.post("/customers", response_model=CustomerOut, tags=["ERP — Customers"])
def create_customer(c: CustomerIn):
    cid = c_insert(c.name, c.email, c.phone)
    return {"id": cid, "name": c.name, "email": c.email, "phone": c.phone}


@app.get("/customers", response_model=List[CustomerOut], tags=["ERP — Customers"])
def list_customers(name: Optional[str] = None):
    rows = c_list(name)
    return [{"id": r[0], "name": r[1], "email": r[2], "phone": r[3]} for r in rows]


@app.get("/customers/{cid}", response_model=CustomerOut, tags=["ERP — Customers"])
def get_customer(cid: str):
    r = c_get(cid)
    if not r:
        raise HTTPException(404, "Customer not found")
    return {"id": r[0], "name": r[1], "email": r[2], "phone": r[3]}


@app.post("/orders", tags=["ERP — Orders"])
def create_order(o: OrderIn):
    try:
        items_dict = [it.model_dump() for it in o.items]
        return o_create(o.customer_id, items_dict)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/orders", tags=["ERP — Orders"])
def list_orders(limit: int = 20, status: Optional[str] = None):
    rows = o_list(limit, status)
    return [
        {"id": r[0], "customer_id": r[1], "customer_name": r[2] or "-",
         "status": r[3], "total_amount": r[4], "created_at": str(r[5])}
        for r in rows
    ]


@app.get("/orders/{oid}", tags=["ERP — Orders"])
def get_order(oid: str):
    r = o_get(oid)
    if not r:
        raise HTTPException(404, "Order not found")
    o = r["order"]
    items = r["items"]
    return {
        "id": o[0], "customer_id": o[1], "customer_name": o[2] or "-",
        "status": o[3], "total_amount": o[4], "created_at": str(o[5]),
        "items": [
            {"id": it[0], "product_id": it[1], "product_name": it[2] or "-",
             "qty": it[3], "price": it[4], "subtotal": it[5]}
            for it in items
        ],
    }


@app.patch("/orders/{oid}/status", tags=["ERP — Orders"])
def set_status(oid: str, status: str = "completed"):
    if not o_get(oid):
        raise HTTPException(404, "Order not found")
    o_set_status(oid, status)
    return {"order_id": oid, "status": status}


@app.get("/report/sales", tags=["ERP — Reports"])
def sales_report_raw(days: int = 7):
    return report_sales(days)


@app.get("/report/low-stock", tags=["ERP — Reports"])
def low_stock_raw(threshold: int = 10):
    return report_low_stock(threshold)


# ======================================================================
# 4. AI GENERATOR + AGENTIC ROUTER (SOP → ERP Actions)
# ======================================================================
@app.post("/ai/report/sales", response_model=GeneratedReport, tags=["AI — Generator"])
async def ai_sales_report(req: SalesReportRequest):
    r = await generate_sales_report(req.days)
    return GeneratedReport(**r, llm_used=state.get("ready", False))


@app.post("/ai/report/low-stock", response_model=GeneratedReport, tags=["AI — Generator"])
async def ai_low_stock_report(req: LowStockReportRequest):
    r = await generate_low_stock_report(req.threshold)
    return GeneratedReport(**r, llm_used=state.get("ready", False))


@app.get("/ai/report/combined", tags=["AI — Generator"])
async def ai_combined_report(days: int = 7, threshold: int = 10):
    s = await generate_sales_report(days)
    ls = await generate_low_stock_report(threshold)
    return {
        "sales": s,
        "low_stock": ls,
        "llm_used": state.get("ready", False),
        "note": (
            "Gabungan laporan naratif Penjualan + Stok Kritis, "
            "siap disalin ke email / presentasi manajemen."
        ),
    }


@app.post("/ai/knowledge/qa", tags=["AI — Knowledge QA (Legacy RAG)"])
async def ai_knowledge_qa(req: SearchRequest):
    """Legacy RAG: merge search SOP + ERP docs → LLM jawab (tanpa routing ERP)."""
    search_rows = k_search(req.q, req.k)
    answer = await answer_with_knowledge(req.q, search_rows)
    return answer


@app.post("/ai/agentic/qa", response_model=AgenticResponse, tags=["AI — AGENTIC SOP→ERP (New!)"])
async def ai_agentic_qa(req: SearchRequest):
    """
    ⭐ AGENTIC ENDPOINT UTAMA ⭐
    Alur:
      1. 🔍 SEARCH SOP KB terlebih dahulu — baca prosedur yang relevan
      2. 🧭 ROUTER (LLM / rule-based) memutuskan ACTION ERP mana yang dijalankan
      3. ⚙️ EXECUTE semua action (lookup produk, cek stok, laporan penjualan, dll)
      4. ✍️ FINAL ANSWER LLM: gabung SOP + hasil ERP → jawaban natural

    Endpoint ini menjawab pertanyaan user SEPERTI CS yang BENAR-BENAR MEMBACA SOP dulu,
    baru kemudian mengambil data ERP yang dibutuhkan.
    """
    llm_ready = state.get("ready", False)
    result = await agentic_sop_erp_qa(req.q, llm_ready=llm_ready, k_sop=req.k)
    return AgenticResponse(**result)


# ======================================================================
# ROOT
# ======================================================================
@app.get("/", tags=["System"])
async def root():
    return {
        "name": "Agentic AI ERP v2",
        "version": "2.0.0",
        "feature": "Dual Knowledge Base (SOP + ERP Docs) + Agentic SOP→ERP Router",
        "modules": [
            "KB #1 SOP          : /sop/ingest/*, /sop/search, /sop/documents",
            "KB #2 ERP Docs     : /erp-docs/ingest/*, /erp-docs/search, /erp-docs/documents",
            "ERP System         : /products, /customers, /orders, /report/*",
            "AI Generator       : /ai/report/*",
            "⭐ AGENTIC SOP→ERP : /ai/agentic/qa (ENDPOINT UTAMA)",
        ],
        "frontend": {
            "dashboard": "/frontend  (atau /ui, /dashboard)",
            "direct_html": "frontend/index.html  (buka langsung di browser)",
        },
        "how_to_test_agentic": (
            "POST /ai/agentic/qa dengan body "
            "{\"q\": \"Laptop NocBook Pro 14 saya rusak, bagaimana klaim garansi?\", \"k\": 4} "
            "→ LLM akan baca SOP klaim garansi, otomatis lookup produk NocBook, lalu jawab."
        ),
        "docs": "/docs",
        "health": "/health",
        "stats": "/stats",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
