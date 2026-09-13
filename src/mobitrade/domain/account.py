from datetime import datetime
from typing import List, Optional
from mobitrade.domain.enums import AccountState, OrderStatus
from mobitrade.domain.trading import Order, Trade

class Account:
    """
    Manages isolated account state for a specific model within a trading session.
    Strictly follows the state transition rules and guarantees the order shutdown sequence.
    """
    def __init__(
        self,
        model_id: str,
        starting_balance: float,
        target_pct: float = 0.10,
        loss_limit_pct: float = 0.05,
        account_id: Optional[str] = None
    ):
        self.model_id = model_id
        self.account_id = account_id or f"acc_{model_id}"
        self.starting_balance = starting_balance
        self.cash = starting_balance
        self.target_pct = target_pct
        self.loss_limit_pct = loss_limit_pct
        self.state = AccountState.READY
        
        # Shutdown thresholds based explicitly on starting_day_balance
        self.daily_target_equity = starting_balance * (1.0 + target_pct)
        self.daily_stop_equity = starting_balance * (1.0 - loss_limit_pct)
        
        self.completed_trades: List[Trade] = []
        self.pending_orders: List[Order] = []
        self.target_reached: bool = False
        self.daily_stop_triggered: bool = False
        self.market_closed_triggered: bool = False
        self.square_off_triggered: bool = False
        self.lock_reason: Optional[str] = None

    @property
    def total_equity(self) -> float:
        return self.cash

    def start_session(self):
        if self.state == AccountState.READY:
            self.state = AccountState.TRADING

    def can_place_order(self) -> bool:
        return self.state == AccountState.TRADING

    def check_equity_thresholds(self, current_equity: float):
        """
        Monitors equity in real-time. If +10% target or -5% stop is hit,
        transitions state immediately to trigger shutdown.
        """
        if self.state != AccountState.TRADING:
            return

        if current_equity >= self.daily_target_equity:
            self.target_reached = True
            self.state = AccountState.TARGET_REACHED
            self.lock_reason = f"Target +{self.target_pct*100:.1f}% reached: Equity {current_equity:.2f} >= {self.daily_target_equity:.2f}"
        elif current_equity <= self.daily_stop_equity:
            self.daily_stop_triggered = True
            self.state = AccountState.DAILY_STOP_TRIGGERED
            self.lock_reason = f"Daily Stop -{self.loss_limit_pct*100:.1f}% hit: Equity {current_equity:.2f} <= {self.daily_stop_equity:.2f}"

    def trigger_market_close(self):
        if self.state in (AccountState.TRADING, AccountState.READY):
            self.market_closed_triggered = True
            self.state = AccountState.MARKET_CLOSED
            self.lock_reason = "Market session closed (intraday square-off)"

    def execute_shutdown_sequence(self):
        """
        Enforces Section 27 shutdown sequence:
        1. Disable new orders (guaranteed by state != TRADING).
        2. Cancel pending orders.
        3. Close open positions (handled via PaperBroker/Portfolio).
        4. Mark account locked.
        """
        for order in self.pending_orders:
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
        self.pending_orders.clear()
        self.state = AccountState.LOCKED

    def trigger_square_off(self):
        """
        Initiates 15:15 IST intraday auto square-off.
        Disables new entry orders while allowing closing orders.
        """
        self.square_off_triggered = True
        self.lock_reason = "15:15 IST auto square-off triggered"

    def compound_to_next_session(self, new_starting_balance: float):
        """
        Compounds realized equity into the next session's starting balance.
        Dynamically recalculates the +10% target and -5% stop loss benchmarks
        from the new starting balance.
        """
        self.starting_balance = new_starting_balance
        self.cash = new_starting_balance
        self.daily_target_equity = new_starting_balance * (1.0 + self.target_pct)
        self.daily_stop_equity = new_starting_balance * (1.0 - self.loss_limit_pct)
        self.completed_trades.clear()
        self.pending_orders.clear()
        self.target_reached = False
        self.daily_stop_triggered = False
        self.market_closed_triggered = False
        self.square_off_triggered = False
        self.lock_reason = None
        self.state = AccountState.READY

