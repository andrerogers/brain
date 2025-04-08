from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator, Dict, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...config import Settings
from ...engine import BaseEngine
from ..dependencies import get_engine, get_settings
from ..models.schemas import QueryInput, QueryResponse

router = APIRouter()


@router.post(
    "/",
    response_model=QueryResponse,
    summary="Query the LLM"
)
async def query(
    input_data: QueryInput,
    engine: BaseEngine = Depends(get_engine),
    settings: Settings = Depends(get_settings)
):
    try:
        top_k = input_data.top_k or settings.rag_top_k
        result = await engine.get_response(input_data.query, top_k)
        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "query": input_data.query
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}"
        )


async def stream_llm_response(
    query: str,
    rag: BaseEngine,
    top_k: Optional[int] = None,
    settings: Settings = Depends(get_settings)
) -> AsyncGenerator[Dict[str, Any], None]:
    try:
        # Signal the start of streaming
        yield {"event": "start", "data": "Processing request..."}

        effective_top_k = top_k or settings.rag_top_k

        async for event in rag.stream_response(query, effective_top_k):
            yield event

        # Signal completion
        yield {"event": "end", "data": "Response complete"}

    except Exception as e:
        # Handle errors
        yield {"event": "error", "data": str(e)}


@router.get(
    "/stream",
    summary="Stream a response from the RAG system"
)
async def stream_chat(
    query: str = Query(..., description="The user's question"),
    top_k: Optional[int] = Query(
        None,
        description="Number of documents to retrieve"
    ),
    rag: BaseEngine = Depends(get_engine),
    settings: Settings = Depends(get_settings)
):
    if settings.debug:
        print(f"Streaming request: {query}")
    return EventSourceResponse(stream_llm_response(
        query,
        rag,
        top_k,
        settings
    ))
