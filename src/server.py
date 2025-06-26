"""
Brain WebSocket Server

Simplified WebSocket server that integrates the application layer,
providing real-time communication for agent-based query processing
and tool execution.
"""

import os
import json
import asyncio
import websockets
import uuid

from pathlib import Path
from typing import Optional, Dict, Any

from tools.client import MCPClient
from agent.engine import AgentEngine
from app.coordinator import AppCoordinator
from app.streaming import WebSocketAppIntegration
from app.session import SessionManager


class WSSettings:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3789,
        mcp_file_path: Path = None,
        log_file: Optional[Path] = None,
        debug: bool = False
    ):
        self.host = host
        self.port = port
        self.mcp_file_path = mcp_file_path
        self.log_file = log_file
        self.debug = debug


class BrainServer:
    """
    Brain WebSocket server with integrated application layer.

    Provides real-time communication for multi-agent query processing,
    tool execution, and session management.
    """

    def __init__(self, logger, settings, ws_settings, engine):
        self.logger = logger
        self.settings = settings
        self.ws_settings = ws_settings
        self.engine = engine

        self.host = ws_settings.host
        self.port = ws_settings.port
        self.mcp_file_path = ws_settings.mcp_file_path

        self.server = None

        # Initialize MCP client for tool access
        self.mcp_client = MCPClient(self.engine, logger=self.logger)

        # Initialize agent engine with config
        # Create models map from settings
        models_config = {
            "planning": f"{settings.engine_type}:{settings.anthropic_llm_model if settings.engine_type == 'anthropic' else settings.openai_llm_model}",
            "orchestrator": f"{settings.engine_type}:{settings.anthropic_llm_model if settings.engine_type == 'anthropic' else settings.openai_llm_model}",
            "execution": f"{settings.engine_type}:{settings.anthropic_llm_model if settings.engine_type == 'anthropic' else settings.openai_llm_model}"
        }

        api_key = settings.anthropic_api_key if settings.engine_type == 'anthropic' else settings.openai_api_key

        self.agent_engine = AgentEngine(
            default_models=models_config,
            api_key=api_key,
            logger=self.logger
        )
        self.app_coordinator = AppCoordinator(
            agent_engine=self.agent_engine,
            tool_client=self.mcp_client,
            logger=self.logger
        )

        # Initialize session management
        self.session_manager = SessionManager(logger=self.logger)

        # Initialize WebSocket app integration
        self.app_integration = WebSocketAppIntegration(
            app_coordinator=self.app_coordinator,
            logger=self.logger
        )

        self.connected_clients = set()

    def load_mcp_settings(self):
        """Load MCP server settings from file."""
        if not self.mcp_file_path.exists():
            default_settings = {
                "servers": []
            }
            with open(self.mcp_file_path, 'w') as f:
                json.dump(default_settings, f, indent=2)
            return default_settings

        try:
            with open(self.mcp_file_path, 'r') as f:
                settings = json.load(f)
            return settings
        except Exception as e:
            self.logger.error(f"Error loading MCP settings: {e}")
            return {"servers": []}

    async def websocket_handler(self, websocket):
        """Handle WebSocket connections with session management."""
        self.connected_clients.add(websocket)
        session_id = str(uuid.uuid4())

        try:
            # Create session for this connection
            session = await self.session_manager.create_session({
                "websocket_connection": True,
                "remote_address": str(websocket.remote_address) if websocket.remote_address else "unknown"
            })
            session_id = session.session_id

            # Send initial status
            servers_info = await self.mcp_client.get_all_servers()
            await websocket.send(json.dumps({
                "type": "status",
                "session_id": session_id,
                "servers": servers_info
            }))

            async for message in websocket:
                try:
                    data = json.loads(message)
                    # Ensure session ID is included
                    data["session_id"] = session_id
                    await self.process_command(websocket, data)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "session_id": session_id,
                        "error": "Invalid JSON message"
                    }))
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "session_id": session_id,
                        "error": str(e)
                    }))
        except websockets.exceptions.ConnectionClosed:
            # normal client disconnect
            pass
        except Exception:
            # catch everything else and log the stack trace
            self.logger.exception("Unhandled error in websocket_handler")
        finally:
            self.connected_clients.discard(websocket)
            # Clean up session
            if session_id:
                await self.session_manager.cancel_session(session_id)

    async def process_command(self, websocket, data):
        """Process incoming WebSocket commands."""
        command = data.get("command")
        session_id = data.get("session_id", "unknown")

        if not command:
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": "Missing command"
            }))
            return

        # Try app integration commands first (agent queries, tool execution, etc.)
        handled = await self.app_integration.handle_app_command(websocket, data)
        if handled:
            return

        # Fall back to legacy MCP commands for backward compatibility
        if command == "connect_server":
            await self.handle_connect_server(websocket, data)
        elif command == "list_tools":
            await self.handle_list_tools(websocket, data)
        elif command == "query":
            await self.handle_legacy_query(websocket, data)
        elif command == "get_servers":
            await self.handle_get_servers(websocket, data)
        elif command == "get_all_tools":
            await self.handle_get_all_tools(websocket, data)
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": f"Unknown command: {command}"
            }))

    async def handle_connect_server(self, websocket, data):
        """Handle MCP server connection requests."""
        server_id = data.get("server_id")
        server_config = data.get("server_config") or data.get("server_path")
        session_id = data.get("session_id", "unknown")

        if not server_id or not server_config:
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": "Missing server_id or server_config"
            }))
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

                with open(self.mcp_file_path, 'w') as f:
                    json.dump(mcp_settings, f, indent=2)

                await websocket.send(json.dumps({
                    "type": "server_connected",
                    "session_id": session_id,
                    "server": server_info
                }))

                await self.broadcast_server_status()
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "session_id": session_id,
                    "error": f"Failed to connect to server {server_id}"
                }))
        except Exception as e:
            self.logger.error(f"Error connecting to server: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": str(e)
            }))

    async def handle_list_tools(self, websocket, data):
        """Handle tool listing requests."""
        server_id = data.get("server_id")
        session_id = data.get("session_id", "unknown")

        if not server_id:
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": "Missing server_id"
            }))
            return

        try:
            tools = await self.mcp_client.list_tools(server_id)

            await websocket.send(json.dumps({
                "type": "tools_list",
                "session_id": session_id,
                "server_id": server_id,
                "tools": [{"name": tool.name, "description": tool.description} for tool in tools]
            }))
        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": str(e)
            }))

    async def handle_legacy_query(self, websocket, data):
        """Handle legacy query processing (direct MCP client)."""
        query = data.get("query")
        session_id = data.get("session_id", "unknown")
        working_directory = data.get("working_directory")

        if not query:
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": "Missing query"
            }))
            return

        try:
            async def progress_callback(progress_data):
                # Handle different types of progress updates
                if progress_data.get("type") == "tool_execution_started":
                    await websocket.send(json.dumps({
                        "type": "tool_execution_started",
                        "session_id": session_id,
                        "tool_name": progress_data.get("tool_name"),
                        "parameters": progress_data.get("parameters", {})
                    }))
                elif progress_data.get("type") == "tool_execution_completed":
                    await websocket.send(json.dumps({
                        "type": "tool_execution_completed",
                        "session_id": session_id,
                        "tool_name": progress_data.get("tool_name"),
                        "success": progress_data.get("success", True),
                        "result": progress_data.get("result"),
                        "error": progress_data.get("error"),
                        "execution_time_seconds": progress_data.get("execution_time_seconds", 0)
                    }))
                elif progress_data.get("type") == "intermediate_reasoning":
                    await websocket.send(json.dumps({
                        "type": "intermediate_reasoning",
                        "session_id": session_id,
                        "message": progress_data.get("message")
                    }))
                else:
                    # Regular thinking/progress message
                    message = {
                        "type": "thinking",
                        "session_id": session_id,
                        "message": self._format_progress_message(progress_data),
                        "metrics": progress_data
                    }

                    # Add agent context if available
                    if "agent_type" in progress_data:
                        message["agent"] = progress_data["agent_type"]

                    await websocket.send(json.dumps(message))

            await websocket.send(json.dumps({
                "type": "thinking",
                "session_id": session_id,
                "message": "Starting query processing...",
                "metrics": {"elapsed_time": 0, "estimated_input_tokens": 0, "tool_calls_completed": 0, "total_tool_calls": 0}
            }))

            response = await self.mcp_client.process_query(query, progress_callback, working_directory)

            self.logger.debug(f"Query response: {response}")

            await websocket.send(json.dumps({
                "type": "query_response",
                "session_id": session_id,
                "query": query,
                "response": response
            }))
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": str(e)
            }))

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

    async def handle_get_servers(self, websocket, data):
        """Handle server list requests."""
        session_id = data.get("session_id", "unknown")

        try:
            servers_info = await self.mcp_client.get_all_servers()

            await websocket.send(json.dumps({
                "type": "servers_list",
                "session_id": session_id,
                "servers": servers_info
            }))
        except Exception as e:
            self.logger.error(f"Error getting servers: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": str(e)
            }))

    async def handle_get_all_tools(self, websocket, data):
        """Handle all tools overview requests."""
        session_id = data.get("session_id", "unknown")

        try:
            tools_by_server = await self.mcp_client.get_all_available_tools()

            await websocket.send(json.dumps({
                "type": "tools_overview",
                "session_id": session_id,
                "tools": tools_by_server
            }))
        except Exception as e:
            self.logger.error(f"Error getting all tools: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": str(e)
            }))

    async def broadcast_server_status(self):
        """Broadcast server status to all connected clients."""
        if not self.connected_clients:
            return

        try:
            servers_info = await self.mcp_client.get_all_servers()
            message = json.dumps({
                "type": "servers_update",
                "servers": servers_info
            })

            # Send to all clients
            failed_clients = []
            for client in self.connected_clients:
                try:
                    await client.send(message)
                except websockets.exceptions.ConnectionClosed:
                    failed_clients.append(client)
                except Exception as e:
                    self.logger.warning(f"Error sending to client: {e}")
                    failed_clients.append(client)

            # Remove failed clients
            for client in failed_clients:
                self.connected_clients.discard(client)

        except Exception as e:
            self.logger.error(f"Error in broadcast_server_status: {e}")

    async def listen(self):
        """Start the server and listen for connections."""
        self.logger.info("Starting Brain server")
        await self.start()
        try:
            self.logger.info("Server running. Press Ctrl+C to exit.")
            # Just wait indefinitely - KeyboardInterrupt will break this
            while True:
                await asyncio.sleep(1)
        finally:
            await self.shutdown()

    async def start(self):
        """Initialize and start the server."""
        self.logger.info("Initializing application layer...")

        # Initialize app coordinator (which initializes agent engine and tool bridge)
        await self.app_integration.initialize()

        self.logger.info("Auto-connecting to built-in development servers...")

        # Connect to built-in MCP servers
        builtin_results = await self.mcp_client.auto_connect_builtin_servers()
        connected_builtin = sum(
            1 for success in builtin_results.values() if success)

        self.logger.info(
            f"Connected to {connected_builtin}/{len(builtin_results)} built-in servers")

        # Connect to user-configured servers
        mcp_settings = self.load_mcp_settings()
        servers = mcp_settings.get("servers", [])

        if servers:
            self.logger.info(f"Connecting to {len(
                servers)} user-configured MCP servers")

            for server in servers:
                server_id = server.get("id")
                server_config = server.get("config") or server.get("path")

                if server_id and server_config:
                    try:
                        self.logger.info(f"Connecting to server {
                                         server_id}: {server_config}")
                        success = await self.mcp_client.connect_server(server_id, server_config)

                        if success:
                            self.logger.info(
                                f"Successfully connected to server {server_id}")
                        else:
                            self.logger.error(
                                f"Failed to connect to server {server_id}")
                    except Exception as e:
                        self.logger.error(
                            f"Error connecting to server {server_id}: {e}")

        # Log server summary
        all_servers = await self.mcp_client.get_all_servers()
        self.logger.info("Brain initialization complete:")
        self.logger.info(
            f"  - Total MCP servers connected: {len(all_servers)}")
        for server_id, server_info in all_servers.items():
            self.logger.info(f"    • {server_id}: {
                             server_info['tools_count']} tools available")

        # Start WebSocket server
        self.logger.info(
            f"Starting websocket server at ws://{self.host}:{self.port}")
        self.server = await websockets.serve(self.websocket_handler, self.host, self.port)
        self.logger.info(f"Brain server started with PID {os.getpid()}")
        return self.server

    async def shutdown(self):
        """Shutdown the server and cleanup resources."""
        self.logger.info("Shutting down Brain server...")
        try:
            if hasattr(self, 'server') and self.server:
                self.logger.info("Closing websocket server...")
                self.server.close()
                await self.server.wait_closed()

            if self.connected_clients:
                self.logger.info(
                    f"Closing {len(self.connected_clients)} connections...")
                for client in list(self.connected_clients):
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
