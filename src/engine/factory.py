from src.engine import BaseEngine

from typing import Dict, Any


class EngineFactory:
    @staticmethod
    def create_engine(engine_type: str, config: Dict[str, Any]) -> BaseEngine:
        if engine_type.lower() == 'anthropic':
            from engine.implementations import AnthropicEngine
            return AnthropicEngine(config)
        # elif engine_type.lower() == 'openai':
        #     from rag_implementations.openai_rag import OpenAIRAG
        #     return OpenAIRAG(config)
        else:
            raise ValueError(f"Unknown Engine type: {engine_type}")
