"""
Unit tests for Performance Analytics Engine and Metrics.
"""

import pytest
from datetime import datetime, timezone

from mobitrade.analytics.metrics import (
    calculate_gross_pnl,
    calculate_net_pnl,
    calculate_return_pct,
    calculate_trade_statistics,
    calculate_drawdown,
    calculate_risk_adjusted_ratios
)
from mobitrade.analytics.tournament import rank_leaderboard, compute_tournament_standings


def test_pnl_mathematical_precision():
    # 10 shares bought at 2500, sold at 2550
    gross = calculate_gross_pnl(2500.0, 2550.0, 10)
    assert gross == 500.0

    # Total fees 15.50, slippage 2.50
    net = calculate_net_pnl(gross, 15.50, 2.50)
    assert net == 482.0

    ret_pct = calculate_return_pct(net, 10000.0)
    assert ret_pct == 4.82


def test_trade_statistics_edge_cases():
    # Zero trades
    empty_stats = calculate_trade_statistics([])
    assert empty_stats["total_trades"] == 0
    assert empty_stats["win_rate"] == 0.0
    assert empty_stats["profit_factor"] == "N/A"

    # All winning trades (zero losses -> profit factor safe)
    trades_wins = [
        {"net_pnl": 100.0, "gross_pnl": 110.0, "total_fees": 8.0, "total_slippage": 2.0},
        {"net_pnl": 50.0, "gross_pnl": 55.0, "total_fees": 4.0, "total_slippage": 1.0},
    ]
    win_stats = calculate_trade_statistics(trades_wins)
    assert win_stats["total_trades"] == 2
    assert win_stats["winning_trades"] == 2
    assert win_stats["win_rate"] == 100.0
    assert win_stats["profit_factor"] == "N/A"
    assert win_stats["profit_factor_num"] == 999.0

    # Normal mix
    mixed_trades = [
        {"net_pnl": 100.0, "gross_pnl": 105.0, "total_fees": 4.0, "total_slippage": 1.0},
        {"net_pnl": -50.0, "gross_pnl": -45.0, "total_fees": 4.0, "total_slippage": 1.0},
    ]
    mixed_stats = calculate_trade_statistics(mixed_trades)
    assert mixed_stats["total_trades"] == 2
    assert mixed_stats["winning_trades"] == 1
    assert mixed_stats["losing_trades"] == 1
    assert mixed_stats["win_rate"] == 50.0
    assert mixed_stats["profit_factor"] == 2.33


def test_drawdown_peak_and_recovery():
    # Equity series: 1000 -> 1100 (peak) -> 1045 (drop 55) -> 1120 (recovered)
    t0 = datetime(2026, 9, 11, 9, 15, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 11, 11, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)

    series = [(t0, 1000.0), (t1, 1100.0), (t2, 1045.0), (t3, 1120.0)]
    dd = calculate_drawdown(series)

    assert dd["peak_equity"] == 1100.0
    assert dd["trough_equity"] == 1045.0
    assert dd["max_drawdown_amount"] == 55.0
    assert dd["max_drawdown_pct"] == 5.0
    assert dd["peak_time"] == str(t1)
    assert dd["trough_time"] == str(t2)
    assert dd["recovery_time"] == str(t3)
    assert dd["recovery_duration_seconds"] == 7200  # 2 hours from peak to recovery


def test_risk_adjusted_ratios_safety():
    # Sample < 3 must return "N/A"
    res_small = calculate_risk_adjusted_ratios([0.02, 0.01])
    assert res_small["sharpe"] == "N/A"
    assert res_small["sortino"] == "N/A"
    assert res_small["calmar"] == "N/A"

    # Zero variance must return "N/A"
    res_zero_var = calculate_risk_adjusted_ratios([0.01, 0.01, 0.01, 0.01])
    assert res_zero_var["sharpe"] == "N/A"
    assert res_zero_var["sortino"] == "N/A"

    # Sufficient sample with variance
    returns = [0.03, -0.01, 0.02, 0.01, -0.005]
    res_valid = calculate_risk_adjusted_ratios(returns, max_drawdown_pct=2.5, cumulative_return_pct=4.5)
    assert isinstance(res_valid["sharpe"], float)
    assert isinstance(res_valid["sortino"], float)
    assert isinstance(res_valid["calmar"], float)


def test_leaderboard_tie_breaking():
    # Model A: Net 100, Ret 10%, DD 2%, PF 3.0, Trades 5
    # Model B: Net 100, Ret 10%, DD 1%, PF 2.0, Trades 4 (smaller DD wins tie)
    # Model C: Net 80, Ret 8%, DD 0.5%, PF 5.0, Trades 10
    models = [
        {"model_id": "model_a", "net_pnl": 100.0, "return_pct": 10.0, "max_drawdown": 2.0, "profit_factor": 3.0, "trades_count": 5},
        {"model_id": "model_b", "net_pnl": 100.0, "return_pct": 10.0, "max_drawdown": 1.0, "profit_factor": 2.0, "trades_count": 4},
        {"model_id": "model_c", "net_pnl": 80.0, "return_pct": 8.0, "max_drawdown": 0.5, "profit_factor": 5.0, "trades_count": 10},
    ]
    ranked = rank_leaderboard(models)
    assert ranked[0]["model_id"] == "model_b"  # Smaller drawdown breaks tie
    assert ranked[0]["rank"] == 1
    assert ranked[1]["model_id"] == "model_a"
    assert ranked[1]["rank"] == 2
    assert ranked[2]["model_id"] == "model_c"
    assert ranked[2]["rank"] == 3
