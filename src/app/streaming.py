"""
WebSocket Streaming Integration for Application Layer

Provides real-time streaming of application execution progress and results
through WebSocket connections, coordinating between agents and tools.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Callable

from agent.models import ProgressUpdate
from agent.tasks import ReasoningChain
from .models import AppSession, AppProgress, ToolExecutionRequest, ToolExecutionResponse
from .coordinator import AppCoordinator


class AppStreamingHandler:
    """
    Handles streaming of application execution progress and results to WebSocket clients.

    Coordinates between the application coordinator and WebSocket clients to provide
    real-time updates during query processing and tool execution.
    """

    def __init__(self, app_coordinator: AppCoordinator, logger: Optional[logging.Logger] = None):
        self.app_coordinator = app_coordinator
        self.logger = logger or logging.getLogger("AppStreamingHandler")

        # Active streaming sessions
        self.active_sessions: Dict[str, AppSession] = {}

    async def handle_agent_query(
        self,
        websocket,
        session_id: str,
        query_data: Dict[str, Any]
    ) -> None:
        """
        Handle a streaming agent query request.

        Args:
            websocket: WebSocket connection
            session_id: Unique session identifier
            query_data: Query data containing user query and context
        """
        user_query = query_data.get("query", "")
        context = query_data.get("context", {})

        if not user_query:
            await self._send_error(websocket, "No query provided")
            return

        self.logger.info(f"Starting streaming agent query for session {
                         session_id}: {user_query}")

        # Create application session
        session = AppSession(session_id=session_id)
        session.start_processing(user_query)
        self.active_sessions[session_id] = session

        try:
            # Send initial response
            await self._send_message(websocket, {
                "type": "agent_query_started",
                "session_id": session_id,
                "query": user_query
            })

            # Create progress callback
            async def progress_callback(update: ProgressUpdate):
                await self._send_progress_update(websocket, session_id, update)

            # Execute query through coordinator
            reasoning_chain = await self.app_coordinator.process_query(
                user_query=user_query,
                context=context,
                progress_callback=progress_callback
            )

            # Update session and send final result
            session.complete_processing(
                reasoning_chain.final_result, reasoning_chain)
            await self._send_final_result(websocket, session_id, reasoning_chain)

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Agent query failed for session {
                              session_id}: {error_msg}")
            session.fail_processing(error_msg)
            await self._send_error(websocket, error_msg, session_id)

        finally:
            # Keep session for history but mark as inactive
            if session_id in self.active_sessions:
                self.active_sessions[session_id].metadata["websocket_closed"] = True

    async def send_agent_workflow_started(
        self,
        websocket,
        session_id: str,
        workflow_id: str,
        agents: List[str],
        estimated_duration: Optional[str] = None
    ) -> None:
        """Send agent workflow started notification."""
        await self._send_message(websocket, {
            "type": "agent_workflow_started",
            "session_id": session_id,
            "workflow_id": workflow_id,
            "agents": agents,
            "estimated_duration": estimated_duration
        })

    async def send_agent_handoff(
        self,
        websocket,
        session_id: str,
        from_agent: str,
        to_agent: str,
        context: Optional[str] = None
    ) -> None:
        """Send agent handoff notification."""
        await self._send_message(websocket, {
            "type": "agent_handoff",
            "session_id": session_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "context": context
        })

    async def send_task_dependencies(
        self,
        websocket,
        session_id: str,
        dependencies: Dict[str, List[str]]
    ) -> None:
        """Send task dependencies notification."""
        await self._send_message(websocket, {
            "type": "task_dependencies",
            "session_id": session_id,
            "dependencies": dependencies
        })

    async def handle_tool_execution(
        self,
        websocket,
        session_id: str,
        tool_data: Dict[str, Any]
    ) -> None:
        """
        Handle direct tool execution request.

        Args:
            websocket: WebSocket connection
            session_id: Unique session identifier
            tool_data: Tool execution data
        """
        tool_name = tool_data.get("tool_name", "")
        parameters = tool_data.get("parameters", {})
        server_id = tool_data.get("server_id")

        if not tool_name:
            await self._send_error(websocket, "No tool name provided")
            return

        self.logger.info(f"Executing tool {
                         tool_name} for session {session_id}")

        try:
            # Send execution started message
            await self._send_message(websocket, {
                "type": "tool_execution_started",
                "session_id": session_id,
                "tool_name": tool_name,
                "parameters": parameters
            })

            # Create tool execution request
            request = ToolExecutionRequest(
                tool_name=tool_name,
                parameters=parameters,
                server_id=server_id,
                session_id=session_id
            )

            # Execute tool through coordinator
            response = await self.app_coordinator.execute_tool(request)

            # Send result
            await self._send_message(websocket, {
                "type": "tool_execution_completed",
                "session_id": session_id,
                "tool_name": tool_name,
                "success": response.success,
                "result": response.result,
                "error": response.error,
                "execution_time_seconds": response.execution_time_seconds
            })

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Tool execution failed for session {
                              session_id}: {error_msg}")
            await self._send_error(websocket, error_msg, session_id)

    async def handle_complexity_analysis(
        self,
        websocket,
        session_id: str,
        query_data: Dict[str, Any]
    ) -> None:
        """
        Handle query complexity analysis request.

        Args:
            websocket: WebSocket connection
            session_id: Unique session identifier
            query_data: Query data to analyze
        """
        user_query = query_data.get("query", "")

        if not user_query:
            await self._send_error(websocket, "No query provided")
            return

        self.logger.info(
            f"Analyzing query complexity for session {session_id}")

        try:
            # Perform complexity analysis through coordinator
            analysis = await self.app_coordinator.analyze_query_complexity(user_query)

            # Send result
            await self._send_message(websocket, {
                "type": "complexity_analysis_completed",
                "session_id": session_id,
                "query": user_query,
                "analysis": analysis
            })

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Complexity analysis failed for session {
                              session_id}: {error_msg}")
            await self._send_error(websocket, error_msg, session_id)

    async def handle_get_available_tools(self, websocket, session_id: str) -> None:
        """Handle request for available tools."""
        try:
            tools = await self.app_coordinator.get_available_tools()

            await self._send_message(websocket, {
                "type": "available_tools",
                "session_id": session_id,
                "tools": tools,
                "total_count": len(tools)
            })

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Failed to get available tools for session {
                              session_id}: {error_msg}")
            await self._send_error(websocket, error_msg, session_id)

    async def handle_system_status(self, websocket, session_id: str) -> None:
        """Handle system status request."""
        try:
            status = await self.app_coordinator.get_system_status()

            await self._send_message(websocket, {
                "type": "system_status",
                "session_id": session_id,
                "status": status
            })

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Failed to get system status for session {
                              session_id}: {error_msg}")
            await self._send_error(websocket, error_msg, session_id)

    async def handle_cancel_workflow(self, websocket, session_id: str) -> None:
        """Handle workflow cancellation request."""
        try:
            cancelled = await self.app_coordinator.cancel_current_workflow()

            await self._send_message(websocket, {
                "type": "workflow_cancelled",
                "session_id": session_id,
                "was_cancelled": cancelled
            })

            # Update session if it exists
            if session_id in self.active_sessions:
                self.active_sessions[session_id].cancel_processing()

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Failed to cancel workflow for session {
                              session_id}: {error_msg}")
            await self._send_error(websocket, error_msg, session_id)

    async def _send_progress_update(
        self,
        websocket,
        session_id: str,
        update: ProgressUpdate
    ) -> None:
        """Send a progress update to the WebSocket client."""

        # Update session progress if it exists
        if session_id in self.active_sessions:
            self.active_sessions[session_id].update_progress(update)

        # Create application-level progress
        app_progress = AppProgress(
            session_id=session_id,
            status=self.active_sessions.get(
                session_id, AppSession(session_id=session_id)).status,
            progress_percentage=update.progress_percentage,
            current_step=update.current_task,
            agent_progress=update,
            elapsed_time_seconds=update.elapsed_time_seconds,
            details=update.details
        )

        # Send enhanced agent progress with agent context
        message = {
            "type": "agent_progress",
            "session_id": session_id,
            "agent": update.agent_type.value if update.agent_type else None,
            "progress": update.progress_percentage,
            "message": update.current_task,
            "details": app_progress.model_dump()
        }

        await self._send_message(websocket, message)

    async def _send_final_result(
        self,
        websocket,
        session_id: str,
        reasoning_chain: ReasoningChain
    ) -> None:
        """Send the final reasoning chain result."""

        # Create summary for client
        summary = {
            "id": reasoning_chain.id,
            "success": reasoning_chain.status.value == "completed",
            "execution_time_seconds": reasoning_chain.total_execution_time_seconds,
            "task_count": len(reasoning_chain.task_list.tasks),
            "reasoning_steps": len(reasoning_chain.reasoning_steps)
        }

        await self._send_message(websocket, {
            "type": "agent_query_completed",
            "session_id": session_id,
            "success": reasoning_chain.status.value == "completed",
            "final_result": reasoning_chain.final_result,
            "summary": summary,
            "reasoning_chain_id": reasoning_chain.id
        })

    async def _send_error(
        self,
        websocket,
        error_message: str,
        session_id: str = None
    ) -> None:
        """Send an error message to the WebSocket client."""
        await self._send_message(websocket, {
            "type": "agent_error",
            "session_id": session_id,
            "error": error_message
        })

    async def _send_message(self, websocket, message: Dict[str, Any]) -> None:
        """Send a message to the WebSocket client."""
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            self.logger.warning(f"Failed to send WebSocket message: {e}")

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active sessions."""
        return {
            session_id: {
                "query": session.user_query,
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "progress": session.progress_percentage
            }
            for session_id, session in self.active_sessions.items()
            if not session.metadata.get("websocket_closed", False)
        }


class WebSocketAppIntegration:
    """
    Integration class to add application capabilities to the existing WebSocket server.
    """

    def __init__(self, app_coordinator: AppCoordinator, logger: Optional[logging.Logger] = None):
        self.app_coordinator = app_coordinator
        self.streaming_handler = AppStreamingHandler(app_coordinator, logger)
        self.logger = logger or logging.getLogger("WebSocketAppIntegration")

    async def initialize(self) -> None:
        """Initialize the application coordinator for WebSocket integration."""
        await self.app_coordinator.initialize()
        self.logger.info("WebSocket application integration initialized")

    async def handle_app_command(
        self,
        websocket,
        command_data: Dict[str, Any]
    ) -> bool:
        """
        Handle application-related WebSocket commands.

        Args:
            websocket: WebSocket connection
            command_data: Command data from client

        Returns:
            True if command was handled, False if not an app command
        """
        command = command_data.get("command", "")
        session_id = command_data.get("session_id", "unknown")

        # Map commands to handlers
        command_handlers = {
            "agent_query": self._handle_agent_query,
            "tool_execute": self._handle_tool_execute,
            "complexity_analysis": self._handle_complexity_analysis,
            "get_available_tools": self._handle_get_tools,
            "system_status": self._handle_system_status,
            "cancel_workflow": self._handle_cancel_workflow,
            # New agent-specific commands
            "get_agents": self._handle_get_agents,
            "get_workflow": self._handle_get_workflow,
            "get_tasks": self._handle_get_tasks,
            "get_reasoning": self._handle_get_reasoning,
            "get_planning": self._handle_get_planning,
            "get_execution": self._handle_get_execution
        }

        if command in command_handlers:
            try:
                await command_handlers[command](websocket, session_id, command_data)
                return True
            except Exception as e:
                self.logger.error(f"Error handling app command {command}: {e}")
                await self.streaming_handler._send_error(websocket, str(e), session_id)
                return True

        return False

    async def _handle_agent_query(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle agent query command."""
        await self.streaming_handler.handle_agent_query(websocket, session_id, command_data)

    async def _handle_tool_execute(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle tool execution command."""
        await self.streaming_handler.handle_tool_execution(websocket, session_id, command_data)

    async def _handle_complexity_analysis(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle complexity analysis command."""
        await self.streaming_handler.handle_complexity_analysis(websocket, session_id, command_data)

    async def _handle_get_tools(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle get available tools command."""
        await self.streaming_handler.handle_get_available_tools(websocket, session_id)

    async def _handle_system_status(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle system status command."""
        await self.streaming_handler.handle_system_status(websocket, session_id)

    async def _handle_cancel_workflow(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle cancel workflow command."""
        await self.streaming_handler.handle_cancel_workflow(websocket, session_id)

    async def _handle_get_agents(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle get agents status command."""
        try:
            agents_info = await self.app_coordinator.get_agents_status()

            await self.streaming_handler._send_message(websocket, {
                "type": "agents_status",
                "session_id": session_id,
                "agents": agents_info
            })

        except Exception as e:
            self.logger.error(f"Failed to get agents status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_workflow(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle get workflow status command."""
        try:
            workflow_info = await self.app_coordinator.get_workflow_status()

            await self.streaming_handler._send_message(websocket, {
                "type": "workflow_status",
                "session_id": session_id,
                "workflow": workflow_info
            })

        except Exception as e:
            self.logger.error(f"Failed to get workflow status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_tasks(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle get tasks status command."""
        try:
            tasks_info = await self.app_coordinator.get_tasks_status()

            await self.streaming_handler._send_message(websocket, {
                "type": "tasks_status",
                "session_id": session_id,
                "tasks": tasks_info
            })

        except Exception as e:
            self.logger.error(f"Failed to get tasks status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_reasoning(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle get reasoning chain command."""
        try:
            reasoning_info = await self.app_coordinator.get_reasoning_chain()

            await self.streaming_handler._send_message(websocket, {
                "type": "reasoning_chain",
                "session_id": session_id,
                "reasoning": reasoning_info
            })

        except Exception as e:
            self.logger.error(f"Failed to get reasoning chain: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_planning(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle get planning agent status command."""
        try:
            planning_info = await self.app_coordinator.get_planning_status()

            await self.streaming_handler._send_message(websocket, {
                "type": "planning_status",
                "session_id": session_id,
                "planning": planning_info
            })

        except Exception as e:
            self.logger.error(f"Failed to get planning status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_execution(self, websocket, session_id: str, command_data: Dict[str, Any]) -> None:
        """Handle get execution agent status command."""
        try:
            execution_info = await self.app_coordinator.get_execution_status()

            await self.streaming_handler._send_message(websocket, {
                "type": "execution_status",
                "session_id": session_id,
                "execution": execution_info
            })

        except Exception as e:
            self.logger.error(f"Failed to get execution status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status information."""
        return {
            "app_coordinator_initialized": self.app_coordinator.is_initialized(),
            "active_sessions": len(self.streaming_handler.active_sessions),
            "session_details": self.streaming_handler.get_active_sessions()
        }
