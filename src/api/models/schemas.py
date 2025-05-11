from typing import List
from pydantic import BaseModel


class QueryInput(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: str
    query: str


class DocumentInput(BaseModel):
    documents: List[str]


class DocumentResponse(BaseModel):
    status: str
    message: str
    count: int
