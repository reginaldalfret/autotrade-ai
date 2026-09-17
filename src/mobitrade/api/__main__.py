"""
Main entrypoint for running the AutoTrade AI Local Operator API with uvicorn.
Usage: python -m mobitrade.api
"""

import os
import socket
import click
import uvicorn


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


@click.command()
@click.option("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
@click.option("--port", default=None, type=int, help="Port to listen on (default: 8000)")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload for development")
def main(host: str, port: int, reload: bool):
    """Start the AutoTrade AI Local Operator API server."""
    if host not in ("127.0.0.1", "localhost"):
        click.secho(f"WARNING: Binding to non-localhost interface {host} is discouraged for safety.", fg="yellow")

    if port is None:
        env_port = os.environ.get("AUTOTRADE_API_PORT")
        if env_port:
            port = int(env_port)
        else:
            if is_port_available(host, 8000):
                port = 8000
            else:
                for candidate in [8008, 8080, 8001]:
                    if is_port_available(host, candidate):
                        click.secho(f"[AutoTrade AI] Notice: Port 8000 is occupied, auto-selecting available port {candidate}", fg="yellow")
                        port = candidate
                        break
                if port is None:
                    port = 8000

    click.secho(f"Starting AutoTrade AI Local Operator API on http://{host}:{port}", fg="green", bold=True)
    uvicorn.run(
        "mobitrade.api.app:create_app",
        host=host,
        port=port,
        factory=True,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
