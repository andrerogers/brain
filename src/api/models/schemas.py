from typing import Optional, List
from pydantic import BaseModel


class QueryInput(BaseModel):
    query: str
    top_k: Optional[int] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    query: str


class DocumentInput(BaseModel):
    documents: List[str]


class DocumentResponse(BaseModel):
    status: str
    message: str
    count: int
