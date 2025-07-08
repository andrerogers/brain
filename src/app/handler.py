import logging
from typing import Any, Dict

from .coordinator import AppCoordinator
from .streaming import AppStreamingHandler


class WebSocketHandler:
    """
    WebSocket command handler that routes application-related commands to appropriate handlers.
    
    Provides the main interface between WebSocket server and the application layer,
    ensuring proper routing of commands to streaming handlers and coordinators.
    """

    def __init__(self, app_coordinator: AppCoordinator, logger: logging.Logger):
        self.app_coordinator = app_coordinator
        self.streaming_handler = AppStreamingHandler(app_coordinator, logger)
        self.logger = logger or logging.getLogger("WebSocketHandler")

    async def initialize(self) -> None:
        """Initialize the application coordinator for WebSocket integration."""
        await self.app_coordinator.initialize()
        self.logger.info("WebSocket handler initialized")

    async def handle_app_command(self, websocket, command_data: Dict[str, Any]) -> bool:
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
            "query": self._handle_agent_query,  # Route legacy "query" command to agent_query
            "tool_execute": self._handle_tool_execute,
            "complexity_analysis": self._handle_complexity_analysis,
            "get_available_tools": self._handle_get_tools,
            "system_status": self._handle_system_status,
            "cancel_workflow": self._handle_cancel_workflow,
            # Agent-specific commands
            "get_agents": self._handle_get_agents,
            "get_workflow": self._handle_get_workflow,
            "get_tasks": self._handle_get_tasks,
            "get_reasoning": self._handle_get_reasoning,
            "get_planning": self._handle_get_planning,
            "get_execution": self._handle_get_execution,
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

    async def _handle_agent_query(
        self, websocket, session_id: str, command_data: Dict[str, Any]
    ) -> None:
        """Handle agent query command."""
        await self.streaming_handler.handle_agent_query(
            websocket, session_id, command_data
        )

    async def _handle_tool_execute(
        self, websocket, session_id: str, command_data: Dict[str, Any]
    ) -> None:
        """Handle tool execution command."""
        await self.streaming_handler.handle_tool_execution(
            websocket, session_id, command_data
        )

    async def _handle_complexity_analysis(
        self, websocket, session_id: str, command_data: Dict[str, Any]
    ) -> None:
        """Handle complexity analysis command."""
        await self.streaming_handler.handle_complexity_analysis(
            websocket, session_id, command_data
        )

    async def _handle_get_tools(
        self, websocket, session_id: str, _command_data: Dict[str, Any]
    ) -> None:
        """Handle get available tools command."""
        await self.streaming_handler.handle_get_available_tools(websocket, session_id)

    async def _handle_system_status(
        self, websocket, session_id: str, _command_data: Dict[str, Any]
    ) -> None:
        """Handle system status command."""
        await self.streaming_handler.handle_system_status(websocket, session_id)

    async def _handle_cancel_workflow(
        self, websocket, session_id: str, _command_data: Dict[str, Any]
    ) -> None:
        """Handle cancel workflow command."""
        await self.streaming_handler.handle_cancel_workflow(websocket, session_id)

    async def _handle_get_agents(
        self, websocket, session_id: str, _command_data: Dict[str, Any]
    ) -> None:
        """Handle get agents status command."""
        try:
            agents_info = await self.app_coordinator.get_agents_status()

            await self.streaming_handler._send_message(
                websocket,
                {
                    "type": "agents_status",
                    "session_id": session_id,
                    "agents": agents_info,
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to get agents status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_workflow(
        self, websocket, session_id: str, _command_data: Dict[str, Any]
    ) -> None:
        """Handle get workflow status command."""
        try:
            workflow_info = await self.app_coordinator.get_workflow_status()

            await self.streaming_handler._send_message(
                websocket,
                {
                    "type": "workflow_status",
                    "session_id": session_id,
                    "workflow": workflow_info,
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to get workflow status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_tasks(
        self, websocket, session_id: str, _command_data: Dict[str, Any]
    ) -> None:
        """Handle get tasks status command."""
        try:
            tasks_info = await self.app_coordinator.get_tasks_status()

            await self.streaming_handler._send_message(
                websocket,
                {"type": "tasks_status", "session_id": session_id, "tasks": tasks_info},
            )

        except Exception as e:
            self.logger.error(f"Failed to get tasks status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_reasoning(
        self, websocket, session_id: str, _command_data: Dict[str, Any]
    ) -> None:
        """Handle get reasoning chain command."""
        try:
            reasoning_info = await self.app_coordinator.get_reasoning_chain()

            await self.streaming_handler._send_message(
                websocket,
                {
                    "type": "reasoning_chain",
                    "session_id": session_id,
                    "reasoning": reasoning_info,
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to get reasoning chain: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_planning(
        self, websocket, session_id: str, _command_data: Dict[str, Any]
    ) -> None:
        """Handle get planning agent status command."""
        try:
            planning_info = await self.app_coordinator.get_planning_status()

            await self.streaming_handler._send_message(
                websocket,
                {
                    "type": "planning_status",
                    "session_id": session_id,
                    "planning": planning_info,
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to get planning status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    async def _handle_get_execution(
        self, websocket, session_id: str, _command_data: Dict[str, Any]
    ) -> None:
        """Handle get execution agent status command."""
        try:
            execution_info = await self.app_coordinator.get_execution_status()

            await self.streaming_handler._send_message(
                websocket,
                {
                    "type": "execution_status",
                    "session_id": session_id,
                    "execution": execution_info,
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to get execution status: {e}")
            await self.streaming_handler._send_error(websocket, str(e), session_id)

    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status information."""
        return {
            "app_coordinator_initialized": self.app_coordinator.is_initialized(),
            "active_sessions": len(self.streaming_handler.active_sessions),
            "session_details": self.streaming_handler.get_active_sessions(),
        }