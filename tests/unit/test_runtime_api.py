"""
Unit tests for Runtime Activity Monitor and Observability Endpoints (Phase 12).
"""

import pytest
from starlette.testclient import TestClient
from mobitrade.api.app import create_app
from mobitrade.logging.runtime_monitor import runtime_monitor


@pytest.fixture
def api_client(tmp_path):
    test_db = tmp_path / "runtime_test.db"
    app = create_app(db_path=str(test_db))
    return TestClient(app)


def test_runtime_status_endpoint(api_client):
    """Test GET /runtime/status reflects live state and idle state."""
    # Test idle
    runtime_monitor.set_idle()
    res = api_client.get("/runtime/status")
    assert res.status_code == 200
    data = res.json()
    assert data["current_model"] == "IDLE"
    assert data["current_phase"] == "IDLE"
    assert data["is_active"] is False

    # Test active
    runtime_monitor.set_active("qwen", "INFERENCE", "Qwen analyzing TATAMOTORS", "sim_001", "TATAMOTORS")
    res_active = api_client.get("/runtime/status")
    assert res_active.status_code == 200
    data_active = res_active.json()
    assert data_active["current_model"] == "qwen"
    assert data_active["current_phase"] == "INFERENCE"
    assert data_active["is_active"] is True
    assert data_active["symbol"] == "TATAMOTORS"
    assert data_active["session_id"] == "sim_001"
    assert any(step["name"] == "Infer" and step["active"] is True for step in data_active["pipeline_steps"])

    # Reset
    runtime_monitor.set_idle()


def test_activity_feed_endpoint(api_client):
    """Test GET /activity returns recent rolling events with timestamps."""
    runtime_monitor.record_event("Test live feed event 1", model_id="nemotron", phase="LOAD")
    runtime_monitor.record_event("Test live feed event 2", model_id="qwen", phase="INFERENCE")

    res = api_client.get("/activity?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 2
    messages = [e["message"] for e in data["events"]]
    assert "Test live feed event 2" in messages


def test_activity_current_endpoint(api_client):
    """Test GET /activity/current returns combined status and recent events."""
    res = api_client.get("/activity/current")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "recent_events" in data
