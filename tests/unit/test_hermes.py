"""
Unit and Integration Tests for Hermes Operator Adapter (Phase 10).
Validates tools, client, error handling, risk boundary descriptions, and daily workflow.
"""

import pytest
from unittest.mock import MagicMock, patch
import requests

from mobitrade.hermes.client import (
    AutoTradeOperatorClient,
    HermesOperatorError,
    HermesConnectionError,
    HermesTimeoutError,
)
from mobitrade.hermes.tools import AutoTradeHermesTools, get_hermes_tools, HERMES_SYSTEM_CONSTRAINTS
from mobitrade.hermes.workflow import run_daily_session_workflow
from mobitrade.api.app import create_app
from mobitrade.paper.persistence import PaperDatabaseRepository


@pytest.fixture
def mock_client():
    """Mock client returning deterministic API payloads."""
    client = AutoTradeOperatorClient(base_url="http://127.0.0.1:8000")
    client._session = MagicMock()
    return client


def test_hermes_client_methods(mock_client):
    """Test all 10 client methods map correctly to appropriate HTTP methods and endpoints."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "ok"}
    mock_resp.raise_for_status.return_value = None
    mock_client._session.request.return_value = mock_resp

    # 1. health
    res = mock_client.get_health()
    assert res == {"status": "ok"}
    mock_client._session.request.assert_called_with(
        "GET", "http://127.0.0.1:8000/health", timeout=15.0
    )

    # 2. models
    mock_client.get_models()
    mock_client._session.request.assert_called_with(
        "GET", "http://127.0.0.1:8000/models", timeout=15.0
    )

    # 3. portfolio
    mock_client.get_portfolio()
    mock_client._session.request.assert_called_with(
        "GET", "http://127.0.0.1:8000/portfolio", timeout=15.0
    )

    # 4. positions
    mock_client.get_positions()
    mock_client._session.request.assert_called_with(
        "GET", "http://127.0.0.1:8000/positions", timeout=15.0
    )

    # 5. trades
    mock_client.get_trades(session_id="sim_001", model_id="nemotron", limit=10)
    mock_client._session.request.assert_called_with(
        "GET",
        "http://127.0.0.1:8000/trades",
        params={"limit": 10, "session_id": "sim_001", "model_id": "nemotron"},
        timeout=15.0,
    )

    # 6. risk
    mock_client.get_risk()
    mock_client._session.request.assert_called_with(
        "GET", "http://127.0.0.1:8000/risk", timeout=15.0
    )

    # 7. analytics
    mock_client.get_analytics(session_id="sim_001")
    mock_client._session.request.assert_called_with(
        "GET", "http://127.0.0.1:8000/analytics", params={"session_id": "sim_001"}, timeout=15.0
    )

    # 8. reports
    mock_client.get_reports()
    mock_client._session.request.assert_called_with(
        "GET", "http://127.0.0.1:8000/reports", timeout=15.0
    )

    # 9. audit
    mock_client.verify_audit(session_id="sim_001")
    mock_client._session.request.assert_called_with(
        "GET", "http://127.0.0.1:8000/audit/verify", params={"session_id": "sim_001"}, timeout=15.0
    )

    # 10. session run
    mock_client.run_paper_session(session_date="2026-09-17", symbol="TATAMOTORS", mock_llm=True)
    mock_client._session.request.assert_called_with(
        "POST",
        "http://127.0.0.1:8000/session/run",
        json={"session_date": "2026-09-17", "symbol": "TATAMOTORS", "symbols": None, "mock_llm": True},
        timeout=15.0,
    )


def test_hermes_client_error_handling(mock_client):
    """Test connection error, timeout error, and HTTP status error handling."""
    # Test connection failure
    mock_client._session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")
    with pytest.raises(HermesConnectionError) as exc_info:
        mock_client.get_health()
    assert "Cannot connect to AutoTrade AI API" in str(exc_info.value)

    # Test timeout failure
    mock_client._session.request.side_effect = requests.exceptions.ConnectTimeout("Timed out")
    with pytest.raises(HermesTimeoutError) as exc_info:
        mock_client.get_health()
    assert "timed out after" in str(exc_info.value)

    # Test HTTP 500 error
    bad_resp = MagicMock()
    bad_resp.status_code = 500
    bad_resp.text = "Internal Server Error"
    mock_client._session.request.side_effect = requests.exceptions.HTTPError(response=bad_resp)
    with pytest.raises(HermesOperatorError) as exc_info:
        mock_client.get_health()
    assert "returned HTTP 500" in str(exc_info.value)


def test_hermes_tool_definitions_and_constraints():
    """Verify tool schemas, boundary prompts, and system constraints."""
    tools = get_hermes_tools()
    defs = tools.get_tool_definitions()

    assert len(defs) == 10
    names = [d["name"] for d in defs]
    assert "autotrade_get_health" in names
    assert "autotrade_get_models" in names
    assert "autotrade_get_portfolio" in names
    assert "autotrade_get_positions" in names
    assert "autotrade_get_trades" in names
    assert "autotrade_get_risk" in names
    assert "autotrade_get_analytics" in names
    assert "autotrade_get_reports" in names
    assert "autotrade_verify_audit" in names
    assert "autotrade_run_paper_session" in names

    # Verify boundary constraints document all required safety rules
    assert "NSE Indian Cash Equities only" in HERMES_SYSTEM_CONSTRAINTS
    assert "STRICT PAPER TRADING ONLY" in HERMES_SYSTEM_CONSTRAINTS
    assert "09:15 to 15:30 IST" in HERMES_SYSTEM_CONSTRAINTS
    assert "15:15 IST mandatory position closure" in HERMES_SYSTEM_CONSTRAINTS
    assert "ZERO overnight holding" in HERMES_SYSTEM_CONSTRAINTS
    assert "-5.0%" in HERMES_SYSTEM_CONSTRAINTS
    assert "Maximum 20 completed trades" in HERMES_SYSTEM_CONSTRAINTS
    assert "Trailing Stop" in HERMES_SYSTEM_CONSTRAINTS
    assert "RiskEngine is deterministic and final" in HERMES_SYSTEM_CONSTRAINTS


def test_hermes_tool_execution(mock_client):
    """Test tool dispatcher routes executions accurately."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"market": "NSE", "is_open": True}
    mock_resp.raise_for_status.return_value = None
    mock_client._session.request.return_value = mock_resp

    tools = AutoTradeHermesTools(client=mock_client)
    res = tools.execute_tool("autotrade_get_health")
    assert res == {"market": "NSE", "is_open": True}

    with pytest.raises(ValueError) as exc:
        tools.execute_tool("unknown_tool_xyz")
    assert "Unknown AutoTrade AI tool" in str(exc.value)


def test_hermes_daily_workflow_mocked(mock_client):
    """Test standard daily session workflow orchestration with mocked client."""
    def fake_request(method, url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        if "/session/run" in url:
            resp.json.return_value = {
                "status": "completed",
                "session_id": "sim_20260917",
                "total_trades": 4,
            }
        elif "/analytics" in url:
            resp.json.return_value = {
                "gross_pnl": 45.0,
                "net_pnl": 38.5,
                "win_rate": 75.0,
                "leaderboard": [{"model_id": "nemotron", "net_pnl": 38.5}],
            }
        elif "/audit/verify" in url:
            resp.json.return_value = {
                "is_valid": True,
                "total_events": 33,
            }
        return resp

    mock_client._session.request.side_effect = fake_request

    summary = run_daily_session_workflow(
        session_date="2026-09-17",
        symbol="TATAMOTORS",
        mock_llm=True,
        client=mock_client,
    )

    assert summary["status"] == "success"
    assert summary["session_id"] == "sim_20260917"
    assert summary["trades_executed"] == 4
    assert summary["net_pnl"] == 38.5
    assert summary["audit_chain_valid"] is True
    assert "nemotron" in summary["top_performing_model"]
    assert "Paper session sim_20260917 completed successfully" in summary["operator_message"]


def test_hermes_integration_with_test_client(tmp_path):
    """
    End-to-end integration test: Hermes client operates through an in-memory FastAPI instance.
    Validates Hermes reading state and executing a session through the API.
    """
    from starlette.testclient import TestClient

    test_db = tmp_path / "hermes_integration.db"
    repo = PaperDatabaseRepository(db_path=str(test_db))
    repo._init_db()

    app = create_app(db_path=str(test_db))

    # Adapter connecting Hermes client to Starlette TestClient
    client = AutoTradeOperatorClient(base_url="http://testserver")
    test_client = TestClient(app)

    def custom_request(method, url, **kwargs):
        # Extract path from URL
        path = url.replace("http://testserver", "")
        # Forward request to TestClient
        resp = test_client.request(
            method=method,
            url=path,
            params=kwargs.get("params"),
            json=kwargs.get("json"),
        )
        return resp

    client._session.request = custom_request

    tools = AutoTradeHermesTools(client=client)

    # 1. Hermes reads health
    health = tools.tool_get_health()
    assert health["status"] in ("ok", "degraded")
    assert health["market_session"]["market"] == "NSE"

    # 2. Hermes inspects risk
    risk = tools.tool_get_risk()
    assert risk["market_segment"] == "NSE Cash Intraday"
    assert risk["hard_stop_loss_pct"] == -5.0
    assert risk["max_trades_per_session"] == 20

    # 3. Hermes runs session workflow
    summary = run_daily_session_workflow(
        session_date="2026-09-17",
        symbol="TATAMOTORS",
        mock_llm=True,
        client=client,
    )

    assert summary["status"] == "success"
    assert summary["trades_executed"] > 0
    assert summary["audit_chain_valid"] is True

    # 4. Hermes queries trade journal
    trades = tools.tool_get_trades(session_id=summary["session_id"])
    assert trades["count"] > 0
