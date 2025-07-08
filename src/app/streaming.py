import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.models import ProgressUpdate
from agent.tasks import ReasoningChain, TaskStatus

from .coordinator import AppCoordinator
from .models import AppProgress, ToolExecutionRequest
from .session import AppSession


def safe_json_serialize(obj):
    """Custom JSON serializer that handles datetime objects and Pydantic models."""
    try:
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Handle Pydantic BaseModel instances
        if hasattr(obj, 'model_dump'):
            return obj.model_dump(mode='json')
        # Handle enum values
        if hasattr(obj, 'value'):
            return obj.value
        # Handle other common types
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    except Exception as e:
        logging.getLogger("safe_json_serialize").error(f"Error serializing {type(obj)}: {e}")
        raise


class AppStreamingHandler:
    """
    Handles streaming of application execution progress and results to WebSocket clients.

    Coordinates between the application coordinator and WebSocket clients to provide
    real-time updates during query processing and tool execution.
    """

    def __init__(self, app_coordinator: AppCoordinator, logger: logging.Logger):
        self.app_coordinator = app_coordinator
        self.logger = logger or logging.getLogger("AppStreamingHandler")

        # Active streaming sessions
        self.active_sessions: Dict[str, AppSession] = {}

    async def handle_agent_query(
        self, websocket, session_id: str, query_data: Dict[str, Any]
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
            await self._send_error(websocket, "No query provided", session_id)
            return

        self.logger.info(
            f"Starting streaming agent query for session {
                         session_id}: {user_query}"
        )

        session = AppSession(session_id=session_id)
        session.start_processing(user_query)
        self.active_sessions[session_id] = session

        try:
            # Send initial response
            await self._send_message(
                websocket,
                {
                    "type": "agent_query_started",
                    "session_id": session_id,
                    "query": user_query,
                },
            )

            # Create progress callback
            async def progress_callback(update: ProgressUpdate) -> None:
                await self._send_progress_update(websocket, session_id, update)

            # Execute query through coordinator
            reasoning_chain = await self.app_coordinator.process_query(
                user_query=user_query,
                context=context,
                progress_callback=progress_callback,
            )

            # Update session and send final result
            # Handle different completion states appropriately
            if reasoning_chain.status == TaskStatus.COMPLETED:
                result = reasoning_chain.final_result or "Query completed successfully"
            elif reasoning_chain.status == TaskStatus.FAILED:
                # Get error from the last reasoning step if available
                error_msg = "Unknown error"
                if reasoning_chain.reasoning_steps:
                    last_step = reasoning_chain.reasoning_steps[-1]
                    if last_step.error:
                        error_msg = last_step.error
                result = f"Query failed: {error_msg}"
            else:
                result = f"Query ended with status: {reasoning_chain.status}"

            session.complete_processing(result, reasoning_chain)
            await self._send_final_result(websocket, session_id, reasoning_chain)

        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                f"Agent query failed for session {
                              session_id}: {error_msg}"
            )
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
        estimated_duration: Optional[str] = None,
    ) -> None:
        """Send agent workflow started notification."""
        await self._send_message(
            websocket,
            {
                "type": "agent_workflow_started",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "agents": agents,
                "estimated_duration": estimated_duration,
            },
        )

    async def send_agent_handoff(
        self,
        websocket,
        session_id: str,
        from_agent: str,
        to_agent: str,
        context: Optional[str] = None,
    ) -> None:
        """Send agent handoff notification."""
        await self._send_message(
            websocket,
            {
                "type": "agent_handoff",
                "session_id": session_id,
                "from_agent": from_agent,
                "to_agent": to_agent,
                "context": context,
            },
        )

    async def send_task_dependencies(
        self, websocket, session_id: str, dependencies: Dict[str, List[str]]
    ) -> None:
        """Send task dependencies notification."""
        await self._send_message(
            websocket,
            {
                "type": "task_dependencies",
                "session_id": session_id,
                "dependencies": dependencies,
            },
        )

    async def handle_tool_execution(
        self, websocket, session_id: str, tool_data: Dict[str, Any]
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
            await self._send_error(websocket, "No tool name provided", session_id)
            return

        self.logger.info(
            f"Executing tool {
                         tool_name} for session {session_id}"
        )

        try:
            # Send execution started message
            await self._send_message(
                websocket,
                {
                    "type": "tool_execution_started",
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "parameters": parameters,
                },
            )

            # Create tool execution request
            request = ToolExecutionRequest(
                tool_name=tool_name,
                parameters=parameters,
                server_id=server_id,
                session_id=session_id,
            )

            # Execute tool through coordinator
            response = await self.app_coordinator.execute_tool(request)

            # Send result
            await self._send_message(
                websocket,
                {
                    "type": "tool_execution_completed",
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "success": response.success,
                    "result": response.result,
                    "error": response.error,
                    "execution_time_seconds": response.execution_time_seconds,
                },
            )

        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                f"Tool execution failed for session {
                              session_id}: {error_msg}"
            )
            await self._send_error(websocket, error_msg, session_id)

    async def handle_complexity_analysis(
        self, websocket, session_id: str, query_data: Dict[str, Any]
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
            await self._send_error(websocket, "No query provided", session_id)
            return

        self.logger.info(f"Analyzing query complexity for session {session_id}")

        try:
            # Perform complexity analysis through coordinator
            analysis = await self.app_coordinator.analyze_query_complexity(user_query)

            # Send result
            await self._send_message(
                websocket,
                {
                    "type": "complexity_analysis_completed",
                    "session_id": session_id,
                    "query": user_query,
                    "analysis": analysis,
                },
            )

        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                f"Complexity analysis failed for session {
                              session_id}: {error_msg}"
            )
            await self._send_error(websocket, error_msg, session_id)

    async def handle_get_available_tools(self, websocket, session_id: str) -> None:
        """Handle request for available tools."""
        try:
            tools = await self.app_coordinator.get_available_tools()

            await self._send_message(
                websocket,
                {
                    "type": "available_tools",
                    "session_id": session_id,
                    "tools": tools,
                    "total_count": len(tools),
                },
            )

        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                f"Failed to get available tools for session {
                              session_id}: {error_msg}"
            )
            await self._send_error(websocket, error_msg, session_id)

    async def handle_system_status(self, websocket, session_id: str) -> None:
        """Handle system status request."""
        try:
            status = await self.app_coordinator.get_system_status()

            await self._send_message(
                websocket,
                {"type": "system_status", "session_id": session_id, "status": status},
            )

        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                f"Failed to get system status for session {
                              session_id}: {error_msg}"
            )
            await self._send_error(websocket, error_msg, session_id)

    async def handle_cancel_workflow(self, websocket, session_id: str) -> None:
        """Handle workflow cancellation request."""
        try:
            cancelled = await self.app_coordinator.cancel_current_workflow()

            await self._send_message(
                websocket,
                {
                    "type": "workflow_cancelled",
                    "session_id": session_id,
                    "was_cancelled": cancelled,
                },
            )

            # Update session if it exists
            if session_id in self.active_sessions:
                self.active_sessions[session_id].cancel_processing()

        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                f"Failed to cancel workflow for session {
                              session_id}: {error_msg}"
            )
            await self._send_error(websocket, error_msg, session_id)

    async def _send_progress_update(
        self, websocket, session_id: str, update: ProgressUpdate
    ) -> None:
        """Send a progress update to the WebSocket client."""
        try:
            # Update session progress if it exists
            if session_id in self.active_sessions:
                self.active_sessions[session_id].update_progress(update)

            # Create application-level progress
            session = self.active_sessions.get(
                session_id, AppSession(session_id=session_id)
            )
            
            app_progress = AppProgress(
                session_id=session_id,
                status=session.status,
                progress_percentage=update.progress_percentage,
                current_step=update.current_task,
                agent_progress=update,
                elapsed_time_seconds=update.elapsed_time_seconds,
                details=update.details,
            )

            # Send enhanced agent progress with agent context
            try:
                # Safely serialize app_progress with JSON mode for proper enum handling
                details = app_progress.model_dump(mode='json')
            except Exception as e:
                self.logger.warning(f"Failed to serialize app_progress: {e}")
                details = {
                    "session_id": session_id,
                    "status": session.status.value if hasattr(session.status, 'value') else str(session.status),
                    "progress_percentage": update.progress_percentage,
                    "current_step": update.current_task,
                    "elapsed_time_seconds": update.elapsed_time_seconds,
                }

            message = {
                "type": "agent_progress",
                "session_id": session_id,
                "agent": (
                    update.agent_type.value 
                    if hasattr(update.agent_type, 'value') 
                    else str(update.agent_type)
                ) if update.agent_type else None,
                "progress": update.progress_percentage,
                "message": update.current_task,
                "details": details,
            }

            await self._send_message(websocket, message)
            
        except Exception as e:
            self.logger.warning(f"Failed to send progress update: {e}")
            # Send simplified fallback message
            try:
                fallback_message = {
                    "type": "agent_progress",
                    "session_id": session_id,
                    "agent": str(update.agent_type) if update.agent_type else None,
                    "progress": update.progress_percentage,
                    "message": update.current_task or "Processing...",
                }
                await self._send_message(websocket, fallback_message)
            except Exception as fallback_error:
                self.logger.error(f"Failed to send fallback progress update: {fallback_error}")

    async def _send_final_result(
        self, websocket, session_id: str, reasoning_chain: ReasoningChain
    ) -> None:
        """Send the final reasoning chain result."""

        # Create summary for client
        status_value = reasoning_chain.status.value if hasattr(reasoning_chain.status, 'value') else str(reasoning_chain.status)
        summary = {
            "id": reasoning_chain.id,
            "success": status_value == "completed",
            "execution_time_seconds": reasoning_chain.total_execution_time_seconds,
            "task_count": len(reasoning_chain.task_list.tasks) if reasoning_chain.task_list else 0,
            "reasoning_steps": len(reasoning_chain.reasoning_steps),
        }

        await self._send_message(
            websocket,
            {
                "type": "agent_query_completed",
                "session_id": session_id,
                "success": status_value == "completed",
                "final_result": reasoning_chain.final_result,
                "summary": summary,
                "reasoning_chain_id": reasoning_chain.id,
            },
        )

    async def _send_error(self, websocket, error_message: str, session_id: str) -> None:
        """Send an error message to the WebSocket client."""
        await self._send_message(
            websocket,
            {"type": "agent_error", "session_id": session_id, "error": error_message},
        )

    async def _send_message(self, websocket, message: Dict[str, Any]) -> None:
        """Send a message to the WebSocket client."""
        try:
            # Validate message structure before sending
            if not isinstance(message, dict):
                self.logger.error(f"Message must be a dictionary, got {type(message)}: {message}")
                return
                
            json_message = json.dumps(message, default=safe_json_serialize)
            await websocket.send_text(json_message)
        except Exception as e:
            self.logger.warning(f"Failed to send WebSocket message: {e}")
            self.logger.debug(f"Failed message content: {message}")
            self.logger.debug(f"WebSocket object: {websocket}")
            self.logger.debug(f"WebSocket type: {type(websocket)}")

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active sessions."""
        return {
            session_id: {
                "query": session.user_query,
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "progress": session.progress_percentage,
            }
            for session_id, session in self.active_sessions.items()
            if not session.metadata.get("websocket_closed", False)
        }
