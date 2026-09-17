import click
from mobitrade.config.model_registry import ModelRegistry
from mobitrade.config.settings import load_yaml_config
from mobitrade.cli.data_commands import data_cli
from mobitrade.cli.features_commands import features_cli
from mobitrade.cli.scanner_commands import scanner_cli
from mobitrade.cli.external_commands import external_cli
from mobitrade.cli.llm_commands import llm_cli
from mobitrade.cli.paper_commands import paper_cli
from mobitrade.cli.audit_commands import audit_cli
from mobitrade.cli.analytics_commands import analytics_cli
from mobitrade.cli.report_commands import report_cli

@click.group()
def cli():
    """AutoTrade AI - Autonomous Trading Research Platform"""
    pass

cli.add_command(data_cli, name="data")
cli.add_command(features_cli, name="features")
cli.add_command(scanner_cli, name="scanner")
cli.add_command(external_cli, name="external")
cli.add_command(llm_cli, name="llm")
cli.add_command(paper_cli, name="paper")
cli.add_command(audit_cli, name="audit")
cli.add_command(analytics_cli, name="analytics")
cli.add_command(report_cli, name="report")

@cli.command()
def status():
    """Display platform environment status."""
    click.echo("==================================================")
    click.echo("AutoTrade AI - Platform Status")
    click.echo("==================================================")
    click.echo("Project Root:   D:\\Trading LLM\\MobiTradeAI")
    click.echo("WSL2 Mount:     /root/projects/AutoTradeAI")
    click.echo("Storage Policy: D: preferred, E: allowed, C: strictly prohibited")
    click.echo("Execution Mode: LOCAL-FIRST PAPER TRADING ONLY")

@cli.command()
@click.option("--config", default="configs/models.yaml", help="Path to models.yaml")
def models(config):
    """List available and enabled local models."""
    registry = ModelRegistry(config)
    models = registry.list_all_models()
    click.echo(f"Registered Local LLMs ({len(models)} configured):")
    for m in models:
        status_str = "[ENABLED]" if m.enabled else "[DISABLED]"
        click.echo(f" - {m.id.ljust(12)}: {m.display_name.ljust(26)} -> Tag: {m.runtime_model_name} {status_str}")

@cli.command()
def validate():
    """Verify configuration files and schema validity."""
    click.echo("Validating configuration files...")
    cfg = load_yaml_config("configs/default.yaml")
    if cfg:
        click.echo("configs/default.yaml: OK")
    models = load_yaml_config("configs/models.yaml")
    if models:
        click.echo(f"configs/models.yaml: OK ({len(models.get('models', []))} models)")
    click.echo("System configuration validated successfully.")

@cli.command()
@click.option("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
@click.option("--port", default=None, type=int, help="Port to listen on (default: 8000)")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload")
def api(host, port, reload):
    """Start the AutoTrade AI Local Operator API server."""
    import socket
    import uvicorn
    if port is None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, 8000))
                port = 8000
            except OSError:
                for cand in [8008, 8080, 8001]:
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                            s2.bind((host, cand))
                            port = cand
                            click.secho(f"[AutoTrade AI] Notice: Port 8000 occupied, auto-selecting port {cand}", fg="yellow")
                            break
                    except OSError:
                        continue
                if port is None:
                    port = 8000

    click.secho(f"Starting AutoTrade AI Local Operator API on http://{host}:{port}", fg="green", bold=True)
    uvicorn.run("mobitrade.api.app:create_app", host=host, port=port, factory=True, reload=reload, log_level="info")

if __name__ == "__main__":
    cli()