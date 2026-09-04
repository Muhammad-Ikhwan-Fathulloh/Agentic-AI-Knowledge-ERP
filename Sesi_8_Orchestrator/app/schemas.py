from pydantic import BaseModel
from typing import Optional, Any, List


class OrchestrateRequest(BaseModel):
    query: str
    temperature: float = 0.3
    use_cache: bool = True


class FeedbackRequest(BaseModel):
    interaction_id: str
    is_like: bool


class OrchestrateResponse(BaseModel):
    interaction_id: str
    query: str
    domain: str
    router_confidence: str
    cached: bool
    cache_distance: Optional[float] = None
    answer: str
    agent_detail: Any
