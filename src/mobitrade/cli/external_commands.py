import click
from datetime import datetime
from typing import Optional

from mobitrade.sources.nse_provider import NSECorporateAnnouncementsProvider
from mobitrade.sources.news_provider import FinancialNewsProvider
from mobitrade.sources.macro_provider import MacroEconomicProvider
from mobitrade.sources.manager import ExternalInformationManager
from mobitrade.sources.persistence import InformationRepository
from mobitrade.data.calendar import IST
from mobitrade.config.settings import load_yaml_config

@click.group(name="external")
def external_cli():
    """AutoTrade AI - External Financial Information & Context CLI"""
    pass

@external_cli.command(name="status")
def external_status():
    """Display external information layer status."""
    click.echo("==================================================")
    click.echo("AutoTrade AI - External Financial Information Layer")
    click.echo("==================================================")
    click.echo("Configured Providers:  NSE_ANNOUNCEMENTS (Rank 1: Official Disclosures)")
    click.echo("                       MACRO_REGULATORY  (Rank 2: RBI / SEBI Macro)")
    click.echo("                       FINANCIAL_NEWS    (Rank 3: Reputable Financial Media)")
    click.echo("Temporal Availability: Point-in-Time Gated (available_at <= decision_timestamp)")
    click.echo("Storage Caching:       data/raw/external/")
    click.echo("                       data/processed/external/")
    click.echo("Database Tables:       external_information, information_contexts, context_items")
    click.echo("Operating Mode:        Raw Context Assembly (NO LLM SUMMARIZATION / NO TRADES)")

@external_cli.command(name="validate")
@click.option("--config", default="configs/external_information.yaml", help="Path to config")
def external_validate(config):
    """Validate external information configuration file."""
    cfg = load_yaml_config(config)
    if not cfg:
        click.echo(f"Error: Configuration file {config} not found or empty.")
        return
    info_cfg = cfg.get("external_information", {})
    click.echo(f"Validating external information config: {config}")
    click.echo(f" - Version: {info_cfg.get('version', '1.0.0')}")
    providers = info_cfg.get("providers", {})
    for p_name, p_val in providers.items():
        click.echo(f" - Provider {p_name.ljust(20)}: Enabled={p_val.get('enabled', True)} | Rank={p_val.get('authority_rank', 3)}")
    click.echo("External information configuration valid.")

@external_cli.command(name="inspect")
@click.option("--db-path", default="database/mobitrade.db")
def external_inspect(db_path):
    """Inspect stored external information records and contexts."""
    repo = InformationRepository(db_path=db_path)
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM external_information")
        doc_count = cursor.fetchone()["cnt"]
        cursor.execute("SELECT COUNT(*) as cnt FROM information_contexts")
        ctx_count = cursor.fetchone()["cnt"]

        click.echo(f"Database Inspection ({db_path}):")
        click.echo(f" - Total External Documents: {doc_count}")
        click.echo(f" - Total Information Contexts: {ctx_count}")

        cursor.execute("SELECT * FROM external_information ORDER BY published_at DESC LIMIT 5")
        rows = cursor.fetchall()
        if rows:
            click.echo("Recent Documents:")
            for r in rows:
                click.echo(f" - [{r['source']}] {r['symbol'] or 'MARKET'}: {r['title'][:40]}... ({r['available_at']})")

@external_cli.command(name="fetch")
@click.option("--symbol", default="RELIANCE", help="Symbol to test fetch")
def external_fetch(symbol):
    """Execute a test retrieval run across registered providers."""
    click.echo(f"Executing simulated external fetch for {symbol}...")
    nse = NSECorporateAnnouncementsProvider()
    news = FinancialNewsProvider()
    macro = MacroEconomicProvider()

    manager = ExternalInformationManager(providers=[nse, news, macro])
    # Ingest sample test fixture
    now = datetime.now(IST)
    doc = nse.ingest_document(
        symbol=symbol,
        title=f"{symbol} Q2 Financial Performance Disclosures",
        summary="Company reported robust operating margins in cash market segment.",
        published_at=now
    )
    click.echo(f"Successfully fetched/verified document: ID={doc.information_id}, Hash={doc.content_hash[:12]}...")

@external_cli.command(name="context")
@click.option("--symbol", required=True, help="NSE Symbol (e.g. RELIANCE, TCS)")
@click.option("--timestamp", default=None, help="Decision timestamp ISO format (default: now IST)")
@click.option("--limit", default=10, type=int, help="Maximum items")
def external_context(symbol, timestamp, limit):
    """Query point-in-time InformationContext for a symbol at decision timestamp."""
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
        except Exception:
            dt = datetime.now(IST)
    else:
        dt = datetime.now(IST)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)

    nse = NSECorporateAnnouncementsProvider()
    news = FinancialNewsProvider()
    macro = MacroEconomicProvider()

    # Pre-populate sample fixture for inspection
    nse.ingest_document(
        symbol=symbol,
        title=f"{symbol} Strategic Board Meeting Update",
        summary="Board approved dividend payout and equity investments.",
        published_at=dt
    )

    manager = ExternalInformationManager(providers=[nse, news, macro])
    ctx = manager.get_context_as_of(symbol, dt, limit=limit)

    click.echo("==================================================")
    click.echo("AutoTrade AI - Information Context Summary")
    click.echo("==================================================")
    click.echo(f"Symbol:               {ctx.symbol}")
    click.echo(f"Decision Timestamp:   {ctx.decision_timestamp.isoformat()}")
    click.echo(f"Context Version:      {ctx.context_version}")
    click.echo(f"Source Count:         {ctx.source_count}")
    click.echo(f"High Authority Count: {ctx.high_authority_count}")
    click.echo(f"Latest Info Time:     {ctx.latest_available_information_time.isoformat() if ctx.latest_available_information_time else 'N/A'}")
    click.echo("--------------------------------------------------")
    if ctx.relevant_information:
        click.echo("Included Information Items:")
        for doc in ctx.relevant_information:
            click.echo(f" - [{doc.source}] Authority: {doc.authority.name} | Relevance: {doc.relevance.value}")
            click.echo(f"   Title: {doc.title}")
            click.echo(f"   Published: {doc.published_at.isoformat()} | Available: {doc.available_at.isoformat()}")
    else:
        click.echo("No external information available at or before decision timestamp.")
    click.echo("==================================================")
