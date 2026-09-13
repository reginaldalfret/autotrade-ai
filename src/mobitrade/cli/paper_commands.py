import click
from datetime import datetime, timezone
from tabulate import tabulate

from mobitrade.paper.engine import PaperTradingEngine, DEFAULT_MODELS
from mobitrade.paper.persistence import PaperDatabaseRepository
from mobitrade.config.settings import load_yaml_config
from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.domain.data_models import Timeframe
from mobitrade.domain.llm_models import LLMDecisionRecord, LLMAction, ValidationStatus
from mobitrade.data.calendar import IST

@click.group(name="paper")
def paper_cli():
    """AutoTrade AI - Paper Trading, Portfolio Manager & Compounding Engine CLI"""
    pass

@paper_cli.command(name="status")
def paper_status():
    """Display Paper Trading & Portfolio Management status."""
    click.echo("==================================================")
    click.echo("AutoTrade AI - Paper Trading Engine Status")
    click.echo("==================================================")
    click.echo("Market:               NSE Indian Equity Cash Market")
    click.echo("Trading Session:      09:15 - 15:30 IST")
    click.echo("Square-Off Cutoff:    15:15 IST (Auto Square-Off)")
    click.echo("Overnight Policy:     STRICTLY PROHIBITED (Zero Overnight Positions)")
    click.echo("Account Model:        8 Completely Isolated Sub-Accounts")
    click.echo("Initial Capital:      ₹1,000 per Model (Total: ₹8,000)")
    click.echo("Daily Target:         +10% of Starting Session Balance (Benchmark)")
    click.echo("Daily Stop Loss:      -5% of Starting Session Balance (Hard Stop)")
    click.echo("Max Completed Trades: 20 Trades / Model / Session")
    click.echo("Order Execution:      PaperBroker (Indian Statutory Costs + 0.05% Slippage)")
    click.echo("Safety Authority:     Deterministic RiskEngine (LLM cannot override)")
    click.echo("Compounding Policy:   Daily Final Realized Equity Compounds to Next Day")
    click.echo("Database:             /mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db")

@paper_cli.command(name="accounts")
@click.option("--db-path", default="/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db")
def paper_accounts(db_path):
    """List 8 isolated model paper trading accounts and current balances."""
    repo = PaperDatabaseRepository(db_path=db_path)
    accounts = repo.list_accounts()

    if not accounts:
        # If DB not initialized, initialize standard 8 models
        engine = PaperTradingEngine(db_path=db_path)
        accounts = repo.list_accounts()

    click.echo("==================================================")
    click.echo("AutoTrade AI - Isolated Model Accounts (8 configured):")
    click.echo("==================================================")
    headers = ["Model ID", "Starting Balance", "Cash", "Target Equity", "Stop Equity", "State"]
    rows = []
    for acc in sorted(accounts, key=lambda a: a.model_id):
        rows.append([
            acc.model_id,
            f"₹{acc.starting_balance:.2f}",
            f"₹{acc.cash:.2f}",
            f"₹{acc.daily_target_equity:.2f}",
            f"₹{acc.daily_stop_equity:.2f}",
            acc.state.value
        ])
    click.echo(tabulate(rows, headers=headers, tablefmt="github"))

@paper_cli.command(name="positions")
@click.option("--model-id", default=None, help="Filter by specific model ID")
@click.option("--db-path", default="/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db")
def paper_positions(model_id, db_path):
    """Show current open positions for model accounts."""
    repo = PaperDatabaseRepository(db_path=db_path)
    open_trades = repo.list_open_trades(model_id=model_id)

    click.echo("==================================================")
    click.echo(f"AutoTrade AI - Open Paper Positions {f'({model_id})' if model_id else '(All Models)'}")
    click.echo("==================================================")
    if not open_trades:
        click.echo("No open intraday positions. All flat.")
        return

    headers = ["Trade ID", "Model ID", "Symbol", "Qty", "Entry Price", "Initial Stop", "Trailing Stop", "Entry Time"]
    rows = []
    for t in open_trades:
        rows.append([
            t.trade_id,
            t.account_id or "N/A",
            t.symbol,
            t.quantity,
            f"₹{t.entry_price:.2f}",
            f"₹{t.initial_stop:.2f}" if t.initial_stop else "-",
            f"₹{t.trailing_stop:.2f}" if t.trailing_stop else "-",
            t.entry_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        ])
    click.echo(tabulate(rows, headers=headers, tablefmt="github"))

@paper_cli.command(name="trades")
@click.option("--date", default=None, help="Session date YYYY-MM-DD")
@click.option("--model-id", default=None, help="Filter by specific model ID")
@click.option("--db-path", default="/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db")
def paper_trades(date, model_id, db_path):
    """List completed trades with gross/net P&L and statutory cost breakdowns."""
    repo = PaperDatabaseRepository(db_path=db_path)
    trades = repo.list_trades(session_id=None, model_id=model_id)

    click.echo("==================================================")
    click.echo("AutoTrade AI - Completed Trade Journal")
    click.echo("==================================================")
    if not trades:
        click.echo("No completed paper trades recorded.")
        return

    headers = ["Trade ID", "Model", "Symbol", "Qty", "Entry", "Exit", "Exit Reason", "Gross P&L", "Costs", "Net P&L"]
    rows = []
    for t in trades:
        if not t.is_closed:
            continue
        costs = t.total_fees + t.total_slippage
        rows.append([
            t.trade_id,
            t.account_id or "N/A",
            t.symbol,
            t.quantity,
            f"₹{t.entry_price:.2f}",
            f"₹{t.exit_price:.2f}" if t.exit_price else "-",
            t.exit_reason.value if t.exit_reason else "N/A",
            f"₹{t.gross_pnl:.2f}",
            f"₹{costs:.2f}",
            f"₹{t.net_pnl:.2f}"
        ])
    click.echo(tabulate(rows, headers=headers, tablefmt="github"))

@paper_cli.command(name="performance")
@click.option("--date", default=None, help="Specific session date YYYY-MM-DD")
@click.option("--db-path", default="/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db")
def paper_performance(date, db_path):
    """View daily multi-model performance leaderboard and compounding history."""
    repo = PaperDatabaseRepository(db_path=db_path)
    records = repo.get_performance_history(date=date)

    click.echo("==================================================")
    click.echo(f"AutoTrade AI - Daily Model Leaderboard {f'({date})' if date else ''}")
    click.echo("==================================================")
    if not records:
        click.echo("No performance records found.")
        return

    headers = ["Date", "Model ID", "Starting Eq", "Ending Eq", "Net P&L", "Return %", "Trades", "Win Rate", "Max DD"]
    rows = []
    for r in records:
        rows.append([
            r.get("session_date"),
            r.get("model_id"),
            f"₹{r.get('starting_equity', r.get('starting_balance', 0.0)):.2f}",
            f"₹{r.get('ending_equity', r.get('ending_balance', 0.0)):.2f}",
            f"₹{r.get('net_pnl', 0.0):.2f}",
            f"{r.get('return_pct', 0.0):+.2f}%",
            r.get("total_trades", r.get("trades_count", 0)),
            f"{r.get('win_rate', 0.0):.1f}%",
            f"{r.get('max_drawdown', 0.0):.2f}%"
        ])
    click.echo(tabulate(rows, headers=headers, tablefmt="github"))

@paper_cli.command(name="simulate")
@click.option("--date", default="2026-09-11", help="Session date to simulate YYYY-MM-DD")
@click.option("--symbol", default="TATAMOTORS", help="Stock symbol to simulate")
@click.option("--db-path", default="/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db")
def paper_simulate(date, symbol, db_path):
    """Run an end-to-end deterministic paper trading replay session."""
    engine = PaperTradingEngine(db_path=db_path)
    session_id = f"sim_{date.replace('-', '')}"
    engine.start_session(session_id, date)

    click.echo("==================================================")
    click.echo(f"AutoTrade AI - Paper Trading Daily Replay: {date}")
    click.echo(f"Session ID: {session_id} | Symbol: {symbol}")
    click.echo("==================================================")

    # 1. Simulate 10:15 IST entry decisions
    dt_1015 = datetime.fromisoformat(f"{date}T10:15:00").replace(tzinfo=IST)
    snap = MarketSnapshot(
        snapshot_id=f"snap_{date}_1015",
        symbol=symbol,
        decision_timestamp=dt_1015,
        timeframe=Timeframe.M5
    )

    market_price = 500.0
    click.echo(f"\n[10:15 IST] Frozen Snapshot Dispatched -> Sequential Evaluation of 8 Models...")

    # Deterministic signals for test replay
    model_actions = {
        "nemotron": (LLMAction.BUY, 0.85, 480.0, 550.0),
        "qwen": (LLMAction.BUY, 0.88, 485.0, 560.0),
        "gemma": (LLMAction.HOLD, 0.50, None, None),
        "llama": (LLMAction.BUY, 0.80, 480.0, 550.0),
        "granite": (LLMAction.HOLD, 0.40, None, None),
        "phi": (LLMAction.BUY, 0.82, 485.0, 550.0),
        "smollm": (LLMAction.HOLD, 0.45, None, None),
        "falcon": (LLMAction.HOLD, 0.48, None, None)
    }

    for mid in DEFAULT_MODELS:
        action, conf, sl, tgt = model_actions.get(mid, (LLMAction.HOLD, 0.5, None, None))
        rec = LLMDecisionRecord(
            decision_id=f"dec_{mid}_{session_id}",
            run_id=f"run_{session_id}",
            model_id=mid,
            model_version="1.0.0",
            prompt_version="1.0.0",
            snapshot_id=snap.snapshot_id,
            decision_timestamp=snap.decision_timestamp,
            symbol=symbol,
            action=action,
            confidence=conf,
            entry_rationale=f"Simulated {action.value} signal based on momentum.",
            proposed_stop_loss=sl,
            proposed_target=tgt,
            holding_intent="INTRADAY",
            reasoning_summary=f"Replay decision for {mid}",
            validation_status=ValidationStatus.VALID,
            raw_output=""
        )
        trade = engine.process_model_decision(rec, snap, session_id, current_market_price=market_price)
        if trade:
            click.echo(f" - {mid.ljust(10)}: BUY APPROVED -> Filled {trade.quantity} shares @ ₹{trade.entry_price:.2f}")
        else:
            click.echo(f" - {mid.ljust(10)}: {action.value} -> No trade")

    # 2. Simulate 13:00 IST price rise to ₹510.0
    dt_1300 = datetime.fromisoformat(f"{date}T13:00:00").replace(tzinfo=IST)
    click.echo(f"\n[13:00 IST] Mid-Session Tick: {symbol} at ₹510.0 (Mark-to-market & trailing stops updated)")
    engine.update_market_prices({symbol: 510.0}, dt_1300, session_id)

    # 3. Simulate 15:15 IST auto square-off at ₹520.0
    dt_1515 = datetime.fromisoformat(f"{date}T15:15:00").replace(tzinfo=IST)
    click.echo(f"\n[15:15 IST] Auto Square-Off Window Triggered -> Closing all in-flight positions...")
    engine.execute_auto_square_off({symbol: 520.0}, dt_1515, session_id)

    # 4. Finalize daily session & compound to next day
    click.echo(f"\n[15:30 IST] Session Closed -> Finalizing performance & compounding to next day...")
    leaderboard = engine.finalize_daily_session(session_id, date)

    click.echo("\n==================================================")
    click.echo(f"AutoTrade AI - Daily Replay Summary ({date}):")
    click.echo("==================================================")
    headers = ["Rank", "Model ID", "Start Eq", "End Eq", "Gross P&L", "Costs", "Net P&L", "Return %", "New Day Balance"]
    rows = []
    for i, p in enumerate(leaderboard, start=1):
        rows.append([
            i,
            p["model_id"],
            f"₹{p['starting_balance']:.2f}",
            f"₹{p['ending_balance']:.2f}",
            f"₹{p['gross_pnl']:.2f}",
            f"₹{(p['total_fees'] + p['total_slippage']):.2f}",
            f"₹{p['net_pnl']:.2f}",
            f"{p['return_pct']:+.2f}%",
            f"₹{p['ending_balance']:.2f}"
        ])
    click.echo(tabulate(rows, headers=headers, tablefmt="github"))
    click.echo("\nDaily results and audit logs successfully persisted to database/mobitrade.db.")
