import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Union

import logfire
from pydantic_ai import Agent

from ..models import AgentConfig, AgentResult, ProgressUpdate, ToolCall
from ..tasks import Task


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig, tool_bridge: Any, logger: logging.Logger):
        self.config = config
        self.tool_bridge = tool_bridge
        self.logger = logger or logging.getLogger(f"{self.__class__.__name__}")

        system_prompt = config.system_prompt or self.get_default_system_prompt()
        self.agent: Any = Agent(
            model=config.model, system_prompt=system_prompt
        )  # Type will be overridden in subclasses

        self.is_busy = False
        self.current_task: Optional[Task] = None
        self.available_tools: List[Any] = []

        self.logger.info(
            f"Initialized {config.agent_type} agent with model {config.model}"
        )

    @abstractmethod
    def get_default_system_prompt(self) -> str:
        """Get the default system prompt for this agent type."""
        pass

    @abstractmethod
    async def process_request(
        self,
        request: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Process a request and return results."""
        pass

    async def initialize(self) -> None:
        """Initialize the agent and load available tools."""
        with logfire.span(f"agent.{self.config.agent_type}.initialize"):
            return await self._initialize_impl()

    async def _initialize_impl(self) -> None:
        """Internal implementation of agent initialization."""
        try:
            self.logger.info(f"Initializing {self.config.agent_type} agent")

            # Load available tools for this agent type
            self.available_tools = await self.tool_bridge.get_tools_for_agent_type(
                self.config.agent_type
            )

            self.logger.info(
                f"Agent initialized with {
                             len(self.available_tools)} available tools"
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {e}")
            raise

    async def execute_with_progress(
        self,
        request: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> AgentResult:
        """
        Execute a request with progress reporting.

        Args:
            request: The request to process
            context: Additional context for processing
            progress_callback: Optional callback for progress updates

        Returns:
            AgentResult with execution details
        """
        with logfire.span(
            f"agent.{self.config.agent_type}.execute_with_progress",
            request_type=type(request).__name__,
            has_context=context is not None,
            has_progress_callback=progress_callback is not None,
        ):
            return await self._execute_with_progress_impl(
                request, context, progress_callback
            )

    async def _execute_with_progress_impl(
        self,
        request: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> AgentResult:
        """Internal implementation of execute_with_progress."""
        if self.is_busy:
            raise RuntimeError(f"{self.config.agent_type} agent is currently busy")

        self.is_busy = True
        start_time = time.time()

        try:
            if progress_callback:
                await self._send_progress_update(
                    progress_callback,
                    status="starting",
                    progress_percentage=0.0,
                    elapsed_time=0.0,
                )

            result = await self.process_request(request, context or {})

            execution_time = time.time() - start_time
            result.execution_time_seconds = execution_time

            if progress_callback:
                await self._send_progress_update(
                    progress_callback,
                    status="completed" if result.success else "failed",
                    progress_percentage=100.0,
                    elapsed_time=execution_time,
                )

            self.logger.info(
                f"Agent execution completed in {
                             execution_time:.2f}s with success={result.success}"
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)

            self.logger.error(f"Agent execution failed: {error_msg}")

            # Send error progress update
            if progress_callback:
                await self._send_progress_update(
                    progress_callback,
                    status="failed",
                    progress_percentage=100.0,
                    elapsed_time=execution_time,
                )

            return AgentResult(
                agent_type=self.config.agent_type,
                success=False,
                error=error_msg,
                execution_time_seconds=execution_time,
            )

        finally:
            self.is_busy = False
            self.current_task = None

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an MCP tool with error handling and logging.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            context: Additional context for execution

        Returns:
            Tool execution result
        """
        with logfire.span(
            f"agent.{self.config.agent_type}.execute_tool",
            tool_name=tool_name,
            parameter_count=len(parameters),
            has_context=context is not None,
        ):
            return await self._execute_tool_impl(tool_name, parameters, context)

    async def _execute_tool_impl(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal implementation of tool execution."""
        self.logger.info(
            f"Executing tool {
                         tool_name} with parameters: {parameters}"
        )

        try:
            # Validate parameters with detailed error guidance
            is_valid, error_msg = await self.tool_bridge.validate_tool_parameters(
                tool_name, parameters
            )
            if not is_valid:
                # Enhanced error response with recovery guidance
                detailed_error = f"Parameter validation failed for tool '{
                    tool_name}':\n{error_msg}"

                # Add tool schema information for recovery
                tool_info = self.tool_bridge.get_tool_by_name(tool_name)
                if (
                    tool_info
                    and hasattr(tool_info, "parameters")
                    and tool_info.parameters
                ):
                    detailed_error += f"\n\nTool Schema Reference:\n{
                        self._format_single_tool_schema(tool_info)}"

                self.logger.error(f"Tool parameter validation failed: {detailed_error}")

                return {
                    "success": False,
                    "error": detailed_error,
                    "error_type": "parameter_validation",
                    "tool_name": tool_name,
                    "provided_parameters": parameters,
                    "recovery_guidance": "Review the parameter requirements above and retry with all required parameters.",
                }

            # Execute the tool
            tool_call = await self.tool_bridge.execute_tool_for_agent(
                ToolCall(tool_name=tool_name, parameters=parameters)
            )

            if tool_call.error:
                # Enhanced error for tool execution failures
                execution_error = f"Tool execution failed: {tool_call.error}"

                # Check if this might be a parameter-related execution error
                if any(
                    keyword in str(tool_call.error).lower()
                    for keyword in [
                        "required",
                        "missing",
                        "parameter",
                        "argument",
                        "validation",
                    ]
                ):
                    tool_info = self.tool_bridge.get_tool_by_name(tool_name)
                    if tool_info:
                        execution_error += f"\n\nTool Schema for Reference:\n{
                            self._format_single_tool_schema(tool_info)}"

                self.logger.error(execution_error)

                return {
                    "success": False,
                    "error": execution_error,
                    "error_type": "execution_error",
                    "tool_name": tool_name,
                    "execution_time": tool_call.execution_time_seconds,
                }

            self.logger.info(
                f"Tool {tool_name} executed successfully in {
                             tool_call.execution_time_seconds:.2f}s"
            )

            return {
                "success": True,
                "result": tool_call.result,
                "execution_time": tool_call.execution_time_seconds,
                "tool_call": tool_call,
            }

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Tool {tool_name} execution failed: {error_msg}")

            return {
                "success": False,
                "error": error_msg,
                "error_type": "unexpected_error",
                "tool_name": tool_name,
                "parameters": parameters,
            }

    async def get_tool_recommendations(self, task: Task) -> Any:
        """Get tool recommendations for a task."""
        return await self.tool_bridge.get_tool_usage_recommendations(
            task, self.config.agent_type
        )

    def format_tools_for_prompt(self, tools: Optional[List[Any]] = None) -> str:
        """Format available tools with detailed parameter schemas for inclusion in prompts."""
        if tools is None:
            tools = self.available_tools

        if not tools:
            return "No tools are currently available."

        tool_descriptions = []
        for tool in tools:
            # Basic tool info
            description = f"- {tool.name}: {tool.description}"
            if tool.server_type != "unknown":
                description += f" (from {tool.server_type} server)"

            # Add parameter schema information
            if hasattr(tool, "parameters") and tool.parameters:
                description += "\n  Parameters:"
                schema = tool.parameters

                # Handle different schema formats
                properties = {}
                required = []

                if isinstance(schema, dict):
                    properties = schema.get("properties", {})
                    required = schema.get("required", [])

                if properties:
                    for param_name, param_info in properties.items():
                        param_type = param_info.get("type", "unknown")
                        param_desc = param_info.get("description", "No description")
                        is_required = param_name in required

                        # Format parameter line
                        param_line = f"    * {param_name} ({param_type}"
                        if is_required:
                            param_line += ", required"
                        else:
                            param_line += ", optional"
                            if "default" in param_info:
                                param_line += f", default: {
                                    param_info['default']}"
                        param_line += f"): {param_desc}"

                        description += f"\n{param_line}"

                    # Add usage example for common tools
                    example = self._get_tool_usage_example(
                        tool.name, properties, required
                    )
                    if example:
                        description += f"\n  Example: {example}"
                else:
                    description += "\n    No parameters required"

            tool_descriptions.append(description)

        return "\n".join(tool_descriptions)

    def _get_tool_usage_example(
        self, tool_name: str, properties: Dict[str, Any], required: List[str]
    ) -> str:
        """Generate usage examples for common tools."""
        examples = {
            "write_file": 'write_file(path="myfile.txt", content="Hello world")',
            "read_file": 'read_file(path="myfile.txt")',
            "list_directory": 'list_directory(path="/home/user/documents")',
            "git_status": "git_status()",
            "git_commit": 'git_commit(message="Add new feature")',
            "run_command": 'run_command(command="ls -la")',
            "web_search_exa": 'web_search_exa(query="python programming tutorials")',
            "crawl_url": 'crawl_url(url="https://example.com")',
        }

        # Return predefined example if available
        if tool_name in examples:
            return examples[tool_name]

        # Generate dynamic example based on required parameters
        if required and properties:
            example_params = []
            for param in required[:3]:  # Limit to first 3 required params
                param_info = properties.get(param, {})
                param_type = param_info.get("type", "string")

                if param_type == "string":
                    if "path" in param.lower():
                        example_params.append(f'{param}="/path/to/file"')
                    elif "content" in param.lower():
                        example_params.append(f'{param}="sample content"')
                    elif "message" in param.lower():
                        example_params.append(f'{param}="sample message"')
                    else:
                        example_params.append(f'{param}="value"')
                elif param_type == "boolean":
                    example_params.append(f"{param}=true")
                elif param_type in ["integer", "number"]:
                    example_params.append(f"{param}=10")
                else:
                    example_params.append(f'{param}="value"')

            if example_params:
                return f'{tool_name}({", ".join(example_params)})'

        return ""

    def _format_single_tool_schema(self, tool_info: Any) -> str:
        """Format schema information for a single tool."""
        if not hasattr(tool_info, "parameters") or not tool_info.parameters:
            return f"Tool '{tool_info.name}' has no parameter schema available."

        schema = tool_info.parameters
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = schema.get("required", []) if isinstance(schema, dict) else []

        if not properties:
            return f"Tool '{tool_info.name}' has no parameters defined."

        lines = [f"Tool: {tool_info.name}"]
        lines.append(
            f"Description: {getattr(tool_info, 'description', 'No description')}"
        )
        lines.append("Parameters:")

        for param_name, param_info in properties.items():
            param_type = param_info.get("type", "unknown")
            param_desc = param_info.get("description", "No description")
            is_required = param_name in required

            status = "REQUIRED" if is_required else "optional"
            default_val = (
                f", default: { param_info['default'] }"
                if "default" in param_info
                else ""
            )

            lines.append(
                f"  - {param_name} ({param_type}, {status}{default_val}): {param_desc}"
            )

        # Add usage example
        example = self._get_tool_usage_example(tool_info.name, properties, required)
        if example:
            lines.append(f"Example: {example}")

        return "\n".join(lines)

    def create_tool_execution_context(self, **kwargs: Any) -> Dict[str, Any]:
        """Create context for tool execution."""
        return {
            "agent_type": self.config.agent_type,
            "model": self.config.model,
            "timestamp": time.time(),
            **kwargs,
        }

    async def _send_progress_update(
        self,
        progress_callback: Optional[Callable],
        status: str,
        progress_percentage: float,
        elapsed_time: float,
        current_task: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a progress update via callback."""
        if not progress_callback:
            return

        try:
            update = ProgressUpdate(
                agent_type=self.config.agent_type,
                status=status,
                progress_percentage=progress_percentage,
                current_task=current_task,
                elapsed_time_seconds=elapsed_time,
                details=details or {},
            )

            await progress_callback(update)

        except Exception as e:
            self.logger.warning(f"Failed to send progress update: {e}")

    def _parse_agent_response(self, response: Any) -> Dict[str, Any]:
        """Parse and validate agent response."""
        try:
            if hasattr(response, "output"):
                output = response.output
            else:
                output = response

            # Handle different response types
            if isinstance(output, str):
                try:
                    # Try to parse as JSON first
                    parsed = json.loads(output)
                    return {"type": "json", "content": parsed}
                except json.JSONDecodeError:
                    return {"type": "text", "content": output}

            elif isinstance(output, dict):
                return {"type": "dict", "content": output}

            elif isinstance(output, list):
                return {"type": "list", "content": output}

            else:
                return {"type": "other", "content": str(output)}

        except Exception as e:
            self.logger.warning(f"Failed to parse agent response: {e}")
            return {"type": "error", "content": str(response)}

    def _extract_token_usage(self, response: Any) -> Dict[str, int]:
        """Extract token usage from agent response."""
        try:
            if hasattr(response, "usage"):
                usage = response.usage()
                return {
                    "request_tokens": getattr(usage, "request_tokens", 0),
                    "response_tokens": getattr(usage, "response_tokens", 0),
                    "total_tokens": getattr(usage, "total_tokens", 0),
                }
        except Exception as e:
            self.logger.warning(f"Failed to extract token usage: {e}")

        return {}

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the agent."""
        return {
            "agent_type": self.config.agent_type,
            "model": self.config.model,
            "is_busy": self.is_busy,
            "available_tools_count": len(self.available_tools),
            "current_task": self.current_task.id if self.current_task else None,
            "status": "healthy",
        }

    async def get_status(self) -> Dict[str, Any]:
        """Get current status of the agent."""
        return {
            "status": "active" if self.is_busy else "idle",
            "current_task": self.current_task.title if self.current_task else None,
            "agent_type": self.config.agent_type,
            "model": self.config.model,
            "available_tools": len(self.available_tools),
        }
