from pydantic import BaseModel
from typing import List, Optional


class ReActRequest(BaseModel):
    query: str
    max_steps: int = 4
    temperature: float = 0.3


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
    total_steps: int
    domain: str = "knowledge"
