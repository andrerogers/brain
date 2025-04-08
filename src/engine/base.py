import json

from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator, Optional


class BaseEngine(ABC):
    """Abstract base class for all RAG implementations."""

    @abstractmethod
    async def add_documents(self, documents: List[str]) -> None:
        pass

    @abstractmethod
    async def get_relevant_docs(self, query: str, top_k: int = 3) -> List[str]:
        pass

    @abstractmethod
    async def stream_response(self, query: str, top_k: int = 3) -> AsyncGenerator[Dict[str, Any], None]:
        pass

    @abstractmethod
    async def get_response(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        pass
