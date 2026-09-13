import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from mobitrade.logging.audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    canonical_json,
    verify_audit_chain,
    GENESIS_PREVIOUS_HASH
)

def test_canonical_json_determinism():
    d1 = {"z": 1, "a": 2, "m": {"y": 2.123456789, "x": 10}}
    d2 = {"a": 2, "m": {"x": 10, "y": 2.123456789}, "z": 1}
    assert canonical_json(d1) == canonical_json(d2)

def test_audit_genesis_and_chain():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        logger = AuditLogger(db_path=db_path)

        # 1. First event should be genesis
        evt1 = logger.record_event(
            session_id="SES_001",
            event_type=AuditEventType.SESSION_STARTED,
            payload={"market": "NSE"},
            model_id="SYSTEM"
        )
        assert evt1.sequence_number == 1
        assert evt1.previous_event_hash == GENESIS_PREVIOUS_HASH
        assert evt1.is_valid()

        # 2. Second event
        evt2 = logger.record_event(
            session_id="SES_001",
            event_type=AuditEventType.ORDER_CREATED,
            payload={"symbol": "RELIANCE", "qty": 10},
            model_id="nemotron"
        )
        assert evt2.sequence_number == 2
        assert evt2.previous_event_hash == evt1.event_hash
        assert evt2.is_valid()

        # 3. Third event
        evt3 = logger.record_event(
            session_id="SES_001",
            event_type=AuditEventType.ORDER_FILLED,
            payload={"symbol": "RELIANCE", "fill_price": 2500.0},
            model_id="nemotron",
            trade_id="trd_123"
        )
        assert evt3.sequence_number == 3
        assert evt3.previous_event_hash == evt2.event_hash
        assert evt3.is_valid()

        # Verify chain
        res = logger.verify_chain(session_id="SES_001")
        assert res.is_valid is True
        assert res.total_events == 3
        assert len(res.errors) == 0

def test_audit_tamper_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        logger = AuditLogger(db_path=db_path)

        for i in range(5):
            logger.record_event(
                session_id="SES_TAMPER",
                event_type=AuditEventType.PORTFOLIO_MARK,
                payload={"step": i, "equity": 1000.0 + i * 10}
            )

        events = logger.get_events(session_id="SES_TAMPER")
        assert len(events) == 5
        assert verify_audit_chain(events).is_valid is True

        # Tamper test 1: Modify payload of event 2
        tampered_events = [AuditEvent(**vars(e)) for e in events]
        tampered_events[2].payload["equity"] = 999999.0
        res = verify_audit_chain(tampered_events)
        assert res.is_valid is False
        assert any("Tamper detected at seq=3" in err for err in res.errors)

        # Tamper test 2: Delete event 3 (sequence gap)
        deleted_events = [events[0], events[1], events[3], events[4]]
        res_del = verify_audit_chain(deleted_events)
        assert res_del.is_valid is False
        assert any("Sequence gap detected" in err for err in res_del.errors)

def test_audit_trail_filtering():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        logger = AuditLogger(db_path=db_path)

        logger.record_event(session_id="SES_A", event_type=AuditEventType.SESSION_STARTED, payload={}, model_id="SYSTEM")
        logger.record_event(session_id="SES_A", event_type=AuditEventType.ORDER_FILLED, payload={}, model_id="qwen", trade_id="T1")
        logger.record_event(session_id="SES_A", event_type=AuditEventType.ORDER_FILLED, payload={}, model_id="gemma", trade_id="T2")
        logger.record_event(session_id="SES_B", event_type=AuditEventType.SESSION_STARTED, payload={}, model_id="SYSTEM")

        events_a = logger.get_events(session_id="SES_A")
        assert len(events_a) == 3

        qwen_events = logger.get_events(model_id="qwen")
        assert len(qwen_events) == 1
        assert qwen_events[0].trade_id == "T1"

        t2_events = logger.get_events(trade_id="T2")
        assert len(t2_events) == 1
        assert t2_events[0].model_id == "gemma"
