import json
import logging
from typing import Any, Dict, List, Optional, Union

import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ..models import AgentConfig, AgentResult, AgentType
from ..tasks import Task, TaskList
from .base_agent import BaseAgent


class ToolExecutionStep(BaseModel):
    """Individual step in a tool execution plan."""

    step_number: int
    tool_name: str
    server_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    description: str
    expected_output: str
    error_handling: str = "retry_once"
    depends_on_steps: List[int] = Field(default_factory=list)


class ToolExecutionPlan(BaseModel):
    """Complete tool execution plan for a task."""

    task_id: str
    task_description: str
    approach: str = Field(description="High-level approach for tool execution")
    execution_steps: List[ToolExecutionStep] = Field(
        description="Ordered list of tool execution steps"
    )
    fallback_strategy: str = Field(
        description="Fallback approach if primary plan fails"
    )
    estimated_duration_seconds: int = Field(
        description="Estimated total execution time"
    )
    risk_assessment: str = Field(description="Assessment of execution risks")
    success_criteria: str = Field(
        description="How to determine if execution was successful"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the execution plan"
    )


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent specializes in tool selection and workflow optimization.

    Responsibilities:
    - Analyze tasks to understand tool requirements
    - Select optimal tools for each task step
    - Design efficient execution sequences
    - Handle tool dependencies and parameter mapping
    - Optimize for performance and reliability
    - Plan error handling and fallback strategies
    """

    def __init__(self, config: AgentConfig, tool_bridge, logger: logging.Logger):
        super().__init__(config, tool_bridge, logger)

        self.agent = Agent(
            model=config.model,
            system_prompt=config.system_prompt or self.get_default_system_prompt(),
            output_type=ToolExecutionPlan,
        )

    def get_default_system_prompt(self) -> str:
        """Get the default system prompt for orchestrator agent."""
        return """You are a tool orchestration specialist responsible for designing optimal tool execution workflows.

Your role:
1. ANALYZE tasks to understand their requirements and objectives
2. SELECT the most appropriate tools from available MCP servers
3. DESIGN efficient execution sequences that minimize redundancy
4. OPTIMIZE workflows for performance, reliability, and maintainability  
5. PLAN error handling and fallback strategies
6. MAP parameters between tools and handle data transformations

Key principles:
- Choose the most appropriate tool for each specific operation
- Minimize the number of tool calls while maintaining effectiveness
- Consider tool dependencies and execution order
- Plan for error scenarios and provide fallback approaches
- Optimize parameter passing and data flow between tools
- Balance thoroughness with efficiency
- Consider resource constraints and execution time

CRITICAL: Tool Parameter Requirements
When designing tool execution plans, you must specify ALL required parameters for each tool:

filesystem (8 tools):
- write_file: requires 'path' AND 'content' parameters
- read_file: requires 'path' parameter
- edit_file: requires 'path', 'old_text', and 'new_text' parameters
- delete_file: requires 'path' parameter
- list_directory: requires 'path' parameter
- create_directory: requires 'path' parameter
- get_file_info: requires 'path' parameter
- search_files: requires 'pattern' and 'directory' parameters

git (11 tools):
- git_commit: requires 'message' parameter
- git_branch_info: no parameters required
- git_status: requires 'path' parameter
- git_diff: may require 'file_path' parameter
- Most other git tools require 'path' parameter for repository location

codebase (6 tools):
- find_definition: requires 'symbol' parameter
- find_references: requires 'symbol' parameter
- analyze_project: requires 'path' parameter
- get_project_structure: requires 'path' parameter

devtools (6 tools):
- run_command_safe: requires 'command' parameter
- run_tests: may require 'pattern' parameter
- Most testing tools work with 'path' parameter

exa (2 tools):
- web_search_exa: requires 'query' parameter
- crawl_url: requires 'url' parameter

Tool Usage Rules:
1. ALWAYS include ALL required parameters in tool execution plans
2. Check tool schemas to understand parameter types (string, boolean, number)
3. Provide realistic parameter values, not placeholders
4. For file operations, use appropriate file paths
5. For commands, specify complete command strings
6. For searches, provide meaningful query terms
7. CRITICAL: Use exact server IDs as listed above (lowercase: filesystem, git, codebase, devtools, exa, context7)

Design comprehensive tool execution plans that achieve task objectives efficiently with COMPLETE parameter specifications."""

    async def process_request(
        self,
        request: Union[str, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Process an orchestration request for a task or task list.

        Args:
            request: Task or task list to orchestrate
            context: Additional context including available tools

        Returns:
            AgentResult containing tool execution plans
        """
        try:
            # Parse request
            if isinstance(request, dict):
                if "task" in request:
                    # Single task orchestration
                    task = request["task"]
                    return await self._orchestrate_single_task(task, context or {})
                elif "task_list" in request:
                    # Multiple task orchestration
                    task_list = request["task_list"]
                    return await self._orchestrate_task_list(task_list, context or {})
                else:
                    raise ValueError("Request must contain 'task' or 'task_list'")
            else:
                # TODO
                # fix the title
                task = Task(
                    title="Orchestrator Processing Request", description=str(request)
                )
                return await self._orchestrate_single_task(task, context or {})

        except Exception as e:
            error_msg = f"Orchestration failed: {str(e)}"
            self.logger.error(error_msg)

            return AgentResult(
                agent_type=AgentType.ORCHESTRATOR,
                success=False,
                error=error_msg,
                execution_time_seconds=0,
            )

    async def _orchestrate_single_task(
        self, task: Task, context: Dict[str, Any]
    ) -> AgentResult:
        """Orchestrate a single task."""

        self.logger.info(f"Orchestrating task: {task.description}")

        # Prepare context with available tools
        with logfire.span("orchestrator_agent.prepare_detailed_tools_context"):
            tools_context = await self._prepare_detailed_tools_context()

        # Get tool recommendations
        with logfire.span(
            "orchestrator_agent.get_tool_recommendations",
            task_description=task.description,
        ):
            recommended_tools = await self.get_tool_recommendations(task)

        # Create enhanced prompt
        with logfire.span("orchestrator_agent.create_task_orchestration_prompt"):
            enhanced_prompt = await self._create_task_orchestration_prompt(
                task, context, tools_context, recommended_tools
            )

        # Execute orchestration
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Executing orchestrator agent with task-specific prompt")

        with logfire.span(
            "orchestrator_agent.agent_run", prompt_length=len(enhanced_prompt)
        ):
            response = await self.agent.run(enhanced_prompt)

        # Extract execution plan
        execution_plan = response.output

        # Validate and enhance the plan
        with logfire.span(
            "orchestrator_agent.enhance_execution_plan",
            steps_count=len(execution_plan.execution_steps),
        ):
            enhanced_plan = await self._enhance_execution_plan(
                execution_plan, tools_context
            )

        # Extract token usage
        token_usage = self._extract_token_usage(response)

        self.logger.info(
            f"Orchestration completed with {
                         len(execution_plan.execution_steps)} steps"
        )

        return AgentResult(
            agent_type=AgentType.ORCHESTRATOR,
            success=True,
            output=enhanced_plan,
            execution_time_seconds=0,  # Will be set by base class
            token_usage=token_usage,
            metadata={
                "task_id": task.id,
                "task_description": task.description,
                "step_count": len(execution_plan.execution_steps),
                "estimated_duration": execution_plan.estimated_duration_seconds,
                "recommended_tools": recommended_tools,
            },
        )

    async def _orchestrate_task_list(
        self, task_list: TaskList, context: Dict[str, Any]
    ) -> AgentResult:
        """Orchestrate multiple tasks in a task list."""

        self.logger.info(
            f"Orchestrating task list with {
                         len(task_list.tasks)} tasks"
        )

        orchestration_results = []
        total_estimated_duration = 0

        # Orchestrate each task
        with logfire.span(
            "orchestrator_agent.orchestrate_task_list", task_count=len(task_list.tasks)
        ):
            for task in task_list.tasks:
                task_result = await self._orchestrate_single_task(task, context)
                orchestration_results.append(task_result)

                if task_result.success and task_result.output:
                    total_estimated_duration += (
                        task_result.output.estimated_duration_seconds
                    )

        # Create summary
        successful_orchestrations = [r for r in orchestration_results if r.success]

        return AgentResult(
            agent_type=AgentType.ORCHESTRATOR,
            success=len(successful_orchestrations) == len(orchestration_results),
            output={
                "task_list_id": task_list.id,
                "orchestration_results": orchestration_results,
                "total_estimated_duration_seconds": total_estimated_duration,
                "successful_tasks": len(successful_orchestrations),
                "total_tasks": len(orchestration_results),
            },
            execution_time_seconds=0,
            metadata={
                "task_list_name": task_list.name,
                "orchestration_summary": {
                    "total_tasks": len(orchestration_results),
                    "successful": len(successful_orchestrations),
                    "failed": len(orchestration_results)
                    - len(successful_orchestrations),
                },
            },
        )

    async def _prepare_detailed_tools_context(self) -> Dict[str, Any]:
        """Prepare detailed context about available tools."""
        try:
            all_tools = await self.tool_bridge.get_available_tools()

            # Group by server with detailed information
            tools_by_server = {}
            for tool in all_tools:
                server_type = tool.server_type
                if server_type not in tools_by_server:
                    tools_by_server[server_type] = []

                tools_by_server[server_type].append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                        "server_id": tool.server_id,
                    }
                )

            return {
                "tools_by_server": tools_by_server,
                "total_tools": len(all_tools),
                "server_status": await self.tool_bridge.get_server_status(),
            }

        except Exception as e:
            self.logger.warning(f"Failed to prepare detailed tools context: {e}")
            return {"error": str(e)}

    async def _create_task_orchestration_prompt(
        self,
        task: Task,
        context: Dict[str, Any],
        tools_context: Dict[str, Any],
        recommended_tools: List[str],
    ) -> str:
        """Create a detailed prompt for task orchestration."""

        # Build detailed tools description
        tools_description = "Available MCP tools with details:\n\n"
        for server_type, tools in tools_context.get("tools_by_server", {}).items():
            tools_description += f"{server_type} server:\n"
            for tool in tools:
                tools_description += f"  • {tool['name']
                                            }: {tool['description']}\n"
                if tool.get("parameters"):
                    # Show key parameters
                    params = tool["parameters"]
                    if isinstance(params, dict) and "properties" in params:
                        param_names = list(params["properties"].keys())[
                            :3
                        ]  # First 3 params
                        if param_names:
                            tools_description += f"    Parameters: {
                                ', '.join(param_names)}\n"
            tools_description += "\n"

        # Build context description
        context_info = ""
        if context:
            context_info = f"Additional context:\n{
                json.dumps(context, indent=2)}\n\n"

        # Build recommended tools section
        recommended_section = ""
        if recommended_tools:
            recommended_section = f"Recommended tools for this task: {
                ', '.join(recommended_tools)}\n\n"

        prompt = f"""Design an optimal tool execution plan for this task:

TASK: {task.description}
TASK ID: {task.id}
PRIORITY: {task.priority}
REQUIRED TOOLS: {', '.join(task.tools_required) if task.tools_required else 'None specified'}

{recommended_section}{tools_description}{context_info}

Instructions:
1. Analyze the task to understand exactly what needs to be accomplished
2. Select the most appropriate tools from the available MCP servers
3. Design an efficient execution sequence that:
   - Minimizes redundant operations
   - Handles dependencies between steps
   - Includes proper error handling
   - Optimizes for performance
4. For each execution step, specify:
   - Tool name and server
   - Required parameters
   - Expected output
   - Dependencies on previous steps
5. Provide a fallback strategy for error scenarios
6. Estimate total execution time
7. Define clear success criteria

Focus on creating a practical, executable plan that achieves the task objectives efficiently."""

        return prompt

    async def _enhance_execution_plan(
        self, plan: ToolExecutionPlan, tools_context: Dict[str, Any]
    ) -> ToolExecutionPlan:
        """Enhance and validate the execution plan."""

        # Validate tool names and servers
        available_tools = {}
        for _server_type, tools in tools_context.get("tools_by_server", {}).items():
            for tool in tools:
                available_tools[tool["name"]] = tool

        # Validate each step
        for step in plan.execution_steps:
            if step.tool_name not in available_tools:
                self.logger.warning(
                    f"Tool {step.tool_name} not found in available tools"
                )
            else:
                # Update server_id if needed or incorrect
                tool_info = available_tools[step.tool_name]
                correct_server_id = tool_info.get("server_id", "unknown")
                if not step.server_id or step.server_id != correct_server_id:
                    self.logger.info(f"Correcting server_id for {step.tool_name}: {step.server_id} -> {correct_server_id}")
                    step.server_id = correct_server_id

        # Add execution metadata
        plan.metadata = {
            "validation_passed": True,
            "available_tools_count": len(available_tools),
            "orchestration_timestamp": tools_context.get("server_status", {}).get(
                "last_cache_update", 0
            ),
        }

        return plan

    async def optimize_execution_sequence(
        self, execution_plans: List[ToolExecutionPlan]
    ) -> Dict[str, Any]:
        """Optimize the execution sequence across multiple plans."""

        # Analyze tool usage patterns
        tool_usage = {}
        total_steps = 0

        for plan in execution_plans:
            for step in plan.execution_steps:
                tool_name = step.tool_name
                tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
                total_steps += 1

        # Find optimization opportunities
        optimizations = []

        # Check for sequential tool calls that could be batched
        for plan in execution_plans:
            consecutive_tools = {}
            for i, step in enumerate(plan.execution_steps[:-1]):
                next_step = plan.execution_steps[i + 1]
                if step.tool_name == next_step.tool_name:
                    key = f"{step.tool_name}_{plan.task_id}"
                    if key not in consecutive_tools:
                        consecutive_tools[key] = []
                    consecutive_tools[key].append((i, i + 1))

            if consecutive_tools:
                optimizations.append(
                    {
                        "type": "batch_opportunity",
                        "task_id": plan.task_id,
                        "consecutive_tools": consecutive_tools,
                    }
                )

        return {
            "total_execution_plans": len(execution_plans),
            "total_execution_steps": total_steps,
            "tool_usage_distribution": tool_usage,
            "optimization_opportunities": optimizations,
            "estimated_total_duration": sum(
                p.estimated_duration_seconds for p in execution_plans
            ),
        }
