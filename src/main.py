import asyncio
import json
import logging
import sys
from pathlib import Path

import logfire

from config import Settings, get_settings
from server import BrainServer, WSSettings

HOME_DIR = Path.home()
CONFIG_DIR = HOME_DIR / ".brain"
LOG_FILE = CONFIG_DIR / "brain.log"
MCP_SETTINGS_FILE = CONFIG_DIR / "mcp.settings.json"
CONFIG_DIR.mkdir(exist_ok=True, parents=True)


def validate_paths() -> None:
    CONFIG_DIR.mkdir(exist_ok=True, parents=True)

    # create an empty log file if missing
    if not LOG_FILE.exists():
        LOG_FILE.touch()

    # create default MCP settings if missing
    if not MCP_SETTINGS_FILE.exists():
        default = {"servers": []}
        with open(MCP_SETTINGS_FILE, "w") as f:
            json.dump(default, f, indent=2)


def setup_logging(settings: Settings) -> logging.Logger:
    # Initialize Logfire if enabled
    if settings.logfire_enabled:
        try:
            logfire.configure(
                token=settings.logfire_token,
                service_name=settings.logfire_service_name,
            )

            # Instrument PydanticAI for automatic agent tracing
            logfire.instrument_pydantic_ai()

            # Instrument HTTPX for HTTP request tracing
            logfire.instrument_httpx(capture_all=True)

            print(f"Logfire initialized for service: {settings.logfire_service_name}")
        except Exception as e:
            print(f"Failed to initialize Logfire: {e}")

    # Set logging level based on debug setting
    log_level = logging.DEBUG if settings.debug else logging.INFO

    logging.basicConfig(
        filename=LOG_FILE,
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("brain")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


async def main() -> None:
    validate_paths()

    settings = get_settings()

    logger = setup_logging(settings)


    ws_settings = WSSettings(
        host=getattr(settings, "WS_HOST", "localhost"),
        port=getattr(settings, "WS_PORT", 3789),
        mcp_file_path=MCP_SETTINGS_FILE,
        log_file=LOG_FILE,
        debug=getattr(settings, "debug", False),
    )

    server = BrainServer(logger, settings, ws_settings)

    try:
        await server.listen()
    except Exception as e:
        print(f"Error running daemon: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
