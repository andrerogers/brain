import json
import logging
import time
from typing import Any, Dict, List, Union

from pydantic import BaseModel, Field

from .base_agent import BaseAgent
from ..models import AgentConfig, AgentResult, AgentType, ToolCall
from .orchestrator_agent import ToolExecutionPlan, ToolExecutionStep


class ExecutionResult(BaseModel):
    """Result of executing a tool execution plan."""
    task_id: str
    success: bool
    completed_steps: int
    total_steps: int
    execution_summary: str = Field(
        description="Summary of what was accomplished")
    final_output: str = Field(
        description="Final synthesized result for the user")
    step_results: List[Dict[str, Any]] = Field(default_factory=list)
    errors_encountered: List[str] = Field(default_factory=list)
    execution_time_seconds: float
    tool_calls_made: int
    recovery_actions_taken: List[str] = Field(default_factory=list)


class ExecutionAgent(BaseAgent):
    """
    Execution Agent specializes in executing tool plans and synthesizing results.

    Responsibilities:
    - Execute tool execution plans step by step
    - Handle errors and implement recovery strategies
    - Manage parameter passing between tool calls
    - Synthesize results into coherent user responses
    - Track execution progress and performance
    - Provide detailed execution reporting
    """

    def __init__(self, config: AgentConfig, tool_bridge, logger: logging.Logger = None):
        super().__init__(config, tool_bridge, logger)

        # Override agent with structured output
        self.agent = self.agent.__class__(
            model=config.model,
            system_prompt=config.system_prompt or self.get_default_system_prompt(),
            output_type=ExecutionResult
        )

        # Execution state
        self.current_execution_plan: ToolExecutionPlan = None
        self.step_results: List[Dict[str, Any]] = []
        self.execution_context: Dict[str, Any] = {}

    def get_default_system_prompt(self) -> str:
        """Get the default system prompt for execution agent."""
        return """You are a task execution specialist responsible for executing tool plans and synthesizing results.

Your role:
1. EXECUTE tool execution plans step by step with precision
2. HANDLE errors gracefully and implement recovery strategies
3. MANAGE data flow and parameter passing between tools
4. SYNTHESIZE results into clear, actionable responses for users
5. TRACK progress and provide detailed execution reporting
6. ENSURE all objectives are met or provide clear explanations of limitations

Key principles:
- Execute each step carefully and verify results before proceeding
- Handle errors with appropriate recovery strategies (retry, fallback, skip)
- Maintain context and state between tool executions
- Transform technical tool outputs into user-friendly responses
- Provide clear status updates and progress information
- Document all actions taken and decisions made
- Focus on achieving the user's original intent

CRITICAL: Tool Usage Guidelines
- ALWAYS check tool parameter requirements before calling any tool
- NEVER call a tool without providing ALL required parameters
- Use the tool parameter schemas to understand what each tool needs
- If a tool fails with parameter validation errors, examine the error message for guidance
- Common tools require specific parameters:
  * write_file: requires both 'path' AND 'content' parameters
  * read_file: requires 'path' parameter
  * git_commit: requires 'message' parameter
  * run_command: requires 'command' parameter
- When tool validation fails, retry with the correct parameters based on the error guidance

Error handling strategies:
- RETRY: Retry the same operation with same parameters (for transient errors)
- RETRY_WITH_CORRECTION: Fix parameter issues and retry (for validation errors)
- FALLBACK: Use alternative tools or approaches (for tool unavailability)
- SKIP: Skip non-critical steps and continue (for optional operations)
- ABORT: Stop execution for critical failures (for data safety)

Parameter Validation Error Recovery:
1. Read the parameter validation error message carefully
2. Check which required parameters are missing
3. Review the tool schema for parameter types and descriptions
4. Retry the tool call with all required parameters included
5. Ensure parameter types match expectations (string, boolean, number, etc.)

Result synthesis guidelines:
- Combine outputs from multiple tools into coherent responses
- Translate technical details into user-understandable language
- Highlight key findings, actions taken, and outcomes achieved
- Include relevant details while maintaining clarity
- Provide actionable next steps when appropriate

Your output should be a comprehensive execution result with clear summaries and user-friendly final output."""

    async def process_request(self, request: Union[str, Dict[str, Any]], context: Dict[str, Any] = None) -> AgentResult:
        """
        Process an execution request for a tool execution plan.

        Args:
            request: Tool execution plan or task with plan
            context: Additional execution context

        Returns:
            AgentResult with execution results
        """
        try:
            # Parse request to get execution plan
            execution_plan = await self._parse_execution_request(request)

            if not execution_plan:
                raise ValueError("No valid execution plan found in request")

            self.logger.info(f"Executing plan for task {execution_plan.task_id} with {
                             len(execution_plan.execution_steps)} steps")

            # Execute the plan
            execution_result = await self._execute_plan(execution_plan, context or {})

            # Extract token usage if agent was used for synthesis
            token_usage = {}
            if hasattr(execution_result, '_synthesis_response'):
                token_usage = self._extract_token_usage(
                    execution_result._synthesis_response)

            return AgentResult(
                agent_type=AgentType.EXECUTION,
                success=execution_result.success,
                output=execution_result,
                execution_time_seconds=execution_result.execution_time_seconds,
                token_usage=token_usage,
                tool_calls=[ToolCall(
                    tool_name=step.get("tool_name", "unknown"),
                    parameters=step.get("parameters", {}),
                    result=step.get("result"),
                    error=step.get("error"),
                    execution_time_seconds=step.get("execution_time", 0)
                ) for step in execution_result.step_results],
                metadata={
                    "task_id": execution_plan.task_id,
                    "completed_steps": execution_result.completed_steps,
                    "total_steps": execution_result.total_steps,
                    "tool_calls_made": execution_result.tool_calls_made,
                    "recovery_actions": execution_result.recovery_actions_taken
                }
            )

        except Exception as e:
            error_msg = f"Execution failed: {str(e)}"
            self.logger.error(error_msg)

            return AgentResult(
                agent_type=AgentType.EXECUTION,
                success=False,
                error=error_msg,
                execution_time_seconds=0
            )

    async def _parse_execution_request(self, request: Union[str, Dict[str, Any]]) -> ToolExecutionPlan:
        """Parse the execution request to extract the execution plan."""

        if isinstance(request, dict):
            if "execution_plan" in request:
                plan_data = request["execution_plan"]
                if isinstance(plan_data, ToolExecutionPlan):
                    return plan_data
                elif isinstance(plan_data, dict):
                    return ToolExecutionPlan(**plan_data)

            elif "task" in request and "plan" in request:
                # Task with embedded plan
                return ToolExecutionPlan(**request["plan"])

            else:
                # Try to parse entire request as execution plan
                return ToolExecutionPlan(**request)

        else:
            raise ValueError(
                "Request must be a dictionary containing execution plan")

    async def _execute_plan(self, plan: ToolExecutionPlan, context: Dict[str, Any]) -> ExecutionResult:
        """Execute a tool execution plan step by step."""

        start_time = time.time()
        self.current_execution_plan = plan
        self.step_results = []
        self.execution_context = context.copy()

        completed_steps = 0
        total_steps = len(plan.execution_steps)
        errors_encountered = []
        recovery_actions = []
        tool_calls_made = 0

        self.logger.info(f"Starting execution of {
                         total_steps} steps for task {plan.task_id}")

        try:
            # Execute steps in order
            for i, step in enumerate(plan.execution_steps):

                # Check dependencies
                if not await self._check_step_dependencies(step, i):
                    error_msg = f"Step {
                        step.step_number} dependencies not satisfied"
                    self.logger.warning(error_msg)
                    errors_encountered.append(error_msg)
                    continue

                # Execute step
                step_result = await self._execute_step(step, i + 1)
                self.step_results.append(step_result)
                tool_calls_made += 1

                if step_result["success"]:
                    completed_steps += 1
                    self.logger.info(
                        f"Step {step.step_number} completed successfully")
                else:
                    error_msg = f"Step {step.step_number} failed: {
                        step_result.get('error', 'Unknown error')}"
                    self.logger.error(error_msg)
                    errors_encountered.append(error_msg)

                    # Attempt recovery
                    recovery_result = await self._attempt_recovery(step, step_result, i)
                    if recovery_result:
                        recovery_actions.append(recovery_result)
                        if recovery_result.startswith("SUCCESS"):
                            completed_steps += 1

            # Calculate execution time
            execution_time = time.time() - start_time

            # Synthesize results
            synthesis_result = await self._synthesize_results(plan, completed_steps, total_steps)

            return ExecutionResult(
                task_id=plan.task_id,
                success=completed_steps == total_steps,
                completed_steps=completed_steps,
                total_steps=total_steps,
                execution_summary=synthesis_result["summary"],
                final_output=synthesis_result["final_output"],
                step_results=self.step_results,
                errors_encountered=errors_encountered,
                execution_time_seconds=execution_time,
                tool_calls_made=tool_calls_made,
                recovery_actions_taken=recovery_actions
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Plan execution failed: {str(e)}"
            self.logger.error(error_msg)

            return ExecutionResult(
                task_id=plan.task_id,
                success=False,
                completed_steps=completed_steps,
                total_steps=total_steps,
                execution_summary=f"Execution failed after {
                    completed_steps}/{total_steps} steps",
                final_output=f"Task execution encountered a critical error: {
                    error_msg}",
                step_results=self.step_results,
                errors_encountered=errors_encountered + [error_msg],
                execution_time_seconds=execution_time,
                tool_calls_made=tool_calls_made,
                recovery_actions_taken=recovery_actions
            )

    async def _check_step_dependencies(self, step: ToolExecutionStep, step_index: int) -> bool:
        """Check if step dependencies are satisfied."""

        if not step.depends_on_steps:
            return True

        for dep_step_num in step.depends_on_steps:
            # Find the corresponding step result
            dep_result = None
            for result in self.step_results:
                if result.get("step_number") == dep_step_num:
                    dep_result = result
                    break

            if not dep_result or not dep_result.get("success"):
                self.logger.warning(f"Step {step.step_number} dependency {
                                    dep_step_num} not satisfied")
                return False

        return True

    async def _execute_step(self, step: ToolExecutionStep, step_number: int) -> Dict[str, Any]:
        """Execute a single tool execution step."""

        start_time = time.time()

        self.logger.info(f"Executing step {step_number}: {
                         step.tool_name} with params {step.parameters}")

        try:
            # Resolve dynamic parameters from previous step results
            resolved_parameters = await self._resolve_step_parameters(step.parameters)

            # Execute the tool
            tool_call = await self.mcp_bridge.execute_tool(
                tool_name=step.tool_name,
                parameters=resolved_parameters,
                server_id=step.server_id
            )

            execution_time = time.time() - start_time

            if tool_call.error:
                return {
                    "step_number": step.step_number,
                    "tool_name": step.tool_name,
                    "success": False,
                    "error": tool_call.error,
                    "execution_time": execution_time,
                    "parameters": resolved_parameters
                }

            # Store result in execution context for future steps
            self.execution_context[f"step_{
                step.step_number}_result"] = tool_call.result

            return {
                "step_number": step.step_number,
                "tool_name": step.tool_name,
                "success": True,
                "result": tool_call.result,
                "execution_time": execution_time,
                "parameters": resolved_parameters,
                "description": step.description
            }

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)

            return {
                "step_number": step.step_number,
                "tool_name": step.tool_name,
                "success": False,
                "error": error_msg,
                "execution_time": execution_time,
                "parameters": step.parameters
            }

    async def _resolve_step_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve dynamic parameters using results from previous steps."""

        resolved = {}

        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # Dynamic parameter reference
                ref = value[2:-1]  # Remove ${ and }

                if ref in self.execution_context:
                    resolved[key] = self.execution_context[ref]
                else:
                    # Try to find in step results
                    for step_result in self.step_results:
                        if ref == f"step_{step_result.get('step_number')}_result":
                            resolved[key] = step_result.get("result")
                            break
                    else:
                        # Keep original value if reference not found
                        resolved[key] = value
            else:
                resolved[key] = value

        return resolved

    async def _attempt_recovery(
        self,
        step: ToolExecutionStep,
        step_result: Dict[str, Any],
        step_index: int
    ) -> str:
        """Attempt to recover from a failed step."""

        error_handling = step.error_handling.lower()

        if error_handling == "retry_once":
            self.logger.info(f"Retrying step {step.step_number}")

            # Retry the step once
            retry_result = await self._execute_step(step, step.step_number)
            if retry_result["success"]:
                self.step_results[step_index] = retry_result
                return f"SUCCESS: Retry of step {step.step_number} succeeded"
            else:
                return f"FAILED: Retry of step {step.step_number} failed"

        elif error_handling == "skip":
            self.logger.info(f"Skipping failed step {step.step_number}")
            return f"SKIPPED: Step {step.step_number} skipped due to failure"

        elif error_handling == "fallback":
            # For now, just log - could implement fallback tool selection
            self.logger.info(f"Fallback needed for step {step.step_number}")
            return f"FALLBACK: Step {step.step_number} needs fallback implementation"

        return f"NO_RECOVERY: No recovery action for step {step.step_number}"

    async def _synthesize_results(
        self,
        plan: ToolExecutionPlan,
        completed_steps: int,
        total_steps: int
    ) -> Dict[str, str]:
        """Synthesize execution results into user-friendly output."""

        # Prepare synthesis context
        synthesis_context = {
            "original_task": plan.task_description,
            "execution_approach": plan.approach,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "step_results": self.step_results,
            "success_criteria": plan.success_criteria
        }

        # Create synthesis prompt
        synthesis_prompt = f"""Synthesize the execution results into a clear, user-friendly response:

ORIGINAL TASK: {plan.task_description}
EXECUTION APPROACH: {plan.approach}
COMPLETION STATUS: {completed_steps}/{total_steps} steps completed
SUCCESS CRITERIA: {plan.success_criteria}

EXECUTION RESULTS:
{json.dumps(self.step_results, indent=2)}

Please provide:
1. A brief summary of what was accomplished
2. A detailed final output that directly addresses the user's original request
3. Any important findings, outcomes, or next steps
4. Clear indication of success/failure and reasons

Focus on being helpful and actionable while translating technical details into user-friendly language."""

        try:
            # Use the agent to synthesize results
            response = await self.agent.run(synthesis_prompt)

            # Store response for token usage extraction
            if hasattr(response, 'output'):
                synthesis_result = response.output
                synthesis_result._synthesis_response = response

                return {
                    "summary": synthesis_result.execution_summary,
                    "final_output": synthesis_result.final_output
                }
            else:
                # Fallback synthesis
                return self._fallback_synthesis(completed_steps, total_steps, plan.task_description)

        except Exception as e:
            self.logger.warning(f"AI synthesis failed, using fallback: {e}")
            return self._fallback_synthesis(completed_steps, total_steps, plan.task_description)

    def _fallback_synthesis(self, completed_steps: int, total_steps: int, task_description: str) -> Dict[str, str]:
        """Fallback synthesis when AI synthesis fails."""

        success_rate = (completed_steps / total_steps) * \
            100 if total_steps > 0 else 0

        if completed_steps == total_steps:
            summary = f"Task completed successfully. All {
                total_steps} execution steps completed."
            final_output = f"Successfully completed the requested task: {
                task_description}"
        elif completed_steps > 0:
            summary = f"Task partially completed. {
                completed_steps}/{total_steps} steps completed ({success_rate:.1f}%)."
            final_output = f"Partially completed the task: {
                task_description}. Some steps encountered issues but partial results are available."
        else:
            summary = "Task execution failed. No steps completed successfully."
            final_output = f"Failed to complete the requested task: {
                task_description}. Please check the error details and try again."

        return {
            "summary": summary,
            "final_output": final_output
        }

    async def execute_single_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a single tool directly (bypass plan execution)."""

        return await self.execute_tool(tool_name, parameters, context or {})
