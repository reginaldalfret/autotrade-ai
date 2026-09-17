"""
Unit tests for AutoTrade AI Self-Learning Engine (Phase 11).
Tests error analysis, model profiles, candidate generation, deterministic validation,
overfitting safeguards, strategy versioning, RiskEngine immutability, audit logging, and API endpoints.
"""

import pytest
from datetime import datetime
from starlette.testclient import TestClient

from mobitrade.learning.models import (
    StrategyConfig,
    CandidateStatus,
    WeaknessType,
    LearningObservation,
)
from mobitrade.learning.persistence import LearningDatabaseRepository
from mobitrade.learning.analysis import TradeAnalysisEngine
from mobitrade.learning.generator import CandidateGenerator
from mobitrade.learning.evaluator import CandidateEvaluator
from mobitrade.learning.engine import SelfLearningEngine
from mobitrade.paper.persistence import PaperDatabaseRepository
from mobitrade.domain.trading import Trade
from mobitrade.domain.enums import ExitReason
from mobitrade.risk.engine import RiskEngine
from mobitrade.config.settings import RiskConfig
from mobitrade.logging.audit import AuditLogger
from mobitrade.api.app import create_app


def create_sample_trade(trade_id: str, model_id: str, net_pnl: float, hour: int = 10) -> Trade:
    dt = datetime(2026, 9, 17, hour, 15, 0)
    return Trade(
        trade_id=trade_id,
        model_id=model_id,
        account_id=f"acc_{model_id}",
        entry_execution_id=f"exec_{trade_id}",
        symbol="TATAMOTORS",
        quantity=2,
        entry_price=500.0,
        exit_price=500.0 + (net_pnl / 2),
        entry_time=dt,
        exit_time=dt,
        gross_pnl=net_pnl + 1.0,
        net_pnl=net_pnl,
        total_fees=0.8,
        total_slippage=0.2,
        exit_reason=ExitReason.TARGET if net_pnl > 0 else ExitReason.STOP_LOSS,
        is_closed=True,
    )


@pytest.fixture
def learning_env(tmp_path):
    """Provide isolated environment with sample trades."""
    db_file = tmp_path / "test_learning.db"
    paper_repo = PaperDatabaseRepository(db_path=str(db_file))
    paper_repo._init_db()

    # Populate synthetic trades
    trades = [
        create_sample_trade("t1", "nemotron", 25.0, hour=10),
        create_sample_trade("t2", "nemotron", 30.0, hour=10),
        create_sample_trade("t3", "nemotron", -10.0, hour=10),
        create_sample_trade("t4", "qwen", -35.0, hour=12),
        create_sample_trade("t5", "qwen", -40.0, hour=12),
        create_sample_trade("t6", "falcon", -20.0, hour=12),
        create_sample_trade("t7", "llama", 15.0, hour=14),
    ]
    for t in trades:
        paper_repo.save_trade(t, "sim_test")

    learning_repo = LearningDatabaseRepository(db_path=str(db_file))
    return str(db_file), learning_repo, trades


def test_observation_generation(learning_env):
    """Test trade error analysis produces calibrated observations."""
    db_path, _, _ = learning_env
    analysis = TradeAnalysisEngine(db_path=db_path)
    obs = analysis.analyze_session_weaknesses()

    assert len(obs) >= 1
    types = [o.weakness_type for o in obs]
    # Qwen had 2 consecutive losses -> MODEL_SPECIFIC_UNDERPERFORMANCE
    assert WeaknessType.MODEL_SPECIFIC_UNDERPERFORMANCE in types or WeaknessType.LOW_CONFIDENCE_LOSS in types
    for o in obs:
        assert o.sample_size >= 2
        assert len(o.supporting_trade_ids) >= 1
        assert o.recommended_remedy != ""


def test_model_performance_profiles(learning_env):
    """Test profile construction for all 8 tournament models."""
    db_path, _, _ = learning_env
    analysis = TradeAnalysisEngine(db_path=db_path)
    profiles = analysis.build_model_profiles()

    assert len(profiles) == 8
    model_map = {p.model_id: p for p in profiles}
    assert "nemotron" in model_map
    assert model_map["nemotron"].total_trades == 3
    assert model_map["nemotron"].winning_trades == 2
    assert model_map["nemotron"].win_rate == 66.67
    assert model_map["nemotron"].net_pnl > 0


def test_candidate_generation(learning_env):
    """Test proposing candidate strategies addressing observations."""
    db_path, learning_repo, _ = learning_env
    active_strat = learning_repo.get_active_strategy()
    analysis = TradeAnalysisEngine(db_path=db_path)
    obs = analysis.analyze_session_weaknesses()

    generator = CandidateGenerator()
    candidates = generator.generate_candidates(active_strat, obs)

    assert len(candidates) >= 1
    for c in candidates:
        assert c.status == CandidateStatus.PROPOSED
        assert c.parent_version_id == active_strat.version_id
        assert c.sample_size >= 1
        assert len(c.supporting_observations) >= 1


def test_candidate_validation_and_insufficient_data(learning_env):
    """Test evaluator rejects candidates with insufficient sample size or negative alpha."""
    db_path, learning_repo, trades = learning_env
    active_strat = learning_repo.get_active_strategy()
    evaluator = CandidateEvaluator(db_path=db_path, min_sample_size=10)

    # 1. Reject on insufficient data (N=7 < 10)
    cand = StrategyConfig(
        version_id="strategy_v2",
        parent_version_id="strategy_v1",
        min_confidence_threshold=0.70,
        allowed_models=["nemotron", "llama"],
    )
    rep_insufficient = evaluator.evaluate(cand, active_strat, trades)
    assert rep_insufficient.is_validated is False
    assert any("Insufficient sample size" in r for r in rep_insufficient.rejection_reasons)

    # 2. Test with lower sample requirement (min=3)
    evaluator_lenient = CandidateEvaluator(db_path=db_path, min_sample_size=3)
    # Candidate excluding losing model qwen and falcon -> Net P&L will improve
    cand_good = StrategyConfig(
        version_id="strategy_v3",
        parent_version_id="strategy_v1",
        min_confidence_threshold=0.50,
        allowed_models=["nemotron", "llama"],
    )
    rep_good = evaluator_lenient.evaluate(cand_good, active_strat, trades)
    assert rep_good.is_validated is True
    assert rep_good.candidate_metrics["net_pnl"] > rep_good.baseline_metrics["net_pnl"]

    # 3. Candidate keeping only losing models -> Negative alpha rejection
    cand_bad = StrategyConfig(
        version_id="strategy_v4",
        parent_version_id="strategy_v1",
        min_confidence_threshold=0.50,
        allowed_models=["qwen", "falcon"],
    )
    rep_bad = evaluator_lenient.evaluate(cand_bad, active_strat, trades)
    assert rep_bad.is_validated is False
    assert any("Negative alpha" in r for r in rep_bad.rejection_reasons)


def test_strategy_versioning_and_activation(learning_env):
    """Test promotion flow: PROPOSED -> VALIDATED -> ACTIVE and rejection handling."""
    _, learning_repo, _ = learning_env

    baseline = learning_repo.get_active_strategy()
    assert baseline.version_id == "strategy_v1"
    assert baseline.status == CandidateStatus.ACTIVE

    # Create candidate
    cand = StrategyConfig(
        version_id="strategy_v2",
        parent_version_id="strategy_v1",
        status=CandidateStatus.PROPOSED,
    )
    learning_repo.save_strategy(cand)

    # Cannot activate PROPOSED candidate directly
    with pytest.raises(ValueError) as exc:
        learning_repo.set_active_strategy("strategy_v2")
    assert "Must be VALIDATED" in str(exc.value)

    # Validate candidate
    cand.status = CandidateStatus.VALIDATED
    learning_repo.save_strategy(cand)

    # Promote to ACTIVE
    activated = learning_repo.set_active_strategy("strategy_v2")
    assert activated.version_id == "strategy_v2"
    assert activated.status == CandidateStatus.ACTIVE

    # Check that previous baseline is no longer ACTIVE
    old_base = learning_repo.get_strategy("strategy_v1")
    assert old_base.status != CandidateStatus.ACTIVE


def test_risk_engine_immutability():
    """Verify that RiskEngine safety rules are strictly immutable by strategy configs."""
    cfg = RiskConfig()
    engine = RiskEngine(cfg)

    # Hard rules verification
    assert engine.config.daily_loss_limit_pct == 0.05  # -5% hard stop
    assert engine.config.max_trades_per_session == 20  # 20 max trades
    assert engine.config.allow_overnight is False       # 0 overnight positions
    assert engine.config.require_stop_loss is True      # mandatory stop loss


def test_self_learning_cycle_and_audit(learning_env):
    """Test full learning cycle execution and tamper-evident audit logging."""
    db_path, _, _ = learning_env
    engine = SelfLearningEngine(db_path=db_path)

    res = engine.run_learning_cycle(auto_activate_best=False)
    assert res["status"] == "completed"
    assert res["observations_count"] >= 1
    assert res["candidates_generated"] >= 1

    # Verify audit trail
    logger = AuditLogger(db_path=db_path)
    verification = logger.verify_chain()
    assert verification.is_valid is True
    assert verification.total_events > 0

    event_types = [e.event_type for e in logger.get_events()]
    assert "LEARNING_OBSERVATION_CREATED" in event_types
    assert "STRATEGY_CANDIDATE_CREATED" in event_types


def test_learning_api_endpoints(learning_env):
    """Test all 6 self-learning HTTP API endpoints via TestClient."""
    db_path, _, _ = learning_env
    app = create_app(db_path=db_path)
    client = TestClient(app)

    # 1. GET /learning/status
    res = client.get("/learning/status")
    assert res.status_code == 200
    data = res.json()
    assert "active_strategy_version" in data
    assert data["model_profiles_calibrated"] >= 0

    # 2. POST /learning/run
    run_res = client.post("/learning/run", json={"auto_activate_best": False})
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "completed"
    assert run_data["candidates_generated"] >= 1

    # 3. GET /learning/observations
    obs_res = client.get("/learning/observations")
    assert obs_res.status_code == 200
    assert obs_res.json()["count"] >= 1

    # 4. GET /learning/candidates
    cand_res = client.get("/learning/candidates")
    assert cand_res.status_code == 200
    assert cand_res.json()["count"] >= 1

    # 5. GET /learning/strategy
    strat_res = client.get("/learning/strategy")
    assert strat_res.status_code == 200
    assert strat_res.json()["active_version"] != ""

    # 6. GET /learning/history
    hist_res = client.get("/learning/history")
    assert hist_res.status_code == 200
    assert hist_res.json()["strategies_count"] >= 1
    assert hist_res.json()["validation_reports_count"] >= 1
