"""
Planning Agent for query decomposition and task planning.

Analyzes user queries and decomposes them into structured, actionable task lists
with appropriate priorities and dependencies.
"""

import json
import logging
from typing import Any, Dict, List, Union

from pydantic import BaseModel, Field

from ..models import AgentConfig, AgentResult, AgentType
# Integration moved to app layer
from ..tasks import Task, TaskList, TaskPriority
from .base_agent import BaseAgent


class TaskPlan(BaseModel):
    """Structured output for planning agent."""
    analysis: str = Field(description="Analysis of the user query")
    approach: str = Field(description="High-level approach to solve the query")
    tasks: List[Dict[str, Any]] = Field(
        description="List of task specifications")
    execution_strategy: str = Field(description="Strategy for task execution")
    estimated_complexity: str = Field(
        description="Complexity assessment: simple, moderate, complex")
    requires_tools: List[str] = Field(
        default_factory=list, description="Tools that will be needed")


class PlanningAgent(BaseAgent):
    """
    Planning Agent specializes in analyzing user queries and creating comprehensive
    task plans with proper dependencies and execution strategies.

    Responsibilities:
    - Query analysis and intent understanding
    - Task decomposition and dependency mapping  
    - Priority assignment and complexity assessment
    - Tool requirement identification
    - Execution strategy formulation
    """

    def __init__(self, config: AgentConfig, tool_bridge, logger: logging.Logger = None):
        super().__init__(config, tool_bridge, logger)

        # Override agent with structured output
        self.agent = self.agent.__class__(
            model=config.model,
            system_prompt=config.system_prompt or self.get_default_system_prompt(),
            output_type=TaskPlan
        )

    def get_default_system_prompt(self) -> str:
        """Get the default system prompt for planning agent."""
        return """You are a strategic planning specialist responsible for analyzing user queries and decomposing them into actionable task lists.

Your role:
1. ANALYZE the user query to understand intent, scope, and requirements
2. DECOMPOSE complex queries into discrete, manageable tasks
3. IDENTIFY task dependencies and execution order
4. ASSIGN appropriate priorities based on importance and urgency
5. ESTIMATE complexity and resource requirements
6. RECOMMEND tools and approaches for task completion

Key principles:
- Break down complex problems into smaller, focused tasks
- Ensure tasks are specific, measurable, and actionable
- Consider dependencies between tasks and order them logically
- Identify which tools from the available MCP servers will be needed
- Balance thoroughness with efficiency
- Consider error scenarios and recovery strategies

Available tool categories:
- Filesystem: File operations, directory management, content manipulation
- Git: Version control, history analysis, branch management
- Codebase: Code analysis, structure understanding, definition finding
- DevTools: Testing, linting, building, dependency management
- Exa: Web search, content crawling, real-time information

Output a comprehensive task plan with clear analysis, approach, and executable tasks."""

    async def process_request(self, request: Union[str, Dict[str, Any]], context: Dict[str, Any] = None) -> AgentResult:
        """
        Process a planning request and generate a structured task plan.

        Args:
            request: User query to analyze and plan
            context: Additional context including available tools and system state

        Returns:
            AgentResult containing the structured task plan
        """
        try:
            # Extract query string
            if isinstance(request, dict):
                query = request.get("query", str(request))
            else:
                query = str(request)

            self.logger.info(f"Planning agent processing query: {query}")

            # Prepare context with available tools
            tools_context = await self._prepare_tools_context()

            # Create enhanced prompt with context
            enhanced_prompt = await self._create_enhanced_prompt(query, context or {}, tools_context)

            # Execute planning with Pydantic AI
            self.logger.debug("Executing planning agent with enhanced prompt")
            response = await self.agent.run(enhanced_prompt)

            # Extract structured plan
            task_plan = response.output

            # Convert to TaskList
            task_list = await self._convert_plan_to_task_list(task_plan, query)

            # Extract token usage
            token_usage = self._extract_token_usage(response)

            self.logger.info(f"Planning completed with {
                             len(task_list.tasks)} tasks")

            return AgentResult(
                agent_type=AgentType.PLANNING,
                success=True,
                output=task_list,
                execution_time_seconds=0,  # Will be set by base class
                token_usage=token_usage,
                metadata={
                    "original_query": query,
                    "task_plan": task_plan.model_dump(),
                    "task_count": len(task_list.tasks),
                    "estimated_complexity": task_plan.estimated_complexity
                }
            )

        except Exception as e:
            error_msg = f"Planning failed: {str(e)}"
            self.logger.error(error_msg)

            return AgentResult(
                agent_type=AgentType.PLANNING,
                success=False,
                error=error_msg,
                execution_time_seconds=0
            )

    async def _prepare_tools_context(self) -> Dict[str, Any]:
        """Prepare context about available tools for planning."""
        try:
            # Get all available tools
            all_tools = await self.mcp_bridge.get_available_tools()

            # Group by server type
            tools_by_server = {}
            for tool in all_tools:
                server_type = tool.server_type
                if server_type not in tools_by_server:
                    tools_by_server[server_type] = []
                tools_by_server[server_type].append({
                    "name": tool.name,
                    "description": tool.description
                })

            return {
                "tools_by_server": tools_by_server,
                "total_tools": len(all_tools),
                "server_types": list(tools_by_server.keys())
            }

        except Exception as e:
            self.logger.warning(f"Failed to prepare tools context: {e}")
            return {"error": str(e)}

    async def _create_enhanced_prompt(
        self,
        query: str,
        context: Dict[str, Any],
        tools_context: Dict[str, Any]
    ) -> str:
        """Create an enhanced prompt with context and available tools."""

        # Build tools description
        tools_description = "Available MCP tools:\n"
        for server_type, tools in tools_context.get("tools_by_server", {}).items():
            tools_description += f"\n{server_type.upper()} SERVER:\n"
            for tool in tools[:5]:  # Limit to first 5 tools per server
                tools_description += f"  - {tool['name']
                                            }: {tool['description']}\n"
            if len(tools) > 5:
                tools_description += f"  ... and {len(tools) - 5} more tools\n"

        # Build context description
        context_info = ""
        if context:
            context_info = f"\nAdditional context:\n{
                json.dumps(context, indent=2)}\n"

        prompt = f"""Analyze this user query and create a comprehensive task execution plan:

USER QUERY: "{query}"

{tools_description}

{context_info}

Instructions:
1. Analyze the query to understand what the user wants to accomplish
2. Break down the work into specific, actionable tasks
3. For each task, specify:
   - Clear description of what needs to be done
   - Priority level (1-4, where 4 is highest)
   - Dependencies on other tasks (use task numbers)
   - Estimated complexity and tools needed
4. Create an execution strategy that maximizes efficiency
5. Consider potential challenges and mitigation strategies

Provide a structured analysis and task breakdown."""

        return prompt

    async def _convert_plan_to_task_list(self, task_plan: TaskPlan, original_query: str) -> TaskList:
        """Convert the structured task plan into a TaskList object."""

        task_list = TaskList(
            name=f"Plan for: {original_query[:50]}...",
            metadata={
                "original_query": original_query,
                "analysis": task_plan.analysis,
                "approach": task_plan.approach,
                "execution_strategy": task_plan.execution_strategy,
                "estimated_complexity": task_plan.estimated_complexity
            }
        )

        # Convert task specifications to Task objects
        for i, task_spec in enumerate(task_plan.tasks):
            # Extract task information with defaults
            description = task_spec.get("description", f"Task {i+1}")
            priority_num = task_spec.get("priority", 2)
            dependencies = task_spec.get("dependencies", [])
            tools_required = task_spec.get("tools_required", [])
            estimated_duration = task_spec.get("estimated_duration_seconds")

            # Map priority number to enum
            priority_mapping = {1: TaskPriority.LOW, 2: TaskPriority.MEDIUM,
                                3: TaskPriority.HIGH, 4: TaskPriority.CRITICAL}
            priority = priority_mapping.get(priority_num, TaskPriority.MEDIUM)

            # Create task
            task = Task(
                description=description,
                priority=priority,
                dependencies=dependencies,
                tools_required=tools_required,
                estimated_duration_seconds=estimated_duration,
                metadata={
                    "task_number": i + 1,
                    "complexity": task_spec.get("complexity", "moderate"),
                    "category": task_spec.get("category", "general")
                }
            )

            task_list.add_task(task)

        # Update execution order based on dependencies
        task_list.execution_order = self._optimize_execution_order(
            task_list.tasks)

        return task_list

    def _optimize_execution_order(self, tasks: List[Task]) -> List[str]:
        """Optimize task execution order based on dependencies and priorities."""

        # Create a mapping of task IDs to tasks
        task_map = {task.id: task for task in tasks}

        # Topological sort with priority consideration
        visited = set()
        temp_visited = set()
        execution_order = []

        def visit(task_id: str):
            if task_id in temp_visited:
                # Circular dependency detected - log warning and continue
                self.logger.warning(
                    f"Circular dependency detected involving task {task_id}")
                return

            if task_id in visited:
                return

            temp_visited.add(task_id)
            task = task_map.get(task_id)

            if task:
                # Visit dependencies first
                for dep_id in task.dependencies:
                    if dep_id in task_map:
                        visit(dep_id)

            temp_visited.remove(task_id)
            visited.add(task_id)
            execution_order.append(task_id)

        # Sort tasks by priority first (higher priority first)
        sorted_tasks = sorted(tasks, key=lambda t: (
            t.priority.value, t.created_at), reverse=True)

        # Visit all tasks
        for task in sorted_tasks:
            if task.id not in visited:
                visit(task.id)

        return execution_order

    async def analyze_query_complexity(self, query: str) -> Dict[str, Any]:
        """Analyze the complexity of a query without full planning."""

        simple_prompt = f"""Quickly analyze this query and assess its complexity:

Query: "{query}"

Provide a brief analysis of:
1. Complexity level (simple/moderate/complex)
2. Main categories of work required
3. Estimated number of steps needed
4. Key challenges or considerations

Keep the response concise and focused."""

        try:
            response = await self.agent.run(simple_prompt)

            return {
                "success": True,
                "analysis": response.output if hasattr(response, 'output') else str(response),
                "token_usage": self._extract_token_usage(response)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
