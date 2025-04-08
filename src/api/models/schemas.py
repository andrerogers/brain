from typing import BaseModel, Optional, List


class QueryInput(BaseModel):
    query: str
    top_k: Optional[int] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    query: str


class DocumentsInput(BaseModel):
    documents: List[str]


class DocumentResponse(BaseModel):
    status: str
    message: str
    count: int
