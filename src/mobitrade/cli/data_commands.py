import click
from datetime import datetime
from tabulate import tabulate
from mobitrade.config.settings import load_yaml_config
from mobitrade.domain.data_models import Timeframe
from mobitrade.data.repository import ParquetDataRepository

@click.group()
def data_cli():
    """AutoTrade AI - Market Data Management"""
    pass

@data_cli.command()
def status():
    """Display historical market data repository status."""
    repo = ParquetDataRepository()
    click.echo("==================================================")
    click.echo("AutoTrade AI - Market Data Status")
    click.echo("==================================================")
    click.echo(f"Raw Storage:       {repo.raw_dir}")
    click.echo(f"Processed Parquet: {repo.processed_dir}")
    click.echo(f"Metadata Storage:  {repo.metadata_dir}")
    click.echo("Primary Market:    Indian Equities (NSE)")

@data_cli.command()
def symbols():
    """List configured test symbols for Indian Equities."""
    market_cfg = load_yaml_config("configs/markets.yaml")
    symbols = market_cfg.get("markets", {}).get("indian_equity", {}).get("symbols", [])
    click.echo(f"Configured Smoke-Test Symbols ({len(symbols)}):")
    for s in symbols:
        click.echo(f" - {s} (NSE Equity)")

@data_cli.command()
@click.option("--symbol", default="RELIANCE", help="Symbol to inspect")
@click.option("--timeframe", default="1m", help="Timeframe (1m, 5m, 15m, 1d)")
def inspect(symbol, timeframe):
    """Inspect stored Parquet candles for a symbol."""
    repo = ParquetDataRepository()
    tf = Timeframe(timeframe)
    candles = repo.load_candles(symbol, tf)
    if not candles:
        click.echo(f"No stored Parquet data found for {symbol} ({tf.value}).")
        return
    click.echo(f"Loaded {len(candles)} candles for {symbol} ({tf.value}):")
    table_data = [
        [c.timestamp.strftime("%Y-%m-%d %H:%M"), c.open, c.high, c.low, c.close, c.volume, c.status.value]
        for c in candles[:5]
    ]
    click.echo(tabulate(table_data, headers=["Timestamp (IST)", "Open", "High", "Low", "Close", "Volume", "Status"]))
    if len(candles) > 5:
        click.echo(f"... and {len(candles) - 5} more rows.")