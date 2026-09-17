"""
AutoTrade AI Local Operator API runner.
Supports: python -m autotrade_ai.api
"""

import os
import sys
import socket
import argparse
import uvicorn
from mobitrade.api.app import create_app


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def run(host: str = "127.0.0.1", port: int = None, reload: bool = False):
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
                        print(f"[AutoTrade AI] Notice: Port 8000 is occupied, auto-selecting available port {candidate}")
                        port = candidate
                        break
                if port is None:
                    port = 8000

    print(f"Starting AutoTrade AI Local Operator API on http://{host}:{port}")
    uvicorn.run(
        "mobitrade.api.app:create_app",
        host=host,
        port=port,
        factory=True,
        reload=reload,
        log_level="info",
    )


def main():
    parser = argparse.ArgumentParser(description="AutoTrade AI Local Operator API")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()
    run(host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
