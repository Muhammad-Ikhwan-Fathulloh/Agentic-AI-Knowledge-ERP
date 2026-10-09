from pydantic import BaseModel, Field
from typing import Optional, List, Any


# ====================================================================
# KNOWLEDGE (SOP + ERP Docs)
# ====================================================================
class IngestTextRequest(BaseModel):
    source: str
    content: str
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None


class SearchRequest(BaseModel):
    q: str
    k: int = 5


class ChunkInfoResponse(BaseModel):
    source: str
    total_chunks: int
    total_words: int
    document_ids: List[str]


class SearchResult(BaseModel):
    id: str
    source: str
    content: str
    score: float


# ====================================================================
# ERP
# ====================================================================
class ProductIn(BaseModel):
    name: str
    price: float
    stock: int = 0


class ProductOut(ProductIn):
    id: str


class CustomerIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class CustomerOut(CustomerIn):
    id: str


class OrderItemIn(BaseModel):
    product_id: str
    qty: int


class OrderIn(BaseModel):
    customer_id: str
    items: List[OrderItemIn]


# ====================================================================
# AI GENERATOR
# ====================================================================
class SalesReportRequest(BaseModel):
    days: Optional[int] = None


class LowStockReportRequest(BaseModel):
    threshold: Optional[int] = None


class GeneratedReport(BaseModel):
    type: str
    period_days: Optional[int] = None
    threshold: Optional[int] = None
    raw_data: Any
    summary_text: str
    narrative: str
    llm_used: bool = True


# ====================================================================
# AGENTIC SOP -> ERP ROUTING (BARU)
# ====================================================================
VALID_ACTIONS = {
    "lookup_product", "check_low_stock", "check_sales_report",
    "lookup_customer", "lookup_order", "lookup_erp_knowledge",
    "no_erp_needed",
}


class AgentAction(BaseModel):
    """Satu action ERP yang diputuskan oleh LLM setelah membaca SOP."""
    action: str = Field(
        description=(
            "Pilih salah satu: lookup_product (cari produk by nama/stok/harga), "
            "check_low_stock (cek barang stok dibawah threshold), "
            "check_sales_report (laporan penjualan N hari), "
            "lookup_customer (cari customer by nama/email), "
            "lookup_order (cari detail order by id), "
            "lookup_erp_knowledge (cari di KB ERP spesifikasi produk/supplier), "
            "no_erp_needed (jawaban cukup dari SOP saja)."
        )
    )
    param: Optional[str] = Field(
        default=None,
        description="Parameter untuk action: nama produk untuk lookup_product, order_id untuk lookup_order, dsb.",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Alasan mengapa action ini dipilih (dari SOP yang dibaca).",
    )


class AgentPlan(BaseModel):
    """Hasil parsing LLM: daftar action ERP yang harus dijalankan."""
    actions: List[AgentAction]
    sop_summary: str = Field(description="Ringkasan SOP yang relevan untuk jawaban user.")


class AgentStep(BaseModel):
    """Satu langkah di rantai agentic: action + result."""
    action: str
    param: Optional[str] = None
    reason: Optional[str] = None
    result: Any


class AgenticResponse(BaseModel):
    """Response final endpoint /ai/agentic/qa."""
    question: str
    sop_context: List[dict]
    plan: Any
    steps: List[AgentStep]
    final_answer: str
    llm_used: bool
