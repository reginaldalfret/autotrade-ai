"""
HTTP Client for Hermes Operator interacting with AutoTrade AI Local Operator API.
Deterministic, isolated client with strict error and timeout boundaries.
"""

from typing import Dict, Any, Optional, List
import requests


class HermesOperatorError(Exception):
    """Base exception for Hermes operator communication errors."""
    pass


class HermesConnectionError(HermesOperatorError):
    """Raised when the AutoTrade AI Local Operator API cannot be reached."""
    pass


class HermesTimeoutError(HermesOperatorError):
    """Raised when an API request to AutoTrade AI times out."""
    pass


class AutoTradeOperatorClient:
    """
    Client allowing an external Hermes agent to inspect and operate AutoTrade AI.
    Connects strictly to localhost (127.0.0.1). Does NOT access database or core trading logic directly.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Hermes-Agent-AutoTrade-Operator/1.0",
            "Accept": "application/json",
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        try:
            resp = self._session.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout) as e:
            raise HermesTimeoutError(
                f"AutoTrade AI API request to {endpoint} timed out after {self.timeout}s: {e}"
            ) from e
        except (requests.exceptions.ConnectionError, requests.exceptions.ProxyError) as e:
            raise HermesConnectionError(
                f"Cannot connect to AutoTrade AI API at {url}. "
                f"Ensure the API server is running (`python -m autotrade_ai.api`): {e}"
            ) from e
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "Unknown"
            text = e.response.text if e.response is not None else str(e)
            raise HermesOperatorError(
                f"AutoTrade AI API returned HTTP {status_code} on {endpoint}: {text}"
            ) from e
        except Exception as e:
            raise HermesOperatorError(
                f"Unexpected error communicating with AutoTrade AI API on {endpoint}: {e}"
            ) from e

    def get_health(self) -> Dict[str, Any]:
        """Query system health, market session status, and provider readiness."""
        return self._request("GET", "/health")

    def get_models(self) -> Dict[str, Any]:
        """List registered local LLMs with runtime parameters."""
        return self._request("GET", "/models")

    def get_portfolio(self) -> Dict[str, Any]:
        """Retrieve aggregated paper trading portfolio and model accounts."""
        return self._request("GET", "/portfolio")

    def get_positions(self) -> Dict[str, Any]:
        """Retrieve currently open paper positions across models."""
        return self._request("GET", "/positions")

    def get_trades(
        self,
        session_id: Optional[str] = None,
        model_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Retrieve completed trades journal with gross/net P&L and fees."""
        params = {"limit": limit}
        if session_id:
            params["session_id"] = session_id
        if model_id:
            params["model_id"] = model_id
        return self._request("GET", "/trades", params=params)

    def get_risk(self) -> Dict[str, Any]:
        """Inspect authoritative RiskEngine parameters and safety limits."""
        return self._request("GET", "/risk")

    def get_analytics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve performance analytics, win rate, drawdown, and leaderboard."""
        params = {}
        if session_id:
            params["session_id"] = session_id
        return self._request("GET", "/analytics", params=params)

    def get_reports(self) -> Dict[str, Any]:
        """Retrieve generated daily PDF reports and SHA-256 fingerprints."""
        return self._request("GET", "/reports")

    def verify_audit(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Verify cryptographic SHA-256 tamper-evident audit log chain."""
        params = {}
        if session_id:
            params["session_id"] = session_id
        return self._request("GET", "/audit/verify", params=params)

    def run_paper_session(
        self,
        session_date: Optional[str] = None,
        symbol: Optional[str] = "TATAMOTORS",
        symbols: Optional[List[str]] = None,
        mock_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        Request explicit execution of a deterministic paper trading replay session.
        Enforces -5% daily stop, 20 max trades, 15:15 IST auto square-off.
        """
        payload: Dict[str, Any] = {
            "session_date": session_date,
            "symbol": symbol,
            "symbols": symbols,
            "mock_llm": mock_llm,
        }
        return self._request("POST", "/session/run", json=payload)
