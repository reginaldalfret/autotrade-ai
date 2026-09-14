"""
CLI commands for Performance Analytics & Tournament Standings.
"""

import click
from tabulate import tabulate
from mobitrade.analytics.engine import PerformanceAnalyticsEngine
from mobitrade.analytics.tournament import compute_tournament_standings


@click.group()
def analytics_cli():
    """Performance analytics, leaderboard, and tournament commands."""
    pass


@analytics_cli.command(name="leaderboard")
@click.option("--session", "session_id", default=None, help="Session ID")
@click.option("--date", "session_date", default=None, help="Date (YYYY-MM-DD)")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def analytics_leaderboard(session_id, session_date, db_path):
    """Display 8-model tournament leaderboard for a session."""
    engine = PerformanceAnalyticsEngine(db_path=db_path)
    target = session_id or session_date
    if not target:
        # Get latest session
        with engine._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, session_date FROM daily_sessions ORDER BY started_at DESC LIMIT 1")
            r = cursor.fetchone()
            if not r:
                click.secho("No trading sessions found in database.", fg="yellow")
                return
            target = r["session_id"]

    data = engine.compute_daily_session_analytics(target)
    leaderboard = data["leaderboard"]
    exec_sum = data["executive_summary"]

    click.echo("==================================================")
    click.echo(f"AutoTrade AI — Leaderboard: {exec_sum['session_date']} ({exec_sum['session_id']})")
    click.echo("==================================================")

    table = []
    for r in leaderboard:
        pf_str = f"{r['profit_factor']:.2f}" if isinstance(r["profit_factor"], (int, float)) else str(r["profit_factor"])
        table.append([
            r["rank"],
            r["model_id"],
            f"₹{r['starting_balance']:,.1f}",
            f"₹{r['ending_balance']:,.1f}",
            f"₹{r['net_pnl']:+,.2f}",
            f"{r['return_pct']:+.2f}%",
            r["trades_count"],
            f"{r['win_rate']:.1f}%",
            pf_str,
            f"{r['max_drawdown']:.1f}%",
            r["target_status"]
        ])

    headers = ["Rank", "Model", "Start", "End", "Net P&L", "Return %", "Trades", "Win Rate", "PF", "Max DD", "Status"]
    click.echo(tabulate(table, headers=headers, tablefmt="grid"))


@analytics_cli.command(name="daily")
@click.option("--session", "session_id", default=None, help="Session ID")
@click.option("--date", "session_date", default=None, help="Date (YYYY-MM-DD)")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def analytics_daily(session_id, session_date, db_path):
    """Display executive performance summary for a trading day."""
    engine = PerformanceAnalyticsEngine(db_path=db_path)
    target = session_id or session_date
    if not target:
        with engine._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, session_date FROM daily_sessions ORDER BY started_at DESC LIMIT 1")
            r = cursor.fetchone()
            if not r:
                click.secho("No trading sessions found in database.", fg="yellow")
                return
            target = r["session_id"]

    data = engine.compute_daily_session_analytics(target)
    ex = data["executive_summary"]

    click.echo("==================================================")
    click.echo(f"AutoTrade AI — Daily Executive Summary: {ex['session_date']}")
    click.echo("==================================================")
    click.echo(f"Session ID:             {ex['session_id']}")
    click.echo(f"Active Models:          {ex['total_models']}")
    click.echo(f"Total Initial Capital:  ₹{ex['total_starting_equity']:,.2f}")
    click.echo(f"Total Final Capital:    ₹{ex['total_ending_equity']:,.2f}")
    click.echo(f"Total Gross P&L:        ₹{ex['total_gross_pnl']:+,.2f}")
    click.echo(f"Total Net P&L:          ₹{ex['total_net_pnl']:+,.2f}")
    click.echo(f"Overall Return %:       {ex['overall_return_pct']:+.2f}%")
    click.echo(f"Total Completed Trades: {ex['total_trades']} ({ex['total_wins']}W / {ex['total_losses']}L)")
    click.echo(f"Aggregate Win Rate:     {ex['overall_win_rate']:.2f}%")
    click.echo(f"Statutory Fees:         ₹{ex['total_fees']:,.2f}")
    click.echo(f"Execution Slippage:     ₹{ex['total_slippage']:,.2f}")
    click.echo(f"Target Hit (+10%):      {ex['targets_reached_count']} Models")
    click.echo(f"Stop Hit (-5%):         {ex['stops_triggered_count']} Models")
    click.echo(f"Top Performer:          {ex['best_performing_model'].upper()}")
    click.echo(f"Lowest Performer:       {ex['worst_performing_model'].upper()}")


@analytics_cli.command(name="model")
@click.argument("model_id")
@click.option("--session", "session_id", default=None, help="Session ID")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def analytics_model(model_id, session_id, db_path):
    """Display detailed metrics deep dive for a single model."""
    engine = PerformanceAnalyticsEngine(db_path=db_path)
    if not session_id:
        with engine._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id FROM daily_sessions ORDER BY started_at DESC LIMIT 1")
            r = cursor.fetchone()
            if not r:
                click.secho("No trading sessions found.", fg="yellow")
                return
            session_id = r["session_id"]

    res = engine.compute_daily_model_analytics(session_id, model_id)
    ts = res["trade_stats"]
    dd = res["drawdown"]
    rr = res["risk_ratios"]

    click.echo("==================================================")
    click.echo(f"AutoTrade AI — Model Profile: {model_id.upper()}")
    click.echo("==================================================")
    click.echo(f"Session:                {session_id}")
    click.echo(f"Capital:                ₹{res['starting_balance']:,.2f} -> ₹{res['ending_balance']:,.2f}")
    click.echo(f"Net P&L:                ₹{res['net_pnl']:+,.2f} ({res['return_pct']:+.2f}%)")
    click.echo(f"Target / Stop Status:   {res['target_status']} / {res['stop_status']}")
    click.echo(f"Trades Executed:        {ts['total_trades']} ({ts['winning_trades']}W / {ts['losing_trades']}L)")
    click.echo(f"Win Rate:               {ts['win_rate']:.2f}%")
    click.echo(f"Profit Factor:          {ts['profit_factor']}")
    click.echo(f"Average Win / Loss:     ₹{ts['average_win']:.2f} / ₹{ts['average_loss']:.2f}")
    click.echo(f"Largest Win / Loss:     ₹{ts['largest_win']:.2f} / ₹{ts['largest_loss']:.2f}")
    click.echo(f"Max Drawdown:           ₹{dd['max_drawdown_amount']:.2f} ({dd['max_drawdown_pct']:.2f}%)")
    click.echo(f"Sharpe / Sortino:       {rr['sharpe']} / {rr['sortino']}")
    click.echo(f"Fees / Slippage:        ₹{ts['total_fees']:.2f} / ₹{ts['total_slippage']:.2f}")


@analytics_cli.command(name="symbol")
@click.option("--session", "session_id", default=None, help="Session ID")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def analytics_symbol(session_id, db_path):
    """Display trading performance grouped by equity symbol."""
    engine = PerformanceAnalyticsEngine(db_path=db_path)
    symbols = engine.compute_symbol_analytics(session_id=session_id)
    if not symbols:
        click.echo("No trades found for symbol analytics.")
        return

    table = []
    for s in symbols:
        pf_str = f"{s['profit_factor']:.2f}" if isinstance(s["profit_factor"], (int, float)) else str(s["profit_factor"])
        table.append([
            s["symbol"],
            s["total_trades"],
            s["winning_trades"],
            s["losing_trades"],
            f"{s['win_rate']:.1f}%",
            f"₹{s['gross_pnl']:+,.2f}",
            f"₹{s['net_pnl']:+,.2f}",
            pf_str
        ])

    headers = ["Symbol", "Trades", "Wins", "Losses", "Win Rate", "Gross P&L", "Net P&L", "Profit Factor"]
    click.echo(f"\nSymbol Performance Breakdown ({len(symbols)} traded symbols):")
    click.echo(tabulate(table, headers=headers, tablefmt="grid"))


@analytics_cli.command(name="reconcile")
@click.argument("session_id")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def analytics_reconcile(session_id, db_path):
    """Run strict mathematical data and ledger reconciliation."""
    engine = PerformanceAnalyticsEngine(db_path=db_path)
    res = engine.reconcile_trading_data(session_id)

    click.echo("==================================================")
    click.echo(f"AutoTrade AI — Data Reconciliation: {session_id}")
    click.echo("==================================================")
    click.echo(f"Total Orders:        {res['total_orders']}")
    click.echo(f"Total Fills:         {res['total_fills']}")
    click.echo(f"Total Trades:        {res['total_trades']}")

    if res["is_reconciled"]:
        click.secho("\n[PASS] LEDGER AND TRADES 100% RECONCILED", fg="green", bold=True)
        click.echo("Orders, fills, trades, and portfolio cash ledgers match to zero discrepancy.")
    else:
        click.secho(f"\n[FAIL] RECONCILIATION FAILED: {res['discrepancies_count']} Discrepancies", fg="red", bold=True)
        for d in res["discrepancies"]:
            click.echo(f" - {d}")
