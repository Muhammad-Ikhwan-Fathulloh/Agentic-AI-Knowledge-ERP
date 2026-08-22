# app/schemas.py
from pydantic import BaseModel
from typing import List

class DocIn(BaseModel):
    source: str
    content: str

class DocOut(DocIn):
    id: str

class DocSearchResult(DocOut):
    score: float