import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import logfire

from agent.models import AgentType, ToolCall
from agent.tasks import Task
from tools.client import MCPClient

from .models import ToolExecutionRequest, ToolExecutionResponse
from .tool_adapters import ToolAdapterFactory, UnifiedTool


@dataclass
class AvailableToolInfo:
    """Information about an available tool (unified interface)."""

    name: str
    server_id: str
    description: str
    parameters: Dict[str, Any]
    server_type: str  # filesystem, git, codebase, devtools, exa, langchain
    _adapter: UnifiedTool  # Internal adapter reference for accessing tool


class ToolBridge:
    """
    Bridge between application layer and MCP tool infrastructure.

    Provides application-level interface for tool discovery, validation,
    and execution while maintaining clean separation from agent logic.
    """

    def __init__(self, tool_client: MCPClient, logger: Optional[logging.Logger] = None):
        self.tool_client = tool_client
        self.logger = logger or logging.getLogger("ToolBridge")
        self._tool_cache: Dict[str, AvailableToolInfo] = {}
        self._last_cache_update: float = 0
        self._cache_ttl_seconds: float = 300  # 5 minutes

    async def get_available_tools(
        self, refresh_cache: bool = False
    ) -> List[AvailableToolInfo]:
        """
        Get all available tools from connected MCP servers.

        Args:
            refresh_cache: Force refresh of tool cache

        Returns:
            List of available tool information
        """
        current_time = time.time()

        if (
            not refresh_cache
            and self._tool_cache
            and (current_time - self._last_cache_update) < self._cache_ttl_seconds
        ):
            return list(self._tool_cache.values())

        self.logger.info("Refreshing MCP tool cache")
        tools_info = []

        with logfire.span(
            "tool_bridge.get_available_tools", refresh_cache=refresh_cache
        ):
            return await self._get_available_tools_impl(tools_info, current_time)

    async def _get_available_tools_impl(
        self, tools_info: List[AvailableToolInfo], current_time: float
    ) -> List[AvailableToolInfo]:
        """Internal implementation of get_available_tools."""
        try:
            # Get servers and their tools
            servers_info = await self.tool_client.get_all_servers()

            for server_id, server_info in servers_info.items():
                server_status = server_info.get("status", "unknown")

                if server_status != "connected":
                    self.logger.warning(f"Server {server_id} not connected, skipping")
                    continue

                # Get tools for this server
                try:
                    tools = await self.tool_client.list_tools(server_id)

                    for tool in tools:
                        # Create unified adapter for the tool
                        server_type = self._determine_server_type(server_id)
                        adapter = ToolAdapterFactory.create_adapter(
                            tool, server_id, server_type
                        )

                        tool_info = AvailableToolInfo(
                            name=adapter.name,
                            server_id=server_id,
                            description=adapter.description or "",
                            parameters=self._extract_tool_parameters(adapter),
                            server_type=server_type,
                            _adapter=adapter,
                        )
                        tools_info.append(tool_info)
                        self._tool_cache[
                            f"{server_id}:{
                            tool.name}"
                        ] = tool_info

                except Exception as e:
                    self.logger.warning(
                        f"Failed to get tools for server {server_id}: {e}"
                    )

            self._last_cache_update = current_time
            self.logger.info(
                f"Cached {len(tools_info)} tools from {
                             len(servers_info)} servers"
            )

        except Exception as e:
            self.logger.error(f"Failed to refresh tool cache: {e}")

        return tools_info

    def _extract_tool_parameters(self, adapter: UnifiedTool) -> Dict[str, Any]:
        """Extract parameter schema from unified tool adapter."""
        try:
            return adapter.get_parameters()
        except Exception as e:
            self.logger.warning(
                f"Failed to extract parameters for tool {adapter.name}: {e}"
            )
            return {}

    def _determine_server_type(self, server_id: str) -> str:
        """Determine the type of server based on server ID."""
        server_type_mapping = {
            "filesystem": "filesystem",
            "git": "git",
            "codebase": "codebase",
            "devtools": "devtools",
            "exa": "exa",
        }

        for key, value in server_type_mapping.items():
            if key in server_id.lower():
                return value

        return "unknown"

    async def execute_tool_request(
        self, request: ToolExecutionRequest
    ) -> ToolExecutionResponse:
        """
        Execute a tool request and return structured response.

        Args:
            request: Tool execution request

        Returns:
            Structured tool execution response
        """
        with logfire.span(
            "tool_bridge.execute_tool_request",
            tool_name=request.tool_name,
            server_id=request.server_id,
        ):
            return await self._execute_tool_request_impl(request)

    async def _execute_tool_request_impl(
        self, request: ToolExecutionRequest
    ) -> ToolExecutionResponse:
        """Internal implementation of tool request execution."""
        start_time = time.time()

        try:
            self.logger.info(
                f"Executing tool {request.tool_name} with params: {
                             request.parameters}"
            )

            # Find server_id if not provided
            server_id = request.server_id
            if not server_id:
                server_id = await self._find_server_for_tool(request.tool_name)
                if not server_id:
                    raise ValueError(
                        f"Tool '{request.tool_name}' not found on any connected server"
                    )

            # Execute via tool client with MCP session
            if not self.tool_client._multi_server_client:
                raise RuntimeError("MCP client not initialized")

            async with self.tool_client._multi_server_client.session(
                server_id
            ) as session:
                await session.initialize()
                result = await self.tool_client.call_tool(
                    server_id,  # 1st param: server_id
                    request.tool_name,  # 2nd param: tool_name
                    request.parameters,  # 3rd param: parameters
                    session,  # 4th param: session object
                )

            execution_time = time.time() - start_time

            return ToolExecutionResponse(
                success=True,
                result=result,
                execution_time_seconds=execution_time,
                tool_name=request.tool_name,
                server_id=server_id,
                metadata={"session_id": request.session_id, "context": request.context},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)

            self.logger.error(f"Tool {request.tool_name} execution failed: {error_msg}")

            return ToolExecutionResponse(
                success=False,
                error=error_msg,
                execution_time_seconds=execution_time,
                tool_name=request.tool_name,
                server_id=request.server_id or "unknown",
                metadata={"session_id": request.session_id, "context": request.context},
            )

    async def execute_tool_for_agent(self, tool_call: ToolCall) -> ToolCall:
        """
        Execute a tool call for an agent and return updated ToolCall.

        Args:
            tool_call: Agent tool call to execute

        Returns:
            Updated ToolCall with results
        """
        start_time = time.time()

        try:
            # Find server if not provided
            if not tool_call.server_id:
                tool_call.server_id = await self._find_server_for_tool(
                    tool_call.tool_name
                )
                if not tool_call.server_id:
                    raise ValueError(
                        f"Tool '{tool_call.tool_name}' not found on any connected server"
                    )

            # Execute via tool client with MCP session
            if not self.tool_client._multi_server_client:
                raise RuntimeError("MCP client not initialized")

            async with self.tool_client._multi_server_client.session(
                tool_call.server_id
            ) as session:
                await session.initialize()
                result = await self.tool_client.call_tool(
                    tool_call.server_id,  # 1st param: server_id
                    tool_call.tool_name,  # 2nd param: tool_name
                    tool_call.parameters,  # 3rd param: parameters
                    session,  # 4th param: session object
                )

            tool_call.result = result
            tool_call.execution_time_seconds = time.time() - start_time

            self.logger.info(
                f"Agent tool {tool_call.tool_name} executed successfully in {
                             tool_call.execution_time_seconds:.2f}s"
            )

        except Exception as e:
            error_msg = str(e)
            tool_call.error = error_msg
            tool_call.execution_time_seconds = time.time() - start_time

            self.logger.error(
                f"Agent tool {tool_call.tool_name} execution failed: {error_msg}"
            )

        return tool_call

    async def _find_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which server provides the specified tool."""
        # Check cache first
        for key, tool_info in self._tool_cache.items():
            if tool_info.name == tool_name:
                return tool_info.server_id

        # Fallback to direct tool client lookup
        return await self.tool_client._find_server_for_tool(tool_name)

    async def get_tools_for_agent_type(
        self, agent_type: AgentType
    ) -> List[AvailableToolInfo]:
        """
        Get tools most relevant for a specific agent type.

        Args:
            agent_type: Type of agent requesting tools

        Returns:
            Filtered list of relevant tools
        """
        all_tools = await self.get_available_tools()

        if agent_type == AgentType.PLANNING:
            # Planning agents need codebase analysis and project understanding tools
            return [
                tool
                for tool in all_tools
                if tool.server_type in ["codebase", "filesystem"]
            ]

        elif agent_type == AgentType.ORCHESTRATOR:
            # Orchestrator needs visibility into all tools for selection
            return all_tools

        elif agent_type == AgentType.EXECUTION:
            # Execution agents need all tools for actual task completion
            return all_tools

        return all_tools

    async def get_tool_usage_recommendations(
        self, task: Task, agent_type: AgentType
    ) -> List[str]:
        """
        Get recommended tools for a specific task based on its description and context.

        Args:
            task: Task to analyze
            agent_type: Type of agent that will execute the task

        Returns:
            List of recommended tool names
        """
        available_tools = await self.get_tools_for_agent_type(agent_type)
        recommendations = []

        task_description = task.description.lower()

        # Simple keyword-based recommendations
        tool_keywords = {
            "filesystem": [
                "file",
                "read",
                "write",
                "directory",
                "path",
                "save",
                "load",
                "create",
            ],
            "git": [
                "git",
                "commit",
                "branch",
                "diff",
                "log",
                "status",
                "history",
                "version",
            ],
            "codebase": [
                "code",
                "function",
                "class",
                "analyze",
                "structure",
                "definition",
                "reference",
            ],
            "devtools": [
                "test",
                "lint",
                "format",
                "build",
                "install",
                "run",
                "check",
                "validate",
            ],
            "exa": [
                "search",
                "web",
                "internet",
                "online",
                "crawl",
                "url",
                "website",
                "information",
            ],
        }

        for tool in available_tools:
            server_keywords = tool_keywords.get(tool.server_type, [])
            if any(keyword in task_description for keyword in server_keywords):
                recommendations.append(tool.name)

        # Add any explicitly required tools
        recommendations.extend(task.tools_required)

        return list(set(recommendations))  # Remove duplicates

    async def validate_tool_parameters(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate parameters for a tool before execution with detailed error guidance.

        Args:
            tool_name: Name of the tool
            parameters: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message_with_guidance)
        """
        try:
            # Find tool info
            tool_info = None
            for cached_tool in self._tool_cache.values():
                if cached_tool.name == tool_name:
                    tool_info = cached_tool
                    break

            if not tool_info:
                return (
                    False,
                    f"Tool '{tool_name}' not found. Available tools: {list(self._tool_cache.keys())}",
                )

            # Basic parameter validation
            if not isinstance(parameters, dict):
                return False, "Parameters must be a dictionary"

            # Detailed parameter validation based on tool schema
            if hasattr(tool_info, "parameters") and tool_info.parameters:
                schema = tool_info.parameters
                properties = (
                    schema.get("properties", {}) if isinstance(schema, dict) else {}
                )
                required = (
                    schema.get("required", []) if isinstance(schema, dict) else []
                )

                # Check for missing required parameters
                missing_required = []
                for req_param in required:
                    if req_param not in parameters:
                        missing_required.append(req_param)

                if missing_required:
                    error_msg = f"Missing required parameters for '{
                        tool_name}': {missing_required}\n"
                    error_msg += "Required parameters:\n"

                    for param in missing_required:
                        param_info = properties.get(param, {})
                        param_type = param_info.get("type", "unknown")
                        param_desc = param_info.get("description", "No description")
                        error_msg += f"  - {param} ({param_type}): {
                            param_desc}\n"

                    # Add usage example
                    example = self._generate_usage_example(
                        tool_name, properties, required
                    )
                    if example:
                        error_msg += f"Example usage: {example}"

                    return False, error_msg.strip()

                # Check for unexpected parameters (warnings, not errors)
                unexpected_params = [
                    p for p in parameters.keys() if p not in properties
                ]
                if unexpected_params:
                    self.logger.warning(
                        f"Tool '{tool_name}' received unexpected parameters: {
                                        unexpected_params}"
                    )

                # Validate parameter types
                type_errors = []
                for param_name, param_value in parameters.items():
                    if param_name in properties:
                        expected_type = properties[param_name].get("type")
                        if expected_type and not self._validate_parameter_type(
                            param_value, expected_type
                        ):
                            type_errors.append(
                                f"Parameter '{param_name}' should be {
                                               expected_type}, got {type(param_value).__name__}"
                            )

                if type_errors:
                    error_msg = f"Parameter type errors for '{tool_name}':\n"
                    error_msg += "\n".join(f"  - {error}" for error in type_errors)
                    return False, error_msg

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _validate_parameter_type(self, value: Any, expected_type: str) -> bool:
        """Validate that a parameter value matches the expected type."""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_mapping.get(expected_type.lower())
        if expected_python_type is None:
            return True  # Unknown type, allow it

        return isinstance(value, expected_python_type)

    def _generate_usage_example(
        self, tool_name: str, properties: Dict[str, Any], required: List[str]
    ) -> str:
        """Generate a usage example for the tool."""
        examples = {
            "write_file": 'write_file(path="myfile.txt", content="Hello world")',
            "read_file": 'read_file(path="myfile.txt")',
            "list_directory": 'list_directory(path="/home/user/documents")',
            "git_commit": 'git_commit(message="Add new feature")',
            "run_command": 'run_command(command="ls -la")',
            "web_search_exa": 'web_search_exa(query="search terms")',
            "crawl_url": 'crawl_url(url="https://example.com")',
        }

        if tool_name in examples:
            return examples[tool_name]

        # Generate dynamic example
        if required and properties:
            example_params = []
            for param in required[:3]:  # Limit to avoid overly long examples
                param_info = properties.get(param, {})
                param_type = param_info.get("type", "string")

                if param_type == "string":
                    if "path" in param.lower():
                        example_params.append(f'{param}="/path/to/file"')
                    elif "content" in param.lower():
                        example_params.append(f'{param}="content here"')
                    elif "message" in param.lower():
                        example_params.append(f'{param}="message text"')
                    else:
                        example_params.append(f'{param}="value"')
                elif param_type == "boolean":
                    example_params.append(f"{param}=true")
                elif param_type in ["integer", "number"]:
                    example_params.append(f"{param}=10")

            if example_params:
                return f'{tool_name}({", ".join(example_params)})'

        return ""

    async def get_server_status(self) -> Dict[str, Any]:
        """Get status of all connected MCP servers."""
        try:
            servers_info = await self.tool_client.get_all_servers()
            return {
                "connected_servers": len(
                    [s for s in servers_info.values() if s.get("status") == "connected"]
                ),
                "total_servers": len(servers_info),
                "servers": servers_info,
                "total_tools": len(self._tool_cache),
                "last_cache_update": self._last_cache_update,
            }
        except Exception as e:
            self.logger.error(f"Failed to get server status: {e}")
            return {"error": str(e)}

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        server_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool by name with parameters.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            server_id: Optional server ID (auto-detected if not provided)
            session_id: Optional session ID for context

        Returns:
            Tool execution result
        """
        try:
            # Create tool execution request
            request = ToolExecutionRequest(
                tool_name=tool_name,
                parameters=parameters,
                server_id=server_id,
                session_id=session_id or "default_session",
            )

            # Execute via tool request method
            response = await self.execute_tool_request(request)

            if response.success:
                return response.result if response.result is not None else {}
            else:
                return {"error": response.error}

        except Exception as e:
            self.logger.error(f"Failed to execute tool {tool_name}: {e}")
            return {"error": str(e)}

    async def execute_multiple_tools(
        self, requests: List[ToolExecutionRequest]
    ) -> List[ToolExecutionResponse]:
        """
        Execute multiple tool requests concurrently.

        Args:
            requests: List of tool execution requests

        Returns:
            List of tool execution responses
        """
        tasks = [self.execute_tool_request(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed ToolExecutionResponse objects
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Create a failed response for the exception
                processed_results.append(
                    ToolExecutionResponse(
                        success=False,
                        result=None,
                        error=str(result),
                        execution_time_seconds=0.0,
                        tool_name=requests[i].tool_name,
                        server_id=requests[i].server_id,
                    )
                )
            else:
                processed_results.append(result)
        
        return processed_results

    def get_tool_by_name(self, tool_name: str) -> Optional[AvailableToolInfo]:
        """Get tool information by name."""
        for tool_info in self._tool_cache.values():
            if tool_info.name == tool_name:
                return tool_info
        return None

    def get_tools_by_server(self, server_id: str) -> List[AvailableToolInfo]:
        """Get all tools for a specific server."""
        return [
            tool_info
            for tool_info in self._tool_cache.values()
            if tool_info.server_id == server_id
        ]

    def get_tools_by_type(self, server_type: str) -> List[AvailableToolInfo]:
        """Get all tools of a specific server type."""
        return [
            tool_info
            for tool_info in self._tool_cache.values()
            if tool_info.server_type == server_type
        ]
