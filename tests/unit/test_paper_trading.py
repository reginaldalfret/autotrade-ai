import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from mobitrade.domain.enums import Action, OrderSide, OrderType, OrderStatus, AccountState, ExitReason, RiskDecision
from mobitrade.domain.trading import OrderRequest, Order, Execution, Trade, TradeDecision
from mobitrade.domain.account import Account
from mobitrade.domain.models import Position, PortfolioSnapshot
from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.domain.data_models import Timeframe
from mobitrade.domain.llm_models import LLMDecisionRecord, LLMAction, ValidationStatus
from mobitrade.config.settings import CostConfig, RiskConfig
from mobitrade.risk.engine import RiskEngine
from mobitrade.execution.paper_broker import PaperBroker
from mobitrade.portfolio.manager import PortfolioManager
from mobitrade.paper.engine import PaperTradingEngine
from mobitrade.paper.persistence import PaperDatabaseRepository
from mobitrade.data.calendar import IST

# ============================================================
# 1. ACCOUNT INITIALIZATION & ISOLATION
# ============================================================

def test_eight_isolated_accounts_initialization(tmp_path):
    db_file = str(tmp_path / "mobitrade_test.db")
    engine = PaperTradingEngine(db_path=db_file, initial_balance_per_model=1000.0)
    
    assert len(engine.accounts) == 8
    expected_models = {"nemotron", "qwen", "gemma", "llama", "granite", "phi", "smollm", "falcon"}
    assert set(engine.accounts.keys()) == expected_models

    for mid, acc in engine.accounts.items():
        assert acc.starting_balance == 1000.0
        assert acc.cash == 1000.0
        assert acc.daily_target_equity == 1100.0 # +10%
        assert acc.daily_stop_equity == 950.0   # -5%
        assert acc.state == AccountState.READY

def test_account_isolation_multi_model(tmp_path):
    db_file = str(tmp_path / "mobitrade_test.db")
    engine = PaperTradingEngine(db_path=db_file)
    engine.start_session("session_iso_01", "2026-09-11")

    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snap = MarketSnapshot(snapshot_id="snap_01", symbol="TCS", decision_timestamp=now, timeframe=Timeframe.M5)

    # Model A (Nemotron) Buys TCS
    rec_a = LLMDecisionRecord(
        decision_id="dec_a", run_id="run_01", model_id="nemotron", model_version="1.0",
        prompt_version="1.0", snapshot_id="snap_01", decision_timestamp=now, symbol="TCS",
        action=LLMAction.BUY, confidence=0.85, entry_rationale="Bullish", proposed_stop_loss=950.0,
        proposed_target=1050.0, holding_intent="INTRADAY", reasoning_summary="Buy",
        validation_status=ValidationStatus.VALID, raw_output=""
    )
    trade_a = engine.process_model_decision(rec_a, snap, "session_iso_01", current_market_price=1000.0)
    assert trade_a is not None

    # Model A's cash should have decreased
    assert engine.portfolios["nemotron"].cash < 1000.0
    assert len(engine.portfolios["nemotron"].positions) == 1

    # Model B (Qwen) must remain completely untouched
    qwen_port = engine.portfolios["qwen"]
    assert qwen_port.cash == 1000.0
    assert qwen_port.total_equity == 1000.0
    assert len(qwen_port.positions) == 0
    assert engine.accounts["qwen"].state == AccountState.TRADING

# ============================================================
# 2. STATUTORY COSTS & SLIPPAGE
# ============================================================

def test_indian_equity_statutory_costs_and_slippage():
    costs = CostConfig(
        brokerage_pct=0.0003,
        brokerage_max_per_order=20.0,
        stt_pct=0.00025,
        exchange_txn_charge_pct=0.0000345,
        gst_pct=0.18,
        sebi_turnover_pct=0.000001,
        stamp_duty_pct=0.00003,
        slippage_pct=0.0005
    )
    broker = PaperBroker(costs)
    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)

    # BUY Order: Turnover = 100 * 10 = 1000.0
    req_buy = OrderRequest(model_id="qwen", symbol="INFY", side=OrderSide.BUY, quantity=10, price=100.0)
    order, exec_buy = broker.submit_order(req_buy, 100.0, now)

    # Fill price includes slippage (+0.05%)
    expected_buy_fill = 100.0 * 1.0005
    assert exec_buy.fill_price == pytest.approx(expected_buy_fill, rel=1e-4)

    # Buy fees include stamp duty (0.003%), brokerage, exchange txn, gst, sebi; STT = 0 on BUY
    turnover_buy = exec_buy.fill_price * 10
    brokerage_buy = min(turnover_buy * 0.0003, 20.0)
    txn_buy = turnover_buy * 0.0000345
    gst_buy = (brokerage_buy + txn_buy) * 0.18
    sebi_buy = turnover_buy * 0.000001
    stamp_buy = turnover_buy * 0.00003
    expected_buy_fee = brokerage_buy + txn_buy + gst_buy + sebi_buy + stamp_buy
    assert exec_buy.fee == pytest.approx(expected_buy_fee, rel=1e-4)

    # SELL Order: Closing position
    req_sell = OrderRequest(model_id="qwen", symbol="INFY", side=OrderSide.SELL, quantity=10, price=110.0)
    sell_order, exec_sell = broker.submit_order(req_sell, 110.0, now, exit_reason=ExitReason.TARGET)

    # Sell fill price includes slippage (-0.05%)
    expected_sell_fill = 110.0 * 0.9995
    assert exec_sell.fill_price == pytest.approx(expected_sell_fill, rel=1e-4)

    # Trade reconciliation
    closed_trade = list(broker.trades.values())[0]
    assert closed_trade.is_closed is True
    expected_gross = (exec_sell.fill_price - exec_buy.fill_price) * 10
    assert closed_trade.gross_pnl == pytest.approx(expected_gross, rel=1e-4)
    expected_net = expected_gross - closed_trade.total_fees - closed_trade.total_slippage
    assert closed_trade.net_pnl == pytest.approx(expected_net, rel=1e-4)
    assert closed_trade.exit_reason == ExitReason.TARGET

# ============================================================
# 3. DAILY TARGET & DAILY STOP LOSS SHUTDOWN
# ============================================================

def test_daily_target_shutdown_sequence(tmp_path):
    db_file = str(tmp_path / "mobitrade_test.db")
    engine = PaperTradingEngine(db_path=db_file)
    engine.start_session("session_target_01", "2026-09-11")

    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snap = MarketSnapshot(snapshot_id="s1", symbol="TATAMOTORS", decision_timestamp=now, timeframe=Timeframe.M5)

    rec = LLMDecisionRecord(
        decision_id="d1", run_id="r1", model_id="nemotron", model_version="1.0",
        prompt_version="1.0", snapshot_id="s1", decision_timestamp=now, symbol="TATAMOTORS",
        action=LLMAction.BUY, confidence=0.9, entry_rationale="Strong", proposed_stop_loss=480.0,
        proposed_target=600.0, holding_intent="INTRADAY", reasoning_summary="Buy",
        validation_status=ValidationStatus.VALID, raw_output=""
    )
    trade = engine.process_model_decision(rec, snap, "session_target_01", current_market_price=500.0)
    assert trade is not None

    # Simulating massive price surge hitting +10% target (Equity >= 1,100)
    surge_price = 600.0
    engine.update_market_prices({"TATAMOTORS": surge_price}, now + timedelta(minutes=30), "session_target_01")

    account = engine.accounts["nemotron"]
    assert account.target_reached is True
    assert account.state == AccountState.LOCKED
    assert len(engine.portfolios["nemotron"].positions) == 0 # Closed out

    # Attempting another BUY order should be rejected
    rec2 = LLMDecisionRecord(
        decision_id="d2", run_id="r1", model_id="nemotron", model_version="1.0",
        prompt_version="1.0", snapshot_id="s1", decision_timestamp=now + timedelta(hours=1), symbol="TATAMOTORS",
        action=LLMAction.BUY, confidence=0.9, entry_rationale="Try again", proposed_stop_loss=580.0,
        proposed_target=650.0, holding_intent="INTRADAY", reasoning_summary="Buy again",
        validation_status=ValidationStatus.VALID, raw_output=""
    )
    trade2 = engine.process_model_decision(rec2, snap, "session_target_01", current_market_price=600.0)
    assert trade2 is None

def test_daily_stop_loss_shutdown_sequence(tmp_path):
    db_file = str(tmp_path / "mobitrade_test.db")
    engine = PaperTradingEngine(db_path=db_file)
    engine.start_session("session_stop_01", "2026-09-11")

    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snap = MarketSnapshot(snapshot_id="s1", symbol="INFY", decision_timestamp=now, timeframe=Timeframe.M5)

    rec = LLMDecisionRecord(
        decision_id="d1", run_id="r1", model_id="qwen", model_version="1.0",
        prompt_version="1.0", snapshot_id="s1", decision_timestamp=now, symbol="INFY",
        action=LLMAction.BUY, confidence=0.9, entry_rationale="Strong", proposed_stop_loss=800.0,
        proposed_target=1100.0, holding_intent="INTRADAY", reasoning_summary="Buy",
        validation_status=ValidationStatus.VALID, raw_output=""
    )
    trade = engine.process_model_decision(rec, snap, "session_stop_01", current_market_price=1000.0)
    assert trade is not None

    # Simulating price drop breaching -5% stop (Equity <= 950)
    drop_price = 930.0
    engine.update_market_prices({"INFY": drop_price}, now + timedelta(minutes=30), "session_stop_01")

    account = engine.accounts["qwen"]
    assert account.daily_stop_triggered is True
    assert account.state == AccountState.LOCKED
    assert len(engine.portfolios["qwen"].positions) == 0

# ============================================================
# 4. TRADE LIMITS & ZERO-TRADE DAYS
# ============================================================

def test_max_20_trades_enforced():
    risk_cfg = RiskConfig(max_trades_per_session=20)
    risk_engine = RiskEngine(risk_cfg)
    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)

    account = Account(model_id="gemma", starting_balance=1000.0)
    account.start_session()

    # Create portfolio snapshot with 20 completed trades
    snap_20 = PortfolioSnapshot(
        model_id="gemma", session_id="s1", timestamp=now, starting_balance=1000.0,
        cash=1000.0, market_value=0.0, total_equity=1000.0, realized_pnl=0.0,
        unrealized_pnl=0.0, daily_pnl=0.0, completed_trades_count=20
    )

    decision = TradeDecision(
        symbol="TCS", action=Action.BUY, confidence=0.8, quantity=1,
        entry_price=100.0, stop_loss=95.0, target_price=110.0, reasoning="21st trade"
    )
    res = risk_engine.evaluate_decision(decision, snap_20, account, current_open_positions=0, timestamp=now)
    assert res.decision == RiskDecision.REJECTED
    assert res.rule_name == "MAX_TRADES_LIMIT"

def test_zero_trades_allowed(tmp_path):
    db_file = str(tmp_path / "mobitrade_test.db")
    engine = PaperTradingEngine(db_path=db_file)
    engine.start_session("session_zero_01", "2026-09-11")

    # All models propose HOLD
    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snap = MarketSnapshot(snapshot_id="s1", symbol="TCS", decision_timestamp=now, timeframe=Timeframe.M5)

    for mid in engine.accounts:
        rec = LLMDecisionRecord(
            decision_id=f"dec_{mid}", run_id="r1", model_id=mid, model_version="1.0",
            prompt_version="1.0", snapshot_id="s1", decision_timestamp=now, symbol="TCS",
            action=LLMAction.HOLD, confidence=0.5, entry_rationale="No edge",
            holding_intent="INTRADAY", reasoning_summary="Hold",
            validation_status=ValidationStatus.VALID, raw_output=""
        )
        trade = engine.process_model_decision(rec, snap, "session_zero_01", 1000.0)
        assert trade is None

    # End of day session closure
    leaderboard = engine.finalize_daily_session("session_zero_01", "2026-09-11")
    for row in leaderboard:
        assert row["trades_count"] == 0
        assert row["ending_balance"] == 1000.0
        assert row["net_pnl"] == 0.0

# ============================================================
# 5. INTRADAY SQUARE-OFF (15:15 IST) & NO OVERNIGHT
# ============================================================

def test_auto_square_off_at_1515(tmp_path):
    db_file = str(tmp_path / "mobitrade_test.db")
    engine = PaperTradingEngine(db_path=db_file)
    engine.start_session("session_sq_01", "2026-09-11")

    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snap = MarketSnapshot(snapshot_id="s1", symbol="TCS", decision_timestamp=now, timeframe=Timeframe.M5)

    rec = LLMDecisionRecord(
        decision_id="d1", run_id="r1", model_id="llama", model_version="1.0",
        prompt_version="1.0", snapshot_id="s1", decision_timestamp=now, symbol="TCS",
        action=LLMAction.BUY, confidence=0.85, entry_rationale="Buy", proposed_stop_loss=900.0,
        proposed_target=1200.0, holding_intent="INTRADAY", reasoning_summary="Buy",
        validation_status=ValidationStatus.VALID, raw_output=""
    )
    trade = engine.process_model_decision(rec, snap, "session_sq_01", 1000.0)
    assert trade is not None
    assert len(engine.portfolios["llama"].positions) == 1

    # At 15:15 IST, execute auto square-off
    dt_1515 = datetime(2026, 9, 11, 15, 15, tzinfo=IST)
    engine.execute_auto_square_off({"TCS": 1050.0}, dt_1515, "session_sq_01")

    assert len(engine.portfolios["llama"].positions) == 0 # Flat
    closed_trade = engine.session_trades["llama"][0]
    assert closed_trade.is_closed is True
    assert closed_trade.exit_reason == ExitReason.MARKET_CLOSE

    # Any new BUY at 15:16 IST must be rejected by RiskEngine
    dt_1516 = datetime(2026, 9, 11, 15, 16, tzinfo=IST)
    snap_late = MarketSnapshot(snapshot_id="s2", symbol="TCS", decision_timestamp=dt_1516, timeframe=Timeframe.M5)
    trade_late = engine.process_model_decision(rec, snap_late, "session_sq_01", 1050.0)
    assert trade_late is None

# ============================================================
# 6. DAILY COMPOUNDING (WINNING & LOSING SESSIONS)
# ============================================================

def test_daily_compounding_winning_day(tmp_path):
    db_file = str(tmp_path / "mobitrade_test.db")
    engine = PaperTradingEngine(db_path=db_file, initial_balance_per_model=1000.0)
    engine.start_session("day_1", "2026-09-11")

    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snap = MarketSnapshot(snapshot_id="s1", symbol="INFY", decision_timestamp=now, timeframe=Timeframe.M5)

    rec = LLMDecisionRecord(
        decision_id="d1", run_id="r1", model_id="nemotron", model_version="1.0",
        prompt_version="1.0", snapshot_id="s1", decision_timestamp=now, symbol="INFY",
        action=LLMAction.BUY, confidence=0.85, entry_rationale="Buy", proposed_stop_loss=900.0,
        proposed_target=1200.0, holding_intent="INTRADAY", reasoning_summary="Buy",
        validation_status=ValidationStatus.VALID, raw_output=""
    )
    engine.process_model_decision(rec, snap, "day_1", 1000.0)

    # Square off at ₹1,090 (Net win around ₹80)
    dt_1515 = datetime(2026, 9, 11, 15, 15, tzinfo=IST)
    engine.execute_auto_square_off({"INFY": 1090.0}, dt_1515, "day_1")
    engine.finalize_daily_session("day_1", "2026-09-11")

    day1_ending = engine.portfolios["nemotron"].starting_day_balance
    assert day1_ending > 1000.0

    # Day 2: Nemotron MUST start with Day 1 final equity
    engine.start_session("day_2", "2026-09-12")
    nemotron_acc = engine.accounts["nemotron"]
    assert nemotron_acc.starting_balance == day1_ending
    assert nemotron_acc.cash == day1_ending
    assert nemotron_acc.daily_target_equity == pytest.approx(day1_ending * 1.10, rel=1e-3)
    assert nemotron_acc.daily_stop_equity == pytest.approx(day1_ending * 0.95, rel=1e-3)

def test_daily_compounding_losing_day(tmp_path):
    db_file = str(tmp_path / "mobitrade_test.db")
    engine = PaperTradingEngine(db_path=db_file, initial_balance_per_model=1000.0)
    engine.start_session("day_1", "2026-09-11")

    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snap = MarketSnapshot(snapshot_id="s1", symbol="INFY", decision_timestamp=now, timeframe=Timeframe.M5)

    rec = LLMDecisionRecord(
        decision_id="d1", run_id="r1", model_id="granite", model_version="1.0",
        prompt_version="1.0", snapshot_id="s1", decision_timestamp=now, symbol="INFY",
        action=LLMAction.BUY, confidence=0.85, entry_rationale="Buy", proposed_stop_loss=900.0,
        proposed_target=1200.0, holding_intent="INTRADAY", reasoning_summary="Buy",
        validation_status=ValidationStatus.VALID, raw_output=""
    )
    engine.process_model_decision(rec, snap, "day_1", 1000.0)

    # Square off at ₹960 (Loss)
    dt_1515 = datetime(2026, 9, 11, 15, 15, tzinfo=IST)
    engine.execute_auto_square_off({"INFY": 960.0}, dt_1515, "day_1")
    engine.finalize_daily_session("day_1", "2026-09-11")

    day1_ending = engine.portfolios["granite"].starting_day_balance
    assert day1_ending < 1000.0

    # Day 2: Starting balance must reflect loss, with recalculated benchmarks
    engine.start_session("day_2", "2026-09-12")
    granite_acc = engine.accounts["granite"]
    assert granite_acc.starting_balance == day1_ending
    assert granite_acc.daily_target_equity == pytest.approx(day1_ending * 1.10, rel=1e-3)
    assert granite_acc.daily_stop_equity == pytest.approx(day1_ending * 0.95, rel=1e-3)

# ============================================================
# 7. TRAILING STOP DYNAMICS
# ============================================================

def test_trailing_stop_dynamic_exit(tmp_path):
    db_file = str(tmp_path / "mobitrade_test.db")
    engine = PaperTradingEngine(db_path=db_file, trailing_distance_pct=0.005) # 0.5%
    engine.start_session("session_trail_01", "2026-09-11")

    now = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    snap = MarketSnapshot(snapshot_id="s1", symbol="TCS", decision_timestamp=now, timeframe=Timeframe.M5)

    rec = LLMDecisionRecord(
        decision_id="d1", run_id="r1", model_id="falcon", model_version="1.0",
        prompt_version="1.0", snapshot_id="s1", decision_timestamp=now, symbol="TCS",
        action=LLMAction.BUY, confidence=0.85, entry_rationale="Buy", proposed_stop_loss=980.0,
        proposed_target=1100.0, holding_intent="INTRADAY", reasoning_summary="Buy",
        validation_status=ValidationStatus.VALID, raw_output=""
    )
    trade = engine.process_model_decision(rec, snap, "session_trail_01", 1000.0)
    assert trade is not None

    # 1. Price rises to ₹1,050.0 -> Trailing stop raises floor to 1,050 * 0.995 = 1,044.75
    engine.update_market_prices({"TCS": 1050.0}, now + timedelta(minutes=15), "session_trail_01")
    key = ("falcon", "TCS")
    assert engine.broker.open_trades[key].trailing_stop == pytest.approx(1050.0 * 0.995, rel=1e-3)

    # 2. Price falls to ₹1,040.0 (breaches trailing stop 1,044.75) -> Triggers exit
    engine.update_market_prices({"TCS": 1040.0}, now + timedelta(minutes=30), "session_trail_01")
    assert key not in engine.broker.open_trades # Position closed!
    closed_trade = engine.session_trades["falcon"][0]
    assert closed_trade.is_closed is True
    assert closed_trade.exit_reason == ExitReason.TRAILING_STOP
    assert closed_trade.net_pnl > 0 # Still locked in profit
