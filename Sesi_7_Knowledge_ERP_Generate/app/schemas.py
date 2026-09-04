from pydantic import BaseModel
from typing import Optional, Any, List


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
