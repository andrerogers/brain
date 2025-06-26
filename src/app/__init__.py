"""
Application Coordination Package

Provides the coordination layer between MCP tools and Agent reasoning,
along with WebSocket streaming and session management.

This package serves as the main application interface that:
- Coordinates between the tools layer (MCP protocol) and agent layer (reasoning)
- Handles WebSocket streaming and real-time progress updates
- Manages user sessions and application state
- Provides a clean interface for the WebSocket server
"""

from .coordinator import AppCoordinator
from .tool_bridge import ToolBridge
from .streaming import AppStreamingHandler, WebSocketAppIntegration
from .session import SessionManager
from .models import AppSession, AppProgress

__all__ = [
    'AppCoordinator',
    'ToolBridge', 
    'AppStreamingHandler',
    'WebSocketAppIntegration',
    'SessionManager',
    'AppSession',
    'AppProgress'
]