import uvicorn
import sys
from pathlib import Path

from src.config import get_settings
from src.api.app import app


# Add the project root to the Python path
# This allows importing modules from the project root
project_root = Path(__file__).parent
sys.path.append(str(project_root))


def main():
    settings = get_settings()
    print("Starting Brain")
    print(f"Server Address: http://{settings.host}:{settings.port}")
    print(f"Debug Mode: {settings.debug}")
    uvicorn.run(
        "api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    )


if __name__ == "__main__":
    main()
