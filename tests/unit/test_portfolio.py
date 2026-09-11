import pytest
from datetime import datetime
from mobitrade.domain.enums import OrderSide
from mobitrade.domain.trading import Execution
from mobitrade.portfolio.manager import PortfolioManager

# Test 15 & 16: Compounding - winning day and losing day compound correctly
def test_compounding_winning_and_losing_day():
    pm = PortfolioManager(model_id="qwen", starting_balance=1000.0)
    now = datetime.utcnow()
    
    # Day 1: Winning trade (Rs 1,000 -> Rs 1,075)
    exec_buy = Execution(
        execution_id="e1", order_id="o1", model_id="qwen", symbol="TCS",
        side=OrderSide.BUY, quantity=1, fill_price=1000.0, fee=5.0, slippage=0.0, executed_at=now
    )
    pm.update_with_execution(exec_buy)
    
    exec_sell = Execution(
        execution_id="e2", order_id="o2", model_id="qwen", symbol="TCS",
        side=OrderSide.SELL, quantity=1, fill_price=1085.0, fee=5.0, slippage=0.0, executed_at=now
    )
    pm.update_with_execution(exec_sell)
    
    assert pm.total_equity == 1075.0
    day2_starting = pm.compound_to_next_session()
    assert day2_starting == 1075.0
    assert pm.starting_day_balance == 1075.0
    
    # Day 2: Losing trade (Rs 1,075 -> Rs 960)
    exec_buy2 = Execution(
        execution_id="e3", order_id="o3", model_id="qwen", symbol="INFY",
        side=OrderSide.BUY, quantity=1, fill_price=1000.0, fee=5.0, slippage=0.0, executed_at=now
    )
    pm.update_with_execution(exec_buy2)
    
    exec_sell2 = Execution(
        execution_id="e4", order_id="o4", model_id="qwen", symbol="INFY",
        side=OrderSide.SELL, quantity=1, fill_price=895.0, fee=5.0, slippage=0.0, executed_at=now
    )
    pm.update_with_execution(exec_sell2)
    
    assert pm.total_equity == 960.0
    day3_starting = pm.compound_to_next_session()
    assert day3_starting == 960.0
    assert pm.starting_day_balance == 960.0

# Test 17: Multi-model account isolation (Model A cannot affect Model B)
def test_model_account_isolation():
    model_a = PortfolioManager(model_id="nemotron", starting_balance=1000.0)
    model_b = PortfolioManager(model_id="qwen", starting_balance=1000.0)
    now = datetime.utcnow()
    
    exec_a = Execution(
        execution_id="ea1", order_id="oa1", model_id="nemotron", symbol="RELIANCE",
        side=OrderSide.BUY, quantity=1, fill_price=500.0, fee=2.0, slippage=0.0, executed_at=now
    )
    model_a.update_with_execution(exec_a)
    
    assert model_a.cash == 498.0
    assert model_a.market_value == 500.0
    assert model_a.total_equity == 998.0
    
    # Model B must remain completely untouched
    assert model_b.cash == 1000.0
    assert model_b.market_value == 0.0
    assert model_b.total_equity == 1000.0
    assert len(model_b.positions) == 0
