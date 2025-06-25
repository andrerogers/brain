import os
import re
import sys
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import tiktoken
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.types import Tool


@dataclass
class QueryMetrics:
    """Metrics for tracking query performance"""
    query: str
    start_time: float
    end_time: Optional[float] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tool_calls: List[Dict[str, Any]] = None
    duration_seconds: Optional[float] = None

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []

    def finish(self):
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time
        self.total_tokens = self.input_tokens + self.output_tokens


class MCPClient:
    def __init__(self, engine: Optional[Any] = None, logger: Optional[logging.Logger] = None):
        self.engine = engine
        self.logger = logger or logging.getLogger("MCPClient")
        self._multi_server_client: Optional[MultiServerMCPClient] = None
        self.servers_config: Dict[str, Dict[str, Any]] = {}

        try:
            # TODO
            # should know what model is being used for the query
            # being processed and use that to infer the encoding
            self.token_encoder = tiktoken.encoding_for_model("gpt-4")
        except Exception as e:
            self.logger.warning(f"Failed to load tiktoken encoder, using cl100k_base: {e}")
            self.token_encoder = tiktoken.get_encoding("cl100k_base")

        self.query_metrics: List[QueryMetrics] = []
        self.logger.info("MCPClient instance created.")

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
            },
            "exa": {
                "path": self._get_server_path("exa_server.py"),
                "description": "Web search and content crawling with real-time information access"
            }
        }

    def _get_server_path(self, server_file: str) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "servers", server_file)

    def _count_tokens(self, text: str) -> int:
        try:
            return len(self.token_encoder.encode(text))
        except Exception as e:
            self.logger.warning(f"Failed to count tokens: {e}")
            # Fallback: approximate token count (1 token ≈ 4 characters)
            return len(text) // 4

    def _count_message_tokens(self, messages: List[Dict[str, Any]]) -> int:
        total_tokens = 0
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                total_tokens += self._count_tokens(content)
            elif isinstance(content, list):
                # Handle message content that is a list (e.g., tool results)
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            total_tokens += self._count_tokens(item.get("text", ""))
                        elif item.get("type") == "tool_result":
                            total_tokens += self._count_tokens(str(item.get("content", "")))
                    elif isinstance(item, str):
                        total_tokens += self._count_tokens(item)
        return total_tokens

    async def _send_progress_update(self, metrics: QueryMetrics, progress_callback: Optional[callable], status: str = "thinking"):
        if progress_callback:
            current_time = time.time()
            elapsed_time = current_time - metrics.start_time

            # Calculate tokens so far (approximation)
            estimated_input_tokens = self._count_tokens(metrics.query) if metrics.input_tokens == 0 else metrics.input_tokens

            progress_data = {
                "status": status,
                "elapsed_time": elapsed_time,
                "estimated_input_tokens": estimated_input_tokens,
                "tool_calls_completed": len([tc for tc in metrics.tool_calls if "end_time" in tc]),
                "total_tool_calls": len(metrics.tool_calls)
            }

            await progress_callback(progress_data)

    def _log_metrics(self, metrics: QueryMetrics):
        tool_summary = f"Tool calls: {len(metrics.tool_calls)}"
        if metrics.tool_calls:
            tool_durations = [tc.get("duration", 0) for tc in metrics.tool_calls if "duration" in tc]
            if tool_durations:
                avg_tool_time = sum(tool_durations) / len(tool_durations)
                tool_summary += f" (avg: {avg_tool_time:.2f}s)"

        self.logger.info(
            f"Query completed - Duration: {metrics.duration_seconds:.2f}s, "
            f"Input tokens: {metrics.input_tokens}, Output tokens: {metrics.output_tokens}, "
            f"Total tokens: {metrics.total_tokens}, {tool_summary}"
        )

    def get_metrics_summary(self) -> Dict[str, Any]:
        if not self.query_metrics:
            return {"total_queries": 0}

        total_queries = len(self.query_metrics)
        total_duration = sum(m.duration_seconds or 0 for m in self.query_metrics)
        total_tokens = sum(m.total_tokens for m in self.query_metrics)
        total_tool_calls = sum(len(m.tool_calls) for m in self.query_metrics)

        avg_duration = total_duration / total_queries if total_queries > 0 else 0
        avg_tokens = total_tokens / total_queries if total_queries > 0 else 0

        return {
            "total_queries": total_queries,
            "total_duration_seconds": total_duration,
            "average_duration_seconds": avg_duration,
            "total_tokens": total_tokens,
            "average_tokens_per_query": avg_tokens,
            "total_tool_calls": total_tool_calls,
            "average_tool_calls_per_query": total_tool_calls / total_queries if total_queries > 0 else 0
        }

    async def auto_connect_builtin_servers(self) -> Dict[str, bool]:
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

    async def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        try:
            # Create LLM prompt for intelligent intent analysis
            intent_prompt = f"""Analyze this user query and determine what MCP servers and tools would be most helpful to answer it.

Query: "{query}"

Available MCP servers and their capabilities:
- filesystem: File operations (read, write, edit, list, search files/directories)
- git: Version control (status, diff, commit, log, branches, history)
- codebase: Project analysis (structure, find definitions/references, explain architecture)  
- devtools: Development tools (run tests, lint, format, type check, install dependencies)
- exa: Web search and content crawling (real-time information, current events, web data)

Respond with a JSON object containing:
{{
  "operation_type": "web_search|file_operation|git_operation|codebase_analysis|development_task|general",
  "servers_needed": ["list", "of", "server", "names"],
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Focus on the primary intent. For queries about current/real-time information (weather, news, latest events), use exa server."""

            messages = [{"role": "user", "content": intent_prompt}]
            response = await self.engine.get_response(messages)

            response_text = ""
            for content_block in response.content:
                if content_block.type == 'text':
                    response_text += content_block.text
            try:
                # Extract JSON from response (handle cases where LLM adds extra text)
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    llm_intent = json.loads(json_str)

                    # Convert to our expected format
                    intent = {
                        "servers_needed": set(llm_intent.get("servers_needed", [])),
                        "operation_type": llm_intent.get("operation_type", "general"),
                        "specific_tools": [],
                        "context_clues": [llm_intent.get("reasoning", "")],
                        "confidence": llm_intent.get("confidence", 0.5)
                    }
                    self.logger.info(f"LLM intent analysis: {intent}")
                    return intent
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse LLM intent response as JSON: {e}")
        except Exception as e:
            self.logger.error(f"LLM intent analysis failed: {e}")
            # Return a basic intent structure when LLM analysis fails
            return {
                "servers_needed": set(),
                "operation_type": "general",
                "specific_tools": [],
                "context_clues": [f"LLM analysis failed: {str(e)}"],
                "confidence": 0.0
            }

    async def enhance_query_with_context(self, query: str, intent: Dict[str, Any]) -> str:
        if intent["operation_type"] == "general":
            return query

        enhanced_query = f"""Development Assistant Query: {query}

Available development tools:"""

        try:
            tools_by_server = await self.get_all_available_tools()

            for server_id in intent["servers_needed"]:
                if server_id in tools_by_server and tools_by_server[server_id]:
                    tools = tools_by_server[server_id]
                    tool_names = [tool["name"] for tool in tools]
                    enhanced_query += f"""
- {server_id.title()} Operations: {", ".join(tool_names)}"""

        except Exception as e:
            self.logger.warning(f"Failed to get dynamic tool context: {e}")
            # Fallback to basic context
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
        final_text_output: List[str],
        metrics: Optional[QueryMetrics] = None
    ):
        try:
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

            if metrics:
                for tool_call in reversed(metrics.tool_calls):
                    if tool_call["tool_use_id"] == tool_use_id and "end_time" not in tool_call:
                        tool_call["end_time"] = time.time()
                        tool_call["duration"] = tool_call["end_time"] - tool_call["start_time"]
                        tool_call["server_id"] = server_id
                        break

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

            if metrics:
                for tool_call in reversed(metrics.tool_calls):
                    if tool_call["tool_use_id"] == tool_use_id and "end_time" not in tool_call:
                        tool_call["end_time"] = time.time()
                        tool_call["duration"] = tool_call["end_time"] - tool_call["start_time"]
                        tool_call["error"] = str(e)
                        break

    async def _find_server_for_tool(self, tool_name: str) -> Optional[str]:
        for server_id in self.servers_config.keys():
            try:
                tools = await self.list_tools(server_id)
                if any(tool.name == tool_name for tool in tools):
                    return server_id
            except Exception as e:
                self.logger.warning(f"Error checking tools for server {server_id}: {e}")
        return None

    async def process_query(self, query: str, progress_callback: Optional[callable] = None) -> str:
        metrics = QueryMetrics(query=query, start_time=time.time())
        self.logger.info(f"Processing query: {query}")

        if not self.engine:
            self.logger.error("LLM Engine not provided to MCPClient. Cannot process query.")
            metrics.finish()
            self.query_metrics.append(metrics)
            self._log_metrics(metrics)
            return "Error: LLM Engine not configured."

        if self.detect_tool_listing_intent(query):
            self.logger.info("Detected tool listing request")
            await self._send_progress_update(metrics, progress_callback, "retrieving_tools")

            try:
                tools_by_server = await self.get_all_available_tools()
                response = self._format_tools_response(tools_by_server)

                metrics.input_tokens = self._count_tokens(query)
                metrics.output_tokens = self._count_tokens(response)
                metrics.finish()
                self.query_metrics.append(metrics)
                self._log_metrics(metrics)

                return response
            except Exception as e:
                self.logger.error(f"Error retrieving tools: {e}")
                return f"Error retrieving available tools: {e}"

        # Send initial progress update
        await self._send_progress_update(metrics, progress_callback, "analyzing_query")
        
        # Analyze query intent using LLM
        intent = await self.analyze_query_intent(query)
        self.logger.info(f"Query intent analysis: {intent}")

        # Enhance query with context
        enhanced_query = await self.enhance_query_with_context(query, intent)

        # Send progress update
        await self._send_progress_update(metrics, progress_callback, "preparing_tools")
        
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

            result = "\n".join(final_text_output)
            metrics.input_tokens = self._count_message_tokens(messages)
            metrics.output_tokens = self._count_tokens(result)
            metrics.finish()

            self.query_metrics.append(metrics)
            self._log_metrics(metrics)

            return result

        try:
            await self._send_progress_update(metrics, progress_callback, "processing_llm")

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

                        tool_call_start = time.time()
                        metrics.tool_calls.append({
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "tool_use_id": tool_use_id,
                            "start_time": tool_call_start
                        })

                        # Append the tool_use block to the current turn's content
                        current_turn_content.append(content_block)

                        # Add the assistant's message (text + tool_use) to the conversation history
                        messages.append({
                            "role": "assistant",
                            "content": current_turn_content
                        })

                        # Send progress update before tool execution
                        await self._send_progress_update(metrics, progress_callback, f"executing_tool_{tool_name}")

                        # Execute tool and update history
                        await self._execute_tool_and_update_history(
                            tool_name, tool_args, tool_use_id, messages, final_text_output, metrics
                        )
                        
                        # Send progress update after tool execution
                        await self._send_progress_update(metrics, progress_callback, "processing_tool_result")

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

        # Calculate final metrics
        result = "\n".join(final_text_output)
        metrics.input_tokens = self._count_message_tokens([{"role": "user", "content": enhanced_query}])
        metrics.output_tokens = self._count_tokens(result)
        metrics.finish()
        
        # Store and log metrics
        self.query_metrics.append(metrics)
        self._log_metrics(metrics)
        
        return result

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

    async def get_all_available_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all available tools organized by server with descriptions"""
        tools_by_server = {}
        
        for server_id in self.servers_config.keys():
            try:
                tools = await self.list_tools(server_id)
                tools_by_server[server_id] = [
                    {
                        "name": tool.name,
                        "description": tool.description or "No description available"
                    }
                    for tool in tools
                ]
                self.logger.debug(f"Retrieved {len(tools)} tools from {server_id}")
            except Exception as e:
                self.logger.warning(f"Failed to get tools from {server_id}: {e}")
                tools_by_server[server_id] = []
        
        return tools_by_server

    def detect_tool_listing_intent(self, query: str) -> bool:
        """Detect if user wants to list MCP tools specifically"""
        query_lower = query.lower()
        
        # Specific patterns for MCP tool listing
        tool_listing_patterns = [
            r'\blist\s+(?:mcp\s+)?tools?\b',
            r'\bshow\s+(?:available\s+)?tools?\b',
            r'\bwhat\s+tools?\s+(?:are\s+)?available\b',
            r'\bwhat\s+(?:mcp\s+)?tools?\s+(?:do\s+)?(?:you\s+)?have\b',
            r'\blist\s+(?:all\s+)?(?:the\s+)?(?:mcp\s+)?tools?\b',
            r'\btell\s+me\s+(?:about\s+)?(?:the\s+)?tools?\b',
            r'\bshow\s+me\s+(?:the\s+)?tools?\b'
        ]
        
        return any(re.search(pattern, query_lower) for pattern in tool_listing_patterns)

    def _format_tools_response(self, tools_by_server: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format the tools listing into a user-friendly response"""
        if not tools_by_server:
            return "No MCP servers are currently connected, so no tools are available."
        
        response_parts = ["# Available MCP Tools\n"]
        total_tools = 0
        
        for server_id, tools in tools_by_server.items():
            if not tools:
                response_parts.append(f"## {server_id.title()} Server\n*No tools available*\n")
                continue
                
            response_parts.append(f"## {server_id.title()} Server ({len(tools)} tools)\n")
            
            for tool in tools:
                response_parts.append(f"• **{tool['name']}** - {tool['description']}")
                total_tools += 1
            
            response_parts.append("")  # Empty line between servers
        
        summary = f"\n**Total: {total_tools} tools across {len(tools_by_server)} servers**"
        response_parts.append(summary)
        
        return "\n".join(response_parts)
