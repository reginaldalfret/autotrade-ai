import pytest
from datetime import datetime
from mobitrade.domain.enums import OrderSide, OrderStatus
from mobitrade.domain.trading import OrderRequest
from mobitrade.config.settings import CostConfig
from mobitrade.execution.paper_broker import PaperBroker

def test_paper_broker_buy_and_sell_lifecycle():
    cfg = CostConfig(brokerage_pct=0.0003, slippage_pct=0.0005)
    broker = PaperBroker(cfg)
    now = datetime.utcnow()
    
    # 1. Submit BUY order
    buy_req = OrderRequest(
        model_id="nemotron",
        symbol="TCS",
        side=OrderSide.BUY,
        quantity=1,
        price=3000.0,
        stop_loss=2950.0,
        target_price=3100.0
    )
    order, exec_buy = broker.submit_order(buy_req, current_market_price=3000.0, timestamp=now)
    assert order.status == OrderStatus.FILLED
    assert exec_buy.fill_price == 3000.0 * 1.0005 # with slippage
    assert exec_buy.fee > 0.0
    assert "TCS" in broker.open_trades
    
    # 2. Submit matching SELL order
    sell_req = OrderRequest(
        model_id="nemotron",
        symbol="TCS",
        side=OrderSide.SELL,
        quantity=1,
        price=3100.0
    )
    sell_order, exec_sell = broker.submit_order(sell_req, current_market_price=3100.0, timestamp=now)
    assert sell_order.status == OrderStatus.FILLED
    assert exec_sell.fill_price == 3100.0 * 0.9995 # with slippage
    assert "TCS" not in broker.open_trades
    
    # Verify trade reconciliation
    closed_trade = list(broker.trades.values())[0]
    assert closed_trade.is_closed is True
    assert closed_trade.gross_pnl > 0
    assert closed_trade.net_pnl == closed_trade.gross_pnl - closed_trade.total_fees - closed_trade.total_slippage
