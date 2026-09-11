import pytest
from datetime import datetime
from mobitrade.domain.enums import Action, OrderSide, OrderType, OrderStatus, AccountState, RiskDecision
from mobitrade.domain.models import MarketTick, OHLCVCandle, MarketSnapshot, TechnicalFeatures, Position, PortfolioSnapshot
from mobitrade.domain.trading import TradeDecision, OrderRequest, Order, Execution, Trade
from mobitrade.domain.account import Account

def test_trade_decision_validation_success():
    decision = TradeDecision(
        symbol="TCS",
        action=Action.BUY,
        confidence=0.85,
        quantity=2,
        entry_price=3500.0,
        stop_loss=3450.0,
        target_price=3600.0,
        reasoning="Bullish RSI divergence + strong volume breakout"
    )
    assert decision.symbol == "TCS"
    assert decision.quantity == 2
    assert decision.stop_loss == 3450.0

def test_trade_decision_invalid_quantity():
    with pytest.raises(ValueError):
        TradeDecision(
            symbol="INFY",
            action=Action.BUY,
            confidence=0.80,
            quantity=0, # Invalid for BUY
            entry_price=1400.0,
            stop_loss=1380.0,
            target_price=1450.0,
            reasoning="Testing invalid quantity"
        )

def test_trade_decision_invalid_stop_loss():
    with pytest.raises(ValueError):
        TradeDecision(
            symbol="INFY",
            action=Action.BUY,
            confidence=0.80,
            quantity=1,
            entry_price=1400.0,
            stop_loss=1450.0, # Stop loss cannot be above entry for BUY
            target_price=1500.0,
            reasoning="Testing invalid stop loss"
        )

def test_trade_decision_invalid_target():
    with pytest.raises(ValueError):
        TradeDecision(
            symbol="INFY",
            action=Action.BUY,
            confidence=0.80,
            quantity=1,
            entry_price=1400.0,
            stop_loss=1350.0,
            target_price=1380.0, # Target cannot be below entry for BUY
            reasoning="Testing invalid target"
        )

def test_position_market_value_and_pnl():
    pos = Position(
        symbol="RELIANCE",
        quantity=10,
        average_entry_price=2500.0,
        current_price=2550.0
    )
    assert pos.market_value == 25500.0
