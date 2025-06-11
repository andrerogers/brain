from config import Settings
from engine import BaseEngine, EngineFactory

# Lazy-loaded singleton pattern
_engine_instance = None


async def get_engine(settings: Settings) -> BaseEngine:
    global _engine_instance

    # Lazy initialization - create only once
    if _engine_instance is None:
        try:
            # Create LLM Engine instance using factory
            _engine_instance = EngineFactory.create_engine(
                settings.engine_type,
                settings.get_engine_config()
            )

        except Exception as e:
            raise Exception({
                "message": f"Failed to initialize LLM Engine: {str(e)}"
            })

    return _engine_instance
