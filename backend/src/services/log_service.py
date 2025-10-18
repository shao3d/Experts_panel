"""
Simple Logging Service for Map-Resolve-Reduce Pipeline

Provides structured logging with SSE integration for real-time updates.
"""

import asyncio
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from collections import deque
import logging

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class LogPhase(Enum):
    """Pipeline phases for logging"""
    STARTUP = "startup"
    MAP = "map"
    RESOLVE = "resolve"
    REDUCE = "reduce"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: float
    level: LogLevel
    phase: LogPhase
    message: str
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "level": self.level.value,
            "phase": self.phase.value,
            "message": self.message,
            "data": self.data
        }


class LogService:
    """
    Centralized logging service for pipeline execution

    Features:
    - Structured logging with phases and levels
    - In-memory log storage for debugging
    - SSE event generation
    - Performance metrics tracking
    - Async-safe operations
    """

    def __init__(self, max_logs: int = 1000):
        """
        Initialize the log service

        Args:
            max_logs: Maximum number of logs to keep in memory
        """
        self._logs: deque = deque(maxlen=max_logs)
        self._sse_callbacks: List[Callable] = []
        self._start_times: Dict[str, float] = {}
        self._metrics: Dict[str, Any] = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "average_processing_time": 0,
            "phase_timings": {}
        }
        self._lock = asyncio.Lock()

    async def log(
        self,
        level: LogLevel,
        phase: LogPhase,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        emit_sse: bool = True
    ) -> LogEntry:
        """
        Create and store a log entry

        Args:
            level: Log severity level
            phase: Pipeline phase
            message: Log message
            data: Additional data to log
            emit_sse: Whether to emit SSE event

        Returns:
            The created log entry
        """
        async with self._lock:
            entry = LogEntry(
                timestamp=time.time(),
                level=level,
                phase=phase,
                message=message,
                data=data
            )

            self._logs.append(entry)

            # Log to Python logger
            log_method = getattr(logger, level.value, logger.info)
            log_method(f"[{phase.value}] {message}", extra={"data": data})

            # Emit SSE event if requested
            if emit_sse:
                await self._emit_sse(entry)

            return entry

    async def log_phase_start(self, phase: LogPhase, message: str = None) -> None:
        """Log the start of a pipeline phase"""
        phase_name = phase.value
        self._start_times[phase_name] = time.time()

        if message is None:
            message = f"Starting {phase_name} phase"

        await self.log(
            level=LogLevel.INFO,
            phase=phase,
            message=message,
            data={"event": "phase_start", "phase": phase_name}
        )

    async def log_phase_complete(
        self,
        phase: LogPhase,
        message: str = None,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log the completion of a pipeline phase"""
        phase_name = phase.value

        # Calculate duration if start time exists
        duration = None
        if phase_name in self._start_times:
            duration = time.time() - self._start_times[phase_name]
            self._metrics["phase_timings"][phase_name] = duration

        if message is None:
            message = f"Completed {phase_name} phase"
            if duration:
                message += f" (took {duration:.2f}s)"

        log_data = {"event": "phase_complete", "phase": phase_name}
        if duration:
            log_data["duration"] = duration
        if data:
            log_data.update(data)

        await self.log(
            level=LogLevel.SUCCESS,
            phase=phase,
            message=message,
            data=log_data
        )

    async def log_map_progress(
        self,
        current_chunk: int,
        total_chunks: int,
        posts_in_chunk: int
    ) -> None:
        """Log progress during map phase"""
        message = f"Processing chunk {current_chunk}/{total_chunks} ({posts_in_chunk} posts)"

        await self.log(
            level=LogLevel.INFO,
            phase=LogPhase.MAP,
            message=message,
            data={
                "event": "map_progress",
                "chunk": current_chunk,
                "total": total_chunks,
                "posts_in_chunk": posts_in_chunk,
                "progress_percentage": (current_chunk / total_chunks) * 100
            }
        )

    async def log_resolve_progress(
        self,
        links_found: int,
        links_evaluated: int
    ) -> None:
        """Log progress during resolve phase"""
        message = f"Evaluating {links_evaluated} of {links_found} links found"

        await self.log(
            level=LogLevel.INFO,
            phase=LogPhase.RESOLVE,
            message=message,
            data={
                "event": "resolve_progress",
                "links_found": links_found,
                "links_evaluated": links_evaluated
            }
        )

    async def log_error(
        self,
        phase: LogPhase,
        error: str,
        exception: Optional[Exception] = None
    ) -> None:
        """Log an error"""
        data = {"event": "error", "error": error}

        if exception:
            data["exception_type"] = type(exception).__name__
            data["exception_message"] = str(exception)

        await self.log(
            level=LogLevel.ERROR,
            phase=phase,
            message=f"Error in {phase.value}: {error}",
            data=data
        )

        self._metrics["failed_queries"] += 1

    async def log_query_complete(
        self,
        query: str,
        total_posts: int,
        relevant_posts: int,
        processing_time: float
    ) -> None:
        """Log successful query completion"""
        self._metrics["successful_queries"] += 1
        self._metrics["total_queries"] += 1

        # Update average processing time
        total = self._metrics["successful_queries"]
        current_avg = self._metrics["average_processing_time"]
        self._metrics["average_processing_time"] = (
            (current_avg * (total - 1) + processing_time) / total
        )

        await self.log(
            level=LogLevel.SUCCESS,
            phase=LogPhase.COMPLETE,
            message=f"Query completed successfully in {processing_time:.2f}s",
            data={
                "event": "query_complete",
                "query": query[:100],  # Truncate long queries
                "total_posts_analyzed": total_posts,
                "relevant_posts_found": relevant_posts,
                "processing_time": processing_time
            }
        )

    def register_sse_callback(self, callback: Callable) -> None:
        """Register a callback for SSE events"""
        self._sse_callbacks.append(callback)

    def unregister_sse_callback(self, callback: Callable) -> None:
        """Unregister an SSE callback"""
        if callback in self._sse_callbacks:
            self._sse_callbacks.remove(callback)

    async def _emit_sse(self, entry: LogEntry) -> None:
        """Emit SSE event for log entry"""
        # Map log levels to SSE event types
        event_type_map = {
            LogLevel.ERROR: "error",
            LogLevel.SUCCESS: "phase_complete",
            LogLevel.INFO: "info",
            LogLevel.WARNING: "warning",
            LogLevel.DEBUG: "debug"
        }

        # Special handling for specific events
        if entry.data and "event" in entry.data:
            event_type = entry.data["event"]
        else:
            event_type = event_type_map.get(entry.level, "info")

        sse_data = {
            "type": event_type,
            "phase": entry.phase.value,
            "message": entry.message,
            "timestamp": entry.timestamp
        }

        if entry.data:
            sse_data.update(entry.data)

        # Call registered callbacks
        for callback in self._sse_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(sse_data)
                else:
                    callback(sse_data)
            except Exception as e:
                logger.error(f"Error in SSE callback: {e}")

    def get_logs(
        self,
        phase: Optional[LogPhase] = None,
        level: Optional[LogLevel] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve logs from memory

        Args:
            phase: Filter by phase
            level: Filter by level
            limit: Maximum number of logs to return

        Returns:
            List of log entries as dictionaries
        """
        logs = list(self._logs)

        if phase:
            logs = [l for l in logs if l.phase == phase]

        if level:
            logs = [l for l in logs if l.level == level]

        # Return most recent logs first
        return [l.to_dict() for l in reversed(logs[-limit:])]

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return self._metrics.copy()

    def clear_logs(self) -> None:
        """Clear all logs from memory"""
        self._logs.clear()
        self._start_times.clear()

    def get_current_phase_duration(self, phase: LogPhase) -> Optional[float]:
        """Get duration of current or completed phase"""
        phase_name = phase.value
        if phase_name in self._start_times:
            if phase_name in self._metrics["phase_timings"]:
                return self._metrics["phase_timings"][phase_name]
            else:
                return time.time() - self._start_times[phase_name]
        return None


# Global instance for easy access
_log_service: Optional[LogService] = None


def get_log_service() -> LogService:
    """Get or create the global log service instance"""
    global _log_service
    if _log_service is None:
        _log_service = LogService()
    return _log_service


def reset_log_service() -> None:
    """Reset the global log service"""
    global _log_service
    _log_service = None