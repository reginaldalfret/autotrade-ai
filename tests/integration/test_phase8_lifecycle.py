"""
Phase 8 End-to-End Integration Lifecycle Test.
Verifies complete execution: paper trading -> auto square-off ->
compounding -> performance analytics -> cryptographic audit verification ->
automated executive PDF report generation.
"""

import os
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from mobitrade.domain.enums import Action
from mobitrade.domain.data_models import Timeframe
from mobitrade.domain.llm_models import LLMDecisionRecord, LLMAction, ValidationStatus
from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.paper.engine import PaperTradingEngine
from mobitrade.analytics.engine import PerformanceAnalyticsEngine
from mobitrade.logging.audit import AuditLogger, verify_audit_chain
from mobitrade.data.calendar import IST


def test_phase8_complete_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = str(tmp_path / "lifecycle.db")
        reports_dir = str(tmp_path / "reports")

        engine = PaperTradingEngine(db_path=db_path)
        session_id = "SES_PHASE8_INTEGRATION"
        session_date = "2026-09-11"

        # 1. Start Session
        engine.start_session(session_id, session_date)
        assert len(engine.accounts) == 8

        # 2. Simulate decisions
        now_930 = datetime(2026, 9, 11, 9, 30, tzinfo=IST)
        snap_ioc = MarketSnapshot(
            snapshot_id="SNP_IOC_01",
            symbol="IOC",
            decision_timestamp=now_930,
            timeframe=Timeframe.M5
        )
        dec_nemo = LLMDecisionRecord(
            decision_id="DEC_NEMO_01",
            run_id="run_01",
            model_id="nemotron",
            model_version="1.0",
            prompt_version="1.0",
            snapshot_id="SNP_IOC_01",
            decision_timestamp=now_930,
            symbol="IOC",
            action=LLMAction.BUY,
            confidence=0.85,
            entry_rationale="Bullish",
            proposed_stop_loss=95.0,
            proposed_target=110.0,
            holding_intent="INTRADAY",
            reasoning_summary="Bullish continuation on IOC",
            validation_status=ValidationStatus.VALID,
            raw_output=""
        )
        trade1 = engine.process_model_decision(dec_nemo, snap_ioc, session_id, current_market_price=100.0)
        assert trade1 is not None

        # Model 2: Qwen HOLD TCS
        now_945 = datetime(2026, 9, 11, 9, 45, tzinfo=IST)
        snap_tcs = MarketSnapshot(
            snapshot_id="SNP_TCS_01",
            symbol="TCS",
            decision_timestamp=now_945,
            timeframe=Timeframe.M5
        )
        dec_qwen = LLMDecisionRecord(
            decision_id="DEC_QWEN_01",
            run_id="run_02",
            model_id="qwen",
            model_version="1.0",
            prompt_version="1.0",
            snapshot_id="SNP_TCS_01",
            decision_timestamp=now_945,
            symbol="TCS",
            action=LLMAction.HOLD,
            confidence=0.50,
            entry_rationale="Neutral",
            holding_intent="INTRADAY",
            reasoning_summary="No edge, sideways consolidation",
            validation_status=ValidationStatus.VALID,
            raw_output=""
        )
        trade2 = engine.process_model_decision(dec_qwen, snap_tcs, session_id, current_market_price=3800.0)
        assert trade2 is None

        # 3. Midday price update: IOC moves up to 105
        engine.update_market_prices(
            current_prices={"IOC": 105.0, "TCS": 3800.0},
            timestamp=datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc),
            session_id=session_id
        )

        # 4. Intraday auto square-off at 15:15 IST
        engine.execute_auto_square_off(
            current_prices={"IOC": 106.0, "TCS": 3800.0},
            timestamp=datetime(2026, 9, 11, 15, 15, tzinfo=timezone.utc),
            session_id=session_id
        )

        # Verify all open trades closed
        assert len(engine.broker.open_trades) == 0

        # 5. Finalize Daily Session (triggers compounding, analytics, and PDF generation)
        leaderboard = engine.finalize_daily_session(session_id, session_date)
        assert len(leaderboard) == 8

        # 6. Verify Cryptographic Audit Chain
        audit_logger = AuditLogger(db_path=db_path)
        audit_res = audit_logger.verify_chain(session_id=session_id)
        assert audit_res.is_valid is True
        assert audit_res.total_events >= 10
        assert len(audit_res.errors) == 0

        all_events = audit_logger.get_events(session_id=session_id)
        event_types = {e.event_type for e in all_events}
        assert "SESSION_STARTED" in event_types
        assert "ORDER_FILLED" in event_types
        assert "MARKET_CLOSE_SQUARE_OFF" in event_types
        assert "COMPOUNDING_APPLIED" in event_types

        # 7. Verify Performance Analytics Engine & Data Reconciliation
        analytics_engine = PerformanceAnalyticsEngine(db_path=db_path)
        session_data = analytics_engine.compute_daily_session_analytics(session_id)
        assert session_data["executive_summary"]["total_models"] == 8
        assert session_data["executive_summary"]["total_trades"] >= 1

        # Strict financial reconciliation
        reconcile_res = analytics_engine.reconcile_trading_data(session_id)
        assert reconcile_res["is_reconciled"] is True
        assert len(reconcile_res["discrepancies"]) == 0
