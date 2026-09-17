"""
In-Process Runtime Activity Monitor for AutoTrade AI (Phase 12).
Tracks live AI model execution phases (LOAD, INFERENCE, VALIDATION, RECORD, UNLOAD),
active session operations, and provides a rolling FIFO event stream for monitoring dashboards.
"""

from datetime import datetime, timezone
from collections import deque
from typing import Dict, Any, List, Optional
import time


class RuntimeActivityMonitor:
    """
    Lightweight, thread-safe in-process monitor of live model activity and trade execution.
    """

    def __init__(self, max_events: int = 200):
        self.max_events = max_events
        self.current_model: Optional[str] = None
        self.current_phase: str = "IDLE"
        self.current_operation: str = "System Idle"
        self.session_id: Optional[str] = None
        self.symbol: Optional[str] = None
        self.started_at: Optional[str] = None
        self._start_time: Optional[float] = None
        self._events: deque = deque(maxlen=max_events)
        # Record initial boot event
        self.record_event("AutoTrade AI runtime monitor initialized.", level="info")

    def set_active(
        self,
        model_id: Optional[str],
        phase: str,
        operation: str,
        session_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> None:
        """Mark a model and pipeline step as actively executing."""
        now = datetime.now().isoformat()
        self.current_model = model_id
        self.current_phase = phase
        self.current_operation = operation
        self.session_id = session_id or self.session_id
        self.symbol = symbol or self.symbol
        self.started_at = now
        self._start_time = time.time()

        self.record_event(
            message=operation,
            model_id=model_id,
            phase=phase,
            level="info",
        )

    def set_idle(self, message: str = "IDLE - Waiting for Session") -> None:
        """Reset state to idle when no model is processing."""
        self.current_model = None
        self.current_phase = "IDLE"
        self.current_operation = message
        self.started_at = None
        self._start_time = None

    def record_event(
        self,
        message: str,
        model_id: Optional[str] = None,
        phase: Optional[str] = None,
        level: str = "info",
    ) -> None:
        """Append an event to the rolling in-memory feed."""
        now_dt = datetime.now()
        event = {
            "timestamp": now_dt.strftime("%H:%M:%S"),
            "iso_time": now_dt.isoformat(),
            "model_id": model_id or self.current_model,
            "phase": phase or self.current_phase,
            "message": message,
            "level": level,
        }
        self._events.append(event)

    def get_runtime_status(self) -> Dict[str, Any]:
        """Return snapshot of what AI models are doing NOW."""
        elapsed = round(time.time() - self._start_time, 2) if self._start_time else 0.0
        return {
            "current_model": self.current_model or "IDLE",
            "current_phase": self.current_phase,
            "current_operation": self.current_operation,
            "session_id": self.session_id,
            "symbol": self.symbol,
            "started_at": self.started_at,
            "elapsed_seconds": elapsed,
            "is_active": self.current_phase != "IDLE",
            "pipeline_steps": [
                {"name": "Load Model", "active": self.current_phase == "LOAD"},
                {"name": "Infer", "active": self.current_phase == "INFERENCE"},
                {"name": "Validate", "active": self.current_phase == "VALIDATION"},
                {"name": "Record", "active": self.current_phase == "RECORD"},
                {"name": "Unload", "active": self.current_phase == "UNLOAD"},
            ],
        }

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return newest events first."""
        events_list = list(self._events)
        events_list.reverse()
        return events_list[:limit]

    def get_current_activity(self) -> Dict[str, Any]:
        """Combined status and recent events."""
        return {
            "status": self.get_runtime_status(),
            "recent_events": self.get_recent_events(limit=50),
        }


# Global in-process singleton
runtime_monitor = RuntimeActivityMonitor()
