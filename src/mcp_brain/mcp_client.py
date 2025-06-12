import os
import sys
import logging
from typing import Any, Dict, List, Optional, Union

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.types import Tool


class MCPClient:
    def __init__(self, engine: Optional[Any] = None, logger: Optional[logging.Logger] = None):
        self.engine = engine
        self.logger = logger or logging.getLogger("MCPClient")
        self._multi_server_client: Optional[MultiServerMCPClient] = None
        self.servers_config: Dict[str, Dict[str, Any]] = {}
        self.logger.info("MCPClient instance created.")

    async def _initialize_multi_server_client(self):
        if not self.servers_config:
            self.logger.warning("No MCP server configurations. MultiServerMCPClient will not be initialized.")
            self._multi_server_client = None
            return
        self.logger.info(f"Initializing MultiServerMCPClient with configurations: {self.servers_config}")
        self._multi_server_client = MultiServerMCPClient(self.servers_config)
        self.logger.info("MultiServerMCPClient initialized.")

    async def connect_server(self, server_id: str, server_config: Union[str, Dict[str, Any]]) -> bool:
        """
        Adds a server configuration and re-initializes the MultiServerMCPClient.

        Args:
            server_id: A unique identifier for the server.
            server_config: Configuration for the server. 
                           - For remote: URL string (e.g., "http://localhost:8000/mcp/").
                           - For local stdio: Path string (e.g., "/path/to/server_script.py") or 
                             a dict (e.g., {"command": "/path/to/venv/python", "args": ["/path/to/script.py"], "transport": "stdio"}).
        """
        self.logger.info(f"Attempting to connect server: {server_id} with config: {server_config}")
        try:
            parsed_config = self._parse_server_config(server_id, server_config)
            self.servers_config[server_id] = parsed_config
            self.logger.info(f"Server configuration for \t{server_id} parsed: {parsed_config}")

            await self._initialize_multi_server_client()

            if self._multi_server_client:
                async with self._multi_server_client.session(server_id) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                self.logger.info(f"Successfully connected to server \t{server_id}. Found {len(tools)} tools.")
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to server {server_id}: {e}", exc_info=True)
            if server_id in self.servers_config:
                del self.servers_config[server_id]
                await self._initialize_multi_server_client()
            return False

    def _parse_server_config(self, server_id: str, config: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        if isinstance(config, str):
            if config.startswith("http://") or config.startswith("https://"):
                self.logger.debug(f"Parsing \t{server_id} as remote HTTP server: {config}")

                return {"url": config, "transport": "streamable_http"}
            else:
                self.logger.debug(f"Parsing \t{server_id} as local stdio server (path): {config}")

                # Use sys.executable to ensure the correct Python interpreter from the venv
                return {"command": sys.executable, "args": [os.path.abspath(config)], "transport": "stdio", "env": {"PYTHONPATH": os.environ.get("PYTHONPATH", "")}} # Added PYTHONPATH to subprocess env
        elif isinstance(config, dict):
            if "transport" not in config:
                raise ValueError(f"Server config dictionary for {server_id} must specify a \'transport\' key.")

            if config["transport"] == "stdio" and config.get("command", "python") == "python":
                self.logger.debug(f"Updating stdio command for \t{server_id} to use sys.executable")
                config["command"] = sys.executable
                if "args" in config and isinstance(config["args"], list):
                    config["args"] = [os.path.abspath(arg) if isinstance(arg, str) and (arg.endswith(".py") or "/" in arg or "\\" in arg) else arg for arg in config["args"]]

            self.logger.debug(f"Parsing \t{server_id} as dictionary config: {config}")
            return config
        else:
            raise ValueError("Invalid server_config type. Must be a URL/path string or a dictionary.")

    async def list_tools(self, server_id: Optional[str] = None) -> List[Tool]:
        if not self._multi_server_client:
            self.logger.warning("MultiServerMCPClient not initialized. Cannot list tools.")
            return []

        self.logger.info(f"Listing tools for server: {server_id or 'all'}")
        try:
            if server_id:
                if server_id not in self.servers_config:
                    self.logger.error(f"Server \t{server_id} not found in configurations.")
                    return []
                async with self._multi_server_client.session(server_id) as session:
                    await session.initialize()
                    langchain_tools = await load_mcp_tools(session)
            else:
                langchain_tools = await self._multi_server_client.get_tools()

            # The tools returned by load_mcp_tools are LangChain Tool objects.
            # We need to ensure they are compatible with mcp.types.Tool or convert them.
            # For now, we assume they have .name and .description attributes.
            # A more robust solution might involve creating mcp.types.Tool instances.
            mcp_tools: List[Tool] = []
            for lc_tool in langchain_tools:
                # FIX: Handle cases where lc_tool.args_schema might be a dict or a Pydantic model
                input_schema = {}
                if lc_tool.args_schema:
                    if isinstance(lc_tool.args_schema, dict):
                        input_schema = lc_tool.args_schema
                    else:
                        # Try Pydantic v2 first, then v1
                        try:
                            input_schema = lc_tool.args_schema.model_json_schema()
                        except AttributeError:
                            input_schema = lc_tool.args_schema.schema()

                mcp_tools.append(Tool(name=lc_tool.name, description=lc_tool.description, inputSchema=input_schema))

            self.logger.info(f"Found {len(mcp_tools)} tools for server: {server_id}")
            return mcp_tools
        except Exception as e:
            self.logger.error(f"Error listing tools for server {server_id}: {e}", exc_info=True)
            return []

    async def call_tool(self, server_id: str, tool_name: str, parameters: Dict[str, Any], session: Any) -> Any:
        if not session:
            self.logger.error("MCP session not provided. Cannot call tool.")
            raise RuntimeError("MCP session not provided.")

        self.logger.info(f"Calling tool {tool_name} on server {server_id} with parameters: {parameters}")
        try:
            all_lc_tools = await load_mcp_tools(session)
            target_lc_tool = next((tool for tool in all_lc_tools if tool.name == tool_name), None)

            if not target_lc_tool:
                self.logger.error(f"Tool {tool_name} not found on server {server_id}.")
                raise ValueError(f"Tool {tool_name} not found on server {server_id}.")

            # LangChain tools are callable; use ainvoke for async execution.
            result = await target_lc_tool.ainvoke(parameters)
            self.logger.info(f"Tool \t{tool_name} executed successfully. Result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name}: {e}", exc_info=True)
            raise

    async def _format_tools_for_llm(self) -> List[Dict[str, Any]]:
        available_tools = []

        if not self._multi_server_client:
            self.logger.warning("MultiServerMCPClient not initialized. No tools available.")
            return []

        try:
            mcp_tools_response = await self._multi_server_client.get_tools()
            for tool in mcp_tools_response:
                input_schema = {}
                if tool.args_schema:
                    if isinstance(tool.args_schema, dict):
                        input_schema = tool.args_schema
                    else:
                        try:
                            input_schema = tool.args_schema.model_json_schema()
                        except AttributeError:
                            input_schema = tool.args_schema.schema()
                available_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": input_schema
                })
            self.logger.info(f"Retrieved {len(available_tools)} tools for query processing.")
        except Exception as e:
            self.logger.error(f"Error retrieving tools for query processing: {e}", exc_info=True)
        return available_tools

    async def _execute_tool_and_update_history(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any], 
        tool_use_id: str, 
        session: Any, 
        messages: List[Dict[str, Any]],
        final_text_output: List[str]
    ):
        try:
            tool_result = await self.call_tool("exa", tool_name, tool_args, session)
            self.logger.info(f"Tool {tool_name} executed. Result: {tool_result}")
            final_text_output.append(f"[Tool Result: {tool_result}]")
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": str(tool_result)
                    }
                ]
            })
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            final_text_output.append(f"[Error executing tool {tool_name}: {e}]")
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": f"Error: {e}"
                    }
                ]
            })

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        self.logger.info(f"Processing query: {query}")

        if not self.engine:
            self.logger.error("LLM Engine not provided to MCPClient. Cannot process query.")
            return "Error: LLM Engine not configured."

        available_tools_for_llm = await self._format_tools_for_llm()

        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        final_text_output = [] # To accumulate the final text response
        # Establish a persistent session for the duration of the query processing
        # Assuming 'exa' is the server_id for tool calls. Adjust if multiple servers are used.
        session = None
        if self._multi_server_client and 'exa' in self.servers_config:
            async with self._multi_server_client.session('exa') as current_session:
                session = current_session
                await session.initialize()

                try:
                    while True:
                        response = self.engine.client.messages.create(
                            model=self.engine.llm_model,
                            max_tokens=self.engine.max_tokens,
                            messages=messages,
                            tools=available_tools_for_llm
                        )

                        tool_use_occurred = False
                        current_turn_content = []

                        for content_block in response.content:
                            if content_block.type == 'text':
                                current_turn_content.append(content_block)
                                final_text_output.append(content_block.text)
                            elif content_block.type == 'tool_use':
                                tool_use_occurred = True
                                tool_name = content_block.name
                                tool_args = content_block.input
                                tool_use_id = content_block.id

                                self.logger.info(f"LLM requested tool: {tool_name} with args: {tool_args}")
                                final_text_output.append(f"[LLM requested tool: {tool_name} with args: {tool_args}]")

                                # Append the tool_use block to the current turn's content
                                current_turn_content.append(content_block)

                                # Add the assistant's message (text + tool_use) to the conversation history
                                messages.append({
                                    "role": "assistant",
                                    "content": current_turn_content
                                })

                                await self._execute_tool_and_update_history(tool_name, tool_args, tool_use_id, session, messages, final_text_output)

                                # Clear current_turn_content as it's been added to messages
                                current_turn_content = []

                        if not tool_use_occurred:
                            # If no tool use occurred, and there's accumulated text, add it as the final assistant message
                            if current_turn_content:
                                messages.append({
                                    "role": "assistant",
                                    "content": current_turn_content
                                })
                            break
                except Exception as e:
                    self.logger.error(f"Error during query processing: {e}", exc_info=True)
                    final_text_output.append(f"Error during query processing: {e}")
        else:
            self.logger.warning("No 'exa' server configured or MultiServerMCPClient not initialized. Proceeding without tool execution.")
            # If no session is established, proceed with LLM call without tools
            response = self.engine.client.messages.create(
                model=self.engine.llm_model,
                max_tokens=self.engine.max_tokens,
                messages=messages,
                tools=[] # No tools available
            )
            for content_block in response.content:
                if content_block.type == 'text':
                    final_text_output.append(content_block.text)
                    messages.append({
                        "role": "assistant",
                        "content": content_block.text
                    })

        return "\n".join(final_text_output)

    async def get_server_info(self, server_id: str) -> Optional[Dict[str, Any]]:
        if server_id not in self.servers_config:
            self.logger.warning(f"Server \t{server_id} not found in configurations.")
            return None

        config = self.servers_config[server_id]
        tools = await self.list_tools(server_id) # This returns mcp.types.Tool

        info = {
            "id": server_id,
            "type": "local" if config.get("transport") == "stdio" else "remote",
            "config": config, # Return the parsed config
            "tools_count": len(tools),
            "tools": [{"name": tool.name, "description": tool.description} for tool in tools]
        }
        return info

    async def get_all_servers(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for server_id in self.servers_config.keys():
            server_info = await self.get_server_info(server_id)
            if server_info:
                result[server_id] = server_info
        return result

    async def cleanup(self):
        """Cleans up all connected MCP servers."""
        if self._multi_server_client:
            await self._multi_server_client.cleanup()
            self.logger.info("Cleaned up MultiServerMCPClient.")


# # Example usage (for testing purposes)
# async def main_test():
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     logger = logging.getLogger("MCPClientTest")
#
#     # Create a dummy engine (replace with your actual AnthropicEngine instance)
#     class DummyEngine(BaseEngine):
#         def __init__(self):
#             self.client = None # Mock client for testing
#             self.llm_model = "dummy-model"
#             self.max_tokens = 1000
#
#         async def stream_response(self, query: str) -> AsyncGenerator[Dict[str, Any], None]:
#             yield {"event": "token", "data": "Dummy stream response"}
#
#         async def get_response(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
#             # Mock LLM response for testing tool calling
#             if "web_search_exa" in messages[-1]["content"]:
#                 return {"answer": "I used web_search_exa. The capital of France is Paris."}
#             return {"answer": "Dummy response: " + messages[-1]["content"]}
#
#     engine = DummyEngine()
#     client = MCPClient(engine=engine, logger=logger)
#
#     # Create a dummy local server script for testing
#     math_server_script = """
# #!/usr/bin/env python3
# import asyncio
# import sys
# from mcp.server.fastmcp import FastMCP
# from mcp.shared.types import Tool
#
# class MathServer:
#     def __init__(self):
#         self.tools = [
#             Tool(
#                 name="add",
#                 description="Adds two numbers",
#                 inputSchema={
#                     "type": "object",
#                     "properties": {
#                         "a": {"type": "number"},
#                         "b": {"type": "number"}
#                     },
#                     "required": ["a", "b"]
#                 }
#             ),
#             Tool(
#                 name="subtract",
#                 description="Subtracts two numbers",
#                 inputSchema={
#                     "type": "object",
#                     "properties": {
#                         "a": {"type": "number"},
#                         "b": {"type": "number"}
#                     },
#                     "required": ["a", "b"]
#                 }
#             )
#         ]
#
#     async def add(self, a: float, b: float) -> float:
#         return a + b
#
#     async def subtract(self, a: float, b: float) -> float:
#         return a - b
#
#     async def get_tools(self):
#         return self.tools
#
#     async def call_tool(self, tool_name: str, arguments: dict):
#         if tool_name == "add":
#             return await self.add(**arguments)
#         elif tool_name == "subtract":
#             return await self.subtract(**arguments)
#         else:
#             raise ValueError(f"Unknown tool: {tool_name}")
#
# async def main():
#     server = MathServer()
#     mcp = FastMCP(server)
#     await mcp.run_stdio_async()
#
# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print("\nMath server stopped.", file=sys.stderr)
#
# """
#     with open("math_server.py", "w") as f:
#         f.write(math_server_script)
#     os.chmod("math_server.py", 0o755)
#     logger.info("Created dummy math_server.py")
#
#     # Connect to a local stdio server
#     connect_success = await client.connect_server("math_local", "./math_server.py")
#     logger.info(f"Connection to math_local successful: {connect_success}")
#
#     # List tools from the local server
#     tools = await client.list_tools("math_local")
#     logger.info(f"Tools from math_local: {[tool.name for tool in tools]}")
#
#     # Call a tool on the local server
#     if tools:
#         try:
#             add_result = await client.call_tool("math_local", "add", {"a": 5, "b": 3})
#             logger.info(f"Result of add(5, 3): {add_result}")
#         except Exception as e:
#             logger.error(f"Error calling add tool: {e}")
#
#     # Test processing a query that might involve tool use (requires a real LLM engine)
#     # For this dummy engine, it will just return a dummy response.
#     query_result = await client.process_query("What is 5 plus 3?")
#     logger.info(f"Query result: {query_result}")
#
#     # Test connecting to a (dummy) remote server
#     # In a real test, you would need a running remote MCP server.
#     # For this example, we\'ll just add the config and expect listing tools to fail gracefully.
#     remote_connect_success = await client.connect_server("dummy_remote", "http://localhost:12345/mcp/")
#     logger.info(f"Connection attempt to dummy_remote: {remote_connect_success}") # Expected to be True if config is added
#
#     remote_tools = await client.list_tools("dummy_remote") # Expected to be empty or fail gracefully
#     logger.info(f"Tools from dummy_remote: {[tool.name for tool in remote_tools]}")
#
#     all_servers_info_after_remote = await client.get_all_servers()
#     logger.info(f"All servers info after remote: {all_servers_info_after_remote}")
#
#     # Test disconnect
#     await client.disconnect_server("math_local")
#     all_servers_info_after_disconnect = await client.get_all_servers()
#     logger.info(f"All servers info after disconnect: {all_servers_info_after_disconnect}")
#
#     await client.cleanup()
#     os.remove("math_server.py")
#     logger.info("Cleaned up dummy math_server.py")
#
# if __name__ == "__main__":
#     # This is for standalone testing of the client.
#     # Ensure you have langchain_mcp_adapters and mcp installed.
#     # pip install langchain-mcp-adapters mcp
#     asyncio.run(main_test())
#
#
