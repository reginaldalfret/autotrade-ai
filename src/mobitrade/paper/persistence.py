import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from mobitrade.domain.account import Account
from mobitrade.domain.trading import Order, Execution, Trade
from mobitrade.domain.models import Position, PortfolioSnapshot
from mobitrade.domain.enums import ExitReason
from mobitrade.logging.audit import AuditLogger, AuditEventType

class PaperDatabaseRepository:
    """
    SQLite persistence repository for Paper Trading & Portfolio Management.
    Stores accounts, daily sessions, orders, fills, positions, trades,
    daily performance metrics, portfolio snapshots, state-change audit events,
    and daily PDF reporting metadata.
    Database: database/mobitrade.db
    """
    def __init__(self, db_path: str = "database/mobitrade.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_logger = AuditLogger(db_path=str(self.db_path))
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL UNIQUE,
                    starting_balance REAL NOT NULL,
                    cash REAL NOT NULL,
                    target_pct REAL NOT NULL,
                    loss_limit_pct REAL NOT NULL,
                    daily_target_equity REAL NOT NULL,
                    daily_stop_equity REAL NOT NULL,
                    state TEXT NOT NULL,
                    target_reached INTEGER NOT NULL,
                    daily_stop_triggered INTEGER NOT NULL,
                    lock_reason TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_sessions (
                    session_id TEXT PRIMARY KEY,
                    session_date TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    closed_at TEXT,
                    models_count INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_orders (
                    order_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    account_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    stop_loss REAL,
                    target_price REAL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    snapshot_id TEXT,
                    decision_id TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_fills (
                    execution_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    account_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    fill_price REAL NOT NULL,
                    fee REAL NOT NULL,
                    slippage REAL NOT NULL,
                    executed_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_trades (
                    trade_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    account_id TEXT,
                    session_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    entry_execution_id TEXT NOT NULL,
                    exit_execution_id TEXT,
                    quantity INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    initial_stop REAL,
                    trailing_stop REAL,
                    gross_pnl REAL NOT NULL,
                    total_fees REAL NOT NULL,
                    total_slippage REAL NOT NULL,
                    net_pnl REAL NOT NULL,
                    exit_reason TEXT,
                    snapshot_id TEXT,
                    decision_id TEXT,
                    is_closed INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_performance (
                    perf_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    starting_balance REAL NOT NULL,
                    ending_balance REAL NOT NULL,
                    gross_pnl REAL NOT NULL,
                    net_pnl REAL NOT NULL,
                    daily_pnl REAL NOT NULL,
                    return_pct REAL NOT NULL,
                    total_fees REAL NOT NULL,
                    total_slippage REAL NOT NULL,
                    trades_count INTEGER NOT NULL,
                    winning_trades_count INTEGER NOT NULL,
                    losing_trades_count INTEGER NOT NULL,
                    win_rate REAL NOT NULL,
                    average_winning_trade REAL NOT NULL,
                    average_losing_trade REAL NOT NULL,
                    largest_win REAL NOT NULL,
                    largest_loss REAL NOT NULL,
                    profit_factor REAL NOT NULL,
                    max_drawdown REAL NOT NULL,
                    target_status TEXT NOT NULL,
                    stop_status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    starting_balance REAL NOT NULL,
                    cash REAL NOT NULL,
                    market_value REAL NOT NULL,
                    total_equity REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    daily_pnl REAL NOT NULL,
                    completed_trades_count INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    sequence_number INTEGER NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    model_id TEXT,
                    trade_id TEXT,
                    order_id TEXT,
                    payload_json TEXT NOT NULL,
                    previous_event_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_seq ON audit_events (sequence_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events (session_id, sequence_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_model ON audit_events (model_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events (event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_trade ON audit_events (trade_id)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    generation_status TEXT NOT NULL,
                    error_message TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_session ON reports (session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_date ON reports (report_date)")
            conn.commit()

    def save_account(self, account: Account) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                INSERT INTO accounts (
                    account_id, model_id, starting_balance, cash, target_pct, loss_limit_pct,
                    daily_target_equity, daily_stop_equity, state, target_reached,
                    daily_stop_triggered, lock_reason, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    starting_balance=excluded.starting_balance,
                    cash=excluded.cash,
                    daily_target_equity=excluded.daily_target_equity,
                    daily_stop_equity=excluded.daily_stop_equity,
                    state=excluded.state,
                    target_reached=excluded.target_reached,
                    daily_stop_triggered=excluded.daily_stop_triggered,
                    lock_reason=excluded.lock_reason,
                    updated_at=excluded.updated_at
            """, (
                account.account_id,
                account.model_id,
                account.starting_balance,
                account.cash,
                account.target_pct,
                account.loss_limit_pct,
                account.daily_target_equity,
                account.daily_stop_equity,
                account.state.value,
                1 if account.target_reached else 0,
                1 if account.daily_stop_triggered else 0,
                account.lock_reason,
                now_iso
            ))
            conn.commit()

    def get_account(self, model_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE model_id = ?", (model_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_accounts(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts ORDER BY model_id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def save_session_start(self, session_id: str, session_date: str, models_count: int = 8) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO daily_sessions (
                    session_id, session_date, state, started_at, closed_at, models_count
                ) VALUES (?, ?, 'ACTIVE', ?, NULL, ?)
            """, (session_id, session_date, now_iso, models_count))
            conn.commit()

    def save_session_close(self, session_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                UPDATE daily_sessions SET state = 'CLOSED', closed_at = ? WHERE session_id = ?
            """, (now_iso, session_id))
            conn.commit()

    def save_order(self, order: Order, session_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO paper_orders (
                    order_id, session_id, model_id, account_id, symbol, side, order_type,
                    quantity, price, stop_loss, target_price, status, created_at,
                    snapshot_id, decision_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.order_id,
                session_id,
                order.model_id,
                order.account_id,
                order.symbol,
                order.side.value,
                order.order_type.value,
                order.quantity,
                order.price,
                order.stop_loss,
                order.target_price,
                order.status.value,
                order.created_at.isoformat(),
                order.snapshot_id,
                order.decision_id
            ))
            conn.commit()

    def save_fill(self, execution: Execution) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO paper_fills (
                    execution_id, order_id, model_id, account_id, symbol, side,
                    quantity, fill_price, fee, slippage, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                execution.execution_id,
                execution.order_id,
                execution.model_id,
                execution.account_id,
                execution.symbol,
                execution.side.value,
                execution.quantity,
                execution.fill_price,
                execution.fee,
                execution.slippage,
                execution.executed_at.isoformat()
            ))
            conn.commit()

    def save_trade(self, trade: Trade, session_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO paper_trades (
                    trade_id, model_id, account_id, session_id, symbol, exchange,
                    entry_execution_id, exit_execution_id, quantity, entry_price, exit_price,
                    entry_time, exit_time, initial_stop, trailing_stop, gross_pnl,
                    total_fees, total_slippage, net_pnl, exit_reason, snapshot_id,
                    decision_id, is_closed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.trade_id,
                trade.model_id,
                trade.account_id,
                session_id,
                trade.symbol,
                trade.exchange,
                trade.entry_execution_id,
                trade.exit_execution_id,
                trade.quantity,
                trade.entry_price,
                trade.exit_price,
                trade.entry_time.isoformat(),
                trade.exit_time.isoformat() if trade.exit_time else None,
                trade.initial_stop,
                trade.trailing_stop,
                trade.gross_pnl,
                trade.total_fees,
                trade.total_slippage,
                trade.net_pnl,
                trade.exit_reason.value if trade.exit_reason else None,
                trade.snapshot_id,
                trade.decision_id,
                1 if trade.is_closed else 0
            ))
            conn.commit()

    def _row_to_trade(self, r: sqlite3.Row) -> Trade:
        exit_val = r["exit_reason"]
        exit_reason = None
        if exit_val:
            try:
                exit_reason = ExitReason(exit_val)
            except Exception:
                exit_reason = None

        return Trade(
            trade_id=r["trade_id"],
            symbol=r["symbol"],
            quantity=r["quantity"],
            entry_price=r["entry_price"],
            entry_time=datetime.fromisoformat(r["entry_time"]),
            model_id=r["model_id"],
            account_id=r["account_id"],
            exchange=r["exchange"] or "NSE",
            entry_execution_id=r["entry_execution_id"],
            exit_execution_id=r["exit_execution_id"],
            exit_price=r["exit_price"],
            exit_time=datetime.fromisoformat(r["exit_time"]) if r["exit_time"] else None,
            initial_stop=r["initial_stop"],
            trailing_stop=r["trailing_stop"],
            gross_pnl=r["gross_pnl"],
            total_fees=r["total_fees"],
            total_slippage=r["total_slippage"],
            net_pnl=r["net_pnl"],
            exit_reason=exit_reason,
            snapshot_id=r["snapshot_id"],
            decision_id=r["decision_id"],
            is_closed=bool(r["is_closed"])
        )

    def list_trades(self, session_id: Optional[str] = None, model_id: Optional[str] = None) -> List[Trade]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM paper_trades WHERE 1=1"
            params = []
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            if model_id:
                query += " AND model_id = ?"
                params.append(model_id)
            query += " ORDER BY entry_time DESC"
            cursor.execute(query, params)
            return [self._row_to_trade(r) for r in cursor.fetchall()]

    def list_open_trades(self, model_id: Optional[str] = None) -> List[Trade]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM paper_trades WHERE is_closed = 0"
            params = []
            if model_id:
                query += " AND model_id = ?"
                params.append(model_id)
            query += " ORDER BY entry_time DESC"
            cursor.execute(query, params)
            return [self._row_to_trade(r) for r in cursor.fetchall()]

    def get_performance_history(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT p.*, COALESCE(s.session_date, SUBSTR(p.created_at, 1, 10)) as session_date
                FROM daily_performance p
                LEFT JOIN daily_sessions s ON p.session_id = s.session_id
                WHERE 1=1
            """
            params = []
            if date:
                query += " AND (s.session_date = ? OR p.session_id LIKE ?)"
                params.extend([date, f"%{date.replace('-', '')}%"])
            query += " ORDER BY p.created_at DESC, p.net_pnl DESC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_trades_for_session(self, session_id: str, model_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if model_id:
                cursor.execute("SELECT * FROM paper_trades WHERE session_id = ? AND model_id = ? ORDER BY entry_time ASC", (session_id, model_id))
            else:
                cursor.execute("SELECT * FROM paper_trades WHERE session_id = ? ORDER BY entry_time ASC", (session_id,))
            return [dict(r) for r in cursor.fetchall()]

    def save_daily_performance(self, perf: Dict[str, Any], session_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            perf_id = f"perf_{session_id}_{perf['model_id']}"
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO daily_performance (
                    perf_id, session_id, model_id, starting_balance, ending_balance,
                    gross_pnl, net_pnl, daily_pnl, return_pct, total_fees, total_slippage,
                    trades_count, winning_trades_count, losing_trades_count, win_rate,
                    average_winning_trade, average_losing_trade, largest_win, largest_loss,
                    profit_factor, max_drawdown, target_status, stop_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                perf_id,
                session_id,
                perf["model_id"],
                perf["starting_balance"],
                perf["ending_balance"],
                perf["gross_pnl"],
                perf["net_pnl"],
                perf["daily_pnl"],
                perf["return_pct"],
                perf["total_fees"],
                perf["total_slippage"],
                perf["trades_count"],
                perf["winning_trades_count"],
                perf["losing_trades_count"],
                perf["win_rate"],
                perf["average_winning_trade"],
                perf["average_losing_trade"],
                perf["largest_win"],
                perf["largest_loss"],
                perf["profit_factor"],
                perf.get("max_drawdown", 0.0),
                perf.get("target_status", "ACTIVE"),
                perf.get("stop_status", "ACTIVE"),
                now_iso
            ))
            conn.commit()

    def get_daily_performance(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM daily_performance WHERE session_id = ? ORDER BY net_pnl DESC", (session_id,))
            return [dict(r) for r in cursor.fetchall()]

    def record_audit_event(
        self,
        session_id: str,
        model_id: Optional[str],
        event_type: str,
        payload: Dict[str, Any],
        timestamp: datetime,
        trade_id: Optional[str] = None,
        order_id: Optional[str] = None
    ) -> None:
        self.audit_logger.record_event(
            session_id=session_id,
            event_type=event_type,
            payload=payload,
            model_id=model_id,
            trade_id=trade_id,
            order_id=order_id,
            timestamp=timestamp
        )

    def get_audit_events(self, session_id: str, model_id: Optional[str] = None) -> List[Dict[str, Any]]:
        events = self.audit_logger.get_events(session_id=session_id, model_id=model_id)
        return [
            {
                "event_id": e.event_id,
                "sequence_number": e.sequence_number,
                "session_id": e.session_id,
                "timestamp": e.timestamp,
                "event_type": e.event_type,
                "model_id": e.model_id,
                "trade_id": e.trade_id,
                "order_id": e.order_id,
                "payload_json": json.dumps(e.payload),
                "payload": e.payload,
                "previous_event_hash": e.previous_event_hash,
                "event_hash": e.event_hash
            }
            for e in events
        ]

    def save_report(
        self,
        report_id: str,
        session_id: str,
        report_date: str,
        file_path: str,
        file_hash: str,
        generated_at: str,
        generation_status: str = "SUCCESS",
        error_message: Optional[str] = None
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO reports (
                    report_id, session_id, report_date, file_path,
                    file_hash, generated_at, generation_status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id,
                session_id,
                report_date,
                file_path,
                file_hash,
                generated_at,
                generation_status,
                error_message
            ))
            conn.commit()

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_report_by_date(self, report_date: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reports WHERE report_date = ? ORDER BY generated_at DESC LIMIT 1", (report_date,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_reports_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reports WHERE session_id = ? ORDER BY generated_at DESC", (session_id,))
            return [dict(r) for r in cursor.fetchall()]

    def save_portfolio_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            snap_id = f"snap_{snapshot.session_id}_{snapshot.model_id}_{int(snapshot.timestamp.timestamp())}"
            cursor.execute("""
                INSERT OR REPLACE INTO portfolio_snapshots (
                    snapshot_id, model_id, session_id, timestamp, starting_balance,
                    cash, market_value, total_equity, realized_pnl, unrealized_pnl,
                    daily_pnl, completed_trades_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snap_id,
                snapshot.model_id,
                snapshot.session_id,
                snapshot.timestamp.isoformat(),
                snapshot.starting_balance,
                snapshot.cash,
                snapshot.market_value,
                snapshot.total_equity,
                snapshot.realized_pnl,
                snapshot.unrealized_pnl,
                snapshot.daily_pnl,
                snapshot.completed_trades_count
            ))
            conn.commit()
