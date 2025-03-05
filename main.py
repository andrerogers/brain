import asyncio
import uvicorn
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator


app = FastAPI(title="Brain SSE Server")


async def stream_llm_response(prompt: str) -> AsyncGenerator[dict, None]:
    """
    Stream chunks of the LLM response as SSE events.
    """
    try:
        # Signal the start of streaming
        yield {"event": "start", "data": "Processing request..."}

        # Placeholder for LLM integration
        # Here you would connect to your LLM
        # service and get a streaming response

        # Mock some response chunks for now
        chunks = ["Hello", ", ", "I'm", " responding",
                  " to", " your", " question", "."]
        for chunk in chunks:
            await asyncio.sleep(0.1)  # Simulating processing time
            yield {"event": "token", "data": chunk}

        # Signal completion
        yield {"event": "end", "data": "Response complete"}

    except Exception as e:
        # Handle errors
        yield {"event": "error", "data": str(e)}


@app.get("/chat/stream")
async def stream_chat(prompt: str):
    """Endpoint for streaming LLM responses via SSE."""
    return EventSourceResponse(stream_llm_response(prompt))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
