"""
Sesi 7 — Knowledge ERP Generate (Laporan Naratif via Qwen) — Port 8007
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm import lifespan, state
from app.schemas import (
    SalesReportRequest, LowStockReportRequest, GeneratedReport,
)
from app.generators import generate_sales_report, generate_low_stock_report

app = FastAPI(
    title="Sesi 7 — Knowledge ERP Generate (Narrative Report via Qwen)",
    version="7.0.0",
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
        "erp_api": settings.erp_api_base,
        "defaults": {
            "report_days": settings.default_report_days,
            "low_stock_threshold": settings.low_stock_threshold,
        },
    }


@app.post("/report/sales", response_model=GeneratedReport)
async def sales_report(req: SalesReportRequest):
    r = await generate_sales_report(req.days)
    return GeneratedReport(**r, llm_used=state.get("ready", False))


@app.post("/report/low-stock", response_model=GeneratedReport)
async def low_stock_report(req: LowStockReportRequest):
    r = await generate_low_stock_report(req.threshold)
    return GeneratedReport(**r, llm_used=state.get("ready", False))


@app.get("/report/combined")
async def combined_report(days: int = 7, threshold: int = 10):
    s = await generate_sales_report(days)
    ls = await generate_low_stock_report(threshold)
    return {
        "sales": s,
        "low_stock": ls,
        "note": "Gabungan laporan penjualan + stok kritis, siap disalin ke email/presentasi.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
