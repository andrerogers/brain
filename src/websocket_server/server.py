import os
import json
import asyncio
import websockets

from pathlib import Path
from typing import Optional

from mcp_brain.mcp_client import MCPClient


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


class WebSocketServer:
    def __init__(self, logger, settings, ws_settings, engine):
        self.logger = logger
        self.settings = settings
        self.ws_settings = ws_settings
        self.engine = engine

        self.host = ws_settings.host
        self.port = ws_settings.port
        self.mcp_file_path = ws_settings.mcp_file_path

        self.server = None
        self.mcp_client = MCPClient(self.engine, logger=self.logger)

        self.connected_clients = set()

    def load_mcp_settings(self):
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
        self.connected_clients.add(websocket)

        try:
            servers_info = await self.mcp_client.get_all_servers()
            await websocket.send(json.dumps({
                "type": "status",
                "servers": servers_info
            }))

            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_command(websocket, data)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "Invalid JSON message"
                    }))
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
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

    async def process_command(self, websocket, data):
        command = data.get("command")

        if not command:
            await websocket.send(json.dumps({
                "type": "error",
                "error": "Missing command"
            }))
            return

        if command == "connect_server":
            await self.handle_connect_server(websocket, data)
        elif command == "list_tools":
            await self.handle_list_tools(websocket, data)
        elif command == "query":
            await self.handle_query(websocket, data)
        elif command == "get_servers":
            await self.handle_get_servers(websocket, data)
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "error": f"Unknown command: {command}"
            }))

    async def listen(self):
        self.logger.info("Starting daemon")
        await self.start()
        try:
            self.logger.info("Server running. Press Ctrl+C to exit.")
            # Just wait indefinitely - KeyboardInterrupt will break this
            while True:
                await asyncio.sleep(1)
        finally:
            await self.shutdown()

    async def handle_connect_server(self, websocket, data):
        server_id = data.get("server_id")
        server_config = data.get("server_config")  # Changed from server_path

        if not server_config and data.get("server_path"):
            server_config = data.get("server_path")

        if not server_id or not server_config:
            await websocket.send(json.dumps({
                "type": "error",
                "error": "Missing server_id or server_config"
            }))
            return

        try:
            success = await self.mcp_client.connect_server(server_id, server_config)

            if success:
                server_info = await self.mcp_client.get_server_info(server_id)

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
                    "server": server_info
                }))

                await self.broadcast_server_status()
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "error": f"Failed to connect to server {server_id}"
                }))
        except Exception as e:
            self.logger.error(f"Error connecting to server: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "error": str(e)
            }))

    async def handle_list_tools(self, websocket, data):
        server_id = data.get("server_id")

        if not server_id:
            await websocket.send(json.dumps({
                "type": "error",
                "error": "Missing server_id"
            }))
            return

        try:
            tools = await self.mcp_client.list_tools(server_id)

            await websocket.send(json.dumps({
                "type": "tools_list",
                "server_id": server_id,
                "tools": [{"name": tool.name, "description": tool.description} for tool in tools]
            }))
        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "error": str(e)
            }))

    async def handle_query(self, websocket, data):
        query = data.get("query")

        if not query:
            await websocket.send(json.dumps({
                "type": "error",
                "error": "Missing query"
            }))
            return

        try:
            await websocket.send(json.dumps({
                "type": "thinking",
                "message": "Processing query..."
            }))

            response = await self.mcp_client.process_query(query)

            self.logger.debug(f"Query response: {response}")

            await websocket.send(json.dumps({
                "type": "query_response",
                "query": query,
                "response": response
            }))
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "error": str(e)
            }))

    async def handle_get_servers(self, websocket, data):
        try:
            servers_info = await self.mcp_client.get_all_servers()

            await websocket.send(json.dumps({
                "type": "servers_list",
                "servers": servers_info
            }))
        except Exception as e:
            self.logger.error(f"Error getting servers: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "error": str(e)
            }))

    async def broadcast_server_status(self):
        if not self.connected_clients:
            return

        try:
            # Try to get server info safely
            try:
                servers_info = await self.mcp_client.get_all_servers()
            except Exception as e:
                print(f"Error getting server info: {e}")
                servers_info = {}  # Use empty dict on error

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
                    print(f"Error sending to client: {e}")
                    failed_clients.append(client)

            # Remove failed clients
            for client in failed_clients:
                self.connected_clients.remove(client)
        except Exception as e:
            print(f"Error in broadcast_server_status: {e}")
            import traceback
            print(traceback.format_exc())

    async def start(self):
        # First, auto-connect to built-in development servers
        self.logger.info("Auto-connecting to built-in development servers...")
        builtin_results = await self.mcp_client.auto_connect_builtin_servers()
        
        connected_builtin = sum(1 for success in builtin_results.values() if success)
        self.logger.info(f"Connected to {connected_builtin}/{len(builtin_results)} built-in servers")
        
        # Then connect to user-configured servers
        mcp_settings = self.load_mcp_settings()
        servers = mcp_settings.get("servers", [])

        if servers:
            self.logger.info(f"Connecting to {len(servers)} user-configured MCP servers")

            for server in servers:
                server_id = server.get("id")
                # Support both old format (path) and new format (config)
                server_config = server.get("config") or server.get("path")

                if server_id and server_config:
                    try:
                        self.logger.info(f"Connecting to server {server_id}: {server_config}")
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

        # Log final server status
        all_servers = await self.mcp_client.get_all_servers()
        self.logger.info(f"Brain initialization complete:")
        self.logger.info(f"  - Total MCP servers connected: {len(all_servers)}")
        for server_id, server_info in all_servers.items():
            self.logger.info(f"    • {server_id}: {server_info['tools_count']} tools available")
        
        self.logger.info(f"Starting websocket server at ws://{self.host}:{self.port}")
        server = await websockets.serve(self.websocket_handler, self.host, self.port)
        self.logger.info(f"Brain started with PID {os.getpid()}")
        return server

    async def shutdown(self):
        self.logger.info("Shutting down...")
        try:
            if hasattr(self, 'server') and self.server:
                self.logger.info("Closing websocket server...")
                self.server.close()
                await self.server.wait_closed()
            if self.connected_clients:
                self.logger.info(f"Closing {len(self.connected_clients)} connections...")
                for client in list(self.connected_clients):
                    try:
                        await client.close()
                    except:
                        pass
                self.connected_clients.clear()
            self.logger.info("......")
        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")
