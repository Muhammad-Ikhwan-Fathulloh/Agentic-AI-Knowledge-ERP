from pydantic import BaseModel
from typing import Optional, List


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
