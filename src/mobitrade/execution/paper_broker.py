import uuid
from datetime import datetime
from typing import Dict, List, Optional
from mobitrade.domain.enums import OrderSide, OrderStatus, OrderType
from mobitrade.domain.trading import OrderRequest, Order, Execution, Trade
from mobitrade.domain.models import Position
from mobitrade.config.settings import CostConfig

class PaperBroker:
    """
    Local simulation broker. Never connects to a live exchange.
    Simulates fills with realistic execution models including slippage and statutory transaction costs.
    """
    def __init__(self, cost_config: CostConfig):
        self.cost_config = cost_config
        self.orders: Dict[str, Order] = {}
        self.executions: Dict[str, Execution] = {}
        self.trades: Dict[str, Trade] = {}
        self.open_trades: Dict[str, Trade] = {} # Keyed by symbol

    def _calculate_costs(self, price: float, quantity: int, side: OrderSide) -> tuple[float, float]:
        turnover = price * quantity
        # 1. Slippage simulation (price penalty)
        slippage_cost = turnover * self.cost_config.slippage_pct

        # 2. Brokerage + Regulatory charges (SEBI, STT, GST, Stamp Duty, Exchange Txn)
        brokerage = min(turnover * self.cost_config.brokerage_pct, self.cost_config.brokerage_max_per_order)
        exchange_charges = turnover * self.cost_config.exchange_txn_charge_pct
        gst = (brokerage + exchange_charges) * self.cost_config.gst_pct
        sebi_charges = turnover * self.cost_config.sebi_turnover_pct
        
        stt = (turnover * self.cost_config.stt_pct) if side == OrderSide.SELL else 0.0
        stamp_duty = (turnover * self.cost_config.stamp_duty_pct) if side == OrderSide.BUY else 0.0

        total_regulatory_fees = brokerage + exchange_charges + gst + sebi_charges + stt + stamp_duty
        return total_regulatory_fees, slippage_cost

    def submit_order(self, request: OrderRequest, current_market_price: float, timestamp: datetime) -> tuple[Order, Execution]:
        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        exec_id = f"exec_{uuid.uuid4().hex[:8]}"

        order = Order(
            order_id=order_id,
            model_id=request.model_id,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=current_market_price,
            stop_loss=request.stop_loss,
            target_price=request.target_price,
            status=OrderStatus.FILLED,
            created_at=timestamp,
            updated_at=timestamp
        )
        self.orders[order_id] = order

        # Realistic fill price incorporating slippage
        fill_price = current_market_price * (1.0 + self.cost_config.slippage_pct) if request.side == OrderSide.BUY \
                     else current_market_price * (1.0 - self.cost_config.slippage_pct)

        fee, slippage = self._calculate_costs(fill_price, request.quantity, request.side)

        execution = Execution(
            execution_id=exec_id,
            order_id=order_id,
            model_id=request.model_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            fill_price=fill_price,
            fee=fee,
            slippage=slippage,
            executed_at=timestamp
        )
        self.executions[exec_id] = execution

        # Manage Trade lifecycle (Entry -> Exit)
        if request.side == OrderSide.BUY:
            trade_id = f"trd_{uuid.uuid4().hex[:8]}"
            trade = Trade(
                trade_id=trade_id,
                model_id=request.model_id,
                symbol=request.symbol,
                entry_execution_id=exec_id,
                quantity=request.quantity,
                entry_price=fill_price,
                entry_time=timestamp,
                total_fees=fee,
                total_slippage=slippage,
                is_closed=False
            )
            self.trades[trade_id] = trade
            self.open_trades[request.symbol] = trade

        elif request.side == OrderSide.SELL and request.symbol in self.open_trades:
            trade = self.open_trades.pop(request.symbol)
            trade.exit_execution_id = exec_id
            trade.exit_price = fill_price
            trade.exit_time = timestamp
            trade.total_fees += fee
            trade.total_slippage += slippage
            trade.gross_pnl = (fill_price - trade.entry_price) * request.quantity
            trade.net_pnl = trade.gross_pnl - trade.total_fees - trade.total_slippage
            trade.is_closed = True

        return order, execution

    def cancel_all_pending(self, model_id: str):
        for o in self.orders.values():
            if o.model_id == model_id and o.status == OrderStatus.PENDING:
                o.status = OrderStatus.CANCELLED
