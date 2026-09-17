"""
Hermes Tool Definitions and Dispatcher for AutoTrade AI.
Exposes safe, structured tools with strict risk and domain boundary prompts for agent consumption.
"""

from typing import Dict, Any, List, Optional, Callable
from mobitrade.hermes.client import AutoTradeOperatorClient

HERMES_SYSTEM_CONSTRAINTS = (
    "OPERATIONAL BOUNDARIES FOR AUTOTRADE AI:\n"
    "1. Market: NSE Indian Cash Equities only. No F&O, no crypto, no forex.\n"
    "2. Execution Mode: STRICT PAPER TRADING ONLY. No live broker connection or real capital.\n"
    "3. Trading Window: 09:15 to 15:30 IST.\n"
    "4. Auto Square-Off: 15:15 IST mandatory position closure.\n"
    "5. Overnight Positions: ZERO overnight holding allowed (intraday only).\n"
    "6. Risk Limit: Daily hard stop loss shutdown at -5.0% of starting equity.\n"
    "7. Trade Cap: Maximum 20 completed trades per model per daily session.\n"
    "8. Trailing Stop: Dynamic trailing stop loss enforced on all open trades.\n"
    "9. Authority: The RiskEngine is deterministic and final. LLM proposals are rejected if unsafe.\n"
    "10. Invocations: Session runs require explicit operator action. Background loops are prohibited."
)


class AutoTradeHermesTools:
    """
    Hermes Agent Toolset for controlling and monitoring AutoTrade AI.
    Each tool maps directly to an existing Phase 9 API endpoint with strict boundary enforcement.
    """

    def __init__(self, client: Optional[AutoTradeOperatorClient] = None, base_url: str = "http://127.0.0.1:8000"):
        self.client = client or AutoTradeOperatorClient(base_url=base_url)

    def tool_get_health(self) -> Dict[str, Any]:
        """
        Check AutoTrade AI platform health, NSE market session status (09:15-15:30 IST),
        local Ollama LLM provider availability, and SQLite database connectivity.
        """
        return self.client.get_health()

    def tool_get_models(self) -> Dict[str, Any]:
        """
        List all 8 registered local LLM tournament models, provider settings, context length,
        temperature, and runtime model names.
        """
        return self.client.get_models()

    def tool_get_portfolio(self) -> Dict[str, Any]:
        """
        Retrieve paper trading portfolio metrics, aggregate cash and equity balances,
        and individual isolated account states for all 8 tournament models.
        """
        return self.client.get_portfolio()

    def tool_get_positions(self) -> Dict[str, Any]:
        """
        List active open intraday paper positions across all models with entry prices,
        initial stop loss, and dynamic trailing stop levels.
        """
        return self.client.get_positions()

    def tool_get_trades(
        self,
        session_id: Optional[str] = None,
        model_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Query the executed paper trading journal. Returns trades with gross P&L,
        statutory fees (STT, exchange, SEBI, GST, stamp duty), slippage, and net P&L.
        """
        return self.client.get_trades(session_id=session_id, model_id=model_id, limit=limit)

    def tool_get_risk(self) -> Dict[str, Any]:
        """
        Inspect authoritative RiskEngine parameters: -5% hard stop shutdown,
        +10% target shutdown, 20 max trades/session, 15:15 IST auto square-off cutoff,
        and zero overnight holding constraints.
        """
        return self.client.get_risk()

    def tool_get_analytics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve performance analytics for a session: overall win rate, total trades,
        net P&L, maximum drawdown, and 8-model tournament leaderboard ranking.
        """
        return self.client.get_analytics(session_id=session_id)

    def tool_get_reports(self) -> Dict[str, Any]:
        """
        List compiled institutional PDF trading reports with physical file paths and
        cryptographic SHA-256 integrity fingerprints.
        """
        return self.client.get_reports()

    def tool_verify_audit(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify cryptographic SHA-256 hash chain of the append-only tamper-evident audit log.
        Returns validation status, total event count, sequence numbers, and any detected errors.
        """
        return self.client.verify_audit(session_id=session_id)

    def tool_run_paper_session(
        self,
        session_date: Optional[str] = None,
        symbol: Optional[str] = "TATAMOTORS",
        mock_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        Explicitly trigger a deterministic intraday paper trading replay session for a given symbol and date.
        Strictly enforces -5% daily hard stop, max 20 trades, and 15:15 IST auto square-off.
        Autonomous background execution is disallowed.
        """
        return self.client.run_paper_session(
            session_date=session_date,
            symbol=symbol,
            mock_llm=mock_llm,
        )

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Returns JSON schema definitions for Hermes agent tool calling.
        """
        return [
            {
                "name": "autotrade_get_health",
                "description": "Inspect AutoTrade AI health, NSE market session (09:15-15:30 IST), and database connectivity.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "autotrade_get_models",
                "description": "List the 8 registered local LLMs and tournament parameters.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "autotrade_get_portfolio",
                "description": "Get paper trading cash, equity, and isolated model accounts.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "autotrade_get_positions",
                "description": "List open paper positions with initial and trailing stops.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "autotrade_get_trades",
                "description": "List executed trades with gross/net P&L and fees.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Optional session ID filter"},
                        "model_id": {"type": "string", "description": "Optional model ID filter"},
                        "limit": {"type": "integer", "description": "Max trades to return (default: 50)"},
                    },
                    "required": [],
                },
            },
            {
                "name": "autotrade_get_risk",
                "description": "Inspect authoritative RiskEngine parameters (-5% hard stop, 20 max trades, 15:15 IST square-off).",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "autotrade_get_analytics",
                "description": "Get session win rate, net P&L, drawdown, and model leaderboard.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Optional session ID to analyze"},
                    },
                    "required": [],
                },
            },
            {
                "name": "autotrade_get_reports",
                "description": "List generated daily PDF reports with SHA-256 fingerprints.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "autotrade_verify_audit",
                "description": "Verify cryptographic SHA-256 hash chain of the audit log.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Optional session ID to verify"},
                    },
                    "required": [],
                },
            },
            {
                "name": "autotrade_run_paper_session",
                "description": "Execute deterministic paper trading replay session with strict RiskEngine enforcement. Requires explicit invocation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_date": {"type": "string", "description": "Session date YYYY-MM-DD (e.g. '2026-09-17')"},
                        "symbol": {"type": "string", "description": "NSE Equity symbol (e.g. 'TATAMOTORS')"},
                        "mock_llm": {"type": "boolean", "description": "Use deterministic replay signals (default: true)"},
                    },
                    "required": [],
                },
            },
        ]

    def execute_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Dispatch tool execution by name for Hermes agent integrations.
        """
        args = arguments or {}
        mapping: Dict[str, Callable[..., Dict[str, Any]]] = {
            "autotrade_get_health": self.tool_get_health,
            "autotrade_get_models": self.tool_get_models,
            "autotrade_get_portfolio": self.tool_get_portfolio,
            "autotrade_get_positions": self.tool_get_positions,
            "autotrade_get_trades": lambda: self.tool_get_trades(**args),
            "autotrade_get_risk": self.tool_get_risk,
            "autotrade_get_analytics": lambda: self.tool_get_analytics(**args),
            "autotrade_get_reports": self.tool_get_reports,
            "autotrade_verify_audit": lambda: self.tool_verify_audit(**args),
            "autotrade_run_paper_session": lambda: self.tool_run_paper_session(**args),
        }

        if tool_name not in mapping:
            raise ValueError(f"Unknown AutoTrade AI tool: {tool_name}")

        return mapping[tool_name]()


def get_hermes_tools(base_url: str = "http://127.0.0.1:8000") -> AutoTradeHermesTools:
    """Helper factory for instantiating Hermes tools."""
    client = AutoTradeOperatorClient(base_url=base_url)
    return AutoTradeHermesTools(client=client)
