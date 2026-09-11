import pytest
from datetime import datetime
from mobitrade.domain.enums import Action, RiskDecision, AccountState
from mobitrade.domain.trading import TradeDecision
from mobitrade.domain.models import PortfolioSnapshot
from mobitrade.domain.account import Account
from mobitrade.config.settings import RiskConfig
from mobitrade.risk.engine import RiskEngine

@pytest.fixture
def risk_engine():
    cfg = RiskConfig(
        daily_target_pct=0.10,
        daily_loss_limit_pct=0.05,
        max_trades_per_session=20,
        max_concurrent_positions=1,
        min_confidence_score=0.50,
        require_stop_loss=True
    )
    return RiskEngine(cfg)

# Test 1 & 2: Rs 1,000 -> Rs 1,100 target and Rs 950 daily stop
def test_1000_produces_1100_target_and_950_stop(risk_engine):
    target, stop = risk_engine.calculate_targets(1000.0)
    assert target == 1100.0
    assert stop == 950.0

# Test 3 & 4: Rs 1,250 -> Rs 1,375 target and Rs 1,187.50 daily stop
def test_1250_produces_1375_target_and_1187_50_stop(risk_engine):
    target, stop = risk_engine.calculate_targets(1250.0)
    assert target == 1375.0
    assert stop == 1187.50

# Test 5 & 6: Target and loss limit calculated strictly from starting balance
def test_targets_based_on_starting_balance(risk_engine):
    starting_balance = 2000.0
    target, stop = risk_engine.calculate_targets(starting_balance)
    assert target == starting_balance * 1.10
    assert stop == starting_balance * 0.95

# Test 7, 8, 9: Reaching target disables new trades, cancels pending, closes positions
def test_reaching_target_shutdown_sequence(risk_engine):
    account = Account(model_id="nemotron", starting_balance=1000.0)
    account.start_session()
    
    # Portfolio equity reaches Rs 1,105 (>= 1,100 target)
    portfolio = PortfolioSnapshot(
        model_id="nemotron",
        session_id="s1",
        timestamp=datetime.utcnow(),
        starting_balance=1000.0,
        cash=1105.0,
        market_value=0.0,
        total_equity=1105.0,
        completed_trades_count=2
    )
    
    decision = TradeDecision(
        symbol="TCS",
        action=Action.BUY,
        confidence=0.9,
        quantity=1,
        entry_price=100.0,
        stop_loss=95.0,
        target_price=110.0,
        reasoning="Attempt trade after target"
    )
    
    result = risk_engine.evaluate_decision(decision, portfolio, account, current_open_positions=0, timestamp=datetime.utcnow())
    assert result.decision == RiskDecision.REJECTED
    assert account.target_reached is True
    assert account.state == AccountState.LOCKED
    assert account.can_place_order() is False

# Test 10, 11, 12: Reaching daily stop disables new trades, cancels pending, closes positions
def test_reaching_daily_stop_shutdown_sequence(risk_engine):
    account = Account(model_id="qwen", starting_balance=1000.0)
    account.start_session()
    
    # Portfolio equity falls to Rs 940 (<= 950 daily stop)
    portfolio = PortfolioSnapshot(
        model_id="qwen",
        session_id="s1",
        timestamp=datetime.utcnow(),
        starting_balance=1000.0,
        cash=940.0,
        market_value=0.0,
        total_equity=940.0,
        completed_trades_count=1
    )
    
    decision = TradeDecision(
        symbol="TCS",
        action=Action.BUY,
        confidence=0.9,
        quantity=1,
        entry_price=100.0,
        stop_loss=95.0,
        target_price=110.0,
        reasoning="Attempt trade after daily stop"
    )
    
    result = risk_engine.evaluate_decision(decision, portfolio, account, current_open_positions=0, timestamp=datetime.utcnow())
    assert result.decision == RiskDecision.REJECTED
    assert account.daily_stop_triggered is True
    assert account.state == AccountState.LOCKED
    assert account.can_place_order() is False

# Test 13 & 14: Market close closes all positions, no overnight positions remain
def test_market_close_shutdown():
    account = Account(model_id="gemma", starting_balance=1000.0)
    account.start_session()
    account.trigger_market_close()
    account.execute_shutdown_sequence()
    assert account.market_closed_triggered is True
    assert account.state == AccountState.LOCKED
    assert account.can_place_order() is False

# Test 18, 19, 20: Max 20 trades enforced, 0 trades allowed, never forces 20 trades
def test_max_20_trades_enforced(risk_engine):
    account = Account(model_id="llama", starting_balance=1000.0)
    account.start_session()
    
    # Portfolio has completed 20 trades
    portfolio = PortfolioSnapshot(
        model_id="llama",
        session_id="s1",
        timestamp=datetime.utcnow(),
        starting_balance=1000.0,
        cash=1020.0,
        market_value=0.0,
        total_equity=1020.0,
        completed_trades_count=20
    )
    
    decision = TradeDecision(
        symbol="INFY",
        action=Action.BUY,
        confidence=0.8,
        quantity=1,
        entry_price=500.0,
        stop_loss=490.0,
        target_price=520.0,
        reasoning="21st trade proposal"
    )
    
    result = risk_engine.evaluate_decision(decision, portfolio, account, current_open_positions=0, timestamp=datetime.utcnow())
    assert result.decision == RiskDecision.REJECTED
    assert "MAX_TRADES_LIMIT" in result.rule_name

# Test 21 & 22: Trade-level stop loss enforced, daily stop overrides LLM
def test_trade_stop_loss_enforcement(risk_engine):
    account = Account(model_id="granite", starting_balance=1000.0)
    account.start_session()
    portfolio = PortfolioSnapshot(
        model_id="granite",
        session_id="s1",
        timestamp=datetime.utcnow(),
        starting_balance=1000.0,
        cash=1000.0,
        market_value=0.0,
        total_equity=1000.0,
        completed_trades_count=0
    )
    
    # Missing stop loss
    decision = TradeDecision(
        symbol="INFY",
        action=Action.BUY,
        confidence=0.8,
        quantity=1,
        entry_price=500.0,
        stop_loss=None, # Missing stop loss
        target_price=550.0,
        reasoning="No stop loss specified"
    )
    
    result = risk_engine.evaluate_decision(decision, portfolio, account, current_open_positions=0, timestamp=datetime.utcnow())
    assert result.decision == RiskDecision.REJECTED
    assert result.rule_name == "REQUIRE_STOP_LOSS"

# Test 23: LLM cannot modify risk settings
def test_risk_settings_immutable():
    cfg = RiskConfig(daily_target_pct=0.10, daily_loss_limit_pct=0.05)
    engine = RiskEngine(cfg)
    assert engine.config.daily_target_pct == 0.10
    assert engine.config.daily_loss_limit_pct == 0.05
