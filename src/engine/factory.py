from typing import Dict, Any

from engine import BaseEngine


class EngineFactory:
    @staticmethod
    def create_engine(engine_type: str, config: Dict[str, Any]) -> BaseEngine:
        if engine_type.lower() == 'anthropic':
            from engine.implementations import AnthropicEngine
            return AnthropicEngine(config)
        # elif engine_type.lower() == 'openai':
        #   from engine.implementations import OpenAIEngine
        #     return OpenAIRAG(config)
        else:
            raise ValueError(f"Unknown Engine type: {engine_type}")
