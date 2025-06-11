import sys
import json
import asyncio
import logging

from pathlib import Path

from config import get_settings
from websocket_server import WSSettings, WebSocketServer
from dependencies import get_engine


HOME_DIR = Path.home()
CONFIG_DIR = HOME_DIR / '.brain'
LOG_FILE = CONFIG_DIR / 'brain.log'
MCP_SETTINGS_FILE = CONFIG_DIR / 'mcp.settings.json'
CONFIG_DIR.mkdir(exist_ok=True, parents=True)


def validate_paths():
    CONFIG_DIR.mkdir(exist_ok=True, parents=True)

    # create an empty log file if missing
    if not LOG_FILE.exists():
        LOG_FILE.touch()

    # create default MCP settings if missing
    if not MCP_SETTINGS_FILE.exists():
        default = {"servers": []}
        with open(MCP_SETTINGS_FILE, 'w') as f:
            json.dump(default, f, indent=2)


async def main():
    validate_paths()

    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("brain")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    settings = get_settings()
    engine = await get_engine(settings)

    ws_settings = WSSettings(
        host=getattr(settings, "WS_HOST", "localhost"),
        port=getattr(settings, "WS_PORT", 3789),
        mcp_file_path=MCP_SETTINGS_FILE,
        log_file=LOG_FILE,
        debug=getattr(settings, "debug", False)
    )

    server = WebSocketServer(logger, settings, ws_settings, engine)

    try:
        logging.getLogger("brain").setLevel(logging.DEBUG)
        await server.listen()
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error running daemon: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
