import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Callable, AsyncIterator

from .models import AgentConfig, AgentType
from .workflow import WorkflowExecutor
from .tasks import ReasoningChain


class AgentEngine:
    def __init__(
        self,
        default_models: Dict[str, str] = None,
        api_key: str = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the agent engine with configurable models and API key.
        
        Args:
            default_models: Default models for each agent type
            api_key: API key for the LLM provider
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("AgentEngine")
        self.api_key = api_key
        
        # Set API key in environment for Pydantic AI
        if api_key:
            # Determine which API key environment variable to set based on model names
            if any("anthropic" in model for model in (default_models or {}).values()):
                os.environ["ANTHROPIC_API_KEY"] = api_key
                self.logger.info("Set ANTHROPIC_API_KEY environment variable for Pydantic AI")
            elif any("openai" in model for model in (default_models or {}).values()):
                os.environ["OPENAI_API_KEY"] = api_key
                self.logger.info("Set OPENAI_API_KEY environment variable for Pydantic AI")

        # Default model configuration
        self.default_models = default_models or {
            "planning": "anthropic:claude-3-5-sonnet-latest",
            "orchestrator": "anthropic:claude-3-5-sonnet-latest",
            "execution": "anthropic:claude-3-5-sonnet-latest"
        }

        # Tool bridge will be injected by the application layer
        self._tool_bridge = None

        # Workflow executor (initialized lazily)
        self._workflow_executor: Optional[WorkflowExecutor] = None
        self._initialized = False

        self.logger.info("AgentEngine initialized")

    def set_tool_bridge(self, tool_bridge) -> None:
        """Set the tool bridge for agent tool execution."""
        self._tool_bridge = tool_bridge
        self.logger.info("Tool bridge configured for agent engine")
    
    async def initialize(self) -> None:
        """Initialize the agent engine and all components."""
        if self._initialized:
            return

        if not self._tool_bridge:
            raise RuntimeError("Tool bridge must be set before initializing agent engine")

        try:
            self.logger.info("Initializing AgentEngine")

            # Create agent configurations
            agent_configs = self._create_agent_configurations()

            # Initialize workflow executor with tool bridge
            self._workflow_executor = WorkflowExecutor(
                tool_bridge=self._tool_bridge,
                planning_config=agent_configs["planning"],
                orchestrator_config=agent_configs["orchestrator"],
                execution_config=agent_configs["execution"],
                logger=self.logger
            )

            await self._workflow_executor.initialize()

            self._initialized = True
            self.logger.info("AgentEngine initialization completed")

        except Exception as e:
            self.logger.error(f"Failed to initialize AgentEngine: {e}")
            raise

    def _create_agent_configurations(self) -> Dict[str, AgentConfig]:
        """Create agent configurations with appropriate models and prompts."""
        return {
            "planning": AgentConfig(
                agent_type=AgentType.PLANNING,
                model=self.default_models["planning"],
                temperature=0.7,
                max_tokens=4000
            ),
            "orchestrator": AgentConfig(
                agent_type=AgentType.ORCHESTRATOR,
                model=self.default_models["orchestrator"],
                temperature=0.3,  # Lower temperature for more deterministic tool selection
                max_tokens=4000
            ),
            "execution": AgentConfig(
                agent_type=AgentType.EXECUTION,
                model=self.default_models["execution"],
                temperature=0.5,
                max_tokens=4000
            )
        }

    async def process_query(
        self,
        user_query: str,
        context: Dict[str, Any] = None,
        progress_callback: Optional[Callable] = None
    ) -> ReasoningChain:
        """
        Process a user query through the complete multi-agent workflow.

        Args:
            user_query: The user's query to process
            context: Optional additional context
            progress_callback: Optional callback for progress updates

        Returns:
            Complete ReasoningChain with results
        """
        if not self._initialized:
            await self.initialize()

        if not self._workflow_executor:
            raise RuntimeError("Workflow executor not initialized")

        self.logger.info(f"Processing user query: {user_query}")

        try:
            reasoning_chain = await self._workflow_executor.execute_query(
                user_query=user_query,
                context=context or {},
                progress_callback=progress_callback
            )

            self.logger.info(f"Query processing completed with status: {
                             reasoning_chain.status}")

            return reasoning_chain

        except Exception as e:
            self.logger.error(f"Query processing failed: {e}")
            raise

    async def process_query_streaming(
        self,
        user_query: str,
        context: Dict[str, Any] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Process a query with streaming progress updates.

        Args:
            user_query: The user's query to process
            context: Optional additional context

        Yields:
            Progress updates and final result
        """
        progress_updates = []

        async def progress_callback(update):
            progress_updates.append(update)

        # Start query processing
        task = asyncio.create_task(
            self.process_query(user_query, context, progress_callback)
        )

        # Stream progress updates
        last_update_count = 0
        while not task.done():
            # Yield any new progress updates
            new_updates = progress_updates[last_update_count:]
            for update in new_updates:
                yield {
                    "type": "progress",
                    "data": update.model_dump()
                }

            last_update_count = len(progress_updates)

            # Small delay to prevent busy waiting
            await asyncio.sleep(0.1)

        # Get final result
        try:
            reasoning_chain = await task
            yield {
                "type": "result",
                "data": reasoning_chain.model_dump()
            }
        except Exception as e:
            yield {
                "type": "error",
                "data": {"error": str(e)}
            }

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get information about all available tools via tool bridge."""
        if not self._tool_bridge:
            raise RuntimeError("Tool bridge not configured")

        tools = await self._tool_bridge.get_available_tools()
        return [
            {
                "name": tool.name,
                "server_type": tool.server_type,
                "server_id": tool.server_id,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in tools
        ]

    async def execute_single_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        server_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a single tool directly via tool bridge.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            server_id: Optional server ID

        Returns:
            Tool execution result
        """
        if not self._tool_bridge:
            raise RuntimeError("Tool bridge not configured")

        from app.models import ToolExecutionRequest
        
        request = ToolExecutionRequest(
            tool_name=tool_name,
            parameters=parameters,
            server_id=server_id
        )
        
        response = await self._tool_bridge.execute_tool_request(request)

        return {
            "success": response.success,
            "result": response.result,
            "error": response.error,
            "execution_time_seconds": response.execution_time_seconds
        }

    async def analyze_query_complexity(self, user_query: str) -> Dict[str, Any]:
        """
        Analyze query complexity without full processing.

        Args:
            user_query: Query to analyze

        Returns:
            Complexity analysis
        """
        if not self._initialized:
            await self.initialize()

        if not self._workflow_executor:
            raise RuntimeError("Workflow executor not initialized")

        # Use just the planning agent for quick analysis
        try:
            result = await self._workflow_executor.planning_agent.analyze_query_complexity(user_query)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        status = {
            "status": "healthy" if self._initialized else "not_initialized",
            "agent_engine": {
                "initialized": self._initialized,
                "default_models": self.default_models,
                "tool_bridge_configured": self._tool_bridge is not None
            },
            "workflow_executor": None
        }

        if self._workflow_executor:
            status["workflow_executor"] = await self._workflow_executor.get_workflow_status()

        return status

    async def update_agent_models(self, model_updates: Dict[str, str]) -> None:
        """
        Update the models used by specific agents.

        Args:
            model_updates: Dict mapping agent types to new model names
        """
        for agent_type, model in model_updates.items():
            if agent_type in self.default_models:
                self.default_models[agent_type] = model
                self.logger.info(
                    f"Updated {agent_type} agent model to {model}")

        # Reinitialize if already initialized
        if self._initialized:
            self.logger.info("Reinitializing agent engine with new models")
            self._initialized = False
            await self.initialize()

    async def cancel_current_workflow(self) -> bool:
        """Cancel the currently executing workflow."""
        if not self._workflow_executor:
            return False

        return await self._workflow_executor.cancel_workflow()

    def get_reasoning_chain_summary(self, reasoning_chain: ReasoningChain) -> Dict[str, Any]:
        """Get a summary of a reasoning chain execution."""
        return {
            "id": reasoning_chain.id,
            "original_query": reasoning_chain.original_query,
            "status": reasoning_chain.status,
            "success": reasoning_chain.status.value == "completed",
            "execution_time_seconds": reasoning_chain.total_execution_time_seconds,
            "task_count": len(reasoning_chain.task_list.tasks),
            "reasoning_steps": len(reasoning_chain.reasoning_steps),
            "final_result": reasoning_chain.final_result,
            "progress_summary": reasoning_chain.get_progress_summary()
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health_status = {
            "agent_engine": "healthy" if self._initialized else "not_initialized",
            "tool_bridge": "unknown",
            "workflow_executor": "unknown",
            "agents": {},
            "overall": "unknown"
        }

        try:
            # Check tool bridge if available
            if self._tool_bridge:
                server_status = await self._tool_bridge.get_server_status()
                connected_servers = server_status.get("connected_servers", 0)
                total_servers = server_status.get("total_servers", 0)

                if connected_servers == total_servers and connected_servers > 0:
                    health_status["mcp_bridge"] = "healthy"
                elif connected_servers > 0:
                    health_status["mcp_bridge"] = "partial"
                else:
                    health_status["mcp_bridge"] = "unhealthy"
            else:
                health_status["mcp_bridge"] = "not_configured"

            # Check individual agents if initialized
            if self._workflow_executor:
                health_status["workflow_executor"] = "healthy"

                agents_health = await asyncio.gather(
                    self._workflow_executor.planning_agent.health_check(),
                    self._workflow_executor.orchestrator_agent.health_check(),
                    self._workflow_executor.execution_agent.health_check(),
                    return_exceptions=True
                )

                for i, agent_type in enumerate(["planning", "orchestrator", "execution"]):
                    if isinstance(agents_health[i], Exception):
                        health_status["agents"][agent_type] = f"error: {
                            agents_health[i]}"
                    else:
                        health_status["agents"][agent_type] = agents_health[i]

            # Determine overall health
            component_statuses = [
                health_status["agent_engine"],
                health_status["tool_bridge"],
                health_status["workflow_executor"]
            ]

            if all(status == "healthy" for status in component_statuses):
                health_status["overall"] = "healthy"
            elif any(status in ["healthy", "partial"] for status in component_statuses):
                health_status["overall"] = "partial"
            else:
                health_status["overall"] = "unhealthy"

        except Exception as e:
            health_status["overall"] = f"error: {str(e)}"

        return health_status
    
    async def get_agents_status(self) -> List[Dict[str, Any]]:
        """Get status of all agents."""
        if not self._workflow_executor:
            return []
        
        try:
            planning_status = await self._workflow_executor.planning_agent.get_status()
            orchestrator_status = await self._workflow_executor.orchestrator_agent.get_status()
            execution_status = await self._workflow_executor.execution_agent.get_status()
            
            return [
                {
                    "name": "Planning Agent",
                    "type": "planning",
                    "status": planning_status.get("status", "idle"),
                    "current_task": planning_status.get("current_task"),
                    "capabilities": ["query_analysis", "task_planning", "requirement_validation"]
                },
                {
                    "name": "Orchestrator Agent", 
                    "type": "orchestrator",
                    "status": orchestrator_status.get("status", "idle"),
                    "current_task": orchestrator_status.get("current_task"),
                    "capabilities": ["workflow_coordination", "task_management", "dependency_resolution"]
                },
                {
                    "name": "Execution Agent",
                    "type": "execution", 
                    "status": execution_status.get("status", "idle"),
                    "current_task": execution_status.get("current_task"),
                    "capabilities": ["tool_execution", "result_processing", "error_handling"]
                }
            ]
        except Exception as e:
            self.logger.error(f"Failed to get agents status: {e}")
            return []
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow status by ID."""
        if not self._workflow_executor:
            return None
        
        try:
            return await self._workflow_executor.get_workflow_status(workflow_id)
        except Exception as e:
            self.logger.error(f"Failed to get workflow status: {e}")
            return None
    
    async def get_tasks_status(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get tasks status for a workflow."""
        if not self._workflow_executor:
            return []
        
        try:
            return await self._workflow_executor.get_tasks_status(workflow_id)
        except Exception as e:
            self.logger.error(f"Failed to get tasks status: {e}")
            return []
    
    async def get_reasoning_chain(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get reasoning chain for a workflow."""
        if not self._workflow_executor:
            return []
        
        try:
            return await self._workflow_executor.get_reasoning_chain(workflow_id)
        except Exception as e:
            self.logger.error(f"Failed to get reasoning chain: {e}")
            return []
    
    async def get_planning_agent_status(self) -> Optional[Dict[str, Any]]:
        """Get planning agent specific status."""
        if not self._workflow_executor:
            return None
        
        try:
            status = await self._workflow_executor.planning_agent.get_status()
            return {
                "status": status.get("status", "idle"),
                "current_analysis": status.get("current_analysis"),
                "plan": status.get("generated_plan", [])
            }
        except Exception as e:
            self.logger.error(f"Failed to get planning agent status: {e}")
            return None
    
    async def get_execution_agent_status(self) -> Optional[Dict[str, Any]]:
        """Get execution agent specific status."""
        if not self._workflow_executor:
            return None
        
        try:
            status = await self._workflow_executor.execution_agent.get_status()
            return {
                "status": status.get("status", "idle"),
                "current_task": status.get("current_task"),
                "tools_executing": status.get("active_tools", []),
                "completed_tasks": status.get("completed_tasks", 0)
            }
        except Exception as e:
            self.logger.error(f"Failed to get execution agent status: {e}")
            return None
    
    async def shutdown(self) -> None:
        """Shutdown the agent engine and cleanup resources."""
        self.logger.info("Shutting down agent engine...")
        
        if self._workflow_executor:
            await self._workflow_executor.cancel_workflow()
            
        self._initialized = False
        self._tool_bridge = None
        self._workflow_executor = None
        
        self.logger.info("Agent engine shutdown completed")
