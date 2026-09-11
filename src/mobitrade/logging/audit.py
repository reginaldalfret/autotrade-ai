import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

class AuditLogger:
    """
    Structured append-only audit logger.
    Every trade, decision, risk evaluation, and snapshot is recorded for reproducibility.
    """
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.log_dir / "audit.jsonl"

    def log_event(self, event_type: str, data: Dict[str, Any], timestamp: Optional[datetime] = None):
        payload = {
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
            "event_type": event_type,
            "data": data
        }
        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
