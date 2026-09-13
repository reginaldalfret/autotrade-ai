"""
Mathematical Performance Metrics Engine.
Deterministic, pure functions for computing P&L, Drawdowns,
Risk-Adjusted Ratios, and Trade Statistics without state mutation.
"""

import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union


def calculate_gross_pnl(entry_price: float, exit_price: float, quantity: int) -> float:
    """Gross P&L = (Exit Price - Entry Price) * Quantity"""
    return round((exit_price - entry_price) * quantity, 4)


def calculate_net_pnl(gross_pnl: float, total_fees: float, total_slippage: float) -> float:
    """Net P&L = Gross P&L - Total Statutory Fees - Total Slippage"""
    return round(gross_pnl - total_fees - total_slippage, 4)


def calculate_return_pct(net_pnl: float, starting_balance: float) -> float:
    """Return % = (Net P&L / Starting Balance) * 100"""
    if starting_balance <= 0:
        return 0.0
    return round((net_pnl / starting_balance) * 100.0, 4)


def calculate_trade_statistics(trades: List[Any]) -> Dict[str, Any]:
    """
    Calculates comprehensive trade distribution statistics.
    Handles empty trade lists and zero losses gracefully.
    """
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "win_loss_ratio": "N/A",
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "profit_factor": "N/A",
            "profit_factor_num": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "total_fees": 0.0,
            "total_slippage": 0.0,
        }

    wins = []
    losses = []
    breakeven = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_fees = 0.0
    total_slippage = 0.0

    for t in trades:
        net_pnl = t.net_pnl if hasattr(t, "net_pnl") else t["net_pnl"]
        gross = t.gross_pnl if hasattr(t, "gross_pnl") else t["gross_pnl"]
        fees = t.total_fees if hasattr(t, "total_fees") else t["total_fees"]
        slip = t.total_slippage if hasattr(t, "total_slippage") else t["total_slippage"]

        total_fees += fees
        total_slippage += slip

        if net_pnl > 0:
            wins.append(net_pnl)
            gross_profit += max(0.0, gross)
        elif net_pnl < 0:
            losses.append(net_pnl)
            gross_loss += abs(min(0.0, gross))
        else:
            breakeven += 1

    winning_count = len(wins)
    losing_count = len(losses)
    win_rate = round((winning_count / total_trades) * 100.0, 2)
    loss_rate = round((losing_count / total_trades) * 100.0, 2)

    avg_win = round(sum(wins) / winning_count, 2) if winning_count > 0 else 0.0
    avg_loss = round(sum(losses) / losing_count, 2) if losing_count > 0 else 0.0

    if avg_loss != 0:
        win_loss_ratio = round(avg_win / abs(avg_loss), 2)
    else:
        win_loss_ratio = "N/A"

    largest_win = round(max(wins), 2) if wins else 0.0
    largest_loss = round(min(losses), 2) if losses else 0.0

    if gross_loss > 0:
        pf_num = round(gross_profit / gross_loss, 2)
        profit_factor = pf_num
    else:
        pf_num = 999.0 if gross_profit > 0 else 0.0
        profit_factor = "N/A"

    return {
        "total_trades": total_trades,
        "winning_trades": winning_count,
        "losing_trades": losing_count,
        "breakeven_trades": breakeven,
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "average_win": avg_win,
        "average_loss": avg_loss,
        "win_loss_ratio": win_loss_ratio,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "profit_factor": profit_factor,
        "profit_factor_num": pf_num,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "total_fees": round(total_fees, 2),
        "total_slippage": round(total_slippage, 2),
    }


def calculate_drawdown(equity_series: List[Tuple[Any, float]]) -> Dict[str, Any]:
    """
    Computes Maximum Drawdown, peak-to-trough drop, peak timestamp,
    trough timestamp, recovery timestamp, and duration.
    Input: list of (timestamp, equity) ordered chronologically.
    """
    if not equity_series or len(equity_series) < 2:
        val = equity_series[0][1] if equity_series else 0.0
        ts_val = str(equity_series[0][0]) if equity_series else None
        return {
            "max_drawdown_amount": 0.0,
            "max_drawdown_pct": 0.0,
            "peak_equity": val,
            "trough_equity": val,
            "peak_time": ts_val,
            "trough_time": ts_val,
            "recovery_time": None,
            "recovery_duration_seconds": None,
        }

    running_peak = equity_series[0][1]
    running_peak_time = equity_series[0][0]

    max_dd_amount = 0.0
    max_dd_pct = 0.0
    best_peak = running_peak
    best_peak_time = running_peak_time
    best_trough = running_peak
    best_trough_time = running_peak_time

    for ts, eq in equity_series:
        if eq > running_peak:
            running_peak = eq
            running_peak_time = ts
        else:
            dd_amount = running_peak - eq
            dd_pct = (dd_amount / running_peak) * 100.0 if running_peak > 0 else 0.0

            if dd_amount > max_dd_amount:
                max_dd_amount = dd_amount
                max_dd_pct = dd_pct
                best_peak = running_peak
                best_peak_time = running_peak_time
                best_trough = eq
                best_trough_time = ts

    # Find recovery after best_trough_time
    recovery_time = None
    recovery_duration_seconds = None
    found_trough = False
    for ts, eq in equity_series:
        if ts == best_trough_time:
            found_trough = True
            continue
        if found_trough and eq >= best_peak:
            recovery_time = ts
            if isinstance(recovery_time, datetime) and isinstance(best_peak_time, datetime):
                recovery_duration_seconds = int((recovery_time - best_peak_time).total_seconds())
            break

    return {
        "max_drawdown_amount": round(max_dd_amount, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "peak_equity": round(best_peak, 2),
        "trough_equity": round(best_trough, 2),
        "peak_time": str(best_peak_time),
        "trough_time": str(best_trough_time),
        "recovery_time": str(recovery_time) if recovery_time else None,
        "recovery_duration_seconds": recovery_duration_seconds,
    }


def calculate_risk_adjusted_ratios(
    trade_returns: List[float],
    annual_risk_free_rate: float = 0.06,
    max_drawdown_pct: float = 0.0,
    cumulative_return_pct: float = 0.0
) -> Dict[str, Any]:
    """
    Computes Sharpe, Sortino, and Calmar ratios.
    Enforces strict statistical safety:
    - Sample size < 3 returns 'N/A'.
    - Zero variance returns 'N/A'.
    - Zero drawdown returns 'N/A' for Calmar.
    """
    result = {
        "sharpe": "N/A",
        "sortino": "N/A",
        "calmar": "N/A",
        "volatility": "N/A",
    }

    n = len(trade_returns)
    if n < 3:
        return result

    # Mean trade return
    mean_ret = sum(trade_returns) / n

    # Variance and standard deviation
    variance = sum((r - mean_ret) ** 2 for r in trade_returns) / (n - 1)
    if variance <= 1e-9:
        return result

    std_dev = math.sqrt(variance)
    annualized_vol = std_dev * math.sqrt(252)
    result["volatility"] = round(annualized_vol, 4)

    # Per-trade risk free rate (assuming 252 trading days)
    rf_per_trade = (annual_risk_free_rate / 252.0)

    # Sharpe ratio
    sharpe = ((mean_ret - rf_per_trade) / std_dev) * math.sqrt(252)
    result["sharpe"] = round(sharpe, 2)

    # Sortino ratio: downside deviation
    negative_excess = [min(0.0, r - rf_per_trade) for r in trade_returns]
    downside_var = sum(ne ** 2 for ne in negative_excess) / (n - 1)
    if downside_var > 1e-9:
        downside_std = math.sqrt(downside_var)
        sortino = ((mean_ret - rf_per_trade) / downside_std) * math.sqrt(252)
        result["sortino"] = round(sortino, 2)
    else:
        result["sortino"] = "N/A"

    # Calmar ratio: Annualized return / Max Drawdown %
    if max_drawdown_pct > 0:
        annualized_return = cumulative_return_pct * (252.0 / 1.0)
        calmar = annualized_return / max_drawdown_pct
        result["calmar"] = round(calmar, 2)
    else:
        result["calmar"] = "N/A"

    return result
