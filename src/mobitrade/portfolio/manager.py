from datetime import datetime
from typing import Dict, List, Optional
from mobitrade.domain.models import Position, PortfolioSnapshot
from mobitrade.domain.trading import Execution
from mobitrade.domain.enums import OrderSide

class PortfolioManager:
    """
    Tracks completely isolated per-model portfolios.
    Enforces daily compounding of capital across trading sessions.
    """
    def __init__(self, model_id: str, starting_balance: float):
        self.model_id = model_id
        self.starting_day_balance = starting_balance
        self.cash = starting_balance
        self.positions: Dict[str, Position] = {}
        self.completed_trades_count = 0
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.total_slippage = 0.0

    @property
    def market_value(self) -> float:
        return sum(pos.market_value for pos in self.positions.values())

    @property
    def total_equity(self) -> float:
        return self.cash + self.market_value

    @property
    def unrealized_pnl(self) -> float:
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    @property
    def daily_pnl(self) -> float:
        return self.total_equity - self.starting_day_balance

    def update_with_execution(self, execution: Execution):
        self.total_fees += execution.fee
        self.total_slippage += execution.slippage

        if execution.side == OrderSide.BUY:
            total_deduction = (execution.fill_price * execution.quantity) + execution.fee
            self.cash -= total_deduction

            if execution.symbol not in self.positions:
                self.positions[execution.symbol] = Position(
                    symbol=execution.symbol,
                    quantity=execution.quantity,
                    average_entry_price=execution.fill_price,
                    current_price=execution.fill_price
                )
            else:
                pos = self.positions[execution.symbol]
                new_qty = pos.quantity + execution.quantity
                avg_price = ((pos.average_entry_price * pos.quantity) + (execution.fill_price * execution.quantity)) / new_qty
                pos.quantity = new_qty
                pos.average_entry_price = avg_price

        elif execution.side == OrderSide.SELL:
            total_addition = (execution.fill_price * execution.quantity) - execution.fee
            self.cash += total_addition

            if execution.symbol in self.positions:
                pos = self.positions[execution.symbol]
                # Realize PnL
                trade_realized = (execution.fill_price - pos.average_entry_price) * execution.quantity
                self.realized_pnl += trade_realized
                self.completed_trades_count += 1

                pos.quantity -= execution.quantity
                if pos.quantity <= 0:
                    del self.positions[execution.symbol]

    def update_market_prices(self, current_prices: Dict[str, float]):
        for symbol, price in current_prices.items():
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos.current_price = price
                pos.unrealized_pnl = (price - pos.average_entry_price) * pos.quantity

    def compound_to_next_session(self) -> float:
        """
        At the beginning of each new trading session:
        starting_day_balance = previous_session_final_equity
        Accounts compound both gains and losses.
        """
        final_equity = self.total_equity
        self.starting_day_balance = final_equity
        self.cash = final_equity
        self.positions.clear()
        self.completed_trades_count = 0
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.total_slippage = 0.0
        return self.starting_day_balance

    def get_snapshot(self, session_id: str, timestamp: datetime) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            model_id=self.model_id,
            session_id=session_id,
            timestamp=timestamp,
            starting_balance=self.starting_day_balance,
            cash=self.cash,
            market_value=self.market_value,
            total_equity=self.total_equity,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=self.unrealized_pnl,
            daily_pnl=self.daily_pnl,
            completed_trades_count=self.completed_trades_count
        )
