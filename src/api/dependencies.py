from fastapi import Depends, HTTPException

from ..config import Settings, get_settings
from ..engine import BaseEngine, EngineFactory

# Lazy-loaded singleton pattern
_engine_instance = None


async def get_engine(settings: Settings = Depends(get_settings)) -> BaseEngine:
    global _engine_instance
    # Lazy initialization - create only once
    if _engine_instance is None:
        try:
            # Create LLM Engine instance using factory
            _rag_instance = EngineFactory.create_engine(
                settings.engine_type,
                settings.get_engine_config()
            )

            # TODO
            # load documents
            documents = []

            await _rag_instance.add_documents(documents)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize RAG system: {str(e)}"
            )

    return _rag_instance
