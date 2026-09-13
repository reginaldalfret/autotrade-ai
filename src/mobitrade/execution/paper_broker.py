import uuid
from datetime import datetime
from typing import Dict, List, Optional
from mobitrade.domain.enums import OrderSide, OrderStatus, OrderType, ExitReason
from mobitrade.domain.trading import OrderRequest, Order, Execution, Trade
from mobitrade.domain.models import Position
from mobitrade.config.settings import CostConfig

class PaperBroker:
    """
    Local simulation broker. Never connects to a live exchange.
    Simulates fills with realistic execution models including slippage and statutory transaction costs.
    Enforces per-model account isolation.
    """
    def __init__(self, cost_config: CostConfig):
        self.cost_config = cost_config
        self.orders: Dict[str, Order] = {}
        self.executions: Dict[str, Execution] = {}
        self.trades: Dict[str, Trade] = {}
        # Keyed by (model_id, symbol) to guarantee account isolation across multiple models
        self.open_trades: Dict[tuple, Trade] = {}
        self.peak_prices: Dict[tuple, float] = {}

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

    def submit_order(
        self,
        request: OrderRequest,
        current_market_price: float,
        timestamp: datetime,
        exit_reason: Optional[ExitReason] = None
    ) -> tuple[Order, Execution]:
        order_id = f"ord_{uuid.uuid4().hex[:8]}"
        exec_id = f"exec_{uuid.uuid4().hex[:8]}"

        order = Order(
            order_id=order_id,
            model_id=request.model_id,
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=current_market_price,
            stop_loss=request.stop_loss,
            target_price=request.target_price,
            status=OrderStatus.FILLED,
            created_at=timestamp,
            updated_at=timestamp,
            snapshot_id=request.snapshot_id,
            decision_id=request.decision_id
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
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            fill_price=fill_price,
            fee=fee,
            slippage=slippage,
            executed_at=timestamp
        )
        self.executions[exec_id] = execution

        key = (request.model_id, request.symbol)

        # Manage Trade lifecycle (Entry -> Exit)
        if request.side == OrderSide.BUY:
            trade_id = f"trd_{uuid.uuid4().hex[:8]}"
            trade = Trade(
                trade_id=trade_id,
                model_id=request.model_id,
                account_id=request.account_id,
                symbol=request.symbol,
                exchange="NSE",
                entry_execution_id=exec_id,
                quantity=request.quantity,
                entry_price=fill_price,
                entry_time=timestamp,
                initial_stop=request.stop_loss,
                trailing_stop=request.stop_loss,
                total_fees=fee,
                total_slippage=slippage,
                snapshot_id=request.snapshot_id,
                decision_id=request.decision_id,
                is_closed=False
            )
            self.trades[trade_id] = trade
            self.open_trades[key] = trade
            # Backward compatibility alias for single-key access in existing test
            self.open_trades[request.symbol] = trade
            self.peak_prices[key] = fill_price

        elif request.side == OrderSide.SELL and (key in self.open_trades or request.symbol in self.open_trades):
            trade = self.open_trades.pop(key, None) or self.open_trades.pop(request.symbol, None)
            if key in self.open_trades:
                self.open_trades.pop(key, None)
            if request.symbol in self.open_trades:
                self.open_trades.pop(request.symbol, None)

            trade.exit_execution_id = exec_id
            trade.exit_price = fill_price
            trade.exit_time = timestamp
            trade.total_fees += fee
            trade.total_slippage += slippage
            trade.gross_pnl = (fill_price - trade.entry_price) * request.quantity
            trade.net_pnl = trade.gross_pnl - trade.total_fees - trade.total_slippage
            trade.exit_reason = exit_reason or ExitReason.TARGET
            trade.is_closed = True
            self.peak_prices.pop(key, None)

        return order, execution

    def close_all_positions(self, model_id: str, current_prices: Dict[str, float], timestamp: datetime, exit_reason: ExitReason) -> List[Trade]:
        """
        Force closes all open positions for a model (e.g. for target shutdown, stop loss, or 15:15 square-off).
        """
        closed_trades = []
        # Find all open trades for this model
        target_symbols = [
            k[1] for k in list(self.open_trades.keys())
            if isinstance(k, tuple) and len(k) == 2 and k[0] == model_id
        ]
        for sym in target_symbols:
            key = (model_id, sym)
            trade = self.open_trades.get(key)
            if not trade or trade.is_closed:
                continue
            price = current_prices.get(sym, trade.entry_price)
            sell_req = OrderRequest(
                model_id=model_id,
                account_id=trade.account_id,
                symbol=sym,
                side=OrderSide.SELL,
                quantity=trade.quantity,
                price=price,
                snapshot_id=trade.snapshot_id,
                decision_id=trade.decision_id
            )
            self.submit_order(sell_req, price, timestamp, exit_reason=exit_reason)
            closed_trades.append(trade)
        return closed_trades

    def cancel_all_pending(self, model_id: str):
        for o in self.orders.values():
            if o.model_id == model_id and o.status == OrderStatus.PENDING:
                o.status = OrderStatus.CANCELLED
