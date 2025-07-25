import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agent.models import ProgressUpdate
from agent.tasks import ReasoningChain

from .models import AppProgress, AppSession, SessionStatus


class SessionManager:
    """
    Manages application sessions including creation, tracking, persistence,
    and cleanup of user interaction sessions.
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        session_timeout_hours: int = 24,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("SessionManager")
        self.session_timeout_hours = session_timeout_hours

        # Setup storage
        self.storage_path = storage_path or Path.home() / ".brain" / "sessions"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Active sessions in memory
        self._active_sessions: Dict[str, AppSession] = {}

        # Session metrics
        self._session_metrics = {
            "total_created": 0,
            "total_completed": 0,
            "total_failed": 0,
            "active_count": 0,
        }

    async def create_session(self, initial_context: Dict[str, Any]) -> AppSession:
        """
        Create a new application session.

        Args:
            initial_context: Optional initial context for the session

        Returns:
            New application session
        """
        session_id = str(uuid.uuid4())

        session = AppSession(
            session_id=session_id,
            status=SessionStatus.READY,
            metadata=initial_context or {},
        )

        # Store in memory
        self._active_sessions[session_id] = session

        # Persist to disk
        await self._persist_session(session)

        # Update metrics
        self._session_metrics["total_created"] += 1
        self._session_metrics["active_count"] += 1

        self.logger.info(f"Created new session: {session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[AppSession]:
        """
        Get a session by ID, loading from disk if necessary.

        Args:
            session_id: Session identifier

        Returns:
            Session if found, None otherwise
        """
        # Check active sessions first
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]

        # Try to load from disk
        session = await self._load_session(session_id)
        if session:
            # Add to active sessions if still valid
            if not self._is_session_expired(session):
                self._active_sessions[session_id] = session
                return session
            else:
                self.logger.info(f"Session {session_id} has expired")
                await self._cleanup_session(session_id)

        return None

    async def update_session_progress(
        self, session_id: str, progress_update: ProgressUpdate
    ) -> bool:
        """
        Update session progress with agent progress information.

        Args:
            session_id: Session identifier
            progress_update: Progress update from agent

        Returns:
            True if session was updated, False if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        # Update session progress
        session.update_progress(progress_update)

        # Persist changes
        await self._persist_session(session)

        self.logger.debug(
            f"Updated progress for session {session_id}: {
                          progress_update.progress_percentage}%"
        )
        return True

    async def complete_session(
        self, session_id: str, result: str, reasoning_chain: ReasoningChain
    ) -> bool:
        """
        Mark a session as completed with results.

        Args:
            session_id: Session identifier
            result: Final result of the session
            reasoning_chain: Completed reasoning chain

        Returns:
            True if session was completed, False if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        # Complete the session
        session.complete_processing(result, reasoning_chain)

        # Persist changes
        await self._persist_session(session)

        # Update metrics
        self._session_metrics["total_completed"] += 1
        if session_id in self._active_sessions:
            self._session_metrics["active_count"] -= 1

        self.logger.info(
            f"Completed session {
                         session_id} with result length: {len(result)}"
        )
        return True

    async def fail_session(self, session_id: str, error: str) -> bool:
        """
        Mark a session as failed with error information.

        Args:
            session_id: Session identifier
            error: Error message

        Returns:
            True if session was failed, False if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        # Fail the session
        session.fail_processing(error)

        # Persist changes
        await self._persist_session(session)

        # Update metrics
        self._session_metrics["total_failed"] += 1
        if session_id in self._active_sessions:
            self._session_metrics["active_count"] -= 1

        self.logger.error(f"Failed session {session_id}: {error}")
        return True

    async def cancel_session(self, session_id: str) -> bool:
        """
        Cancel a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was cancelled, False if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        # Cancel the session
        session.cancel_processing()

        # Persist changes
        await self._persist_session(session)

        # Update metrics
        if session_id in self._active_sessions:
            self._session_metrics["active_count"] -= 1

        self.logger.info(f"Cancelled session {session_id}")
        return True

    async def list_active_sessions(self) -> List[AppSession]:
        """
        Get all active sessions.

        Returns:
            List of active sessions
        """
        # Clean up expired sessions
        await self._cleanup_expired_sessions()

        return list(self._active_sessions.values())

    async def get_session_history(
        self, limit: int = 50, status_filter: Optional[SessionStatus] = None
    ) -> List[AppSession]:
        """
        Get session history from disk storage.

        Args:
            limit: Maximum number of sessions to return
            status_filter: Optional status filter

        Returns:
            List of historical sessions
        """
        sessions = []

        try:
            # Get all session files
            session_files = list(self.storage_path.glob("*.json"))
            session_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            # Get more to account for filtering
            for session_file in session_files[: limit * 2]:
                try:
                    session = await self._load_session_from_file(session_file)
                    if session:
                        if status_filter is None or session.status == status_filter:
                            sessions.append(session)
                            if len(sessions) >= limit:
                                break
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load session from {
                                        session_file}: {e}"
                    )

        except Exception as e:
            self.logger.error(f"Failed to get session history: {e}")

        return sessions

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session completely.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted, False if not found
        """
        # Remove from active sessions
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            self._session_metrics["active_count"] -= 1

        # Remove from disk
        session_file = self.storage_path / f"{session_id}.json"
        if session_file.exists():
            try:
                session_file.unlink()
                self.logger.info(f"Deleted session {session_id}")
                return True
            except Exception as e:
                self.logger.error(
                    f"Failed to delete session file {
                                  session_file}: {e}"
                )

        return False

    async def cleanup_old_sessions(self, older_than_days: int = 30) -> int:
        """
        Clean up old session files.

        Args:
            older_than_days: Delete sessions older than this many days

        Returns:
            Number of sessions cleaned up
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        cleaned_count = 0

        try:
            session_files = list(self.storage_path.glob("*.json"))

            for session_file in session_files:
                try:
                    # Check file modification time
                    file_time = datetime.utcfromtimestamp(session_file.stat().st_mtime)

                    if file_time < cutoff_date:
                        session_file.unlink()
                        cleaned_count += 1

                except Exception as e:
                    self.logger.warning(
                        f"Failed to process session file {
                                        session_file}: {e}"
                    )

        except Exception as e:
            self.logger.error(f"Failed to cleanup old sessions: {e}")

        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} old session files")

        return cleaned_count

    def get_session_metrics(self) -> Dict[str, Any]:
        """Get session manager metrics."""
        return {
            **self._session_metrics,
            "storage_path": str(self.storage_path),
            "session_timeout_hours": self.session_timeout_hours,
        }

    async def _persist_session(self, session: AppSession) -> None:
        """Persist a session to disk."""
        session_file = self.storage_path / f"{session.session_id}.json"

        try:
            with open(session_file, "w") as f:
                json.dump(session.model_dump(), f, indent=2, default=str)
        except Exception as e:
            self.logger.error(
                f"Failed to persist session {
                              session.session_id}: {e}"
            )

    async def _load_session(self, session_id: str) -> Optional[AppSession]:
        """Load a session from disk."""
        session_file = self.storage_path / f"{session_id}.json"
        return await self._load_session_from_file(session_file)

    async def _load_session_from_file(self, session_file: Path) -> Optional[AppSession]:
        """Load a session from a specific file."""
        if not session_file.exists():
            return None

        try:
            with open(session_file, "r") as f:
                session_data = json.load(f)

            # Convert datetime strings back to datetime objects
            for field in ["created_at", "started_at", "completed_at"]:
                if session_data.get(field):
                    session_data[field] = datetime.fromisoformat(
                        session_data[field].replace("Z", "+00:00")
                    )

            return AppSession(**session_data)

        except Exception as e:
            self.logger.error(
                f"Failed to load session from {
                              session_file}: {e}"
            )
            return None

    def _is_session_expired(self, session: AppSession) -> bool:
        """Check if a session has expired."""
        if not session.created_at:
            return False

        expiry_time = session.created_at + timedelta(hours=self.session_timeout_hours)
        return datetime.utcnow() > expiry_time

    async def _cleanup_session(self, session_id: str) -> None:
        """Clean up an expired session."""
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            self._session_metrics["active_count"] -= 1

    async def _cleanup_expired_sessions(self) -> None:
        """Clean up all expired sessions from active memory."""
        expired_sessions = []

        for session_id, session in self._active_sessions.items():
            if self._is_session_expired(session):
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            await self._cleanup_session(session_id)

        if expired_sessions:
            self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")


class SessionProgressTracker:
    """
    Tracks and aggregates progress updates for sessions.
    """

    def __init__(
        self, session_manager: SessionManager, logger: Optional[logging.Logger] = None
    ):
        self.session_manager = session_manager
        self.logger = logger or logging.getLogger("SessionProgressTracker")

        # Progress callbacks by session
        self._progress_callbacks: Dict[str, List[Callable[[AppProgress], None]]] = {}

    def register_progress_callback(
        self, session_id: str, callback: Callable[[AppProgress], None]
    ) -> None:
        """
        Register a progress callback for a session.

        Args:
            session_id: Session identifier
            callback: Callback function to call with progress updates
        """
        if session_id not in self._progress_callbacks:
            self._progress_callbacks[session_id] = []

        self._progress_callbacks[session_id].append(callback)
        self.logger.debug(f"Registered progress callback for session {session_id}")

    def unregister_progress_callback(
        self, session_id: str, callback: Callable[[AppProgress], None]
    ) -> None:
        """
        Unregister a progress callback for a session.

        Args:
            session_id: Session identifier
            callback: Callback function to remove
        """
        if session_id in self._progress_callbacks:
            try:
                self._progress_callbacks[session_id].remove(callback)
                if not self._progress_callbacks[session_id]:
                    del self._progress_callbacks[session_id]
                self.logger.debug(
                    f"Unregistered progress callback for session {session_id}"
                )
            except ValueError:
                pass

    async def update_session_progress(
        self, session_id: str, agent_progress: ProgressUpdate
    ) -> None:
        """
        Update session progress and notify callbacks.

        Args:
            session_id: Session identifier
            agent_progress: Progress update from agent
        """
        # Update session in manager
        updated = await self.session_manager.update_session_progress(
            session_id, agent_progress
        )

        if updated and session_id in self._progress_callbacks:
            # Get updated session
            session = await self.session_manager.get_session(session_id)
            if session:
                # Create application progress
                app_progress = AppProgress(
                    session_id=session_id,
                    status=session.status,
                    progress_percentage=agent_progress.progress_percentage,
                    current_step=agent_progress.current_task,
                    agent_progress=agent_progress,
                    elapsed_time_seconds=agent_progress.elapsed_time_seconds,
                    details=agent_progress.details,
                )

                # Notify all callbacks
                for callback in self._progress_callbacks[session_id]:
                    try:
                        callback(app_progress)
                    except Exception as e:
                        self.logger.error(
                            f"Progress callback failed for session {
                                          session_id}: {e}"
                        )

    def cleanup_session_callbacks(self, session_id: str) -> None:
        """
        Clean up all callbacks for a session.

        Args:
            session_id: Session identifier
        """
        if session_id in self._progress_callbacks:
            del self._progress_callbacks[session_id]
            self.logger.debug(f"Cleaned up progress callbacks for session {session_id}")
