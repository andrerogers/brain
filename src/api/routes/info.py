from fastapi import APIRouter, Depends, status
from typing import Dict, Any

from config import Settings
from api.dependencies import get_settings

router = APIRouter()


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Get system information"
)
async def get_info(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    return {
        "engine_type": settings.rag_type,
        "embedding_model": (
            settings.anthropic_embedding_model
            if settings.rag_type == "anthropic"
            else settings.openai_embedding_model
        ),
        "llm_model": (
            settings.anthropic_llm_model
            if settings.rag_type == "anthropic"
            else settings.openai_llm_model
        ),
        "max_tokens": settings.max_tokens,
        "top_k": settings.rag_top_k
    }


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint"
)
async def health_check() -> Dict[str, str]:
    return {"status": "healthy"}
