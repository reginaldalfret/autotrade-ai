"""
CLI commands for Automated Daily PDF Report Generation.
"""

import os
import click
import hashlib
from mobitrade.reporting.generator import DailyReportGenerator
from mobitrade.paper.persistence import PaperDatabaseRepository


@click.group()
def report_cli():
    """Daily PDF report compilation and validation commands."""
    pass


@report_cli.command(name="generate")
@click.option("--session", "session_id", default=None, help="Session ID")
@click.option("--date", "session_date", default=None, help="Date (YYYY-MM-DD)")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def report_generate(session_id, session_date, db_path):
    """Generate institutional multi-page PDF trading report."""
    repo = PaperDatabaseRepository(db_path=db_path)
    target = session_id or session_date
    if not target:
        with repo._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, session_date FROM daily_sessions ORDER BY started_at DESC LIMIT 1")
            r = cursor.fetchone()
            if not r:
                click.secho("No trading sessions found in database.", fg="yellow")
                return
            target = r["session_id"]

    generator = DailyReportGenerator(db_path=db_path)
    click.echo(f"Compiling Daily Trading PDF Report for: {target}...")
    try:
        pdf_path = generator.generate(target)
        click.secho(f"\n[SUCCESS] PDF Report Generated Successfully:", fg="green", bold=True)
        click.echo(f"Location: {pdf_path}")
        click.echo(f"Size:     {os.path.getsize(pdf_path):,} bytes")
    except Exception as e:
        click.secho(f"\n[ERROR] PDF Generation Failed: {e}", fg="red", bold=True)


@report_cli.command(name="regenerate")
@click.option("--session", "session_id", default=None, help="Session ID")
@click.option("--date", "session_date", default=None, help="Date (YYYY-MM-DD)")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def report_regenerate(session_id, session_date, db_path):
    """Force re-generate and update an existing daily report."""
    generator = DailyReportGenerator(db_path=db_path)
    target = session_id or session_date
    if not target:
        click.secho("Specify either --session or --date to regenerate.", fg="red")
        return

    click.echo(f"Regenerating Daily Trading Report for: {target}...")
    try:
        pdf_path = generator.generate(target)
        click.secho(f"\n[SUCCESS] PDF Report Recompiled Successfully:", fg="green", bold=True)
        click.echo(f"Location: {pdf_path}")
    except Exception as e:
        click.secho(f"\n[ERROR] PDF Regeneration Failed: {e}", fg="red", bold=True)


@report_cli.command(name="validate")
@click.argument("pdf_path_or_id")
@click.option("--db-path", default="database/mobitrade.db", help="Path to SQLite DB")
def report_validate(pdf_path_or_id, db_path):
    """Validate cryptographic SHA-256 fingerprint of a PDF report against database."""
    repo = PaperDatabaseRepository(db_path=db_path)
    
    # Try finding report by path or ID
    report = repo.get_report(pdf_path_or_id)
    if not report:
        # Check by filename / date
        report = repo.get_report_by_date(pdf_path_or_id)
    if not report:
        # Assume it's a file path
        if os.path.exists(pdf_path_or_id):
            file_path = pdf_path_or_id
            expected_hash = None
        else:
            click.secho(f"Report or file '{pdf_path_or_id}' not found.", fg="red")
            return
    else:
        file_path = report["file_path"]
        expected_hash = report["file_hash"]

    if not os.path.exists(file_path):
        click.secho(f"Physical file not found at: {file_path}", fg="red")
        return

    # Compute hash of file on disk
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest()

    click.echo("==================================================")
    click.echo(f"AutoTrade AI — PDF Report Fingerprint Validation")
    click.echo("==================================================")
    click.echo(f"File:           {file_path}")
    click.echo(f"Computed Hash:  {actual_hash}")
    if expected_hash:
        click.echo(f"Database Hash:  {expected_hash}")
        if actual_hash == expected_hash:
            click.secho("\n[PASS] PDF INTEGRITY VERIFIED: SHA-256 MATCHES DATABASE RECORD", fg="green", bold=True)
        else:
            click.secho("\n[FAIL] TAMPER DETECTED: PDF HASH DOES NOT MATCH DATABASE RECORD", fg="red", bold=True)
    else:
        click.echo("\n[INFO] Valid SHA-256 calculated (no DB reference provided).")
