from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import query_router, info_router


def create_api() -> FastAPI:
    brain_api = FastAPI(
        title="Modular LLM Server",
        description="A modular Retrieval-Augmented Generation (RAG) \
        server that supports multiple LLM providers",
        version="0.1.0"
    )

    brain_api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify exact origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    brain_api.include_router(query_router, prefix="/query", tags=["Queries"])
    brain_api.include_router(info_router, prefix="/info", tags=["System Info"])

    @brain_api.on_event("startup")
    async def startup_event():
        from config import get_settings
        settings = get_settings()
        print("Server starting")
        print(f"Host: {settings.host}, Port: {settings.port}")

        from .dependencies import get_engine
        try:
            await get_engine(settings)
            print("LLM Engine initialized successfully")
        except Exception as e:
            print(f"Failed to initialize LLM Engine: {str(e)}")

    return brain_api


# API instance to be used by the server
brain_api = create_api()
