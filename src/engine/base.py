from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator


class BaseEngine(ABC):
    @abstractmethod
    async def stream_response(self, query: str) -> AsyncGenerator[Dict[str, Any], None]:
        pass

    @abstractmethod
    async def get_response(self, query: str) -> Dict[str, Any]:
        pass
