from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Types of specialized agents available in the system."""

    PLANNING = "planning"
    ORCHESTRATOR = "orchestrator"
    EXECUTION = "execution"


class AgentConfig(BaseModel):
    """Configuration for creating an agent instance."""

    agent_type: AgentType
    model: str = Field(
        description="LLM model to use (e.g., 'anthropic:claude-3-5-sonnet-latest')"
    )
    system_prompt: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, gt=0)
    timeout_seconds: int = Field(default=300, gt=0)

    class Config:
        use_enum_values = True


class AgentResult(BaseModel):
    """Result from an agent execution."""

    agent_type: AgentType
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    execution_time_seconds: float
    token_usage: Dict[str, int] = Field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class ToolCall(BaseModel):
    """Represents a tool call made by an agent."""

    tool_name: str
    server_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentMessage(BaseModel):
    """Message exchanged between agents or with the system."""

    sender: str
    recipient: str
    message_type: str
    content: Union[str, Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None


class ProgressUpdate(BaseModel):
    """Progress update for streaming to WebSocket clients."""

    agent_type: AgentType
    status: str
    progress_percentage: float = Field(ge=0.0, le=100.0)
    current_task: Optional[str] = None
    elapsed_time_seconds: float
    estimated_remaining_seconds: Optional[float] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
