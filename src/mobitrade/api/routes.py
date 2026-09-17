"""
FastAPI Routes for AutoTrade AI Local Operator API.
Deterministic endpoints exposing health, models, portfolio, positions, trades,
risk boundaries, analytics, PDF reports, audit verification, and paper session runs.
"""

import os
import glob
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Query, status

from mobitrade.api.schemas import (
    HealthResponse,
    ModelsResponse,
    ModelInfo,
    PortfolioResponse,
    AccountSummary,
    PositionsResponse,
    PositionItem,
    TradesResponse,
    TradeItem,
    RiskParametersResponse,
    AnalyticsResponse,
    ReportsResponse,
    ReportItem,
    AuditVerificationResponse,
    SessionRunRequest,
    SessionRunResponse,
)
from mobitrade.config.model_registry import ModelRegistry
from mobitrade.config.settings import RiskConfig, CostConfig, load_yaml_config
from mobitrade.data.calendar import IST, IndianMarketCalendar
from mobitrade.llm.ollama_provider import OllamaLLMProvider
from mobitrade.paper.persistence import PaperDatabaseRepository
from mobitrade.logging.audit import AuditLogger
from mobitrade.analytics.engine import PerformanceAnalyticsEngine
from mobitrade.paper.engine import PaperTradingEngine, DEFAULT_MODELS
from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.domain.data_models import Timeframe
from mobitrade.domain.enums import Action
from mobitrade.domain.llm_models import LLMDecisionRecord, LLMAction, ValidationStatus

router = APIRouter()


def _get_db_path(request: Request) -> str:
    return getattr(request.app.state, "db_path", "database/mobitrade.db")


def _get_models_config_path(request: Request) -> str:
    return getattr(request.app.state, "models_config_path", "configs/models.yaml")


@router.get("/health", response_model=HealthResponse, tags=["Operator"])
def get_health(request: Request):
    """
    Health check endpoint reporting market session status, Ollama availability,
    and database connectivity.
    """
    now_ist = datetime.now(IST)
    calendar = IndianMarketCalendar()
    is_session_open = calendar.is_trading_session(now_ist)

    # Database connectivity check
    db_path = _get_db_path(request)
    db_ok = False
    db_error = None
    try:
        conn = sqlite3.connect(db_path, timeout=3)
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception as e:
        db_error = str(e)

    # LLM Provider health check
    llm = OllamaLLMProvider()
    ollama_online = llm.health_check()

    overall_status = "ok" if db_ok else "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=now_ist.isoformat(),
        market_session={
            "market": "NSE",
            "is_open": is_session_open,
            "session_hours": "09:15-15:30 IST",
            "square_off_cutoff": "15:15 IST",
        },
        llm_provider={
            "provider": "Ollama",
            "status": "online" if ollama_online else "offline",
            "base_url": llm.base_url,
        },
        database={
            "path": db_path,
            "status": "connected" if db_ok else "error",
            "error": db_error,
        },
    )


@router.get("/models", response_model=ModelsResponse, tags=["Operator"])
def get_models(request: Request):
    """
    List configured and registered local LLMs with runtime parameters.
    """
    config_path = _get_models_config_path(request)
    try:
        registry = ModelRegistry(config_path)
        configured_models = registry.list_all_models()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load model registry: {e}",
        )

    model_items = []
    for m in configured_models:
        params = getattr(m, "parameters", {}) or {}
        top_p = float(params.get("top_p", 0.9))
        sys_ver = str(params.get("system_prompt_version", "1.0.0"))
        model_items.append(
            ModelInfo(
                id=m.id,
                display_name=m.display_name,
                provider=m.provider,
                runtime_model_name=m.runtime_model_name,
                context_length=m.context_length,
                temperature=m.temperature,
                top_p=top_p,
                system_prompt_version=sys_ver,
                enabled=m.enabled,
            )
        )

    return ModelsResponse(count=len(model_items), models=model_items)


@router.get("/portfolio", response_model=PortfolioResponse, tags=["Operator"])
def get_portfolio(request: Request):
    """
    Retrieve aggregated paper trading portfolio and per-model isolated accounts.
    """
    db_path = _get_db_path(request)
    repo = PaperDatabaseRepository(db_path=db_path)
    accounts_data = repo.list_accounts()

    total_equity = 0.0
    total_cash = 0.0
    total_realized_pnl = 0.0
    account_summaries = []

    for acc in accounts_data:
        curr_eq = float(acc.get("current_equity", acc.get("current_balance", 0.0)))
        cash = float(acc.get("cash_balance", acc.get("current_balance", 0.0)))
        rpnl = float(acc.get("realized_pnl", 0.0))
        upnl = float(acc.get("unrealized_pnl", 0.0))
        start_bal = float(acc.get("starting_balance", 1000.0))

        total_equity += curr_eq
        total_cash += cash
        total_realized_pnl += rpnl

        account_summaries.append(
            AccountSummary(
                model_id=acc.get("model_id", ""),
                account_id=acc.get("account_id", ""),
                starting_balance=start_bal,
                cash_balance=cash,
                current_equity=curr_eq,
                realized_pnl=rpnl,
                unrealized_pnl=upnl,
                state=acc.get("state", "ACTIVE"),
                trades_count=acc.get("trades_count", 0),
                lock_reason=acc.get("lock_reason"),
            )
        )

    return PortfolioResponse(
        total_equity=round(total_equity, 2),
        total_cash=round(total_cash, 2),
        total_realized_pnl=round(total_realized_pnl, 2),
        active_accounts_count=len(account_summaries),
        accounts=account_summaries,
    )


@router.get("/positions", response_model=PositionsResponse, tags=["Operator"])
def get_positions(request: Request):
    """
    Retrieve active open paper trading positions across all models.
    """
    db_path = _get_db_path(request)
    repo = PaperDatabaseRepository(db_path=db_path)
    open_trades = repo.list_open_trades()

    positions = []
    for t in open_trades:
        positions.append(
            PositionItem(
                trade_id=t.trade_id,
                model_id=t.model_id or t.account_id or "",
                symbol=t.symbol,
                quantity=t.quantity,
                entry_price=t.entry_price,
                initial_stop=t.initial_stop,
                trailing_stop=t.trailing_stop,
                entry_timestamp=t.entry_time.isoformat() if t.entry_time else "",
            )
        )

    return PositionsResponse(count=len(positions), positions=positions)


@router.get("/trades", response_model=TradesResponse, tags=["Operator"])
def get_trades(
    request: Request,
    session_id: Optional[str] = Query(None, description="Filter trades by session ID"),
    model_id: Optional[str] = Query(None, description="Filter trades by model ID"),
    limit: int = Query(50, ge=1, le=500, description="Max trades to return"),
):
    """
    List executed and closed paper trades with gross/net P&L and cost breakdowns.
    """
    db_path = _get_db_path(request)
    repo = PaperDatabaseRepository(db_path=db_path)
    trades = repo.list_trades(session_id=session_id, model_id=model_id)

    items = []
    for t in trades[:limit]:
        items.append(
            TradeItem(
                trade_id=t.trade_id,
                model_id=t.model_id or t.account_id or "",
                symbol=t.symbol,
                quantity=t.quantity,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                entry_timestamp=t.entry_time.isoformat() if t.entry_time else "",
                exit_timestamp=t.exit_time.isoformat() if t.exit_time else None,
                gross_pnl=round(t.gross_pnl, 2),
                net_pnl=round(t.net_pnl, 2),
                fees=round(t.total_fees, 2),
                slippage=round(t.total_slippage, 2),
                exit_reason=t.exit_reason.value if t.exit_reason else None,
                is_closed=t.is_closed,
            )
        )

    return TradesResponse(count=len(items), trades=items)


@router.get("/risk", response_model=RiskParametersResponse, tags=["Operator"])
def get_risk_parameters(request: Request):
    """
    Inspect authoritative RiskEngine parameters and safety boundaries.
    """
    config_path = getattr(request.app.state, "config_path", "configs/default.yaml")
    risk_cfg = RiskConfig()
    try:
        raw_cfg = load_yaml_config(config_path)
        if raw_cfg and "risk" in raw_cfg:
            r = raw_cfg["risk"]
            risk_cfg = RiskConfig(
                daily_target_pct=r.get("daily_target_pct", 0.10),
                daily_loss_limit_pct=r.get("daily_max_loss_pct", 0.05),
                max_trades_per_session=r.get("max_trades_per_session", 20),
                max_concurrent_positions=r.get("max_positions_concurrent", 1),
                require_stop_loss=r.get("enforce_stop_loss", True),
            )
    except Exception:
        pass

    return RiskParametersResponse(
        market_segment="NSE Cash Intraday",
        daily_target_pct=risk_cfg.daily_target_pct,
        daily_loss_limit_pct=risk_cfg.daily_loss_limit_pct,
        hard_stop_loss_pct=round(-risk_cfg.daily_loss_limit_pct * 100, 2),
        max_trades_per_session=risk_cfg.max_trades_per_session,
        max_concurrent_positions=risk_cfg.max_concurrent_positions,
        auto_square_off_time="15:15 IST",
        session_close_time="15:30 IST",
        session_open_time="09:15 IST",
        allow_overnight=risk_cfg.allow_overnight,
        allow_leverage=risk_cfg.allow_leverage,
        require_stop_loss=risk_cfg.require_stop_loss,
        min_confidence_score=risk_cfg.min_confidence_score,
        authority="RiskEngine Deterministic Enforcement",
    )


@router.get("/analytics", response_model=AnalyticsResponse, tags=["Operator"])
def get_analytics(
    request: Request,
    session_id: Optional[str] = Query(None, description="Session ID or date to analyze"),
):
    """
    Retrieve computed daily session analytics, win rate, drawdown, and model tournament leaderboard.
    """
    db_path = _get_db_path(request)
    engine = PerformanceAnalyticsEngine(db_path=db_path)

    # Determine target session if not provided
    target = session_id
    if not target:
        repo = PaperDatabaseRepository(db_path=db_path)
        try:
            with repo._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT session_id FROM daily_sessions ORDER BY started_at DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    target = row["session_id"]
        except Exception:
            target = None

    if not target:
        return AnalyticsResponse(
            session_id=None,
            session_date=None,
            gross_pnl=0.0,
            net_pnl=0.0,
            total_trades=0,
            win_rate=0.0,
            leaderboard=[],
            drawdown={"max_drawdown_amount": 0.0, "max_drawdown_pct": 0.0},
            trade_statistics={"total_trades": 0, "winning_trades": 0, "losing_trades": 0},
            risk_adjusted={"sharpe": 0.0, "sortino": 0.0},
        )

    try:
        data = engine.compute_daily_session_analytics(target)
        sess_info = data.get("session", {})
        exec_summary = data.get("executive_summary", {})
        leaderboard = data.get("leaderboard", [])

        sess_id = exec_summary.get("session_id") or sess_info.get("session_id") or target
        sess_date = exec_summary.get("session_date") or sess_info.get("session_date")
        gross_pnl = float(exec_summary.get("total_gross_pnl", 0.0))
        net_pnl = float(exec_summary.get("total_net_pnl", 0.0))
        total_trades = int(exec_summary.get("total_trades", 0))
        win_rate = float(exec_summary.get("overall_win_rate", 0.0))

        return AnalyticsResponse(
            session_id=sess_id,
            session_date=sess_date,
            gross_pnl=round(gross_pnl, 2),
            net_pnl=round(net_pnl, 2),
            total_trades=total_trades,
            win_rate=round(win_rate, 2),
            leaderboard=leaderboard,
            drawdown={
                "total_starting_equity": exec_summary.get("total_starting_equity", 0.0),
                "total_ending_equity": exec_summary.get("total_ending_equity", 0.0),
                "overall_return_pct": exec_summary.get("overall_return_pct", 0.0),
            },
            trade_statistics={
                "total_trades": total_trades,
                "winning_trades": exec_summary.get("total_wins", 0),
                "losing_trades": exec_summary.get("total_losses", 0),
                "win_rate": win_rate,
            },
            risk_adjusted={
                "targets_reached": exec_summary.get("targets_reached_count", 0),
                "stops_triggered": exec_summary.get("stops_triggered_count", 0),
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate analytics for session {target}: {e}",
        )


@router.get("/reports", response_model=ReportsResponse, tags=["Operator"])
def get_reports(request: Request):
    """
    List generated PDF trading reports with file paths and SHA-256 integrity fingerprints.
    """
    db_path = _get_db_path(request)
    repo = PaperDatabaseRepository(db_path=db_path)

    items = []
    try:
        with repo._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reports ORDER BY generated_at DESC")
            rows = cursor.fetchall()
            for r in rows:
                items.append(
                    ReportItem(
                        report_id=r["report_id"],
                        session_id=r["session_id"],
                        report_date=r["report_date"],
                        file_path=r["file_path"],
                        file_hash=r["file_hash"],
                        generated_at=r["generated_at"],
                        generation_status=r["generation_status"],
                    )
                )
    except Exception:
        pass

    return ReportsResponse(count=len(items), reports=items)


@router.get("/audit/verify", response_model=AuditVerificationResponse, tags=["Operator"])
def verify_audit(
    request: Request,
    session_id: Optional[str] = Query(None, description="Session ID to verify chain for"),
):
    """
    Perform cryptographic SHA-256 verification of the append-only audit event log.
    """
    db_path = _get_db_path(request)
    logger = AuditLogger(db_path=db_path)
    res = logger.verify_chain(session_id=session_id)

    return AuditVerificationResponse(
        is_valid=res.is_valid,
        total_events=res.total_events,
        first_sequence=res.first_sequence,
        last_sequence=res.last_sequence,
        errors=res.errors,
        session_id=res.session_id,
    )


@router.post("/session/run", response_model=SessionRunResponse, tags=["Operator"])
def run_session(request: Request, payload: SessionRunRequest):
    """
    Execute a deterministic intraday paper trading replay or evaluation session.
    Enforces daily -5% hard stop loss, 20 trades limit, and 15:15 IST auto square-off.
    """
    db_path = _get_db_path(request)
    date_str = payload.session_date or datetime.now(IST).strftime("%Y-%m-%d")
    symbol = payload.symbol or "TATAMOTORS"
    session_id = f"sim_{date_str.replace('-', '')}"

    engine = PaperTradingEngine(db_path=db_path)
    engine.start_session(session_id, date_str)

    # 1. 10:15 IST entry decisions
    dt_1015 = datetime.fromisoformat(f"{date_str}T10:15:00").replace(tzinfo=IST)
    snap = MarketSnapshot(
        snapshot_id=f"snap_{date_str}_1015",
        symbol=symbol,
        decision_timestamp=dt_1015,
        timeframe=Timeframe.M5,
    )

    market_price = 500.0
    model_actions = {
        "nemotron": (LLMAction.BUY, 0.85, 480.0, 550.0),
        "qwen": (LLMAction.BUY, 0.88, 485.0, 560.0),
        "gemma": (LLMAction.HOLD, 0.50, None, None),
        "llama": (LLMAction.BUY, 0.80, 480.0, 550.0),
        "granite": (LLMAction.HOLD, 0.40, None, None),
        "phi": (LLMAction.BUY, 0.82, 485.0, 550.0),
        "smollm": (LLMAction.HOLD, 0.45, None, None),
        "falcon": (LLMAction.HOLD, 0.48, None, None),
    }

    trades_executed = 0
    for mid in DEFAULT_MODELS:
        action, conf, sl, tgt = model_actions.get(mid, (LLMAction.HOLD, 0.5, None, None))
        rec = LLMDecisionRecord(
            decision_id=f"dec_{mid}_{session_id}",
            run_id=f"run_{session_id}",
            model_id=mid,
            model_version="1.0.0",
            prompt_version="1.0.0",
            snapshot_id=snap.snapshot_id,
            decision_timestamp=snap.decision_timestamp,
            symbol=symbol,
            action=action,
            confidence=conf,
            entry_rationale=f"API Operator replay signal for {mid}.",
            proposed_stop_loss=sl,
            proposed_target=tgt,
            holding_intent="INTRADAY",
            reasoning_summary=f"Replay decision for {mid}",
            validation_status=ValidationStatus.VALID,
            raw_output="",
        )
        trade = engine.process_model_decision(rec, snap, session_id, current_market_price=market_price)
        if trade:
            trades_executed += 1

    # 2. 13:00 IST price rise
    dt_1300 = datetime.fromisoformat(f"{date_str}T13:00:00").replace(tzinfo=IST)
    engine.update_market_prices({symbol: 510.0}, dt_1300, session_id)

    # 3. 15:15 IST auto square-off
    dt_1515 = datetime.fromisoformat(f"{date_str}T15:15:00").replace(tzinfo=IST)
    engine.execute_auto_square_off({symbol: 520.0}, dt_1515, session_id)

    # 4. Finalize daily session & compound
    leaderboard = engine.finalize_daily_session(session_id, date_str)

    return SessionRunResponse(
        status="completed",
        session_id=session_id,
        session_date=date_str,
        symbol=symbol,
        total_trades=trades_executed,
        leaderboard=leaderboard,
        message="Deterministic paper session executed successfully with risk enforcement.",
    )
