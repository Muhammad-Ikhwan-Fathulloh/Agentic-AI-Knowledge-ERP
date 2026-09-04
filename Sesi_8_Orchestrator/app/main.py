"""
Sesi 8 — Agentic AI Orchestrator (Port 8000)
===============================================
Menyatukan Knowledge Agent + ERP Agent dengan:
  • Router LLM (klasifikasi domain) + rule-based fallback
  • Semantic Cache (DuckDB VSS) — adaptasi pola P3 di End-to-End-LLM-Serving
  • Feedback Loop (Like/Dislike) — adaptasi pola P4 di End-to-End-LLM-Serving
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm import lifespan, state
from app.schemas import OrchestrateRequest, OrchestrateResponse, FeedbackRequest
from app.router import route_query
from app.dispatch import dispatch_knowledge, dispatch_erp
from app.database import (
    cache_lookup, cache_store,
    interaction_store, interaction_set_feedback, interaction_stats,
)

app = FastAPI(
    title="Sesi 8 — Agentic AI Orchestrator (Knowledge + ERP)",
    version="8.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
async def health():
    p = state.get("process")
    return {
        "app": "ok",
        "llama_alive": p is not None and p.poll() is None,
        "llama_ready": state.get("ready", False),
        "services": {
            "knowledge_api": settings.knowledge_api_base,
            "erp_api": settings.erp_api_base,
            "erp_report_api": settings.erp_report_api_base,
        },
        "duckdb": settings.duckdb_path,
        "stats": interaction_stats(),
    }


@app.post("/agent/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(req: OrchestrateRequest):
    # 1) Semantic Cache lookup
    cache_hit = cache_lookup(req.query) if req.use_cache else None
    if cache_hit:
        iid = interaction_store(
            query=req.query, answer=cache_hit["response"],
            domain=cache_hit["domain"], router_confidence="cache", cached=True,
        )
        return OrchestrateResponse(
            interaction_id=iid, query=req.query,
            domain=cache_hit["domain"], router_confidence="cache",
            cached=True, cache_distance=cache_hit["distance"],
            answer=cache_hit["response"],
            agent_detail={"note": "respons diambil dari semantic cache"},
        )

    # 2) Router
    domain, conf = await route_query(req.query)

    # 3) Dispatch ke agent sesuai domain
    if domain == "erp":
        result = await dispatch_erp(req.query, temperature=req.temperature)
    else:
        result = await dispatch_knowledge(req.query, temperature=req.temperature)

    answer = result.get("answer", "")

    # 4) Simpan ke cache (hanya jawaban panjang & tidak error)
    if len(answer) > 20 and "ERROR" not in answer[:40] and "LLM tidak siap" not in answer:
        try:
            cache_store(req.query, answer, domain)
        except Exception:
            pass

    # 5) Interaction log
    iid = interaction_store(
        query=req.query, answer=answer, domain=domain,
        router_confidence=conf, cached=False,
    )

    return OrchestrateResponse(
        interaction_id=iid, query=req.query,
        domain=domain, router_confidence=conf,
        cached=False, cache_distance=None,
        answer=answer,
        agent_detail=result,
    )


@app.post("/agent/feedback")
async def feedback(req: FeedbackRequest):
    row = interaction_set_feedback(req.interaction_id, req.is_like)
    if not row:
        raise HTTPException(404, "interaction_id tidak ditemukan")
    return {
        "status": "success",
        "interaction_id": row[0],
        "query": row[1],
        "domain": row[2],
        "feedback": "like" if row[3] else "dislike",
    }


@app.get("/agent/stats")
async def stats():
    return interaction_stats()


@app.get("/agent/eval-benchmark")
async def eval_benchmark():
    """10 Skenario evaluasi end-to-end (tanpa benar-benar eksekusi, cuma routing & suggestion)."""
    scenarios = [
        ("Apa itu kebijakan garansi NocBook?", "knowledge"),
        ("Bagaimana cara klaim refund?", "knowledge"),
        ("SOP pengembalian barang?", "knowledge"),
        ("Halo, selamat pagi!", "knowledge"),
        ("Stok NocBook tersisa berapa?", "erp"),
        ("Daftar semua produk dong", "erp"),
        ("Saya mau order 1 NocMouse untuk Budi", "erp"),
        ("Bagaimana laporan penjualan 7 hari terakhir?", "erp"),
        ("Cek status order ORD-123", "erp"),
        ("Produk mana yang stoknya hampir habis?", "erp"),
    ]
    return {
        "note": "Rekomendasi skenario evaluasi (bisa run manual via /agent/orchestrate).",
        "expected_routing": [
            {"query": q, "expected_domain": d} for q, d in scenarios
        ],
        "checklist": [
            "Domain routing benar/salah (10 percobaan)",
            "Latency total / request (detik)",
            "Pola prompting: ReAct vs Planner vs Cached",
            "Akurasi jawaban final (subjektif / rubrik)",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
