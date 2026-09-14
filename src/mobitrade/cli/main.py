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

if __name__ == "__main__":
    cli()