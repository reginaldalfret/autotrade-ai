"""
Hermes Operator Example Workflows for AutoTrade AI.
Demonstrates orchestrating multi-step operator actions via the localhost API:
Run session -> Retrieve analytics -> Verify audit integrity -> Return concise summary.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from mobitrade.hermes.client import AutoTradeOperatorClient


def run_daily_session_workflow(
    session_date: Optional[str] = None,
    symbol: str = "TATAMOTORS",
    mock_llm: bool = True,
    client: Optional[AutoTradeOperatorClient] = None,
    base_url: str = "http://127.0.0.1:8000",
) -> Dict[str, Any]:
    """
    Standard Operator Workflow:
    Hermes: 'Run today's paper session for AutoTrade AI'
      1. POST /session/run (executes intraday replay with RiskEngine checks)
      2. GET /analytics (retrieves daily performance and tournament leaderboard)
      3. GET /audit/verify (verifies tamper-evident cryptographic hash chain)
      4. Compiles concise, structured operator report.
    """
    operator = client or AutoTradeOperatorClient(base_url=base_url)
    date_str = session_date or datetime.now().strftime("%Y-%m-%d")

    # Step 1: Trigger paper session replay
    session_resp = operator.run_paper_session(
        session_date=date_str,
        symbol=symbol,
        mock_llm=mock_llm,
    )
    session_id = session_resp.get("session_id", f"sim_{date_str.replace('-', '')}")

    # Step 2: Retrieve computed session analytics
    analytics_resp = operator.get_analytics(session_id=session_id)

    # Step 3: Verify audit log integrity
    audit_resp = operator.verify_audit(session_id=session_id)

    # Step 4: Format concise operator summary
    leaderboard = analytics_resp.get("leaderboard", [])
    top_model = leaderboard[0]["model_id"] if leaderboard else "N/A"
    top_pnl = leaderboard[0].get("net_pnl", 0.0) if leaderboard else 0.0

    summary = {
        "status": "success",
        "session_id": session_id,
        "session_date": date_str,
        "symbol": symbol,
        "trades_executed": session_resp.get("total_trades", 0),
        "gross_pnl": analytics_resp.get("gross_pnl", 0.0),
        "net_pnl": analytics_resp.get("net_pnl", 0.0),
        "win_rate_pct": analytics_resp.get("win_rate", 0.0),
        "top_performing_model": f"{top_model} (₹{top_pnl:+.2f})",
        "audit_chain_valid": audit_resp.get("is_valid", False),
        "audit_events_count": audit_resp.get("total_events", 0),
        "operator_message": (
            f"Paper session {session_id} completed successfully for {symbol}. "
            f"Net P&L: ₹{analytics_resp.get('net_pnl', 0.0):+.2f}. "
            f"Top model: {top_model}. "
            f"Audit chain verified: {'PASS' if audit_resp.get('is_valid') else 'FAIL'}."
        ),
    }

    return summary
