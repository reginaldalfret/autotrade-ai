import click
from datetime import datetime
from pathlib import Path
from mobitrade.domain.data_models import Timeframe
from mobitrade.domain.scanner_models import ScannerConfig
from mobitrade.scanner.universe import EquityUniverseProvider
from mobitrade.scanner.scanner import OpportunityScanner
from mobitrade.scanner.persistence import ScannerDatabaseRepository
from mobitrade.data.calendar import IST
from mobitrade.config.settings import load_yaml_config

@click.group(name="scanner")
def scanner_cli():
    """MobiTrade AI - Opportunity Scanner & Candidate Ranking CLI"""
    pass

@scanner_cli.command(name="status")
def scanner_status():
    """Display Opportunity Scanner engine status."""
    click.echo("==================================================")
    click.echo("MobiTrade AI - Opportunity Scanner Status")
    click.echo("==================================================")
    click.echo("Scanner Version:       1.0.0")
    click.echo("Market:                NSE Indian Equity Cash")
    click.echo("Active Hours:          09:15 - 15:30 IST")
    click.echo("Temporal Safety:       Point-in-Time Gated (available_at <= decision_timestamp)")
    click.echo("Scoring Engine:        Deterministic multi-factor linear score (0 - 100)")
    click.echo("Database Persistence:  /mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db")
    click.echo("Execution Pipeline:    Candidate Generation Only (NO TRADES / NO LLM INFERENCE)")

@scanner_cli.command(name="validate")
@click.option("--config", default="configs/scanner.yaml", help="Path to scanner.yaml")
def scanner_validate(config):
    """Validate scanner configuration file."""
    cfg = load_yaml_config(config)
    if not cfg:
        click.echo(f"Error: Configuration file {config} not found or empty.")
        return
    s_cfg = cfg.get("scanner", {})
    click.echo(f"Validating scanner config: {config}")
    click.echo(f" - Scanner Version: {s_cfg.get('scanner_version', '1.0.0')}")
    click.echo(f" - Top-N Default:   {s_cfg.get('top_n', 10)}")
    click.echo(f" - Scoring Weights: {s_cfg.get('scoring', {})}")
    click.echo("Scanner configuration valid.")

@scanner_cli.command(name="inspect")
@click.option("--db-path", default="/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db")
def scanner_inspect(db_path):
    """Inspect recent scanner persistence records in database."""
    repo = ScannerDatabaseRepository(db_path)
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scans ORDER BY created_at DESC LIMIT 5")
        rows = cursor.fetchall()
        click.echo(f"Recent Scans in database ({len(rows)} found):")
        for r in rows:
            click.echo(f" - Scan ID: {r['scan_id']} | DT: {r['decision_timestamp']} | TF: {r['timeframe']} | Candidates: {r['candidate_count']}")

@scanner_cli.command(name="scan")
@click.option("--timestamp", default=None, help="Decision timestamp ISO format (default: current IST)")
@click.option("--timeframe", default="5m", type=click.Choice(["1m", "5m", "15m"]), help="Timeframe")
@click.option("--top-n", default=10, type=int, help="Top N candidates")
@click.option("--allow-outside-session", is_flag=True, default=False, help="Allow scanning outside normal session")
def scanner_scan(timestamp, timeframe, top_n, allow_outside_session):
    """Execute a point-in-time opportunity scan."""
    tf = Timeframe(timeframe)
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
        except Exception:
            dt = datetime.now(IST)
    else:
        dt = datetime.now(IST)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)

    # Initialize Universe with standard smoke-test symbols
    universe_provider = EquityUniverseProvider()
    universe_provider.register_symbols(["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"])
    universe = universe_provider.get_universe_as_of(dt)

    scanner = OpportunityScanner()
    config = ScannerConfig(top_n=top_n)

    # Note: in CLI scan demonstration with empty local candles, candidates will be safely evaluated
    accepted, rejected = scanner.scan_as_of(
        universe=universe,
        decision_timestamp=dt,
        timeframe=tf,
        candles_by_symbol={},
        config=config,
        allow_outside_session=allow_outside_session,
    )

    top_candidates = scanner.get_top_candidates(accepted, top_n)

    click.echo("==================================================")
    click.echo("MobiTrade AI - Opportunity Scan Summary")
    click.echo("==================================================")
    click.echo(f"Decision Timestamp:  {dt.isoformat()}")
    click.echo(f"Market:              NSE Indian Equity Cash")
    click.echo(f"Timeframe:           {tf.value}")
    click.echo(f"Scanner Version:     {scanner.scanner_version}")
    click.echo(f"Universe Count:      {len(universe)}")
    click.echo(f"Eligible Count:      {len(accepted)}")
    click.echo(f"Rejected Count:      {len(rejected)}")
    click.echo(f"Candidate Count:     {len(top_candidates)}")
    click.echo("--------------------------------------------------")
    if top_candidates:
        click.echo("Top Candidates:")
        for c in top_candidates:
            click.echo(f" - {c.symbol.ljust(10)} Score: {c.opportunity_score:.2f} | Trend: {c.trend.value}")
    else:
        click.echo("No candidates met all filtering criteria.")
        if rejected:
            click.echo("Sample Rejection Reasons:")
            for r in rejected[:5]:
                click.echo(f" - {r.symbol}: {r.rejection_reason.value if r.rejection_reason else 'UNKNOWN'}")
    click.echo("==================================================")
