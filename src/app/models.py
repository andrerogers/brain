"""
Application-level data models for coordination layer.

Defines data structures for session management, progress tracking,
and application state coordination.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agent.models import ProgressUpdate
from agent.tasks import ReasoningChain


class SessionStatus(str, Enum):
    """Status of an application session."""

    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AppSession(BaseModel):
    """Application session for tracking user interactions."""

    session_id: str
    status: SessionStatus = SessionStatus.INITIALIZING
    user_query: Optional[str] = None

    # Execution tracking
    reasoning_chain_id: Optional[str] = None
    current_step: Optional[str] = None
    progress_percentage: float = 0.0

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    final_result: Optional[str] = None
    error_message: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate session duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return None

    def start_processing(self, query: str) -> None:
        """Start processing a query."""
        self.status = SessionStatus.PROCESSING
        self.user_query = query
        self.started_at = datetime.utcnow()

    def complete_processing(self, result: str, reasoning_chain: ReasoningChain) -> None:
        """Complete processing with result."""
        self.status = SessionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.final_result = result
        self.reasoning_chain_id = reasoning_chain.id
        self.progress_percentage = 100.0

    def fail_processing(self, error: str) -> None:
        """Fail processing with error."""
        self.status = SessionStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error

    def cancel_processing(self) -> None:
        """Cancel processing."""
        self.status = SessionStatus.CANCELLED
        self.completed_at = datetime.utcnow()

    def update_progress(self, update: ProgressUpdate) -> None:
        """Update session progress."""
        self.progress_percentage = update.progress_percentage
        self.current_step = update.current_task

        # Update metadata with progress details
        self.metadata.update(
            {
                "last_progress_update": update.model_dump(),
                "agent_type": update.agent_type,
                "elapsed_time": update.elapsed_time_seconds,
            }
        )


class AppProgress(BaseModel):
    """Application-level progress information."""

    session_id: str
    status: SessionStatus
    progress_percentage: float = Field(ge=0.0, le=100.0)
    current_step: Optional[str] = None

    # Agent-specific progress
    agent_progress: Optional[ProgressUpdate] = None

    # Timing
    elapsed_time_seconds: float
    estimated_remaining_seconds: Optional[float] = None

    # Context
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolExecutionRequest(BaseModel):
    """Request for direct tool execution."""

    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    server_id: Optional[str] = None
    session_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResponse(BaseModel):
    """Response from tool execution."""

    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_seconds: float
    tool_name: str
    server_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryComplexityAnalysis(BaseModel):
    """Analysis of query complexity."""

    query: str
    complexity_level: str  # simple, moderate, complex
    estimated_steps: int
    estimated_duration_seconds: Optional[int] = None
    required_capabilities: List[str] = Field(default_factory=list)
    recommended_approach: str
    confidence_score: float = Field(ge=0.0, le=1.0)


class SystemHealthStatus(BaseModel):
    """System health status information."""

    overall_status: str  # healthy, partial, unhealthy
    components: Dict[str, str] = Field(default_factory=dict)
    active_sessions_count: int
    tool_servers_connected: int
    total_tool_servers: int
    agent_engine_status: str
    last_check_timestamp: datetime = Field(default_factory=datetime.utcnow)
    issues: List[str] = Field(default_factory=list)
