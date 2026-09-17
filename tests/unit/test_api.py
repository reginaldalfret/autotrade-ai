"""
Unit tests for AutoTrade AI Local Operator API (Phase 9).
Tests all 10 endpoints, CORS policy, deterministic replay, and risk boundary reporting.
"""

import os
import pytest
from fastapi.testclient import TestClient
from mobitrade.api.app import create_app
from mobitrade.paper.persistence import PaperDatabaseRepository


@pytest.fixture
def test_client(tmp_path):
    """
    Provide TestClient initialized with a temporary SQLite database.
    """
    db_file = tmp_path / "test_mobitrade.db"
    repo = PaperDatabaseRepository(db_path=str(db_file))
    repo._init_db()

    app = create_app(
        db_path=str(db_file),
        config_path="configs/default.yaml",
        models_config_path="configs/models.yaml",
    )
    with TestClient(app) as client:
        yield client


def test_health_endpoint(test_client):
    """Test GET /health returns expected structure and database connectivity."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "market_session" in data
    assert data["market_session"]["market"] == "NSE"
    assert "llm_provider" in data
    assert "database" in data
    assert data["database"]["status"] == "connected"


def test_models_endpoint(test_client):
    """Test GET /models returns configured tournament models."""
    response = test_client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 8
    model_ids = [m["id"] for m in data["models"]]
    assert "nemotron" in model_ids
    assert "qwen" in model_ids
    assert "llama" in model_ids


def test_portfolio_endpoint(test_client):
    """Test GET /portfolio returns account list and aggregate equity."""
    response = test_client.get("/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert "total_equity" in data
    assert "total_cash" in data
    assert "accounts" in data
    assert isinstance(data["accounts"], list)


def test_positions_endpoint(test_client):
    """Test GET /positions returns active positions."""
    response = test_client.get("/positions")
    assert response.status_code == 200
    data = response.json()
    assert "positions" in data
    assert "count" in data
    assert isinstance(data["positions"], list)


def test_trades_endpoint(test_client):
    """Test GET /trades returns executed trade journal."""
    response = test_client.get("/trades")
    assert response.status_code == 200
    data = response.json()
    assert "trades" in data
    assert "count" in data
    assert isinstance(data["trades"], list)


def test_risk_endpoint(test_client):
    """Test GET /risk reflects authoritative risk engine parameters."""
    response = test_client.get("/risk")
    assert response.status_code == 200
    data = response.json()
    assert data["market_segment"] == "NSE Cash Intraday"
    assert data["daily_loss_limit_pct"] == 0.05
    assert data["hard_stop_loss_pct"] == -5.0
    assert data["max_trades_per_session"] == 20
    assert data["auto_square_off_time"] == "15:15 IST"
    assert data["allow_overnight"] is False
    assert data["require_stop_loss"] is True
    assert "RiskEngine" in data["authority"]


def test_analytics_endpoint_empty_db(test_client):
    """Test GET /analytics on empty database handles no sessions gracefully."""
    response = test_client.get("/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_trades"] == 0
    assert data["win_rate"] == 0.0
    assert data["leaderboard"] == []


def test_reports_endpoint(test_client):
    """Test GET /reports returns list of generated PDF reports."""
    response = test_client.get("/reports")
    assert response.status_code == 200
    data = response.json()
    assert "reports" in data
    assert "count" in data
    assert isinstance(data["reports"], list)


def test_audit_verify_endpoint(test_client):
    """Test GET /audit/verify runs cryptographic verification."""
    response = test_client.get("/audit/verify")
    assert response.status_code == 200
    data = response.json()
    assert "is_valid" in data
    assert data["is_valid"] is True
    assert "total_events" in data
    assert data["errors"] == []


def test_session_run_endpoint_and_analytics(test_client):
    """
    Test POST /session/run executes deterministic replay session,
    followed by GET /analytics and GET /trades to verify updates.
    """
    payload = {
        "session_date": "2026-09-11",
        "symbol": "TATAMOTORS",
        "mock_llm": True
    }
    run_resp = test_client.post("/session/run", json=payload)
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["status"] == "completed"
    assert run_data["session_id"] == "sim_20260911"
    assert run_data["total_trades"] > 0
    assert len(run_data["leaderboard"]) > 0

    # Verify /trades reflects executed trades
    trades_resp = test_client.get("/trades?session_id=sim_20260911")
    assert trades_resp.status_code == 200
    trades_data = trades_resp.json()
    assert trades_data["count"] > 0

    # Verify /analytics reflects the completed session
    analytics_resp = test_client.get("/analytics?session_id=sim_20260911")
    assert analytics_resp.status_code == 200
    analytics_data = analytics_resp.json()
    assert analytics_data["session_id"] == "sim_20260911"
    assert len(analytics_data["leaderboard"]) > 0

    # Verify /audit/verify validates the events generated during run
    audit_resp = test_client.get("/audit/verify?session_id=sim_20260911")
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert audit_data["is_valid"] is True
    assert audit_data["total_events"] > 0


def test_cors_headers(test_client):
    """Test localhost CORS headers are returned properly."""
    response = test_client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:8000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:8000"
