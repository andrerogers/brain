from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import query_router, info_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Modular LLM Server",
        description="A modular Retrieval-Augmented Generation (RAG) \
        server that supports multiple LLM providers",
        version="0.1.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify exact origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(query_router, prefix="/query", tags=["Queries"])
    app.include_router(info_router, prefix="/info", tags=["System Info"])

    @app.on_event("startup")
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

    return app


# Application instance to be used by the server
app = create_app()
