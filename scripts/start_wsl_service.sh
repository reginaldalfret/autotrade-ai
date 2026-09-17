#!/bin/bash
# AutoTrade AI - WSL Service Helper
set -e

PROJECT_DIR="/root/projects/AutoTradeAI"
cd "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/runtime"

SERVICE="$1"
shift || true

case "$SERVICE" in
    valkey)
        if redis-cli ping 2>/dev/null | grep -q "PONG"; then
            echo "Valkey is already running."
        else
            valkey-server --daemonize yes
            echo "Valkey started."
        fi
        ;;
    api)
        if curl -s http://127.0.0.1:8008/health 2>/dev/null | grep -q "ok"; then
            echo "FastAPI is already running."
        else
            nohup "$PROJECT_DIR/.venv/bin/python" -m mobitrade.cli.main api --host 127.0.0.1 --port 8008 > "$PROJECT_DIR/logs/fastapi.log" 2>&1 &
            echo "FastAPI background job spawned."
        fi
        ;;
    dashboard)
        if curl -s -I http://127.0.0.1:3000 2>/dev/null | grep -q "200 OK"; then
            echo "Dashboard is already running."
        else
            cd "$PROJECT_DIR/dashboard"
            nohup npx next start -H 127.0.0.1 -p 3000 > "$PROJECT_DIR/logs/nextjs.log" 2>&1 &
            echo "Next.js dashboard background job spawned."
        fi
        ;;
    session)
        nohup "$PROJECT_DIR/.venv/bin/python" -u "$PROJECT_DIR/scripts/run_today_session.py" "$@" > "$PROJECT_DIR/logs/today_session.log" 2>&1 &
        echo $! > "$PROJECT_DIR/runtime/session_pid.txt"
        echo "Today session spawned with PID $(cat "$PROJECT_DIR/runtime/session_pid.txt")."
        ;;
    *)
        echo "Unknown service: $SERVICE"
        exit 1
        ;;
esac
