"""
Comprehensive Performance Analytics Engine.
Performs read-only financial computations, multi-day rollups,
symbol breakdowns, hourly distribution, and strict ledger reconciliation.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from mobitrade.analytics.metrics import (
    calculate_gross_pnl,
    calculate_net_pnl,
    calculate_return_pct,
    calculate_trade_statistics,
    calculate_drawdown,
    calculate_risk_adjusted_ratios
)
from mobitrade.analytics.tournament import rank_leaderboard


class PerformanceAnalyticsEngine:
    """
    Read-only analytics engine querying mobitrade.db to produce
    auditable performance reports, model comparisons, and financial reconciliations.
    """
    def __init__(self, db_path: str = "/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db"):
        self.db_path = Path(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_session_by_id_or_date(self, session_id_or_date: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM daily_sessions WHERE session_id = ? OR session_date = ?",
                (session_id_or_date, session_id_or_date)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def compute_daily_model_analytics(self, session_id: str, model_id: str) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Fetch trades
            cursor.execute(
                "SELECT * FROM paper_trades WHERE session_id = ? AND model_id = ? ORDER BY entry_time ASC",
                (session_id, model_id)
            )
            trades = [dict(r) for r in cursor.fetchall()]

            # 2. Fetch equity curve snapshots
            cursor.execute(
                "SELECT timestamp, total_equity FROM portfolio_snapshots WHERE session_id = ? AND model_id = ? ORDER BY timestamp ASC",
                (session_id, model_id)
            )
            snapshots = [(r["timestamp"], float(r["total_equity"])) for r in cursor.fetchall()]

            # 3. Fetch daily performance record
            cursor.execute(
                "SELECT * FROM daily_performance WHERE session_id = ? AND model_id = ?",
                (session_id, model_id)
            )
            perf_row = cursor.fetchone()
            perf = dict(perf_row) if perf_row else {}

            # 4. Fetch account
            cursor.execute("SELECT * FROM accounts WHERE model_id = ?", (model_id,))
            acct_row = cursor.fetchone()
            account = dict(acct_row) if acct_row else {}

        trade_stats = calculate_trade_statistics(trades)
        dd_stats = calculate_drawdown(snapshots)

        # Trade returns for Sharpe/Sortino
        trade_returns = []
        st_balance = perf.get("starting_balance", account.get("starting_balance", 1000.0))
        for t in trades:
            if st_balance > 0:
                trade_returns.append(t["net_pnl"] / st_balance)

        ret_pct = perf.get("return_pct", calculate_return_pct(trade_stats["gross_profit"] - trade_stats["gross_loss"] - trade_stats["total_fees"] - trade_stats["total_slippage"], st_balance))
        risk_ratios = calculate_risk_adjusted_ratios(
            trade_returns=trade_returns,
            annual_risk_free_rate=0.06,
            max_drawdown_pct=dd_stats["max_drawdown_pct"],
            cumulative_return_pct=ret_pct
        )

        return {
            "model_id": model_id,
            "session_id": session_id,
            "starting_balance": st_balance,
            "ending_balance": perf.get("ending_balance", st_balance + trade_stats["gross_profit"] - trade_stats["gross_loss"] - trade_stats["total_fees"] - trade_stats["total_slippage"]),
            "gross_pnl": perf.get("gross_pnl", trade_stats["gross_profit"] - trade_stats["gross_loss"]),
            "net_pnl": perf.get("net_pnl", trade_stats["gross_profit"] - trade_stats["gross_loss"] - trade_stats["total_fees"] - trade_stats["total_slippage"]),
            "return_pct": ret_pct,
            "target_status": perf.get("target_status", "NORMAL"),
            "stop_status": perf.get("stop_status", "NORMAL"),
            "trade_stats": trade_stats,
            "drawdown": dd_stats,
            "risk_ratios": risk_ratios,
            "trades": trades,
        }

    def compute_daily_session_analytics(self, session_id: str) -> Dict[str, Any]:
        """
        Aggregates analytics for all 8 models for a specific session,
        computes executive summary totals and deterministic leaderboard.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM daily_sessions WHERE session_id = ?", (session_id,))
            sess_row = cursor.fetchone()
            session = dict(sess_row) if sess_row else {"session_id": session_id, "session_date": "UNKNOWN"}

            cursor.execute("SELECT DISTINCT model_id FROM daily_performance WHERE session_id = ?", (session_id,))
            model_ids = [r["model_id"] for r in cursor.fetchall()]
            if not model_ids:
                cursor.execute("SELECT DISTINCT model_id FROM accounts")
                model_ids = [r["model_id"] for r in cursor.fetchall()]

        model_results = []
        for mid in model_ids:
            res = self.compute_daily_model_analytics(session_id, mid)
            model_results.append(res)

        # Leaderboard ranking
        leaderboard_rows = []
        for mr in model_results:
            row = {
                "model_id": mr["model_id"],
                "starting_balance": mr["starting_balance"],
                "ending_balance": mr["ending_balance"],
                "gross_pnl": mr["gross_pnl"],
                "net_pnl": mr["net_pnl"],
                "return_pct": mr["return_pct"],
                "trades_count": mr["trade_stats"]["total_trades"],
                "winning_trades_count": mr["trade_stats"]["winning_trades"],
                "losing_trades_count": mr["trade_stats"]["losing_trades"],
                "win_rate": mr["trade_stats"]["win_rate"],
                "profit_factor": mr["trade_stats"]["profit_factor"],
                "profit_factor_num": mr["trade_stats"]["profit_factor_num"],
                "max_drawdown": mr["drawdown"]["max_drawdown_pct"],
                "target_status": mr["target_status"],
                "stop_status": mr["stop_status"],
                "sharpe": mr["risk_ratios"]["sharpe"],
            }
            leaderboard_rows.append(row)

        ranked_leaderboard = rank_leaderboard(leaderboard_rows)

        # Executive summary rollups
        total_starting_equity = sum(r["starting_balance"] for r in ranked_leaderboard)
        total_ending_equity = sum(r["ending_balance"] for r in ranked_leaderboard)
        total_net_pnl = sum(r["net_pnl"] for r in ranked_leaderboard)
        total_gross_pnl = sum(r["gross_pnl"] for r in ranked_leaderboard)
        total_trades = sum(r["trades_count"] for r in ranked_leaderboard)
        total_wins = sum(r["winning_trades_count"] for r in ranked_leaderboard)
        total_losses = sum(r["losing_trades_count"] for r in ranked_leaderboard)
        total_fees = sum(mr["trade_stats"]["total_fees"] for mr in model_results)
        total_slippage = sum(mr["trade_stats"]["total_slippage"] for mr in model_results)
        overall_return_pct = round((total_net_pnl / total_starting_equity) * 100.0, 2) if total_starting_equity > 0 else 0.0
        overall_win_rate = round((total_wins / total_trades) * 100.0, 2) if total_trades > 0 else 0.0

        targets_reached = sum(1 for r in ranked_leaderboard if r["target_status"] == "TARGET_REACHED")
        stops_triggered = sum(1 for r in ranked_leaderboard if r["stop_status"] == "STOP_TRIGGERED")

        best_model = ranked_leaderboard[0]["model_id"] if ranked_leaderboard else "N/A"
        worst_model = ranked_leaderboard[-1]["model_id"] if ranked_leaderboard else "N/A"

        return {
            "session": session,
            "executive_summary": {
                "session_id": session_id,
                "session_date": session.get("session_date", "UNKNOWN"),
                "total_models": len(ranked_leaderboard),
                "total_starting_equity": round(total_starting_equity, 2),
                "total_ending_equity": round(total_ending_equity, 2),
                "total_gross_pnl": round(total_gross_pnl, 2),
                "total_net_pnl": round(total_net_pnl, 2),
                "overall_return_pct": overall_return_pct,
                "total_trades": total_trades,
                "total_wins": total_wins,
                "total_losses": total_losses,
                "overall_win_rate": overall_win_rate,
                "total_fees": round(total_fees, 2),
                "total_slippage": round(total_slippage, 2),
                "targets_reached_count": targets_reached,
                "stops_triggered_count": stops_triggered,
                "best_performing_model": best_model,
                "worst_performing_model": worst_model,
            },
            "leaderboard": ranked_leaderboard,
            "models_analytics": model_results,
        }

    def compute_symbol_analytics(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Aggregates performance by traded equity symbol."""
        query = "SELECT * FROM paper_trades WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        query += " ORDER BY symbol ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            trades = [dict(r) for r in cursor.fetchall()]

        symbols_map: Dict[str, List[Dict[str, Any]]] = {}
        for t in trades:
            sym = t["symbol"]
            symbols_map.setdefault(sym, []).append(t)

        results = []
        for sym, sym_trades in symbols_map.items():
            stats = calculate_trade_statistics(sym_trades)
            net_pnl = sum(t["net_pnl"] for t in sym_trades)
            gross_pnl = sum(t["gross_pnl"] for t in sym_trades)
            results.append({
                "symbol": sym,
                "total_trades": len(sym_trades),
                "winning_trades": stats["winning_trades"],
                "losing_trades": stats["losing_trades"],
                "win_rate": stats["win_rate"],
                "gross_pnl": round(gross_pnl, 2),
                "net_pnl": round(net_pnl, 2),
                "profit_factor": stats["profit_factor"],
                "total_fees": stats["total_fees"],
                "total_slippage": stats["total_slippage"],
            })

        results.sort(key=lambda x: x["net_pnl"], reverse=True)
        return results

    def compute_hourly_analytics(self, session_id: str) -> List[Dict[str, Any]]:
        """Buckets trade executions into hourly intervals (09:00 - 15:00 IST)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM paper_trades WHERE session_id = ?", (session_id,))
            trades = [dict(r) for r in cursor.fetchall()]

        hourly_buckets: Dict[int, List[Dict[str, Any]]] = {h: [] for h in range(9, 16)}
        for t in trades:
            entry_time_str = t["entry_time"]
            try:
                dt = datetime.fromisoformat(entry_time_str)
                hour = dt.hour
                if hour in hourly_buckets:
                    hourly_buckets[hour].append(t)
            except Exception:
                continue

        results = []
        for h in range(9, 16):
            b_trades = hourly_buckets[h]
            stats = calculate_trade_statistics(b_trades)
            results.append({
                "hour": f"{h:02d}:00 - {h+1:02d}:00",
                "trade_count": len(b_trades),
                "win_rate": stats["win_rate"],
                "net_pnl": round(sum(t["net_pnl"] for t in b_trades), 2),
            })
        return results

    def reconcile_trading_data(self, session_id: str) -> Dict[str, Any]:
        """
        Validates mathematical and accounting consistency:
        1. Trades vs Fills: every trade must have valid entry and exit fills.
        2. Fills vs Orders: every execution must map to a known order.
        3. Starting Equity + Net P&L == Ending Equity for each model.
        4. No orphaned executions.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM paper_orders WHERE session_id = ?", (session_id,))
            orders = {r["order_id"]: dict(r) for r in cursor.fetchall()}

            cursor.execute("""
                SELECT f.* FROM paper_fills f
                JOIN paper_orders o ON f.order_id = o.order_id
                WHERE o.session_id = ?
            """, (session_id,))
            fills = {r["execution_id"]: dict(r) for r in cursor.fetchall()}

            cursor.execute("SELECT * FROM paper_trades WHERE session_id = ?", (session_id,))
            trades = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM daily_performance WHERE session_id = ?", (session_id,))
            perf_records = {r["model_id"]: dict(r) for r in cursor.fetchall()}

        discrepancies: List[str] = []
        model_balances: Dict[str, Dict[str, Any]] = {}

        # 1. Validate Trades vs Fills
        for t in trades:
            entry_fill = fills.get(t["entry_execution_id"])
            if not entry_fill:
                discrepancies.append(f"Trade {t['trade_id']} missing entry execution {t['entry_execution_id']}")

            if t["is_closed"] and t.get("exit_execution_id"):
                exit_fill = fills.get(t["exit_execution_id"])
                if not exit_fill:
                    discrepancies.append(f"Trade {t['trade_id']} missing exit execution {t['exit_execution_id']}")

        # 2. Validate Fills vs Orders
        for fid, fill in fills.items():
            if fill["order_id"] not in orders:
                discrepancies.append(f"Execution {fid} references unknown order {fill['order_id']}")

        # 3. Validate Ledger Equation: Start + Net P&L (+ embedded slippage) = End
        for mid, perf in perf_records.items():
            model_trades = [t for t in trades if t["model_id"] == mid]
            sum_net_pnl = sum(t["net_pnl"] for t in model_trades)
            sum_slippage = sum(t["total_slippage"] for t in model_trades)
            st_bal = perf["starting_balance"]
            end_bal = perf["ending_balance"]

            # Note: In the execution engine, trade.gross_pnl is computed from fill prices
            # (which already embed execution slippage), and trade.net_pnl explicitly deducts
            # total_slippage for conservative reporting. The cash ledger change is:
            # delta_cash = sum(net_pnl) + sum(slippage) = sum(gross_pnl - fees).
            expected_end = round(st_bal + sum_net_pnl + sum_slippage, 2)
            actual_end = round(end_bal, 2)

            diff = round(abs(expected_end - actual_end), 2)
            is_match = diff < 0.05  # Allowing rounding tolerance

            if not is_match:
                discrepancies.append(
                    f"Ledger mismatch for {mid}: start={st_bal} + net_pnl={sum_net_pnl} + slippage={sum_slippage} "
                    f"-> expected={expected_end} != actual={actual_end} (diff={diff})"
                )

            model_balances[mid] = {
                "starting_balance": st_bal,
                "trade_sum_net_pnl": round(sum_net_pnl, 2),
                "perf_net_pnl": perf["net_pnl"],
                "ending_balance": actual_end,
                "expected_ending_balance": expected_end,
                "is_balanced": is_match,
            }

        return {
            "session_id": session_id,
            "is_reconciled": len(discrepancies) == 0,
            "discrepancies_count": len(discrepancies),
            "discrepancies": discrepancies,
            "model_reconciliation": model_balances,
            "total_orders": len(orders),
            "total_fills": len(fills),
            "total_trades": len(trades),
        }
