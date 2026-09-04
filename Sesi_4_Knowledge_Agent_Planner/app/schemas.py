from pydantic import BaseModel
from typing import Optional, Any


class PlannerDecision(BaseModel):
    need_tool: bool = False
    tool: Optional[str] = None
    query: Optional[str] = None


class PlannerRequest(BaseModel):
    question: str
    temperature: float = 0.2


class PlannerResponse(BaseModel):
    question: str
    decision: PlannerDecision
    context: str = ""
    llm_calls: int = 0
    planner_retries: int = 0
    final_answer: str
    domain: str = "knowledge"
    method: str = "planner-executor (structured JSON)"
