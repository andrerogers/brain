import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable

from .models import AgentConfig, AgentResult, AgentType, ProgressUpdate
from .tasks import TaskList, TaskStatus, ReasoningChain, ReasoningStep
from .agents import PlanningAgent, OrchestratorAgent, ExecutionAgent


class WorkflowExecutor:
    """
    Coordinates the execution of multi-agent workflows.

    Manages the flow between planning, orchestration, and execution agents
    to complete complex user queries through reasoning chains.
    """

    def __init__(
        self,
        tool_bridge,
        planning_config: AgentConfig,
        orchestrator_config: AgentConfig,
        execution_config: AgentConfig,
        logger: Optional[logging.Logger] = None
    ):
        self.tool_bridge = tool_bridge
        self.logger = logger or logging.getLogger("WorkflowExecutor")

        # Initialize agents with tool bridge
        self.planning_agent = PlanningAgent(
            planning_config, tool_bridge, logger)
        self.orchestrator_agent = OrchestratorAgent(
            orchestrator_config, tool_bridge, logger)
        self.execution_agent = ExecutionAgent(
            execution_config, tool_bridge, logger)

        # Workflow state
        self.current_reasoning_chain: Optional[ReasoningChain] = None
        self.is_executing = False

        self.logger.info("WorkflowExecutor initialized with all agents")

    async def initialize(self) -> None:
        """Initialize all agents and the workflow system."""
        try:
            self.logger.info("Initializing workflow executor and agents")

            # Initialize all agents concurrently
            await asyncio.gather(
                self.planning_agent.initialize(),
                self.orchestrator_agent.initialize(),
                self.execution_agent.initialize()
            )

            self.logger.info("All agents initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize workflow executor: {e}")
            raise

    async def execute_query(
        self,
        user_query: str,
        context: Dict[str, Any] = None,
        progress_callback: Optional[Callable] = None
    ) -> ReasoningChain:
        """
        Execute a complete multi-agent workflow for a user query.

        Args:
            user_query: The user's query to process
            context: Additional context for processing
            progress_callback: Optional callback for progress updates

        Returns:
            Complete ReasoningChain with results
        """
        if self.is_executing:
            raise RuntimeError(
                "Workflow executor is already processing a query")

        self.is_executing = True
        start_time = time.time()

        try:
            self.logger.info(
                f"Starting workflow execution for query: {user_query}")

            # Create reasoning chain
            reasoning_chain = ReasoningChain(
                original_query=user_query,
                task_list=TaskList(name=f"Workflow for: {user_query[:50]}...")
            )
            reasoning_chain.start_chain()
            self.current_reasoning_chain = reasoning_chain

            # Send initial progress update
            if progress_callback:
                await self._send_workflow_progress(
                    progress_callback, "starting", 0.0, 0.0, "Initializing workflow"
                )

            # Step 1: Planning
            planning_result = await self._execute_planning_step(
                user_query, context or {}, progress_callback
            )

            if not planning_result.success:
                reasoning_chain.fail_chain(
                    f"Planning failed: {planning_result.error}")
                return reasoning_chain

            task_list = planning_result.output
            reasoning_chain.task_list = task_list

            # Step 2: Orchestration
            orchestration_result = await self._execute_orchestration_step(
                task_list, context or {}, progress_callback
            )

            if not orchestration_result.success:
                reasoning_chain.fail_chain(f"Orchestration failed: {
                                           orchestration_result.error}")
                return reasoning_chain

            # Step 3: Execution
            execution_result = await self._execute_execution_step(
                orchestration_result.output, context or {}, progress_callback
            )

            if not execution_result.success:
                reasoning_chain.fail_chain(
                    f"Execution failed: {execution_result.error}")
                return reasoning_chain

            # Complete the reasoning chain
            final_output = self._synthesize_final_output(
                reasoning_chain, planning_result, orchestration_result, execution_result
            )
            reasoning_chain.complete_chain(final_output)

            # Send completion progress update
            if progress_callback:
                execution_time = time.time() - start_time
                await self._send_workflow_progress(
                    progress_callback, "completed", 100.0, execution_time, "Workflow completed successfully"
                )

            self.logger.info(f"Workflow completed successfully in {
                             reasoning_chain.total_execution_time_seconds:.2f}s")

            return reasoning_chain

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Workflow execution failed: {str(e)}"
            self.logger.error(error_msg)

            if self.current_reasoning_chain:
                self.current_reasoning_chain.fail_chain(error_msg)

            # Send error progress update
            if progress_callback:
                await self._send_workflow_progress(
                    progress_callback, "failed", 100.0, execution_time, error_msg
                )

            raise

        finally:
            self.is_executing = False
            self.current_reasoning_chain = None

    async def _execute_planning_step(
        self,
        user_query: str,
        context: Dict[str, Any],
        progress_callback: Optional[Callable]
    ) -> AgentResult:
        """Execute the planning step of the workflow."""

        self.logger.info("Executing planning step")

        # Create reasoning step
        planning_step = ReasoningStep(
            step_number=1,
            agent_type=AgentType.PLANNING,
            description="Analyze query and create task plan",
            input_data={"query": user_query, "context": context}
        )
        planning_step.status = TaskStatus.IN_PROGRESS
        self.current_reasoning_chain.add_reasoning_step(planning_step)

        # Send progress update
        if progress_callback:
            await self._send_workflow_progress(
                progress_callback, "planning", 10.0, 0.0, "Analyzing query and creating task plan"
            )

        try:
            # Execute planning agent
            start_time = time.time()
            planning_result = await self.planning_agent.execute_with_progress(
                user_query, context, progress_callback
            )
            execution_time = time.time() - start_time

            # Update reasoning step
            planning_step.status = TaskStatus.COMPLETED if planning_result.success else TaskStatus.FAILED
            planning_step.execution_time_seconds = execution_time
            planning_step.output_data = {
                "success": planning_result.success,
                "task_count": planning_result.metadata.get("task_count", 0) if planning_result.success else 0,
                "complexity": planning_result.metadata.get("estimated_complexity", "unknown") if planning_result.success else "unknown"
            }

            if not planning_result.success:
                planning_step.error = planning_result.error

            self.logger.info(f"Planning step completed with success={
                             planning_result.success}")

            return planning_result

        except Exception as e:
            planning_step.status = TaskStatus.FAILED
            planning_step.error = str(e)
            raise

    async def _execute_orchestration_step(
        self,
        task_list: TaskList,
        context: Dict[str, Any],
        progress_callback: Optional[Callable]
    ) -> AgentResult:
        """Execute the orchestration step of the workflow."""

        self.logger.info(f"Executing orchestration step for {
                         len(task_list.tasks)} tasks")

        # Create reasoning step
        orchestration_step = ReasoningStep(
            step_number=2,
            agent_type=AgentType.ORCHESTRATOR,
            description="Design tool execution plans for tasks",
            input_data={"task_list": task_list.model_dump(),
                        "context": context}
        )
        orchestration_step.status = TaskStatus.IN_PROGRESS
        self.current_reasoning_chain.add_reasoning_step(orchestration_step)

        # Send progress update
        if progress_callback:
            await self._send_workflow_progress(
                progress_callback, "orchestrating", 30.0, 0.0, "Designing tool execution plans"
            )

        try:
            # Execute orchestrator agent
            start_time = time.time()
            orchestration_result = await self.orchestrator_agent.execute_with_progress(
                {"task_list": task_list}, context, progress_callback
            )
            execution_time = time.time() - start_time

            # Update reasoning step
            orchestration_step.status = TaskStatus.COMPLETED if orchestration_result.success else TaskStatus.FAILED
            orchestration_step.execution_time_seconds = execution_time
            orchestration_step.output_data = {
                "success": orchestration_result.success,
                "orchestrated_tasks": orchestration_result.metadata.get("successful_tasks", 0) if orchestration_result.success else 0,
                "total_tasks": orchestration_result.metadata.get("total_tasks", 0) if orchestration_result.success else 0
            }

            if not orchestration_result.success:
                orchestration_step.error = orchestration_result.error

            self.logger.info(f"Orchestration step completed with success={
                             orchestration_result.success}")

            return orchestration_result

        except Exception as e:
            orchestration_step.status = TaskStatus.FAILED
            orchestration_step.error = str(e)
            raise

    async def _execute_execution_step(
        self,
        orchestration_output: Dict[str, Any],
        context: Dict[str, Any],
        progress_callback: Optional[Callable]
    ) -> AgentResult:
        """Execute the execution step of the workflow."""

        self.logger.info("Executing execution step")

        # Create reasoning step
        execution_step = ReasoningStep(
            step_number=3,
            agent_type=AgentType.EXECUTION,
            description="Execute tool plans and synthesize results",
            input_data={
                "orchestration_output": orchestration_output, "context": context}
        )
        execution_step.status = TaskStatus.IN_PROGRESS
        self.current_reasoning_chain.add_reasoning_step(execution_step)

        # Send progress update
        if progress_callback:
            await self._send_workflow_progress(
                progress_callback, "executing", 50.0, 0.0, "Executing tool plans and generating results"
            )

        try:
            # Execute all orchestrated plans
            orchestration_results = orchestration_output.get(
                "orchestration_results", [])
            execution_results = []

            for i, orchestration_result in enumerate(orchestration_results):
                if orchestration_result.success and orchestration_result.output:

                    # Send detailed progress update
                    if progress_callback:
                        progress_pct = 50.0 + \
                            (i / len(orchestration_results)) * 40.0
                        await self._send_workflow_progress(
                            progress_callback, "executing", progress_pct, 0.0,
                            f"Executing task {
                                i+1}/{len(orchestration_results)}"
                        )

                    # Execute the plan
                    exec_result = await self.execution_agent.execute_with_progress(
                        {"execution_plan": orchestration_result.output}, context, progress_callback
                    )
                    execution_results.append(exec_result)
                else:
                    # Create failed result for failed orchestration
                    failed_result = AgentResult(
                        agent_type=AgentType.EXECUTION,
                        success=False,
                        error=f"Orchestration failed: {
                            orchestration_result.error}",
                        execution_time_seconds=0
                    )
                    execution_results.append(failed_result)

            # Aggregate results
            successful_executions = [r for r in execution_results if r.success]

            execution_time = sum(
                r.execution_time_seconds for r in execution_results)

            # Update reasoning step
            execution_step.status = TaskStatus.COMPLETED if len(
                successful_executions) > 0 else TaskStatus.FAILED
            execution_step.execution_time_seconds = execution_time
            execution_step.output_data = {
                "success": len(successful_executions) > 0,
                "successful_executions": len(successful_executions),
                "total_executions": len(execution_results),
                "execution_results": [r.model_dump() for r in execution_results]
            }

            if len(successful_executions) == 0:
                execution_step.error = "All task executions failed"

            # Create aggregated result
            aggregated_result = AgentResult(
                agent_type=AgentType.EXECUTION,
                success=len(successful_executions) > 0,
                output={
                    "execution_results": execution_results,
                    "successful_count": len(successful_executions),
                    "total_count": len(execution_results)
                },
                execution_time_seconds=execution_time,
                metadata={
                    "workflow_step": "execution",
                    "tasks_executed": len(execution_results)
                }
            )

            if len(successful_executions) == 0:
                aggregated_result.error = "All task executions failed"

            self.logger.info(f"Execution step completed: {len(
                successful_executions)}/{len(execution_results)} tasks successful")

            return aggregated_result

        except Exception as e:
            execution_step.status = TaskStatus.FAILED
            execution_step.error = str(e)
            raise

    def _synthesize_final_output(
        self,
        reasoning_chain: ReasoningChain,
        planning_result: AgentResult,
        orchestration_result: AgentResult,
        execution_result: AgentResult
    ) -> str:
        """Synthesize the final output from all workflow steps."""

        if not execution_result.success:
            return f"I apologize, but I was unable to complete your request. {execution_result.error}"

        execution_data = execution_result.output
        execution_results = execution_data.get("execution_results", [])

        # Collect all successful execution outputs
        successful_outputs = []
        for result in execution_results:
            if result.success and result.output:
                if hasattr(result.output, 'final_output'):
                    successful_outputs.append(result.output.final_output)
                elif isinstance(result.output, dict) and 'final_output' in result.output:
                    successful_outputs.append(result.output['final_output'])

        if successful_outputs:
            # Combine all outputs
            combined_output = "\n\n".join(successful_outputs)
            return f"Here's what I accomplished for your request:\n\n{combined_output}"
        else:
            return "I completed the requested tasks, but no specific output was generated."

    async def _send_workflow_progress(
        self,
        progress_callback: Callable,
        status: str,
        progress_percentage: float,
        elapsed_time: float,
        current_task: str
    ) -> None:
        """Send workflow progress update."""
        try:
            update = ProgressUpdate(
                agent_type=AgentType.EXECUTION,  # Use execution as the workflow coordinator
                status=status,
                progress_percentage=progress_percentage,
                current_task=current_task,
                elapsed_time_seconds=elapsed_time,
                details={
                    "workflow_stage": status,
                    "reasoning_chain_id": self.current_reasoning_chain.id if self.current_reasoning_chain else None
                }
            )

            await progress_callback(update)

        except Exception as e:
            self.logger.warning(
                f"Failed to send workflow progress update: {e}")

    async def get_workflow_status(self, workflow_id: str = None) -> Optional[Dict[str, Any]]:
        """Get workflow status by ID or current status if no ID provided."""
        if workflow_id is None:
            # Return general workflow status
            return {
                "is_executing": self.is_executing,
                "current_reasoning_chain_id": self.current_reasoning_chain.id if self.current_reasoning_chain else None,
                "agents_ready": {
                    "planning": not self.planning_agent.is_busy,
                    "orchestrator": not self.orchestrator_agent.is_busy,
                    "execution": not self.execution_agent.is_busy
                }
            }

        # Return specific workflow status
        if not self.current_reasoning_chain or self.current_reasoning_chain.id != workflow_id:
            return None

        return {
            "status": self.current_reasoning_chain.status.value,
            "progress": 50.0 if self.is_executing else (100.0 if self.current_reasoning_chain.status.value == "completed" else 0.0),
            "current_phase": "executing" if self.is_executing else self.current_reasoning_chain.status.value,
            "reasoning_chain_id": self.current_reasoning_chain.id
        }

    async def get_tasks_status(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get tasks status for a workflow."""
        if not self.current_reasoning_chain or self.current_reasoning_chain.id != workflow_id:
            return []

        tasks = []
        if self.current_reasoning_chain.task_list:
            for task in self.current_reasoning_chain.task_list.tasks:
                tasks.append({
                    "title": task.title,
                    "description": task.description,
                    "status": task.status.value,
                    "dependencies": [dep.title for dep in task.dependencies],
                    "agent": task.assigned_agent.value if task.assigned_agent else None
                })
        return tasks

    async def get_reasoning_chain(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get reasoning chain for a workflow."""
        if not self.current_reasoning_chain or self.current_reasoning_chain.id != workflow_id:
            return []

        steps = []
        for step in self.current_reasoning_chain.reasoning_steps:
            steps.append({
                "agent": step.agent_type.value,
                "action": step.title,
                "reasoning": step.description,
                "tools_used": [tool.tool_name for tool in step.tool_calls] if step.tool_calls else []
            })
        return steps

    async def cancel_workflow(self) -> bool:
        """Cancel the current workflow execution."""
        if not self.is_executing:
            return False

        self.logger.warning("Cancelling workflow execution")

        if self.current_reasoning_chain:
            self.current_reasoning_chain.fail_chain(
                "Workflow cancelled by user")

        self.is_executing = False
        self.current_reasoning_chain = None

        return True
