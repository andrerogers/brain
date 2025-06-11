from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator, Dict, Optional, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status

from engine import BaseEngine
from api.dependencies import get_engine
from api.models.schemas import QueryInput, QueryResponse

router = APIRouter()


@router.post(
    "/response",
    response_model=QueryResponse,
    summary="Query the LLM"
)
async def query(
    input_data: QueryInput,
    engine: BaseEngine = Depends(get_engine)
):
    try:
        result = await engine.get_response(input_data.query)
        return {
            "answer": result["answer"],
            "query": input_data.query
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}"
        )


async def stream_llm_response(
    query: str,
    engine: BaseEngine
) -> AsyncGenerator[Dict[str, Any], None]:
    try:
        # Signal the start of streaming
        yield {"event": "start", "data": "Processing request..."}
        async for event in engine.stream_response(query):
            yield event
        # Signal completion
        yield {"event": "end", "data": "Response complete"}
    except Exception as e:
        # Handle errors
        yield {"event": "error", "data": str(e)}


class QueryRequest(BaseModel):
    query: str = Field(..., description="The user's question")
    top_k: Optional[int] = Field(None, description="Number of documents to retrieve")


@router.post(
    "/stream",
    summary="Stream a response from the LLM Engine"
)
async def stream_chat(
    request: QueryRequest,
    engine: BaseEngine = Depends(get_engine),
):
    print(f"Streaming request: {request.query}")
    return EventSourceResponse(stream_llm_response(
        request.query,
        engine
    ))
