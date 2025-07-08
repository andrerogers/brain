"""
Task Management System for Agent Engine

Provides task modeling, execution tracking, and reasoning chain orchestration
for multi-agent workflows.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, validator

from .models import AgentType, ToolCall


class TaskStatus(str, Enum):
    """Status of a task in the execution pipeline."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class TaskPriority(int, Enum):
    """Priority levels for task execution."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Task(BaseModel):
    """Individual task within a reasoning chain."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(description="Short title for the task")
    description: str = Field(description="Human-readable task description")
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: List[str] = Field(
        default_factory=list, description="Task IDs that must complete before this task"
    )
    assigned_agent: Optional[AgentType] = None

    # Execution details
    tools_required: List[str] = Field(
        default_factory=list, description="Tools needed for execution"
    )
    estimated_duration_seconds: Optional[int] = None
    actual_duration_seconds: Optional[float] = None

    # Results
    result: Optional[Any] = None
    error: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("dependencies")
    def validate_dependencies(cls, v: List[str]) -> List[str]:
        """Ensure dependencies don't include self-references."""
        return list(set(v))  # Remove duplicates

    def start_execution(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()

    def complete_execution(self, result: Any = None) -> None:
        """Mark task as completed with result."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result = result
        if self.started_at:
            self.actual_duration_seconds = (
                self.completed_at - self.started_at
            ).total_seconds()

    def fail_execution(self, error: str) -> None:
        """Mark task as failed with error."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error = error
        if self.started_at:
            self.actual_duration_seconds = (
                self.completed_at - self.started_at
            ).total_seconds()

    def can_execute(self, completed_task_ids: Set[str]) -> bool:
        """Check if task can be executed based on dependencies."""
        if self.status != TaskStatus.PENDING:
            return False
        return all(dep_id in completed_task_ids for dep_id in self.dependencies)

    class Config:
        use_enum_values = True


class TaskList(BaseModel):
    """Collection of tasks with execution ordering."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(description="Name of the task list")
    tasks: List[Task] = Field(default_factory=list)
    execution_order: List[str] = Field(
        default_factory=list, description="Ordered list of task IDs"
    )

    # Status tracking
    status: TaskStatus = TaskStatus.PENDING
    current_task_id: Optional[str] = None
    completed_task_ids: Set[str] = Field(default_factory=set)
    failed_task_ids: Set[str] = Field(default_factory=set)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def add_task(self, task: Task) -> None:
        """Add a task to the list."""
        self.tasks.append(task)
        if task.id not in self.execution_order:
            self.execution_order.append(task.id)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return next((task for task in self.tasks if task.id == task_id), None)

    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute."""
        return [
            task for task in self.tasks if task.can_execute(self.completed_task_ids)
        ]

    def get_blocked_tasks(self) -> List[Task]:
        """Get tasks that are blocked by dependencies."""
        return [
            task
            for task in self.tasks
            if task.status == TaskStatus.PENDING
            and not task.can_execute(self.completed_task_ids)
        ]

    def mark_task_completed(self, task_id: str) -> None:
        """Mark a task as completed."""
        self.completed_task_ids.add(task_id)
        if task_id in self.failed_task_ids:
            self.failed_task_ids.remove(task_id)

    def mark_task_failed(self, task_id: str) -> None:
        """Mark a task as failed."""
        self.failed_task_ids.add(task_id)

    def get_progress_percentage(self) -> float:
        """Calculate overall progress percentage."""
        if not self.tasks:
            return 100.0

        completed = len(self.completed_task_ids)
        total = len(self.tasks)
        return (completed / total) * 100.0

    def is_complete(self) -> bool:
        """Check if all tasks are completed."""
        return len(self.completed_task_ids) == len(self.tasks)

    def has_failures(self) -> bool:
        """Check if any tasks have failed."""
        return len(self.failed_task_ids) > 0

    class Config:
        use_enum_values = True


class ReasoningStep(BaseModel):
    """Individual step in a reasoning chain."""

    step_number: int
    title: str = Field(description="Short title for the reasoning step")
    agent_type: AgentType
    description: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    execution_time_seconds: Optional[float] = None
    error: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list, description="Tool calls made during this step")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReasoningChain(BaseModel):
    """Complete reasoning chain for multi-agent query processing."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_query: str = Field(description="Original user query")
    task_list: TaskList
    reasoning_steps: List[ReasoningStep] = Field(default_factory=list)

    # Results
    intermediate_results: Dict[str, Any] = Field(default_factory=dict)
    final_result: Optional[str] = None

    # Status tracking
    status: TaskStatus = TaskStatus.PENDING
    current_step: int = 0

    # Performance metrics
    total_execution_time_seconds: Optional[float] = None
    total_token_usage: Dict[str, int] = Field(default_factory=dict)
    total_tool_calls: int = 0

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def start_chain(self) -> None:
        """Start executing the reasoning chain."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        self.task_list.status = TaskStatus.IN_PROGRESS
        self.task_list.started_at = self.started_at

    def complete_chain(self, final_result: str) -> None:
        """Complete the reasoning chain with final result."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.final_result = final_result
        self.task_list.status = TaskStatus.COMPLETED
        self.task_list.completed_at = self.completed_at

        if self.started_at:
            self.total_execution_time_seconds = (
                self.completed_at - self.started_at
            ).total_seconds()

    def fail_chain(self, error: str) -> None:
        """Fail the reasoning chain with error."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.task_list.status = TaskStatus.FAILED
        self.task_list.completed_at = self.completed_at

        # Add error to the current step
        if self.reasoning_steps and self.current_step < len(self.reasoning_steps):
            self.reasoning_steps[self.current_step].error = error
            self.reasoning_steps[self.current_step].status = TaskStatus.FAILED

    def add_reasoning_step(self, step: ReasoningStep) -> None:
        """Add a reasoning step."""
        step.step_number = len(self.reasoning_steps) + 1
        self.reasoning_steps.append(step)

    def get_current_step(self) -> Optional[ReasoningStep]:
        """Get the current reasoning step."""
        if 0 <= self.current_step < len(self.reasoning_steps):
            return self.reasoning_steps[self.current_step]
        return None

    def advance_step(self) -> bool:
        """Advance to the next reasoning step."""
        if self.current_step < len(self.reasoning_steps) - 1:
            self.current_step += 1
            return True
        return False

    def get_progress_summary(self) -> Dict[str, Any]:
        """Get comprehensive progress summary."""
        return {
            "reasoning_chain_id": self.id,
            "status": self.status,
            "current_step": self.current_step + 1,
            "total_steps": len(self.reasoning_steps),
            "task_progress": self.task_list.get_progress_percentage(),
            "completed_tasks": len(self.task_list.completed_task_ids),
            "total_tasks": len(self.task_list.tasks),
            "execution_time_seconds": self.total_execution_time_seconds,
            "has_failures": self.task_list.has_failures(),
        }

    class Config:
        use_enum_values = True
