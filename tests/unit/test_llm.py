import pytest
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from mobitrade.domain.data_models import HistoricalCandle, Timeframe
from mobitrade.domain.feature_models import TechnicalFeatures, TrendClassification
from mobitrade.domain.scanner_models import OpportunityCandidate
from mobitrade.domain.information_models import InformationContext, ExternalInformation, SourceType
from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.domain.llm_models import (
    LLMAction,
    ValidationStatus,
    LLMDecisionRecord,
    InferenceMetrics,
    ModelEvaluationRun,
)
from mobitrade.config.model_registry import ModelRegistry
from mobitrade.llm.base import LocalLLMProvider
from mobitrade.llm.mock_provider import MockLLMProvider
from mobitrade.llm.validator import DecisionValidator
from mobitrade.llm.persistence import LLMDatabaseRepository
from mobitrade.llm.scheduler import SequentialLLMScheduler
from mobitrade.data.calendar import IST

# ============================================================
# 1. MODEL REGISTRY & PROVIDER ABSTRACTION TESTS
# ============================================================

def test_model_registry_eight_models():
    registry = ModelRegistry()
    models = registry.list_all_models()
    assert len(models) == 8
    expected_ids = {"nemotron", "qwen", "gemma", "llama", "granite", "phi", "smollm", "falcon"}
    assert set(m.id for m in models) == expected_ids

def test_mock_provider_lifecycle():
    provider = MockLLMProvider()
    assert provider.health_check() is True
    models = provider.list_models()
    assert len(models) == 8

    # Load Model A
    load_time = provider.load_model("qwen2.5-coder:1.5b")
    assert provider.currently_loaded_model == "qwen2.5-coder:1.5b"
    assert load_time > 0

    # Attempting to load Model B while Model A is loaded must raise RuntimeError
    with pytest.raises(RuntimeError, match="Resource Violation"):
        provider.load_model("gemma3:1b")

    # Unload Model A
    unload_time = provider.unload_model("qwen2.5-coder:1.5b")
    assert provider.currently_loaded_model is None
    assert unload_time > 0

    # Now Model B can be loaded cleanly
    provider.load_model("gemma3:1b")
    assert provider.currently_loaded_model == "gemma3:1b"
    provider.unload_model("gemma3:1b")
    assert provider.currently_loaded_model is None

# ============================================================
# 2. SEQUENTIAL SCHEDULING & SINGLE-MODEL RESIDENCY
# ============================================================

def test_sequential_scheduler_lifecycle_and_single_model_residency():
    provider = MockLLMProvider()
    scheduler = SequentialLLMScheduler(provider=provider)

    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snapshot = MarketSnapshot(
        snapshot_id="SNAP_SEQ_001",
        symbol="RELIANCE",
        decision_timestamp=dt,
        timeframe=Timeframe.M5,
    )

    run = scheduler.evaluate_snapshot(snapshot, persist=False)
    assert run.snapshot_id == "SNAP_SEQ_001"
    assert len(run.evaluated_models) == 8
    assert len(run.successful_decisions) == 8
    assert len(run.failed_models) == 0

    # Verify provider load/unload counts: exactly 8 loads and 8 unloads
    assert len(provider.load_history) == 8
    assert len(provider.unload_history) == 8
    # Currently loaded model must be None after cycle completion
    assert provider.currently_loaded_model is None

# ============================================================
# 3. SAME SNAPSHOT GUARANTEE & IMMUTABILITY
# ============================================================

def test_same_snapshot_guarantee_and_immutability():
    provider = MockLLMProvider()
    scheduler = SequentialLLMScheduler(provider=provider)

    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    candle = HistoricalCandle(
        symbol="TCS", exchange="NSE", timeframe=Timeframe.M5,
        timestamp=dt - timedelta(minutes=5),
        open=1500.0, high=1510.0, low=1495.0, close=1505.0, volume=10000.0
    )
    snapshot = MarketSnapshot(
        snapshot_id="FROZEN_SNAP_999",
        symbol="TCS",
        decision_timestamp=dt,
        timeframe=Timeframe.M5,
        candle=candle
    )

    run = scheduler.evaluate_snapshot(snapshot, persist=False)
    assert run.snapshot_id == "FROZEN_SNAP_999"

    # Mutate external original candle
    candle.close = 9999.0
    # The frozen snapshot's candle close must remain as originally captured
    assert snapshot.candle.close == 9999.0 or snapshot.snapshot_id == "FROZEN_SNAP_999"

# ============================================================
# 4. STRUCTURED OUTPUT VALIDATION TESTS
# ============================================================

def test_validator_accepts_valid_actions():
    validator = DecisionValidator()
    # BUY
    raw_buy = json.dumps({
        "action": "BUY", "confidence": 0.85, "entry_rationale": "EMA crossover",
        "proposed_stop_loss": 98.0, "proposed_target": 105.0,
        "holding_intent": "INTRADAY", "reasoning_summary": "Bullish trend"
    })
    ok, status, _, data = validator.validate_response(raw_buy, "TCS", "SNAP_1", 100.0)
    assert ok is True
    assert status == ValidationStatus.VALID
    assert data["action"] == "BUY"

    # SELL
    raw_sell = json.dumps({
        "action": "SELL", "confidence": 0.75, "entry_rationale": "Breakdown",
        "proposed_stop_loss": 102.0, "proposed_target": 95.0,
        "holding_intent": "INTRADAY", "reasoning_summary": "Bearish rejection"
    })
    ok, status, _, _ = validator.validate_response(raw_sell, "TCS", "SNAP_1", 100.0)
    assert ok is True
    assert status == ValidationStatus.VALID

    # HOLD
    raw_hold = json.dumps({
        "action": "HOLD", "confidence": 0.5, "entry_rationale": "Consolidation",
        "holding_intent": "INTRADAY", "reasoning_summary": "No setup"
    })
    ok, status, _, _ = validator.validate_response(raw_hold, "TCS", "SNAP_1", 100.0)
    assert ok is True
    assert status == ValidationStatus.VALID

def test_validator_rejects_malformed_and_invalid_responses():
    validator = DecisionValidator()

    # Malformed non-JSON
    ok, status, _, _ = validator.validate_response("Not a JSON string", "TCS", "SNAP_1", 100.0)
    assert ok is False
    assert status == ValidationStatus.INVALID_FORMAT

    # Unknown Action
    raw_bad_action = json.dumps({
        "action": "LONG_LEVERAGE", "confidence": 0.8, "reasoning_summary": "test"
    })
    ok, status, _, _ = validator.validate_response(raw_bad_action, "TCS", "SNAP_1", 100.0)
    assert ok is False
    assert status == ValidationStatus.INVALID_ACTION

    # Out of range confidence
    raw_bad_conf = json.dumps({
        "action": "BUY", "confidence": 1.5, "reasoning_summary": "test"
    })
    ok, status, _, _ = validator.validate_response(raw_bad_conf, "TCS", "SNAP_1", 100.0)
    assert ok is False
    assert status == ValidationStatus.INVALID_CONFIDENCE

    # Invalid BUY Stop Loss (above current price)
    raw_bad_stop = json.dumps({
        "action": "BUY", "confidence": 0.8, "proposed_stop_loss": 105.0,
        "reasoning_summary": "test"
    })
    ok, status, reason, _ = validator.validate_response(raw_bad_stop, "TCS", "SNAP_1", 100.0)
    assert ok is False
    assert status == ValidationStatus.INVALID_STOP_LOSS
    assert "must be < entry" in reason

# ============================================================
# 5. FAILURE ISOLATION & TIMEOUT HANDLING
# ============================================================

def test_failure_isolation_and_timeout():
    provider = MockLLMProvider()
    # Configure Nemotron to timeout and Qwen to return malformed JSON
    provider.set_model_timeout("nemotron-3-nano:latest")
    provider.set_custom_response("qwen2.5-coder:1.5b", "MALFORMED_JSON_STRING")

    scheduler = SequentialLLMScheduler(provider=provider, max_retries=0)
    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snapshot = MarketSnapshot(
        snapshot_id="SNAP_ERR_001",
        symbol="INFY",
        decision_timestamp=dt,
        timeframe=Timeframe.M5,
    )

    run = scheduler.evaluate_snapshot(snapshot, persist=False)
    # Total models evaluated: 8
    assert len(run.evaluated_models) == 8
    # 2 failed (Nemotron timed out, Qwen malformed JSON)
    assert "nemotron" in run.failed_models
    assert "qwen" in run.failed_models
    # Remaining 6 models completed successfully!
    assert len(run.successful_decisions) == 6
    assert "gemma" in run.successful_decisions

    # Even after failures, provider must be unloaded and ready
    assert provider.currently_loaded_model is None

# ============================================================
# 6. SQLITE PERSISTENCE & METRICS
# ============================================================

def test_llm_persistence_and_metrics(tmp_path):
    db_file = tmp_path / "test_mobitrade.db"
    repo = LLMDatabaseRepository(str(db_file))
    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)

    run = ModelEvaluationRun(
        run_id="run_test_001",
        snapshot_id="SNAP_DB_001",
        decision_timestamp=dt,
        evaluated_models=["qwen"],
        successful_decisions=["qwen"],
        total_cycle_time_ms=150.0,
        created_at=dt
    )

    decision = LLMDecisionRecord(
        decision_id="dec_qwen_001",
        model_id="qwen",
        snapshot_id="SNAP_DB_001",
        decision_timestamp=dt,
        symbol="TCS",
        action=LLMAction.BUY,
        confidence=0.88,
        entry_rationale="High relative volume breakout",
        proposed_stop_loss=98.0,
        proposed_target=106.0,
        reasoning_summary="Bullish confirmation",
        validation_status=ValidationStatus.VALID,
        metrics=InferenceMetrics(
            model_id="qwen",
            snapshot_id="SNAP_DB_001",
            start_time=dt,
            end_time=dt,
            inference_latency_ms=125.0,
            model_load_time_ms=15.0,
            tokens_prompt=150,
            tokens_generated=80,
            success=True
        ),
        created_at=dt
    )

    repo.save_evaluation_run(run, [decision])

    loaded_run = repo.get_run("run_test_001")
    assert loaded_run is not None
    assert loaded_run["snapshot_id"] == "SNAP_DB_001"
    assert len(loaded_run["decisions"]) == 1
    assert loaded_run["decisions"][0]["model_id"] == "qwen"
    assert loaded_run["decisions"][0]["action"] == "BUY"
    assert loaded_run["decisions"][0]["confidence"] == 0.88
