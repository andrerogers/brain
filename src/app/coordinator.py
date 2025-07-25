import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from agent.engine import AgentEngine
from agent.models import ProgressUpdate
from agent.tasks import ReasoningChain
from tools.client import MCPClient

from .models import (
    QueryComplexityAnalysis,
    SystemHealthStatus,
    ToolExecutionRequest,
    ToolExecutionResponse,
)
from .tool_bridge import ToolBridge


class AppCoordinator:
    """
    Main application coordinator that bridges the agent engine and MCP infrastructure.

    Provides high-level interface for query processing, tool execution, and system
    management while maintaining clean separation of concerns.
    """

    def __init__(
        self,
        agent_engine: AgentEngine,
        tool_client: MCPClient,
        logger: Optional[logging.Logger] = None,
    ):
        self.agent_engine = agent_engine
        self.tool_client = tool_client
        self.logger = logger or logging.getLogger("AppCoordinator")

        # Initialize tool bridge
        self.tool_bridge = ToolBridge(tool_client, logger)

        # System state
        self._initialized = False
        self._current_workflow_id: Optional[str] = None
        self._system_metrics = {
            "queries_processed": 0,
            "tools_executed": 0,
            "average_query_time": 0.0,
            "success_rate": 1.0,
        }

    async def initialize(self) -> None:
        """Initialize the application coordinator and all subsystems."""
        if self._initialized:
            return

        self.logger.info("Initializing application coordinator...")
        await self.tool_bridge.get_available_tools(refresh_cache=True)

        # this should be in the constructor of AgentEngine
        self.agent_engine.set_tool_bridge(self.tool_bridge)
        await self.agent_engine.initialize()

        self._initialized = True
        self.logger.info("Application coordinator initialization completed")

    def is_initialized(self) -> bool:
        """Check if the coordinator is initialized."""
        return self._initialized

    async def process_query(
        self,
        user_query: str,
        context: Dict[str, Any],
        progress_callback: Callable[[ProgressUpdate], Awaitable[None]],
    ) -> ReasoningChain:
        """
        Process a user query through the agent engine with tool integration.

        Args:
            user_query: Natural language query from user
            context: Additional context for query processing
            progress_callback: Optional callback for progress updates

        Returns:
            Completed reasoning chain with results
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        context = context or {}

        self.logger.info(f"Processing query: {user_query}")

        try:
            reasoning_chain = await self.agent_engine.process_query(
                user_query=user_query,
                context=context,
                progress_callback=progress_callback,
            )

            self._current_workflow_id = reasoning_chain.id

            execution_time = time.time() - start_time
            self._update_metrics(success=True, execution_time=execution_time)

            self.logger.info(
                f"Query processed successfully in {
                             execution_time:.2f}s"
            )
            return reasoning_chain

        except Exception as e:
            execution_time = time.time() - start_time
            self._update_metrics(success=False, execution_time=execution_time)
            self.logger.error(f"Query processing failed: {e}")
            raise
        finally:
            self._current_workflow_id = None

    async def execute_tool(
        self, request: ToolExecutionRequest
    ) -> ToolExecutionResponse:
        """
        Execute a single tool directly through the tool bridge.

        Args:
            request: Tool execution request

        Returns:
            Tool execution response
        """
        if not self._initialized:
            await self.initialize()

        self.logger.info(f"Direct tool execution: {request.tool_name}")

        try:
            response = await self.tool_bridge.execute_tool_request(request)
            self._system_metrics["tools_executed"] += 1

            return response

        except Exception as e:
            self.logger.error(f"Direct tool execution failed: {e}")
            raise

    async def analyze_query_complexity(
        self, user_query: str
    ) -> QueryComplexityAnalysis:
        """
        Analyze the complexity of a user query.

        Args:
            user_query: Query to analyze

        Returns:
            Complexity analysis
        """
        if not self._initialized:
            await self.initialize()

        self.logger.info(f"Analyzing query complexity: {user_query}")

        try:
            analysis_result = await self.agent_engine.analyze_query_complexity(
                user_query
            )

            return QueryComplexityAnalysis(
                query=user_query,
                complexity_level=analysis_result.get("complexity", "moderate"),
                estimated_steps=analysis_result.get("estimated_steps", 3),
                estimated_duration_seconds=analysis_result.get(
                    "estimated_duration", 30
                ),
                required_capabilities=analysis_result.get("capabilities", []),
                recommended_approach=analysis_result.get(
                    "approach", "multi-agent workflow"
                ),
                confidence_score=analysis_result.get("confidence", 0.8),
            )

        except Exception as e:
            self.logger.error(f"Complexity analysis failed: {e}")
            raise

    async def get_available_tools(
        self, server_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available tools, optionally filtered by server type.

        Args:
            server_type: Optional server type filter

        Returns:
            List of tool information dictionaries
        """
        if not self._initialized:
            await self.initialize()

        try:
            if server_type:
                tools = self.tool_bridge.get_tools_by_type(server_type)
            else:
                tools = await self.tool_bridge.get_available_tools()

            # Convert to dictionaries for JSON serialization
            return [
                {
                    "name": tool.name,
                    "server_id": tool.server_id,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "server_type": tool.server_type,
                }
                for tool in tools
            ]

        except Exception as e:
            self.logger.error(f"Failed to get available tools: {e}")
            return []

    async def get_system_status(self) -> SystemHealthStatus:
        """
        Get comprehensive system health status.

        Returns:
            System health status
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get server status from tool bridge
            server_status = await self.tool_bridge.get_server_status()

            # Get agent engine status
            agent_status = await self.agent_engine.get_system_status()

            # Determine overall health
            connected_servers = server_status.get("connected_servers", 0)
            total_servers = server_status.get("total_servers", 0)
            agent_healthy = agent_status.get("status") == "healthy"

            if connected_servers == total_servers and agent_healthy:
                overall_status = "healthy"
            elif connected_servers > 0 and agent_healthy:
                overall_status = "partial"
            else:
                overall_status = "unhealthy"

            # Collect issues
            issues = []
            if connected_servers < total_servers:
                issues.append(
                    f"{total_servers - connected_servers} servers disconnected"
                )
            if not agent_healthy:
                issues.append("Agent engine not healthy")

            return SystemHealthStatus(
                overall_status=overall_status,
                components={
                    "agent_engine": "healthy" if agent_healthy else "unhealthy",
                    "tool_servers": f"{connected_servers}/{total_servers}",
                    "tool_bridge": "healthy",
                },
                active_sessions_count=0,  # This would be managed by session manager
                tool_servers_connected=connected_servers,
                total_tool_servers=total_servers,
                agent_engine_status=agent_status.get("status", "unknown"),
                issues=issues,
            )

        except Exception as e:
            self.logger.error(f"Failed to get system status: {e}")
            return SystemHealthStatus(
                overall_status="unhealthy",
                components={"error": str(e)},
                active_sessions_count=0,
                tool_servers_connected=0,
                total_tool_servers=0,
                agent_engine_status="error",
            )

    async def cancel_current_workflow(self) -> bool:
        """
        Cancel the currently running workflow.

        Returns:
            True if workflow was cancelled, False if no workflow was running
        """
        if not self._current_workflow_id:
            return False

        try:
            cancelled = await self.agent_engine.cancel_current_workflow()
            if cancelled:
                self._current_workflow_id = None
                self.logger.info("Current workflow cancelled")
            return cancelled

        except Exception as e:
            self.logger.error(f"Failed to cancel workflow: {e}")
            return False

    def _update_metrics(self, success: bool, execution_time: float) -> None:
        """Update internal system metrics."""
        self._system_metrics["queries_processed"] += 1

        # Update average query time (simple moving average)
        current_avg = self._system_metrics["average_query_time"]
        query_count = self._system_metrics["queries_processed"]
        self._system_metrics["average_query_time"] = (
            current_avg * (query_count - 1) + execution_time
        ) / query_count

        # Update success rate
        if success:
            current_success_rate = self._system_metrics["success_rate"]
            self._system_metrics["success_rate"] = (
                current_success_rate * (query_count - 1) + 1.0
            ) / query_count
        else:
            current_success_rate = self._system_metrics["success_rate"]
            self._system_metrics["success_rate"] = (
                current_success_rate * (query_count - 1) + 0.0
            ) / query_count

    def get_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        return {
            **self._system_metrics,
            "initialized": self._initialized,
            "current_workflow_active": self._current_workflow_id is not None,
        }

    async def get_agents_status(self) -> List[Dict[str, Any]]:
        """Get current status of all agents."""
        if not self._initialized:
            return []

        try:
            agents_status = await self.agent_engine.get_agents_status()
            return agents_status
        except Exception as e:
            self.logger.error(f"Failed to get agents status: {e}")
            return []

    async def get_workflow_status(self) -> Optional[Dict[str, Any]]:
        """Get current workflow status."""
        if not self._current_workflow_id:
            return None

        try:
            workflow_status = await self.agent_engine.get_workflow_status(
                self._current_workflow_id
            )
            return workflow_status
        except Exception as e:
            self.logger.error(f"Failed to get workflow status: {e}")
            return None

    async def get_tasks_status(self) -> List[Dict[str, Any]]:
        """Get current tasks status."""
        if not self._current_workflow_id:
            return []

        try:
            tasks_status = await self.agent_engine.get_tasks_status(
                self._current_workflow_id
            )
            return tasks_status
        except Exception as e:
            self.logger.error(f"Failed to get tasks status: {e}")
            return []

    async def get_reasoning_chain(self) -> List[Dict[str, Any]]:
        """Get current reasoning chain."""
        if not self._current_workflow_id:
            return []

        try:
            reasoning_chain = await self.agent_engine.get_reasoning_chain(
                self._current_workflow_id
            )
            return reasoning_chain
        except Exception as e:
            self.logger.error(f"Failed to get reasoning chain: {e}")
            return []

    async def get_planning_status(self) -> Optional[Dict[str, Any]]:
        """Get planning agent status."""
        try:
            planning_status = await self.agent_engine.get_planning_agent_status()
            return planning_status
        except Exception as e:
            self.logger.error(f"Failed to get planning status: {e}")
            return None

    async def get_execution_status(self) -> Optional[Dict[str, Any]]:
        """Get execution agent status."""
        try:
            execution_status = await self.agent_engine.get_execution_agent_status()
            return execution_status
        except Exception as e:
            self.logger.error(f"Failed to get execution status: {e}")
            return None

    async def shutdown(self) -> None:
        """Shutdown the coordinator and cleanup resources."""
        self.logger.info("Shutting down application coordinator...")

        # Cancel any running workflow
        if self._current_workflow_id:
            await self.cancel_current_workflow()

        # Shutdown agent engine
        if hasattr(self.agent_engine, "shutdown"):
            await self.agent_engine.shutdown()

        self._initialized = False
        self.logger.info("Application coordinator shutdown completed")
