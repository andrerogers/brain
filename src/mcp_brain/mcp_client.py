import os
import sys
import re
import logging
from typing import Any, Dict, List, Optional, Union, Set
from pathlib import Path

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
        
        # Built-in server configurations for development tools
        self.builtin_servers = {
            "filesystem": {
                "path": self._get_server_path("filesystem_server.py"),
                "description": "File system operations (read, write, edit, list, search)"
            },
            "git": {
                "path": self._get_server_path("git_server.py"),
                "description": "Git operations (status, diff, commit, log, branches)"
            },
            "codebase": {
                "path": self._get_server_path("codebase_server.py"),
                "description": "Codebase analysis (project structure, find definitions/references)"
            },
            "devtools": {
                "path": self._get_server_path("devtools_server.py"),
                "description": "Development tools (run tests, lint, format, type check)"
            }
        }

    def _get_server_path(self, server_file: str) -> str:
        """Get the absolute path to a built-in server"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "servers", server_file)

    async def auto_connect_builtin_servers(self) -> Dict[str, bool]:
        """Automatically connect to built-in development servers"""
        results = {}
        
        for server_id, server_info in self.builtin_servers.items():
            server_path = server_info["path"]
            
            if os.path.exists(server_path):
                self.logger.info(f"Auto-connecting to built-in server: {server_id}")
                success = await self.connect_server(server_id, server_path)
                results[server_id] = success
                
                if success:
                    self.logger.info(f"Successfully connected to {server_id} server")
                else:
                    self.logger.warning(f"Failed to connect to {server_id} server")
            else:
                self.logger.warning(f"Built-in server not found: {server_path}")
                results[server_id] = False
        
        return results

    def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyze query to determine which servers/tools might be needed
        """
        query_lower = query.lower()
        intent = {
            "servers_needed": set(),
            "operation_type": "general",
            "specific_tools": [],
            "context_clues": []
        }

        # File operations patterns
        file_patterns = [
            r'\b(read|view|show|cat)\s+(?:file\s+)?[\w\./]+',
            r'\b(write|save|create)\s+(?:file\s+)?[\w\./]+',
            r'\b(edit|modify|change)\s+(?:file\s+)?[\w\./]+',
            r'\b(list|ls|dir)\s+',
            r'\b(search|find|grep)\s+',
            r'\bfile\b', r'\bdirectory\b', r'\bfolder\b'
        ]
        
        if any(re.search(pattern, query_lower) for pattern in file_patterns):
            intent["servers_needed"].add("filesystem")
            intent["operation_type"] = "file_operation"

        # Git operations patterns
        git_patterns = [
            r'\bgit\s+', r'\bcommit\b', r'\bdiff\b', r'\bstatus\b',
            r'\bbranch\b', r'\bhistory\b', r'\blog\b', r'\bstage\b',
            r'\badd\b.*\bfile', r'\bversion\s+control\b'
        ]
        
        if any(re.search(pattern, query_lower) for pattern in git_patterns):
            intent["servers_needed"].add("git")
            intent["operation_type"] = "git_operation"

        # Codebase analysis patterns
        codebase_patterns = [
            r'\bproject\s+structure\b', r'\barchitecture\b', r'\bcodebase\b',
            r'\bfind\s+definition\b', r'\bfind\s+references\b', r'\banalyze\b',
            r'\bexplain\s+(?:this\s+)?(?:project|code)\b', r'\bwhere\s+is\b',
            r'\bclass\s+\w+', r'\bfunction\s+\w+', r'\bmethod\s+\w+'
        ]
        
        if any(re.search(pattern, query_lower) for pattern in codebase_patterns):
            intent["servers_needed"].add("codebase")
            intent["operation_type"] = "codebase_analysis"

        # Development tools patterns
        devtools_patterns = [
            r'\brun\s+tests?\b', r'\btest\s+', r'\blint\b', r'\bformat\b',
            r'\btype\s+check\b', r'\binstall\b.*\bdependencies\b',
            r'\bbuild\b', r'\bcompile\b', r'\bdebug\b'
        ]
        
        if any(re.search(pattern, query_lower) for pattern in devtools_patterns):
            intent["servers_needed"].add("devtools")
            intent["operation_type"] = "development_task"

        # If no specific patterns match but contains development keywords
        dev_keywords = [
            'fix', 'bug', 'error', 'issue', 'implement', 'refactor',
            'optimize', 'debug', 'solve', 'problem'
        ]
        
        if intent["operation_type"] == "general" and any(keyword in query_lower for keyword in dev_keywords):
            # Might need multiple servers for complex development tasks
            intent["servers_needed"].update(["filesystem", "git", "codebase"])
            intent["operation_type"] = "development_assistance"

        return intent

    def enhance_query_with_context(self, query: str, intent: Dict[str, Any]) -> str:
        """
        Enhance the query with context about available tools and servers
        """
        if intent["operation_type"] == "general":
            return query

        enhanced_query = f"""Development Assistant Query: {query}

Available development tools:"""

        if "filesystem" in intent["servers_needed"]:
            enhanced_query += """
- File Operations: read_file, write_file, edit_file, list_directory, search_files, create_directory"""

        if "git" in intent["servers_needed"]:
            enhanced_query += """
- Git Operations: git_status, git_diff, git_log, git_add, git_commit, git_branch_info"""

        if "codebase" in intent["servers_needed"]:
            enhanced_query += """
- Codebase Analysis: analyze_project, get_project_structure, find_definition, find_references, explain_codebase"""

        if "devtools" in intent["servers_needed"]:
            enhanced_query += """
- Development Tools: run_tests, lint_code, format_code, check_types, install_dependencies"""

        enhanced_query += """

Instructions: Use the appropriate tools to help with this development task. Provide clear, actionable responses."""

        return enhanced_query

    async def _initialize_multi_server_client(self):
        if not self.servers_config:
            self.logger.warning("No MCP server configurations. MultiServerMCPClient will not be initialized.")
            self._multi_server_client = None
            return
            
        self.logger.info(f"Initializing MultiServerMCPClient with {len(self.servers_config)} servers")
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
            self.logger.info(f"Server configuration for {server_id} parsed: {parsed_config}")

            await self._initialize_multi_server_client()

            if self._multi_server_client:
                async with self._multi_server_client.session(server_id) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                self.logger.info(f"Successfully connected to server {server_id}. Found {len(tools)} tools.")
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
                self.logger.debug(f"Parsing {server_id} as remote HTTP server: {config}")
                return {"url": config, "transport": "streamable_http"}
            else:
                self.logger.debug(f"Parsing {server_id} as local stdio server (path): {config}")
                return {
                    "command": sys.executable, 
                    "args": [os.path.abspath(config)], 
                    "transport": "stdio", 
                    "env": {"PYTHONPATH": os.environ.get("PYTHONPATH", "")}
                }
        elif isinstance(config, dict):
            if "transport" not in config:
                raise ValueError(f"Server config dictionary for {server_id} must specify a \'transport\' key.")

            if config["transport"] == "stdio" and config.get("command", "python") == "python":
                self.logger.debug(f"Updating stdio command for {server_id} to use sys.executable")
                config["command"] = sys.executable
                if "args" in config and isinstance(config["args"], list):
                    config["args"] = [os.path.abspath(arg) if isinstance(arg, str) and (arg.endswith(".py") or "/" in arg or "\\" in arg) else arg for arg in config["args"]]

            self.logger.debug(f"Parsing {server_id} as dictionary config: {config}")
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
                    self.logger.error(f"Server {server_id} not found in configurations.")
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
            self.logger.info(f"Tool {tool_name} executed successfully. Result: {result}")
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
        messages: List[Dict[str, Any]],
        final_text_output: List[str]
    ):
        """Execute a tool and update conversation history"""
        try:
            # Find which server has this tool
            server_id = await self._find_server_for_tool(tool_name)
            
            if not server_id:
                error_msg = f"Tool {tool_name} not found on any connected server"
                self.logger.error(error_msg)
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": f"Error: {error_msg}"
                    }]
                })
                return

            # Execute the tool on the appropriate server
            async with self._multi_server_client.session(server_id) as session:
                await session.initialize()
                tool_result = await self.call_tool(server_id, tool_name, tool_args, session)
                
            self.logger.info(f"Tool {tool_name} executed on {server_id}. Result: {tool_result}")
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": str(tool_result)
                }]
            })
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": f"Error: {e}"
                }]
            })

    async def _find_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which server provides a specific tool"""
        for server_id in self.servers_config.keys():
            try:
                tools = await self.list_tools(server_id)
                if any(tool.name == tool_name for tool in tools):
                    return server_id
            except Exception as e:
                self.logger.warning(f"Error checking tools for server {server_id}: {e}")
        return None

    async def process_query(self, query: str) -> str:
        """Process a query with intelligent routing and tool selection"""
        self.logger.info(f"Processing query: {query}")

        if not self.engine:
            self.logger.error("LLM Engine not provided to MCPClient. Cannot process query.")
            return "Error: LLM Engine not configured."

        # Analyze query intent
        intent = self.analyze_query_intent(query)
        self.logger.info(f"Query intent analysis: {intent}")

        # Enhance query with context
        enhanced_query = self.enhance_query_with_context(query, intent)

        # Get all available tools from all servers
        available_tools_for_llm = await self._format_tools_for_llm()

        messages = [{"role": "user", "content": enhanced_query}]
        final_text_output = []

        if not self._multi_server_client:
            self.logger.warning("MultiServerMCPClient not initialized. Processing without tools.")
            response = await self.engine.get_response(messages)
            for content_block in response.content:
                if content_block.type == 'text':
                    final_text_output.append(content_block.text)
            return "\n".join(final_text_output)

        # Process with multi-server support
        try:
            while True:
                response = await self.engine.get_response(messages, available_tools_for_llm)
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

                        # Append the tool_use block to the current turn's content
                        current_turn_content.append(content_block)

                        # Add the assistant's message (text + tool_use) to the conversation history
                        messages.append({
                            "role": "assistant",
                            "content": current_turn_content
                        })

                        # Execute tool and update history
                        await self._execute_tool_and_update_history(
                            tool_name, tool_args, tool_use_id, messages, final_text_output
                        )

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

        return "\n".join(final_text_output)

    async def get_server_info(self, server_id: str) -> Optional[Dict[str, Any]]:
        if server_id not in self.servers_config:
            self.logger.warning(f"Server {server_id} not found in configurations.")
            return None

        config = self.servers_config[server_id]
        tools = await self.list_tools(server_id)

        info = {
            "id": server_id,
            "type": "local" if config.get("transport") == "stdio" else "remote",
            "config": config,
            "tools_count": len(tools),
            "tools": [{"name": tool.name, "description": tool.description} for tool in tools],
            "status": "connected"  # If we can get info, it's connected
        }
        return info

    async def get_all_servers(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for server_id in self.servers_config.keys():
            server_info = await self.get_server_info(server_id)
            if server_info:
                result[server_id] = server_info
        return result
