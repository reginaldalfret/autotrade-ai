"""
Hermes Operator Integration for AutoTrade AI.
Safe client and tool adapter for external Hermes agent operator tooling.
"""

from mobitrade.hermes.client import (
    AutoTradeOperatorClient,
    HermesOperatorError,
    HermesConnectionError,
    HermesTimeoutError,
)
from mobitrade.hermes.tools import get_hermes_tools, AutoTradeHermesTools
from mobitrade.hermes.workflow import run_daily_session_workflow

__all__ = [
    "AutoTradeOperatorClient",
    "AutoTradeHermesTools",
    "get_hermes_tools",
    "run_daily_session_workflow",
    "HermesOperatorError",
    "HermesConnectionError",
    "HermesTimeoutError",
]
