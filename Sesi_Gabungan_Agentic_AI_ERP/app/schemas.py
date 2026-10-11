from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


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
# AGENTIC SOP -> ERP ROUTING
# ====================================================================
VALID_ACTIONS = {
    "lookup_product", "check_low_stock", "check_sales_report",
    "lookup_customer", "lookup_order", "lookup_erp_knowledge",
    "no_erp_needed",
}


class AgentAction(BaseModel):
    action: str
    param: Optional[str] = None
    reason: Optional[str] = None


class AgentPlan(BaseModel):
    actions: List[AgentAction]
    sop_summary: str


class AgentStep(BaseModel):
    action: str
    param: Optional[str] = None
    reason: Optional[str] = None
    result: Any


class AgenticResponse(BaseModel):
    question: str
    sop_context: List[dict]
    plan: Any
    steps: List[AgentStep]
    final_answer: str
    llm_used: bool


# ====================================================================
# CHATBOT / CONVERSATION MEMORY (CHATGPT-STYLE)
# ====================================================================
class ChatSessionIn(BaseModel):
    title: Optional[str] = "Percakapan baru"
    customer_id: Optional[str] = None


class ChatSession(BaseModel):
    id: str
    title: str
    customer_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages_count: int = 0
    last_message: Optional[str] = None


class ChatMessage(BaseModel):
    id: str
    session_id: str
    role: str = Field(description="user | assistant | system")
    content: str
    tokens_used: Optional[int] = 0
    agentic_steps: Optional[Any] = None
    created_at: datetime


class ChatRequest(BaseModel):
    """Request send message ke chatbot."""
    message: str
    session_id: Optional[str] = Field(
        default=None,
        description="ID session yang sudah ada. Jika kosong → session baru dibuat otomatis."
    )
    k_sop: int = 4
    memory_last_n: int = Field(
        default=6,
        description="Berapa pesan terakhir yang dimasukkan ke context LLM (memory)."
    )
    use_agentic: bool = Field(
        default=True,
        description="True = agentic SOP→ERP Router; False = basic RAG (lebih cepat tapi tanpa ERP)."
    )
    stream: bool = False  # reserved SSE (belum dipakai v3)


class ChatResponse(BaseModel):
    """Response chatbot dengan session + pesan balasan + langkah agentic."""
    session_id: str
    session_title: str
    message_id: str
    reply: str
    role: str = "assistant"
    memory_used: int = 0
    agentic: Optional[AgenticResponse] = None
    tokens_used: int = 0
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Daftar pesan dalam satu session (untuk ditampilkan ulang ke frontend)."""
    session: ChatSession
    messages: List[ChatMessage]
