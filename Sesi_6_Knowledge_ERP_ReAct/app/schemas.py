from pydantic import BaseModel
from typing import List, Optional, Any


class ReActRequest(BaseModel):
    query: str
    max_steps: Optional[int] = None
    temperature: float = 0.3
    confirm_answer: Optional[str] = None


class StepLog(BaseModel):
    step: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[str] = None
    observation: Optional[str] = None


class ReActResponse(BaseModel):
    query: str
    final_answer: str
    steps: List[StepLog]
    need_human_confirm: bool = False
    prompt_confirm: Optional[str] = None
    domain: str = "erp"
