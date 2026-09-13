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

    def calculate_daily_performance(self, trades: Optional[List[Trade]] = None) -> Dict[str, Any]:
        """
        Calculates comprehensive auditable daily performance metrics.
        All rankings and compounding are strictly based on NET P&L.
        """
        model_trades = trades or []
        winning_trades = [t for t in model_trades if t.net_pnl > 0]
        losing_trades = [t for t in model_trades if t.net_pnl < 0]

        total_wins = sum(t.net_pnl for t in winning_trades)
        total_losses = abs(sum(t.net_pnl for t in losing_trades))

        if total_losses > 0:
            profit_factor = total_wins / total_losses
        elif total_wins > 0:
            profit_factor = float("inf")
        else:
            profit_factor = 0.0

        win_rate = (len(winning_trades) / len(model_trades) * 100.0) if model_trades else 0.0
        avg_win = (total_wins / len(winning_trades)) if winning_trades else 0.0
        avg_loss = (sum(t.net_pnl for t in losing_trades) / len(losing_trades)) if losing_trades else 0.0
        largest_win = max([t.net_pnl for t in model_trades], default=0.0)
        largest_loss = min([t.net_pnl for t in model_trades], default=0.0)
        gross_pnl = sum(t.gross_pnl for t in model_trades)
        net_pnl = sum(t.net_pnl for t in model_trades)

        return {
            "model_id": self.model_id,
            "starting_balance": self.starting_day_balance,
            "ending_balance": self.total_equity,
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "daily_pnl": self.daily_pnl,
            "return_pct": (self.daily_pnl / self.starting_day_balance * 100.0) if self.starting_day_balance > 0 else 0.0,
            "total_fees": self.total_fees,
            "total_slippage": self.total_slippage,
            "trades_count": len(model_trades),
            "winning_trades_count": len(winning_trades),
            "losing_trades_count": len(losing_trades),
            "win_rate": win_rate,
            "average_winning_trade": avg_win,
            "average_losing_trade": avg_loss,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "profit_factor": profit_factor,
            "max_drawdown": 0.0
        }

