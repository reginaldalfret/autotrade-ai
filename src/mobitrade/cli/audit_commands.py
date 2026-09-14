"""
CLI commands for Tamper-Evident Cryptographic Audit Logging.
"""

import click
import json
from tabulate import tabulate
from mobitrade.logging.audit import AuditLogger, canonical_json


@click.group()
def audit_cli():
    """Audit logging and cryptographic chain verification commands."""
    pass


@audit_cli.command(name="status")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def audit_status(db_path):
    """Display audit log summary and chain health."""
    logger = AuditLogger(db_path=db_path)
    events = logger.get_events()
    total = len(events)
    first_seq = events[0].sequence_number if events else "N/A"
    last_seq = events[-1].sequence_number if events else "N/A"
    latest_hash = events[-1].event_hash if events else "N/A"

    click.echo("==================================================")
    click.echo("AutoTrade AI — Cryptographic Audit Log Status")
    click.echo("==================================================")
    click.echo(f"Database:           {db_path}")
    click.echo(f"Total Audit Events: {total}")
    click.echo(f"Sequence Range:     {first_seq} -> {last_seq}")
    click.echo(f"Genesis Block:      {'0'*64}")
    click.echo(f"Latest Event Hash:  {latest_hash}")
    click.echo(f"Hash Algorithm:     SHA-256 (Canonical JSON)")


@audit_cli.command(name="verify")
@click.option("--session", "session_id", default=None, help="Filter verification to specific session")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def audit_verify(session_id, db_path):
    """Verify cryptographic SHA-256 chain integrity."""
    logger = AuditLogger(db_path=db_path)
    res = logger.verify_chain(session_id=session_id)

    click.echo("==================================================")
    click.echo("AutoTrade AI — Cryptographic Chain Verification")
    click.echo("==================================================")
    click.echo(f"Scope:          {session_id or 'ALL SESSIONS'}")
    click.echo(f"Total Events:   {res.total_events}")
    click.echo(f"Sequence Range: {res.first_sequence or 'N/A'} -> {res.last_sequence or 'N/A'}")

    if res.is_valid:
        click.secho("\n[PASS] CRYPTOGRAPHIC INTEGRITY VERIFIED: 100% VALID", fg="green", bold=True)
        click.echo("All SHA-256 event hashes match payloads and form an unbroken chain to Genesis.")
    else:
        click.secho(f"\n[FAIL] TAMPER DETECTED: {len(res.errors)} Discrepancies Found!", fg="red", bold=True)
        for err in res.errors[:10]:
            click.echo(f" - {err}")


@audit_cli.command(name="inspect")
@click.argument("event_id")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def audit_inspect(event_id, db_path):
    """Inspect full payload and cryptographic hash of a single event."""
    logger = AuditLogger(db_path=db_path)
    event = logger.get_event_by_id(event_id)
    if not event:
        click.secho(f"Event '{event_id}' not found.", fg="red")
        return

    click.echo("==================================================")
    click.echo(f"Audit Event Inspection: {event.event_id}")
    click.echo("==================================================")
    click.echo(f"Sequence Number:    {event.sequence_number}")
    click.echo(f"Session ID:         {event.session_id}")
    click.echo(f"Timestamp:          {event.timestamp}")
    click.echo(f"Event Type:         {event.event_type}")
    click.echo(f"Model ID:           {event.model_id or 'SYSTEM'}")
    click.echo(f"Trade ID:           {event.trade_id or 'N/A'}")
    click.echo(f"Order ID:           {event.order_id or 'N/A'}")
    click.echo(f"Previous Hash:      {event.previous_event_hash}")
    click.echo(f"Stored Hash:        {event.event_hash}")
    computed = event.compute_expected_hash()
    click.echo(f"Computed Hash:      {computed}")
    if event.is_valid():
        click.secho("Integrity:          VALID (Matches)", fg="green", bold=True)
    else:
        click.secho("Integrity:          INVALID (TAMPER DETECTED)", fg="red", bold=True)

    click.echo("\nCanonical Payload:")
    click.echo(json.dumps(event.payload, indent=2))


@audit_cli.command(name="session")
@click.argument("session_id")
@click.option("--limit", default=50, help="Max events to display")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def audit_session(session_id, limit, db_path):
    """Display audit trail for a specific trading session."""
    logger = AuditLogger(db_path=db_path)
    events = logger.get_events(session_id=session_id, limit=limit)
    if not events:
        click.echo(f"No audit events found for session '{session_id}'.")
        return

    table = []
    for e in events:
        table.append([
            e.sequence_number,
            e.timestamp[-12:],
            e.event_type,
            e.model_id or "SYS",
            e.trade_id or "-",
            f"{e.event_hash[:16]}..."
        ])

    click.echo(f"\nAudit Trail for Session: {session_id} (Showing {len(events)} events)")
    click.echo(tabulate(table, headers=["Seq", "Time", "Event Type", "Model", "Trade", "Hash Prefix"], tablefmt="grid"))


@audit_cli.command(name="trade")
@click.argument("trade_id")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def audit_trade(trade_id, db_path):
    """Display full lifecycle audit trail for a specific trade."""
    logger = AuditLogger(db_path=db_path)
    events = logger.get_events(trade_id=trade_id)
    if not events:
        click.echo(f"No audit events linked to trade '{trade_id}'.")
        return

    click.echo(f"\nAudit Trail for Trade: {trade_id}")
    for e in events:
        click.echo(f"[{e.timestamp}] Seq={e.sequence_number} {e.event_type} (Model: {e.model_id})")
        click.echo(f"  Hash: {e.event_hash}")
        click.echo(f"  Payload: {json.dumps(e.payload)}")
