from abc import ABC, abstractmethod
from typing import Dict, List, Any, AsyncGenerator


class BaseEngine(ABC):
    @abstractmethod
    async def stream_response(self, query: str) -> AsyncGenerator[Dict[str, Any], None]:
        pass

    @abstractmethod
    async def get_response(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], system_message: str = '') -> Dict[str, Any]:
        pass
