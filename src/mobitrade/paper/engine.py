import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from mobitrade.domain.enums import Action, OrderSide, OrderType, OrderStatus, AccountState, ExitReason, RiskDecision
from mobitrade.domain.trading import OrderRequest, Order, Execution, Trade, TradeDecision
from mobitrade.domain.account import Account
from mobitrade.domain.models import Position, PortfolioSnapshot
from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.domain.llm_models import LLMDecisionRecord, ValidationStatus
from mobitrade.config.settings import CostConfig, RiskConfig, load_yaml_config
from mobitrade.config.model_registry import ModelRegistry
from mobitrade.risk.engine import RiskEngine
from mobitrade.risk.trailing_stop import TrailingStopEngine
from mobitrade.execution.paper_broker import PaperBroker
from mobitrade.portfolio.manager import PortfolioManager
from mobitrade.paper.persistence import PaperDatabaseRepository

DEFAULT_MODELS = ["nemotron", "qwen", "gemma", "llama", "granite", "phi", "smollm", "falcon"]

class PaperTradingEngine:
    """
    Central Paper Trading & Portfolio Management Engine.
    Coordinates 8 isolated model accounts, deterministic RiskEngine validation,
    PaperBroker execution with Indian statutory fees, TrailingStop dynamic exits,
    15:15 IST auto square-off, and daily capital compounding.
    """
    def __init__(
        self,
        cost_config: Optional[CostConfig] = None,
        risk_config: Optional[RiskConfig] = None,
        db_path: str = "/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db",
        initial_balance_per_model: float = 1000.0,
        trailing_distance_pct: float = 0.005
    ):
        self.cost_config = cost_config or CostConfig()
        self.risk_config = risk_config or RiskConfig()
        self.initial_balance = initial_balance_per_model
        self.trailing_distance_pct = trailing_distance_pct
        self.persistence = PaperDatabaseRepository(db_path=db_path)
        self.risk_engine = RiskEngine(self.risk_config)
        self.trailing_stop_engine = TrailingStopEngine(default_trailing_pct=trailing_distance_pct)
        self.broker = PaperBroker(self.cost_config)

        # 8 isolated per-model portfolios and accounts
        self.accounts: Dict[str, Account] = {}
        self.portfolios: Dict[str, PortfolioManager] = {}
        self.session_trades: Dict[str, List[Trade]] = {}

        self._init_accounts()

    def _init_accounts(self) -> None:
        registry = ModelRegistry()
        model_ids = [m.id for m in registry.list_all_models()] if registry.list_all_models() else DEFAULT_MODELS
        for mid in model_ids:
            # Check if existing account exists in DB
            saved = self.persistence.get_account(mid)
            balance = saved["starting_balance"] if saved else self.initial_balance
            account = Account(
                model_id=mid,
                starting_balance=balance,
                target_pct=self.risk_config.daily_target_pct,
                loss_limit_pct=self.risk_config.daily_loss_limit_pct
            )
            self.accounts[mid] = account
            self.portfolios[mid] = PortfolioManager(model_id=mid, starting_balance=balance)
            self.session_trades[mid] = []
            self.persistence.save_account(account)

    def start_session(self, session_id: str, session_date: str) -> None:
        """
        Starts a new trading session across all 8 isolated model accounts.
        """
        self.persistence.save_session_start(session_id, session_date, len(self.accounts))
        for mid, account in self.accounts.items():
            account.start_session()
            self.persistence.save_account(account)
            self.session_trades[mid] = []
            self.persistence.record_audit_event(
                session_id=session_id,
                model_id=mid,
                event_type="SESSION_STARTED",
                payload={"starting_balance": account.starting_balance, "date": session_date},
                timestamp=datetime.now()
            )

    def process_model_decision(
        self,
        decision_record: LLMDecisionRecord,
        snapshot: MarketSnapshot,
        session_id: str,
        current_market_price: float
    ) -> Optional[Trade]:
        """
        Connects an LLM decision to paper trading through the strict safety pipeline:
        LLM Decision -> Validator -> RiskEngine -> PortfolioManager -> PaperBroker.
        The LLM CANNOT directly submit orders to PaperBroker.
        """
        mid = decision_record.model_id
        account = self.accounts.get(mid)
        portfolio = self.portfolios.get(mid)
        if not account or not portfolio:
            return None

        # 1. Reject invalid or HOLD decisions
        if decision_record.validation_status != ValidationStatus.VALID:
            self.persistence.record_audit_event(
                session_id=session_id,
                model_id=mid,
                event_type="DECISION_REJECTED_INVALID",
                payload={"reason": str(decision_record.validation_status), "raw_output": decision_record.raw_output},
                timestamp=snapshot.decision_timestamp
            )
            return None

        if decision_record.action in (Action.HOLD, "HOLD", "NO_ACTION"):
            self.persistence.record_audit_event(
                session_id=session_id,
                model_id=mid,
                event_type="DECISION_HOLD",
                payload={"action": "HOLD", "reasoning": decision_record.reasoning_summary},
                timestamp=snapshot.decision_timestamp
            )
            return None

        # 2. Process BUY decision
        if decision_record.action == Action.BUY:
            # Deterministic position sizing
            qty = self.risk_engine.calculate_position_size(current_market_price, portfolio.cash)
            if qty <= 0:
                self.persistence.record_audit_event(
                    session_id=session_id,
                    model_id=mid,
                    event_type="ORDER_REJECTED_ZERO_QTY",
                    payload={"price": current_market_price, "cash": portfolio.cash},
                    timestamp=snapshot.decision_timestamp
                )
                return None

            proposed_stop = decision_record.proposed_stop_loss
            # Default safe stop loss if omitted or invalid (2% below entry)
            if proposed_stop is None or proposed_stop >= current_market_price:
                proposed_stop = round(current_market_price * 0.98, 2)

            proposed_tgt = decision_record.proposed_target
            if proposed_tgt is None or proposed_tgt <= current_market_price:
                proposed_tgt = round(current_market_price * 1.03, 2)

            trade_decision = TradeDecision(
                symbol=snapshot.symbol,
                action=Action.BUY,
                confidence=decision_record.confidence,
                quantity=qty,
                entry_price=current_market_price,
                stop_loss=proposed_stop,
                target_price=proposed_tgt,
                reasoning=decision_record.reasoning_summary or "LLM BUY signal"
            )

            current_open_positions = len(portfolio.positions)
            risk_check = self.risk_engine.evaluate_decision(
                decision=trade_decision,
                portfolio=portfolio.get_snapshot(session_id, snapshot.decision_timestamp),
                account=account,
                current_open_positions=current_open_positions,
                timestamp=snapshot.decision_timestamp
            )

            if risk_check.decision == RiskDecision.REJECTED:
                self.persistence.record_audit_event(
                    session_id=session_id,
                    model_id=mid,
                    event_type="ORDER_REJECTED",
                    payload={"rule": risk_check.rule_name, "reason": risk_check.reason},
                    timestamp=snapshot.decision_timestamp
                )
                return None

            # 3. Submit order to PaperBroker
            order_req = OrderRequest(
                model_id=mid,
                account_id=account.account_id,
                symbol=snapshot.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=qty,
                price=current_market_price,
                stop_loss=proposed_stop,
                target_price=proposed_tgt,
                snapshot_id=snapshot.snapshot_id,
                decision_id=decision_record.decision_id
            )
            order, execution = self.broker.submit_order(order_req, current_market_price, snapshot.decision_timestamp)
            portfolio.update_with_execution(execution)

            self.persistence.save_order(order, session_id)
            self.persistence.save_fill(execution)

            key = (mid, snapshot.symbol)
            trade = self.broker.open_trades.get(key)
            if trade:
                self.persistence.save_trade(trade, session_id)

            self.persistence.record_audit_event(
                session_id=session_id,
                model_id=mid,
                event_type="ORDER_FILLED",
                payload={"order_id": order.order_id, "fill_price": execution.fill_price, "qty": qty},
                timestamp=snapshot.decision_timestamp
            )
            return trade

        # 4. Process SELL decision (close existing position)
        elif decision_record.action == Action.SELL:
            key = (mid, snapshot.symbol)
            if key in self.broker.open_trades or snapshot.symbol in portfolio.positions:
                trade = self.broker.open_trades.get(key)
                qty = trade.quantity if trade else portfolio.positions[snapshot.symbol].quantity
                sell_req = OrderRequest(
                    model_id=mid,
                    account_id=account.account_id,
                    symbol=snapshot.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=qty,
                    price=current_market_price,
                    snapshot_id=snapshot.snapshot_id,
                    decision_id=decision_record.decision_id
                )
                order, execution = self.broker.submit_order(sell_req, current_market_price, snapshot.decision_timestamp, exit_reason=ExitReason.TARGET)
                portfolio.update_with_execution(execution)

                self.persistence.save_order(order, session_id)
                self.persistence.save_fill(execution)
                if trade and trade.is_closed:
                    self.session_trades[mid].append(trade)
                    self.persistence.save_trade(trade, session_id)

                self.persistence.record_audit_event(
                    session_id=session_id,
                    model_id=mid,
                    event_type="POSITION_CLOSED",
                    payload={"symbol": snapshot.symbol, "net_pnl": trade.net_pnl if trade else 0.0},
                    timestamp=snapshot.decision_timestamp
                )
                return trade

        return None

    def update_market_prices(self, current_prices: Dict[str, float], timestamp: datetime, session_id: str) -> None:
        """
        Updates in-flight mark-to-market prices and checks:
        1. Daily target (+10%) & stop loss (-5%) shutdown.
        2. Dynamic trailing-stop triggering.
        """
        for mid in self.accounts:
            portfolio = self.portfolios[mid]
            account = self.accounts[mid]

            portfolio.update_market_prices(current_prices)

            # Check equity thresholds
            if account.state == AccountState.TRADING:
                account.check_equity_thresholds(portfolio.total_equity)

                if account.target_reached:
                    # Execute daily target shutdown
                    account.execute_shutdown_sequence()
                    closed = self.broker.close_all_positions(mid, current_prices, timestamp, ExitReason.DAILY_TARGET)
                    for t in closed:
                        exit_exec = self.broker.executions[t.exit_execution_id]
                        portfolio.update_with_execution(exit_exec)
                        if exit_exec.order_id in self.broker.orders:
                            self.persistence.save_order(self.broker.orders[exit_exec.order_id], session_id)
                        self.persistence.save_fill(exit_exec)
                        self.session_trades[mid].append(t)
                        self.persistence.save_trade(t, session_id)

                    self.persistence.record_audit_event(
                        session_id=session_id,
                        model_id=mid,
                        event_type="DAILY_TARGET_REACHED",
                        payload={"equity": portfolio.total_equity, "target": account.daily_target_equity},
                        timestamp=timestamp
                    )
                    self.persistence.save_account(account)
                    continue

                elif account.daily_stop_triggered:
                    # Execute daily stop shutdown
                    account.execute_shutdown_sequence()
                    closed = self.broker.close_all_positions(mid, current_prices, timestamp, ExitReason.DAILY_STOP)
                    for t in closed:
                        exit_exec = self.broker.executions[t.exit_execution_id]
                        portfolio.update_with_execution(exit_exec)
                        if exit_exec.order_id in self.broker.orders:
                            self.persistence.save_order(self.broker.orders[exit_exec.order_id], session_id)
                        self.persistence.save_fill(exit_exec)
                        self.session_trades[mid].append(t)
                        self.persistence.save_trade(t, session_id)

                    self.persistence.record_audit_event(
                        session_id=session_id,
                        model_id=mid,
                        event_type="DAILY_STOP_TRIGGERED",
                        payload={"equity": portfolio.total_equity, "stop": account.daily_stop_equity},
                        timestamp=timestamp
                    )
                    self.persistence.save_account(account)
                    continue

            # Check trailing stop for in-flight positions
            target_symbols = [
                k[1] for k in list(self.broker.open_trades.keys())
                if isinstance(k, tuple) and len(k) == 2 and k[0] == mid
            ]
            for sym in target_symbols:
                key = (mid, sym)
                trade = self.broker.open_trades.get(key)
                if not trade or trade.is_closed or sym not in current_prices:
                    continue

                curr_px = current_prices[sym]
                peak_px = self.broker.peak_prices.get(key, trade.entry_price)
                if curr_px > peak_px:
                    self.broker.peak_prices[key] = curr_px
                    peak_px = curr_px

                # Update trailing stop floor
                trail_stop_floor = peak_px * (1.0 - self.trailing_distance_pct)
                if trade.trailing_stop is None or trail_stop_floor > trade.trailing_stop:
                    trade.trailing_stop = trail_stop_floor

                # Check if stop triggered
                is_stop_loss = trade.initial_stop is not None and curr_px <= trade.initial_stop
                is_trailing_stop = trade.trailing_stop is not None and curr_px <= trade.trailing_stop

                if is_stop_loss or is_trailing_stop:
                    reason = ExitReason.STOP_LOSS if is_stop_loss else ExitReason.TRAILING_STOP
                    sell_req = OrderRequest(
                        model_id=mid,
                        account_id=account.account_id,
                        symbol=sym,
                        side=OrderSide.SELL,
                        quantity=trade.quantity,
                        price=curr_px,
                        snapshot_id=trade.snapshot_id,
                        decision_id=trade.decision_id
                    )
                    order, execution = self.broker.submit_order(sell_req, curr_px, timestamp, exit_reason=reason)
                    portfolio.update_with_execution(execution)
                    self.session_trades[mid].append(trade)
                    self.persistence.save_trade(trade, session_id)
                    self.persistence.record_audit_event(
                        session_id=session_id,
                        model_id=mid,
                        event_type="STOP_TRIGGERED",
                        payload={"reason": reason.value, "fill_price": execution.fill_price, "net_pnl": trade.net_pnl},
                        timestamp=timestamp
                    )

    def execute_auto_square_off(self, current_prices: Dict[str, float], timestamp: datetime, session_id: str) -> None:
        """
        Executes intraday square-off (15:15 IST).
        Closes all open positions across all models to ensure zero overnight risk.
        """
        for mid in self.accounts:
            account = self.accounts[mid]
            portfolio = self.portfolios[mid]
            account.trigger_square_off()

            closed = self.broker.close_all_positions(mid, current_prices, timestamp, ExitReason.MARKET_CLOSE)
            for t in closed:
                exit_exec = self.broker.executions[t.exit_execution_id]
                portfolio.update_with_execution(exit_exec)
                if exit_exec.order_id in self.broker.orders:
                    self.persistence.save_order(self.broker.orders[exit_exec.order_id], session_id)
                self.persistence.save_fill(exit_exec)
                self.session_trades[mid].append(t)
                self.persistence.save_trade(t, session_id)

            self.persistence.record_audit_event(
                session_id=session_id,
                model_id=mid,
                event_type="MARKET_CLOSE_SQUARE_OFF",
                payload={"closed_trades_count": len(closed), "final_equity": portfolio.total_equity},
                timestamp=timestamp
            )
            self.persistence.save_account(account)

    def finalize_daily_session(self, session_id: str, session_date: str) -> List[Dict[str, Any]]:
        """
        Finalizes daily trading session:
        1. Enforces zero open positions.
        2. Calculates comprehensive daily performance per model.
        3. Compounds realized equity to next day's starting balance.
        4. Persists performance records and audit events.
        """
        leaderboard = []
        for mid, portfolio in self.portfolios.items():
            account = self.accounts[mid]
            account.trigger_market_close()

            trades = self.session_trades.get(mid, [])
            perf = portfolio.calculate_daily_performance(trades)
            perf["target_status"] = "TARGET_REACHED" if account.target_reached else ("LOCKED" if account.state == AccountState.LOCKED else "NORMAL")
            perf["stop_status"] = "STOP_TRIGGERED" if account.daily_stop_triggered else "NORMAL"

            self.persistence.save_daily_performance(perf, session_id)

            # Compounding to next session
            new_starting_balance = portfolio.compound_to_next_session()
            account.compound_to_next_session(new_starting_balance)
            self.persistence.save_account(account)

            self.persistence.record_audit_event(
                session_id=session_id,
                model_id=mid,
                event_type="COMPOUNDING_APPLIED",
                payload={
                    "previous_ending_equity": perf["ending_balance"],
                    "new_starting_balance": new_starting_balance,
                    "new_target_equity": account.daily_target_equity,
                    "new_stop_equity": account.daily_stop_equity
                },
                timestamp=datetime.now()
            )
            leaderboard.append(perf)

        self.persistence.save_session_close(session_id)

        # Automatic PDF daily report generation (resilient against trading interruption)
        try:
            from mobitrade.reporting.generator import DailyReportGenerator
            generator = DailyReportGenerator(db_path=str(self.persistence.db_path))
            generator.generate(session_id)
        except Exception as e:
            self.persistence.record_audit_event(
                session_id=session_id,
                model_id="SYSTEM",
                event_type="REPORT_FAILED",
                payload={"error": str(e)},
                timestamp=datetime.now()
            )

        # Sort leaderboard by Net P&L descending
        leaderboard.sort(key=lambda x: x["net_pnl"], reverse=True)
        return leaderboard
