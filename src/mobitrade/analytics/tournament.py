"""
8-Model Tournament Leaderboard & Standings Engine.
Deterministic rankings with strict tie-breaking hierarchy:
1. Net P&L (descending)
2. Return % (descending)
3. Maximum Drawdown % (ascending / smallest loss)
4. Profit Factor (descending)
5. Total Trade Count (descending)
"""

from typing import List, Dict, Any, Optional


def rank_leaderboard(model_performances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ranks model performance records deterministically based on institutional criteria.
    Assigns rank (1-indexed).
    """
    def _sort_key(item: Dict[str, Any]):
        net_pnl = float(item.get("net_pnl", 0.0))
        ret_pct = float(item.get("return_pct", 0.0))
        dd_pct = float(item.get("max_drawdown", item.get("max_drawdown_pct", 0.0)))
        
        # Profit factor handling
        pf = item.get("profit_factor_num", item.get("profit_factor", 0.0))
        if pf == "N/A" or pf is None:
            pf_val = 0.0
        else:
            try:
                pf_val = float(pf)
            except (ValueError, TypeError):
                pf_val = 0.0

        trade_count = int(item.get("trades_count", item.get("total_trades", 0)))

        # 1. net_pnl DESC -> -net_pnl
        # 2. ret_pct DESC -> -ret_pct
        # 3. dd_pct ASC -> dd_pct
        # 4. pf_val DESC -> -pf_val
        # 5. trade_count DESC -> -trade_count
        return (-net_pnl, -ret_pct, dd_pct, -pf_val, -trade_count)

    sorted_list = sorted(model_performances, key=_sort_key)
    
    ranked = []
    for idx, item in enumerate(sorted_list, start=1):
        record = dict(item)
        record["rank"] = idx
        ranked.append(record)

    return ranked


def compute_tournament_standings(daily_records_by_session: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Computes multi-session cumulative tournament standings for the 8 models.
    Aggregates:
    - Cumulative Net P&L
    - Cumulative Return %
    - Overall Win Rate
    - Total Trades
    - Profitable Sessions Count
    - Target Reached Count
    - Average Daily Rank
    """
    models_data: Dict[str, Dict[str, Any]] = {}

    for session_perf in daily_records_by_session:
        ranked = rank_leaderboard(session_perf)
        for row in ranked:
            mid = row["model_id"]
            if mid not in models_data:
                models_data[mid] = {
                    "model_id": mid,
                    "cumulative_net_pnl": 0.0,
                    "cumulative_gross_pnl": 0.0,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "total_fees": 0.0,
                    "total_slippage": 0.0,
                    "sessions_count": 0,
                    "profitable_sessions": 0,
                    "targets_hit": 0,
                    "stops_hit": 0,
                    "rank_sum": 0,
                    "starting_equity_initial": row.get("starting_balance", 1000.0),
                    "latest_equity": row.get("ending_balance", 1000.0),
                }

            entry = models_data[mid]
            entry["cumulative_net_pnl"] += row.get("net_pnl", 0.0)
            entry["cumulative_gross_pnl"] += row.get("gross_pnl", 0.0)
            entry["total_trades"] += row.get("trades_count", 0)
            entry["winning_trades"] += row.get("winning_trades_count", 0)
            entry["losing_trades"] += row.get("losing_trades_count", 0)
            entry["total_fees"] += row.get("total_fees", 0.0)
            entry["total_slippage"] += row.get("total_slippage", 0.0)
            entry["sessions_count"] += 1
            if row.get("net_pnl", 0.0) > 0:
                entry["profitable_sessions"] += 1
            if row.get("target_status") == "TARGET_REACHED":
                entry["targets_hit"] += 1
            if row.get("stop_status") == "STOP_TRIGGERED":
                entry["stops_hit"] += 1
            entry["rank_sum"] += row["rank"]
            entry["latest_equity"] = row.get("ending_balance", entry["latest_equity"])

    standings = []
    for mid, data in models_data.items():
        sess_cnt = data["sessions_count"]
        tot_trades = data["total_trades"]
        win_rate = round((data["winning_trades"] / tot_trades) * 100.0, 2) if tot_trades > 0 else 0.0
        avg_rank = round(data["rank_sum"] / sess_cnt, 2) if sess_cnt > 0 else 0.0
        initial_eq = data["starting_equity_initial"]
        cum_ret = round((data["cumulative_net_pnl"] / initial_eq) * 100.0, 2) if initial_eq > 0 else 0.0

        standings.append({
            "model_id": mid,
            "cumulative_net_pnl": round(data["cumulative_net_pnl"], 2),
            "cumulative_gross_pnl": round(data["cumulative_gross_pnl"], 2),
            "cumulative_return_pct": cum_ret,
            "total_trades": tot_trades,
            "overall_win_rate": win_rate,
            "sessions_played": sess_cnt,
            "profitable_sessions": data["profitable_sessions"],
            "consistency_pct": round((data["profitable_sessions"] / sess_cnt) * 100.0, 1) if sess_cnt > 0 else 0.0,
            "targets_hit": data["targets_hit"],
            "stops_hit": data["stops_hit"],
            "average_rank": avg_rank,
            "latest_equity": round(data["latest_equity"], 2),
        })

    # Sort cumulative standings by cumulative net pnl descending
    standings.sort(key=lambda x: (x["cumulative_net_pnl"], x["cumulative_return_pct"], -x["average_rank"]), reverse=True)
    for idx, s in enumerate(standings, start=1):
        s["tournament_rank"] = idx

    return standings
