"""
Tamper-evident Cryptographic Audit Logging Layer.
Provides continuous SHA-256 hash chaining, canonical JSON serialization,
strict append-only persistence, and integrity verification.
"""

import json
import hashlib
import sqlite3
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Union


class AuditEventType(str, Enum):
    # Session lifecycle
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_CLOSED = "SESSION_CLOSED"
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"

    # LLM execution lifecycle
    LLM_RUN_STARTED = "LLM_RUN_STARTED"
    LLM_RUN_COMPLETED = "LLM_RUN_COMPLETED"
    LLM_RUN_FAILED = "LLM_RUN_FAILED"
    DECISION_CREATED = "DECISION_CREATED"
    DECISION_REJECTED = "DECISION_REJECTED"
    DECISION_VALIDATED = "DECISION_VALIDATED"

    # Risk evaluation
    RISK_CHECK_PASSED = "RISK_CHECK_PASSED"
    RISK_CHECK_FAILED = "RISK_CHECK_FAILED"

    # Execution & Order lifecycle
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_FILLED = "ORDER_FILLED"

    # Position lifecycle
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_UPDATED = "POSITION_UPDATED"
    POSITION_CLOSED = "POSITION_CLOSED"

    # Exit & Stop triggers
    STOP_LOSS_TRIGGERED = "STOP_LOSS_TRIGGERED"
    TRAILING_STOP_TRIGGERED = "TRAILING_STOP_TRIGGERED"
    DAILY_TARGET_REACHED = "DAILY_TARGET_REACHED"
    DAILY_STOP_TRIGGERED = "DAILY_STOP_TRIGGERED"
    AUTO_SQUARE_OFF = "AUTO_SQUARE_OFF"

    # Accounting & Compounding
    PORTFOLIO_MARK = "PORTFOLIO_MARK"
    DAILY_FINALIZED = "DAILY_FINALIZED"
    COMPOUNDING_APPLIED = "COMPOUNDING_APPLIED"

    # Reporting
    REPORT_GENERATED = "REPORT_GENERATED"
    REPORT_FAILED = "REPORT_FAILED"


GENESIS_PREVIOUS_HASH = "0" * 64


def canonical_json(data: Any) -> str:
    """
    Serializes Python data structures into deterministic, canonical JSON.
    - Keys sorted recursively.
    - No redundant whitespaces (separators=(',', ':')).
    - Float rounding to 8 decimal places to eliminate float precision discrepancies.
    - Datetimes formatted as ISO 8601 UTC.
    - Enums converted to string values.
    """
    def _normalize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _normalize(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, (list, tuple)):
            return [_normalize(item) for item in obj]
        elif isinstance(obj, float):
            return round(obj, 8)
        elif isinstance(obj, datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=timezone.utc)
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        elif obj is None or isinstance(obj, (int, str, bool)):
            return obj
        else:
            return str(obj)

    normalized = _normalize(data)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass
class AuditEvent:
    event_id: str
    sequence_number: int
    session_id: str
    timestamp: str
    event_type: str
    model_id: Optional[str]
    trade_id: Optional[str]
    order_id: Optional[str]
    payload: Dict[str, Any]
    previous_event_hash: str
    event_hash: str

    def compute_expected_hash(self) -> str:
        """
        Recomputes hash from core fields and previous hash.
        event_hash = SHA256(canonical_json(core_fields) + previous_event_hash)
        """
        core = {
            "event_id": self.event_id,
            "sequence_number": self.sequence_number,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "model_id": self.model_id,
            "trade_id": self.trade_id,
            "order_id": self.order_id,
            "payload": self.payload,
            "previous_event_hash": self.previous_event_hash,
        }
        raw_str = canonical_json(core) + self.previous_event_hash
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def is_valid(self) -> bool:
        return self.event_hash == self.compute_expected_hash()


@dataclass
class AuditVerificationResult:
    is_valid: bool
    total_events: int
    first_sequence: Optional[int] = None
    last_sequence: Optional[int] = None
    errors: List[str] = field(default_factory=list)
    session_id: Optional[str] = None


def verify_audit_chain(events: List[AuditEvent]) -> AuditVerificationResult:
    """
    Verifies cryptographic hash chain integrity for an ordered sequence of events.
    Checks:
    1. Genesis block sequence 1 previous hash == '0'*64.
    2. Consecutive sequence numbers without gaps or duplicates.
    3. Chain continuity: previous_event_hash == previous event's event_hash.
    4. Payload integrity: recomputed event_hash == stored event_hash.
    """
    if not events:
        return AuditVerificationResult(
            is_valid=True,
            total_events=0,
            first_sequence=None,
            last_sequence=None,
            errors=[]
        )

    errors = []
    first_seq = events[0].sequence_number
    last_seq = events[-1].sequence_number

    for i, event in enumerate(events):
        # 1. Verify self-hash integrity
        computed_hash = event.compute_expected_hash()
        if computed_hash != event.event_hash:
            errors.append(
                f"Tamper detected at seq={event.sequence_number} (id={event.event_id}): "
                f"stored_hash={event.event_hash} != computed_hash={computed_hash}"
            )

        # 2. Check chain linkage
        if i == 0:
            if event.sequence_number == 1 and event.previous_event_hash != GENESIS_PREVIOUS_HASH:
                errors.append(
                    f"Invalid genesis block at seq=1: previous_hash={event.previous_event_hash} "
                    f"!= {GENESIS_PREVIOUS_HASH}"
                )
        else:
            prev_event = events[i - 1]
            if event.sequence_number != prev_event.sequence_number + 1:
                errors.append(
                    f"Sequence gap detected: seq={event.sequence_number} immediately follows seq={prev_event.sequence_number}"
                )
            if event.previous_event_hash != prev_event.event_hash:
                errors.append(
                    f"Broken chain link at seq={event.sequence_number}: previous_event_hash={event.previous_event_hash} "
                    f"!= prev_seq_{prev_event.sequence_number}_hash={prev_event.event_hash}"
                )

    is_valid = len(errors) == 0
    return AuditVerificationResult(
        is_valid=is_valid,
        total_events=len(events),
        first_sequence=first_seq,
        last_sequence=last_seq,
        errors=errors
    )


class AuditLogger:
    """
    Cryptographic append-only audit logger backed by SQLite and optional JSONL file.
    Enforces sequential sequence numbers and continuous SHA-256 hash chains.
    """
    def __init__(self, db_path: str = "/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db", log_dir: Optional[str] = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir = Path(log_dir) if log_dir else None
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.audit_file = self.log_dir / "audit.jsonl"
        else:
            self.audit_file = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    sequence_number INTEGER,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    model_id TEXT,
                    trade_id TEXT,
                    order_id TEXT,
                    payload_json TEXT NOT NULL,
                    previous_event_hash TEXT,
                    event_hash TEXT
                )
            """)
            # Check existing columns and migrate if table was created in Phase 7
            cursor.execute("PRAGMA table_info(audit_events)")
            cols = {r["name"] for r in cursor.fetchall()}
            if "sequence_number" not in cols:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN sequence_number INTEGER")
            if "previous_event_hash" not in cols:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN previous_event_hash TEXT")
            if "event_hash" not in cols:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN event_hash TEXT")
            if "trade_id" not in cols:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN trade_id TEXT")
            if "order_id" not in cols:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN order_id TEXT")

            # Backfill any legacy unchained events
            cursor.execute("SELECT * FROM audit_events WHERE sequence_number IS NULL ORDER BY timestamp ASC, rowid ASC")
            unhashed = cursor.fetchall()
            if unhashed:
                cursor.execute("SELECT sequence_number, event_hash FROM audit_events WHERE sequence_number IS NOT NULL ORDER BY sequence_number DESC LIMIT 1")
                last = cursor.fetchone()
                cur_seq = last["sequence_number"] if last else 0
                prev_h = last["event_hash"] if last else GENESIS_PREVIOUS_HASH
                for row in unhashed:
                    cur_seq += 1
                    payload_dict = json.loads(row["payload_json"]) if row["payload_json"] else {}
                    core = {
                        "event_id": row["event_id"],
                        "sequence_number": cur_seq,
                        "session_id": row["session_id"],
                        "timestamp": row["timestamp"],
                        "event_type": row["event_type"],
                        "model_id": row["model_id"] if "model_id" in row.keys() else None,
                        "trade_id": row["trade_id"] if "trade_id" in row.keys() else None,
                        "order_id": row["order_id"] if "order_id" in row.keys() else None,
                        "payload": payload_dict,
                        "previous_event_hash": prev_h,
                    }
                    raw = canonical_json(core) + prev_h
                    eh = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                    cursor.execute(
                        "UPDATE audit_events SET sequence_number = ?, previous_event_hash = ?, event_hash = ? WHERE event_id = ?",
                        (cur_seq, prev_h, eh, row["event_id"])
                    )
                    prev_h = eh

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_seq ON audit_events (sequence_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events (session_id, sequence_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_model ON audit_events (model_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events (event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trade ON audit_events (trade_id)")
            conn.commit()

    def record_event(
        self,
        session_id: str,
        event_type: Union[AuditEventType, str],
        payload: Dict[str, Any],
        model_id: Optional[str] = None,
        trade_id: Optional[str] = None,
        order_id: Optional[str] = None,
        timestamp: Optional[Union[datetime, str]] = None,
        event_id: Optional[str] = None
    ) -> AuditEvent:
        """
        Appends an immutable audit event to the cryptographic hash chain.
        Guarantees consecutive sequence numbering and parent hash linkage.
        """
        if isinstance(event_type, Enum):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)

        if timestamp is None:
            ts_str = datetime.now(timezone.utc).isoformat()
        elif isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            ts_str = timestamp.isoformat()
        else:
            ts_str = str(timestamp)

        import uuid
        actual_event_id = event_id or f"evt_{uuid.uuid4().hex[:12]}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Atomically get highest sequence number and latest hash
            cursor.execute("SELECT sequence_number, event_hash FROM audit_events ORDER BY sequence_number DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                next_seq = row["sequence_number"] + 1
                prev_hash = row["event_hash"]
            else:
                next_seq = 1
                prev_hash = GENESIS_PREVIOUS_HASH

            core_data = {
                "event_id": actual_event_id,
                "sequence_number": next_seq,
                "session_id": session_id,
                "timestamp": ts_str,
                "event_type": event_type_str,
                "model_id": model_id,
                "trade_id": trade_id,
                "order_id": order_id,
                "payload": payload,
                "previous_event_hash": prev_hash,
            }
            raw_str = canonical_json(core_data) + prev_hash
            event_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

            event = AuditEvent(
                event_id=actual_event_id,
                sequence_number=next_seq,
                session_id=session_id,
                timestamp=ts_str,
                event_type=event_type_str,
                model_id=model_id,
                trade_id=trade_id,
                order_id=order_id,
                payload=payload,
                previous_event_hash=prev_hash,
                event_hash=event_hash
            )

            cursor.execute("""
                INSERT INTO audit_events (
                    event_id, sequence_number, session_id, timestamp,
                    event_type, model_id, trade_id, order_id,
                    payload_json, previous_event_hash, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.sequence_number,
                event.session_id,
                event.timestamp,
                event.event_type,
                event.model_id,
                event.trade_id,
                event.order_id,
                json.dumps(event.payload, sort_keys=True),
                event.previous_event_hash,
                event.event_hash
            ))
            conn.commit()

        # Optional JSONL mirroring
        if self.audit_file:
            with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(canonical_json(asdict(event)) + "\n")

        return event

    def log_event(self, event_type: str, data: Dict[str, Any], timestamp: Optional[datetime] = None) -> AuditEvent:
        """Backward-compatibility wrapper for legacy calls."""
        return self.record_event(
            session_id="LEGACY",
            event_type=event_type,
            payload=data,
            timestamp=timestamp
        )

    def get_events(
        self,
        session_id: Optional[str] = None,
        model_id: Optional[str] = None,
        event_type: Optional[str] = None,
        trade_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[AuditEvent]:
        """Queries events in chronological sequence."""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: List[Any] = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if model_id:
            query += " AND model_id = ?"
            params.append(model_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if trade_id:
            query += " AND trade_id = ?"
            params.append(trade_id)

        query += " ORDER BY sequence_number ASC"
        if limit:
            query += f" LIMIT {int(limit)}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append(AuditEvent(
                    event_id=r["event_id"],
                    sequence_number=r["sequence_number"],
                    session_id=r["session_id"],
                    timestamp=r["timestamp"],
                    event_type=r["event_type"],
                    model_id=r["model_id"],
                    trade_id=r["trade_id"],
                    order_id=r["order_id"],
                    payload=json.loads(r["payload_json"]),
                    previous_event_hash=r["previous_event_hash"],
                    event_hash=r["event_hash"]
                ))
            return results

    def get_event_by_id(self, event_id: str) -> Optional[AuditEvent]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_events WHERE event_id = ?", (event_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return AuditEvent(
                event_id=r["event_id"],
                sequence_number=r["sequence_number"],
                session_id=r["session_id"],
                timestamp=r["timestamp"],
                event_type=r["event_type"],
                model_id=r["model_id"],
                trade_id=r["trade_id"],
                order_id=r["order_id"],
                payload=json.loads(r["payload_json"]),
                previous_event_hash=r["previous_event_hash"],
                event_hash=r["event_hash"]
            )

    def verify_chain(self, session_id: Optional[str] = None) -> AuditVerificationResult:
        """Verifies integrity of the stored audit chain."""
        events = self.get_events(session_id=session_id)
        res = verify_audit_chain(events)
        res.session_id = session_id
        return res

