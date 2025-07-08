import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import logfire
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agent.engine import AgentEngine
from app.coordinator import AppCoordinator
from app.session import SessionManager
from app.handler import WebSocketHandler
from tools.client import MCPClient


def safe_json_serialize(obj):
    """Custom JSON serializer that handles datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class WSSettings:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3789,
        mcp_file_path: Optional[Path] = None,
        log_file: Optional[Path] = None,
        debug: bool = False,
    ):
        self.host = host
        self.port = port
        self.mcp_file_path = mcp_file_path
        self.log_file = log_file
        self.debug = debug


class BrainServer:
    def __init__(self, logger, settings, ws_settings) -> None:
        self.logger = logger
        self.settings = settings
        self.ws_settings = ws_settings

        self.host = ws_settings.host
        self.port = ws_settings.port
        self.mcp_file_path = ws_settings.mcp_file_path

        self.app = FastAPI(title="Brain WebSocket Server", version="1.0.0")
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.mcp_client = MCPClient(logger=self.logger)

        # Initialize agent engine with config
        models_config = {
            "planning": f"{settings.engine_type}:{settings.anthropic_llm_model if settings.engine_type == 'anthropic' else settings.openai_llm_model}",
            "orchestrator": f"{settings.engine_type}:{settings.anthropic_llm_model if settings.engine_type == 'anthropic' else settings.openai_llm_model}",
            "execution": f"{settings.engine_type}:{settings.anthropic_llm_model if settings.engine_type == 'anthropic' else settings.openai_llm_model}",
        }

        api_key = (
            settings.anthropic_api_key
            if settings.engine_type == "anthropic"
            else settings.openai_api_key
        )

        self.agent_engine = AgentEngine(
            default_models=models_config, api_key=api_key, logger=self.logger
        )
        self.app_coordinator = AppCoordinator(
            agent_engine=self.agent_engine,
            tool_client=self.mcp_client,
            logger=self.logger,
        )

        # Initialize session management
        self.session_manager = SessionManager(logger=self.logger)

        # Initialize WebSocket handler
        self.app_handler = WebSocketHandler(
            app_coordinator=self.app_coordinator, logger=self.logger
        )

        self.connected_clients: Dict[str, WebSocket] = {}

        # Register WebSocket route
        @self.app.websocket("/")
        async def websocket_endpoint(websocket: WebSocket):
            await self.websocket_handler(websocket)

        # Health check endpoint
        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "connected_clients": len(self.connected_clients),
            }

    def load_mcp_settings(self) -> Dict[str, Any]:
        """Load MCP server settings from file."""
        if not self.mcp_file_path.exists():
            default_settings = {"servers": []}
            with open(self.mcp_file_path, "w") as f:
                json.dump(default_settings, f, indent=2)
            return default_settings

        try:
            with open(self.mcp_file_path, "r") as f:
                settings = json.load(f)
            return settings
        except Exception as e:
            self.logger.error(f"Error loading MCP settings: {e}")
            return {"servers": []}

    async def _safe_send_json(
        self, websocket: WebSocket, message: Dict[str, Any]
    ) -> bool:
        """Safely send JSON message to websocket, return True if successful."""
        try:
            # Check if websocket is still open
            if hasattr(websocket, "client_state") and websocket.client_state.value >= 2:
                return False
            # Use custom JSON serializer to handle datetime objects
            await websocket.send_text(json.dumps(message, default=safe_json_serialize))
            return True
        except Exception as e:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"Failed to send message to websocket: {e}")
            return False

    async def websocket_handler(self, websocket: WebSocket) -> None:
        """Handle WebSocket connections with session management."""
        await websocket.accept()
        session_id = str(uuid.uuid4())
        self.connected_clients[session_id] = websocket

        with logfire.span("brain_server.websocket_connection", session_id=session_id):
            await self._handle_websocket_session(websocket, session_id)

    async def _handle_websocket_session(
        self, websocket: WebSocket, session_id: str
    ) -> None:
        """Handle individual WebSocket session."""
        try:
            # Create session for this connection
            session = await self.session_manager.create_session(
                {
                    "websocket_connection": True,
                    "remote_address": (
                        str(websocket.client) if websocket.client else "unknown"
                    ),
                }
            )
            session_id = session.session_id

            # Send initial status
            servers_info = await self.mcp_client.get_all_servers()
            success = await self._safe_send_json(
                websocket,
                {
                    "type": "status",
                    "session_id": session_id,
                    "servers": servers_info,
                }
            )
            if not success:
                self.logger.warning("Failed to send initial status - connection closed")
                return

            while True:
                try:
                    # Receive message from WebSocket
                    message = await websocket.receive_text()
                    data = json.loads(message)

                    # Ensure session ID is included
                    data["session_id"] = session_id

                    with logfire.span(
                        "brain_server.process_command",
                        command=data.get("command", "unknown"),
                        session_id=session_id,
                    ):
                        await self.process_command(websocket, data)

                except json.JSONDecodeError:
                    success = await self._safe_send_json(
                        websocket,
                        {
                            "type": "error",
                            "session_id": session_id,
                            "error": "Invalid JSON message",
                        }
                    )
                    if not success:
                        # Connection is closed, break out of loop
                        break
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    success = await self._safe_send_json(
                        websocket,
                        {"type": "error", "session_id": session_id, "error": str(e)}
                    )
                    if not success:
                        # Connection is closed, break out of loop
                        break

        except WebSocketDisconnect:
            # Normal client disconnect
            pass
        except Exception:
            # Catch everything else and log the stack trace
            self.logger.exception("Unhandled error in websocket_handler")
        finally:
            # Clean up session
            if session_id in self.connected_clients:
                del self.connected_clients[session_id]
            if session_id:
                await self.session_manager.cancel_session(session_id)

    async def process_command(self, websocket: WebSocket, data):
        """Process incoming WebSocket commands."""
        command = data.get("command")
        session_id = data.get("session_id", "unknown")

        if not command:
            await self._safe_send_json(
                websocket,
                {"type": "error", "session_id": session_id, "error": "Missing command"},
            )
            return

        # Try app handler commands first (agent queries, tool execution, etc.)
        handled = await self.app_handler.handle_app_command(websocket, data)
        if handled:
            return

        # Fall back to legacy MCP commands for backward compatibility
        if command == "connect_server":
            await self.handle_connect_server(websocket, data)
        elif command == "list_tools":
            await self.handle_list_tools(websocket, data)
        elif command == "get_servers":
            await self.handle_get_servers(websocket, data)
        elif command == "get_all_tools":
            await self.handle_get_all_tools(websocket, data)
        else:
            await self._safe_send_json(
                websocket,
                {
                    "type": "error",
                    "session_id": session_id,
                    "error": f"Unknown command: {command}",
                },
            )

    async def handle_connect_server(self, websocket: WebSocket, data):
        """Handle MCP server connection requests."""
        server_id = data.get("server_id")
        server_config = data.get("server_config") or data.get("server_path")
        session_id = data.get("session_id", "unknown")

        if not server_id or not server_config:
            await self._safe_send_json(
                websocket,
                {
                    "type": "error",
                    "session_id": session_id,
                    "error": "Missing server_id or server_config",
                },
            )
            return

        try:
            success = await self.mcp_client.connect_server(server_id, server_config)

            if success:
                server_info = await self.mcp_client.get_server_info(server_id)

                # Save to settings
                mcp_settings = self.load_mcp_settings()
                servers = mcp_settings.get("servers", [])

                server_exists = False
                for i, server in enumerate(servers):
                    if server.get("id") == server_id:
                        servers[i] = {"id": server_id, "config": server_config}
                        server_exists = True
                        break

                if not server_exists:
                    servers.append({"id": server_id, "config": server_config})

                mcp_settings["servers"] = servers

                with open(self.mcp_file_path, "w") as f:
                    json.dump(mcp_settings, f, indent=2)

                await self._safe_send_json(
                    websocket,
                    {
                        "type": "server_connected",
                        "session_id": session_id,
                        "server": server_info,
                    },
                )

                await self.broadcast_server_status()
            else:
                await self._safe_send_json(
                    websocket,
                    {
                        "type": "error",
                        "session_id": session_id,
                        "error": f"Failed to connect to server {server_id}",
                    },
                )
        except Exception as e:
            self.logger.error(f"Error connecting to server: {e}")
            await self._safe_send_json(
                websocket, {"type": "error", "session_id": session_id, "error": str(e)}
            )

    async def handle_list_tools(self, websocket: WebSocket, data):
        """Handle tool listing requests."""
        server_id = data.get("server_id")
        session_id = data.get("session_id", "unknown")

        if not server_id:
            await self._safe_send_json(
                websocket,
                {
                    "type": "error",
                    "session_id": session_id,
                    "error": "Missing server_id",
                }
            )
            return

        try:
            tools = await self.mcp_client.list_tools(server_id)

            await self._safe_send_json(
                websocket,
                {
                    "type": "tools_list",
                    "session_id": session_id,
                    "server_id": server_id,
                    "tools": [
                        {"name": tool.name, "description": tool.description}
                        for tool in tools
                    ],
                },
            )
        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            await self._safe_send_json(
                websocket, {"type": "error", "session_id": session_id, "error": str(e)}
            )


    def _format_progress_message(self, progress_data: Dict[str, Any]) -> str:
        """Format progress data into a human-readable message."""
        elapsed = progress_data.get("elapsed_time", 0)
        status = progress_data.get("status", "thinking")
        tokens = progress_data.get("estimated_input_tokens", 0)
        completed_calls = progress_data.get("tool_calls_completed", 0)
        total_calls = progress_data.get("total_tool_calls", 0)

        if elapsed < 1:
            time_str = f"{elapsed*1000:.0f}ms"
        else:
            time_str = f"{elapsed:.1f}s"

        if status.startswith("executing_tool_"):
            tool_name = status.replace("executing_tool_", "")
            status_msg = f"executing {tool_name}"
        elif status == "processing_tool_result":
            status_msg = "processing result"
        elif status == "analyzing_query":
            status_msg = "analyzing"
        elif status == "preparing_tools":
            status_msg = "preparing tools"
        elif status == "processing_llm":
            status_msg = "processing"
        else:
            status_msg = status

        parts = [f"{status_msg} ({time_str})"]

        if tokens > 0:
            parts.append(f"{tokens} tokens")

        if total_calls > 0:
            parts.append(f"tools: {completed_calls}/{total_calls}")

        return " • ".join(parts)

    async def handle_get_servers(self, websocket: WebSocket, data):
        """Handle server list requests."""
        session_id = data.get("session_id", "unknown")

        try:
            servers_info = await self.mcp_client.get_all_servers()

            await self._safe_send_json(
                websocket,
                {
                    "type": "servers_list",
                    "session_id": session_id,
                    "servers": servers_info,
                },
            )
        except Exception as e:
            self.logger.error(f"Error getting servers: {e}")
            await self._safe_send_json(
                websocket, {"type": "error", "session_id": session_id, "error": str(e)}
            )

    async def handle_get_all_tools(self, websocket: WebSocket, data):
        """Handle all tools overview requests."""
        session_id = data.get("session_id", "unknown")

        try:
            tools_by_server = await self.mcp_client.get_all_available_tools()

            await self._safe_send_json(
                websocket,
                {
                    "type": "tools_overview",
                    "session_id": session_id,
                    "tools": tools_by_server,
                },
            )
        except Exception as e:
            self.logger.error(f"Error getting all tools: {e}")
            await self._safe_send_json(
                websocket, {"type": "error", "session_id": session_id, "error": str(e)}
            )

    async def broadcast_server_status(self):
        """Broadcast server status to all connected clients."""
        if not self.connected_clients:
            return

        try:
            servers_info = await self.mcp_client.get_all_servers()
            message = {"type": "servers_update", "servers": servers_info}

            # Send to all clients
            failed_clients = []
            for session_id, client in self.connected_clients.items():
                try:
                    # Check if websocket is still open before sending
                    if (
                        hasattr(client, "client_state")
                        and client.client_state.value >= 2
                    ):
                        # Connection is closing or closed
                        failed_clients.append(session_id)
                        continue
                    await client.send_text(json.dumps(message, default=safe_json_serialize))
                except Exception as e:
                    self.logger.warning(f"Error sending to client {session_id}: {e}")
                    failed_clients.append(session_id)

            # Remove failed clients
            for session_id in failed_clients:
                if session_id in self.connected_clients:
                    del self.connected_clients[session_id]

        except Exception as e:
            self.logger.error(f"Error in broadcast_server_status: {e}")

    async def listen(self):
        """Start the server and listen for connections."""
        self.logger.info("Starting Brain FastAPI server")
        await self.start()

        # Start the FastAPI server with uvicorn
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info" if self.ws_settings.debug else "warning",
        )
        server = uvicorn.Server(config)

        try:
            self.logger.info(
                f"Brain FastAPI server running on ws://{self.host}:{self.port}"
            )
            await server.serve()
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        finally:
            await self.shutdown()

    async def start(self):
        """Initialize and start the server."""
        self.logger.info("Initializing application layer...")

        # Initialize app coordinator (which initializes agent engine and tool bridge)
        await self.app_handler.initialize()

        self.logger.info("Auto-connecting to built-in development servers...")

        # Connect to built-in MCP servers
        builtin_results = await self.mcp_client.auto_connect_builtin_servers()
        connected_builtin = sum(1 for success in builtin_results.values() if success)

        self.logger.info(
            f"Connected to {connected_builtin}/{len(builtin_results)} built-in servers"
        )

        # Connect to user-configured servers
        mcp_settings = self.load_mcp_settings()
        servers = mcp_settings.get("servers", [])

        if servers:
            self.logger.info(
                f"Connecting to {len(
                servers)} user-configured MCP servers"
            )

            for server in servers:
                server_id = server.get("id")
                server_config = server.get("config") or server.get("path")

                if server_id and server_config:
                    try:
                        self.logger.info(
                            f"Connecting to server {
                                         server_id}: {server_config}"
                        )
                        success = await self.mcp_client.connect_server(
                            server_id, server_config
                        )

                        if success:
                            self.logger.info(
                                f"Successfully connected to server {server_id}"
                            )
                        else:
                            self.logger.error(
                                f"Failed to connect to server {server_id}"
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Error connecting to server {server_id}: {e}"
                        )

        # Log server summary
        all_servers = await self.mcp_client.get_all_servers()
        self.logger.info("Brain initialization complete:")
        self.logger.info(f"  - Total MCP servers connected: {len(all_servers)}")
        for server_id, server_info in all_servers.items():
            self.logger.info(
                f"    • {server_id}: {
                             server_info['tools_count']} tools available"
            )

        self.logger.info(f"Brain server started with PID {os.getpid()}")

    async def shutdown(self):
        """Shutdown the server and cleanup resources."""
        self.logger.info("Shutting down Brain server...")
        try:
            if self.connected_clients:
                self.logger.info(
                    f"Closing {len(self.connected_clients)} connections..."
                )
                for session_id, client in list(self.connected_clients.items()):
                    try:
                        await client.close()
                    except:
                        pass
                self.connected_clients.clear()

            # Shutdown app coordinator
            await self.app_coordinator.shutdown()

            self.logger.info("Brain server shutdown completed")
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")


# Alias for backward compatibility
WebSocketServer = BrainServer
