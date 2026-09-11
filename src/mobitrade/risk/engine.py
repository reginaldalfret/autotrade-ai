from datetime import datetime
from mobitrade.domain.enums import Action, RiskDecision
from mobitrade.domain.trading import TradeDecision
from mobitrade.domain.models import PortfolioSnapshot
from mobitrade.domain.risk import RiskCheckResult
from mobitrade.domain.account import Account
from mobitrade.config.settings import RiskConfig

class RiskEngine:
    """
    Deterministic Safety & Control Layer.
    The LLM proposes; the RiskEngine decides whether the proposal is allowed.
    The LLM cannot override these hard rules.
    """
    def __init__(self, config: RiskConfig):
        self.config = config

    def calculate_targets(self, starting_balance: float):
        """
        Target = starting_day_balance * (1 + target_pct)
        Stop   = starting_day_balance * (1 - loss_limit_pct)
        """
        target_equity = starting_balance * (1.0 + self.config.daily_target_pct)
        stop_equity = starting_balance * (1.0 - self.config.daily_loss_limit_pct)
        return target_equity, stop_equity

    def evaluate_decision(
        self,
        decision: TradeDecision,
        portfolio: PortfolioSnapshot,
        account: Account,
        current_open_positions: int,
        timestamp: datetime
    ) -> RiskCheckResult:
        now = timestamp

        # Rule 1: Account state validation
        if not account.can_place_order():
            return RiskCheckResult(
                decision=RiskDecision.REJECTED,
                reason=f"Account not in TRADING state (Current: {account.state.value}, Lock Reason: {account.lock_reason})",
                rule_name="ACCOUNT_STATE_CHECK",
                timestamp=now
            )

        # Rule 2: Pass HOLD decisions safely
        if decision.action == Action.HOLD:
            return RiskCheckResult(
                decision=RiskDecision.APPROVED,
                reason="HOLD action approved",
                rule_name="ACTION_VALIDATION",
                timestamp=now
            )

        # Rule 3: Trade Count Ceiling (Max 20 completed trades per session)
        if portfolio.completed_trades_count >= self.config.max_trades_per_session:
            return RiskCheckResult(
                decision=RiskDecision.REJECTED,
                reason=f"Max trades limit ({self.config.max_trades_per_session}) reached for session",
                rule_name="MAX_TRADES_LIMIT",
                timestamp=now
            )

        # Rule 4: Daily +10% Target Shutdown Check
        target_equity, stop_equity = self.calculate_targets(portfolio.starting_balance)
        if portfolio.total_equity >= target_equity:
            account.check_equity_thresholds(portfolio.total_equity)
            account.execute_shutdown_sequence()
            return RiskCheckResult(
                decision=RiskDecision.REJECTED,
                reason=f"Daily +10% target hit (Equity: {portfolio.total_equity:.2f} >= {target_equity:.2f}). Orders disabled.",
                rule_name="DAILY_TARGET_SHUTDOWN",
                timestamp=now
            )

        # Rule 5: Daily -5% Hard Loss Shutdown Check
        if portfolio.total_equity <= stop_equity:
            account.check_equity_thresholds(portfolio.total_equity)
            account.execute_shutdown_sequence()
            return RiskCheckResult(
                decision=RiskDecision.REJECTED,
                reason=f"Daily -5% stop hit (Equity: {portfolio.total_equity:.2f} <= {stop_equity:.2f}). Orders disabled.",
                rule_name="DAILY_STOP_SHUTDOWN",
                timestamp=now
            )

        # Rule 6: Confidence threshold
        if decision.confidence < self.config.min_confidence_score:
            return RiskCheckResult(
                decision=RiskDecision.REJECTED,
                reason=f"Confidence {decision.confidence:.2f} below minimum threshold {self.config.min_confidence_score:.2f}",
                rule_name="MIN_CONFIDENCE_CHECK",
                timestamp=now
            )

        # Rule 7: Trade-level stop loss enforcement for entries
        if decision.action == Action.BUY:
            if self.config.require_stop_loss and decision.stop_loss is None:
                return RiskCheckResult(
                    decision=RiskDecision.REJECTED,
                    reason="Trade-level stop loss required for BUY proposal",
                    rule_name="REQUIRE_STOP_LOSS",
                    timestamp=now
                )

            # Rule 8: Concurrent positions check
            if current_open_positions >= self.config.max_concurrent_positions:
                return RiskCheckResult(
                    decision=RiskDecision.REJECTED,
                    reason=f"Max concurrent positions reached ({self.config.max_concurrent_positions})",
                    rule_name="MAX_POSITIONS_LIMIT",
                    timestamp=now
                )

            # Rule 9: Cash / Purchasing power check
            order_cost = decision.entry_price * decision.quantity
            if order_cost > portfolio.cash:
                return RiskCheckResult(
                    decision=RiskDecision.REJECTED,
                    reason=f"Insufficient cash: order cost {order_cost:.2f} > available cash {portfolio.cash:.2f}",
                    rule_name="INSUFFICIENT_CASH",
                    timestamp=now
                )

        return RiskCheckResult(
            decision=RiskDecision.APPROVED,
            reason="Proposal satisfies all deterministic risk rules",
            rule_name="ALL_RULES_PASSED",
            timestamp=now
        )
