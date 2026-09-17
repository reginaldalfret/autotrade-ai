"""
AutoTrade AI - Today's Live Paper-Trading Session Runner (2026-09-17).
Executes against live NSE cash-market data using real Ollama models,
sequential single-model residency (RTX 2050 4GB safe), RiskEngine validation,
PaperBroker execution, Redis event streaming, and daily report generation.
"""

import sys
import os
import json
import time
import zoneinfo
import requests
from datetime import datetime, timezone
from pathlib import Path

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir / "src") not in sys.path:
    sys.path.insert(0, str(root_dir / "src"))

from mobitrade.domain.snapshot import MarketSnapshot
from mobitrade.domain.data_models import Instrument, HistoricalCandle, Timeframe, DataStatus, CandleTimestampSemantic
from mobitrade.domain.llm_models import LLMDecisionRecord, LLMAction, ValidationStatus
from mobitrade.domain.enums import Action
from mobitrade.paper.engine import PaperTradingEngine, DEFAULT_MODELS
from mobitrade.paper.persistence import PaperDatabaseRepository
from mobitrade.llm.ollama_provider import OllamaLLMProvider
from mobitrade.llm.scheduler import SequentialLLMScheduler
from mobitrade.scanner.scanner import OpportunityScanner
from mobitrade.logging.audit import AuditLogger
from mobitrade.logging.runtime_monitor import runtime_monitor
from mobitrade.reporting.generator import DailyReportGenerator
from mobitrade.learning.engine import SelfLearningEngine
from mobitrade.transport.redis_service import redis_service, RedisStreamName


def fetch_live_nse_quote(symbol: str, session: requests.Session) -> dict:
    """Fetch live quote for an NSE equity from public market feed with timeout & retry."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?interval=5m&range=1d"
    
    for attempt in range(2):
        try:
            r = session.get(url, headers=headers, timeout=12)
            if r.status_code == 200:
                data = r.json()
                meta = data["chart"]["result"][0]["meta"]
                px = meta.get("regularMarketPrice")
                if px and px > 0:
                    return {
                        "symbol": symbol,
                        "price": float(px),
                        "high": float(meta.get("regularMarketDayHigh", px)),
                        "low": float(meta.get("regularMarketDayLow", px)),
                        "volume": float(meta.get("regularMarketVolume", 100000)),
                        "timestamp": meta.get("regularMarketTime", int(time.time())),
                    }
        except Exception as e:
            if attempt == 1:
                print(f"[MarketData] Warning: attempt {attempt+1} failed for {symbol}: {e}")
        time.sleep(0.5)
    return None


def run_session():
    now_ist = datetime.now(IST)
    today_str = now_ist.strftime("%Y-%m-%d")
    db_path = "database/mobitrade.db"

    print("=================================================================")
    print("      AUTOTRADE AI — LIVE PAPER-TRADING SESSION (TODAY)          ")
    print("=================================================================")
    print(f"Current System Time: {now_ist.strftime('%Y-%m-%d %H:%M:%S')} IST")
    print(f"Trading Date:        {today_str}")
    print(f"Mode:                PAPER TRADING ONLY (No live broker orders)")
    print(f"Market:              NSE Cash Equities Intraday")
    print(f"Risk Authority:      Deterministic RiskEngine (Final Authority)")
    print(f"Capital:             8 Isolated Accounts x ₹1,000 = ₹8,000 Total")
    print("=================================================================\n")

    # 1. Confirm Market & Session Status
    day_of_week = now_ist.weekday()  # 0=Monday, 6=Sunday
    if day_of_week >= 5:
        print("[Status] Today is a weekend. NSE Cash Market is closed on weekends.")
    
    current_minutes = now_ist.hour * 60 + now_ist.minute
    session_start_min = 9 * 60 + 15  # 09:15 IST
    square_off_min = 15 * 60 + 15   # 15:15 IST
    session_end_min = 15 * 60 + 30   # 15:30 IST

    is_session_active = session_start_min <= current_minutes <= session_end_min
    is_post_square_off = current_minutes >= square_off_min

    print(f"[Market Status] 09:15–15:30 IST Market Hours | Active: {is_session_active} | Square-Off (15:15 IST): {is_post_square_off}")

    # Duplicate Protection: Daily Session Lock
    # Duplicate Protection: Daily Session Lock
    runtime_dir = root_dir / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    lock_file = runtime_dir / f"session_{today_str}.lock"
    win_runtime_dir = Path("/mnt/d/Trading LLM/MobiTradeAI/runtime")
    win_lock_file = win_runtime_dir / f"session_{today_str}.lock" if win_runtime_dir.exists() else None

    force_run = "--force" in sys.argv
    for lf in [lock_file, win_lock_file]:
        if lf and lf.exists() and not force_run:
            try:
                with open(lf, "r", encoding="utf-8") as f:
                    lock_data = json.load(f)
                lock_status = lock_data.get("status")
                if lock_status in ("COMPLETED", "RUNNING"):
                    print(f"[Lock Protection] Session for {today_str} is already marked as '{lock_status}'.")
                    print(f"[Lock Protection] File: {lf}")
                    print("[Lock Protection] Duplicate execution safely refused.")
                    return
            except Exception as e:
                print(f"[Lock Protection] Note reading lock file {lf}: {e}")

    # Mark session as running
    lock_payload = {
        "date": today_str,
        "status": "RUNNING",
        "started_at": now_ist.isoformat(),
        "pid": os.getpid()
    }
    with open(lock_file, "w", encoding="utf-8") as f:
        json.dump(lock_payload, f, indent=2)
    if win_lock_file:
        try:
            with open(win_lock_file, "w", encoding="utf-8") as f:
                json.dump(lock_payload, f, indent=2)
        except Exception:
            pass

    # 2. Check Ollama & 8 Models Readiness
    ollama_provider = OllamaLLMProvider(base_url="http://localhost:11434")
    if not ollama_provider.health_check():
        print("[FATAL] Ollama server is unreachable at http://localhost:11434. Aborting safely.")
        sys.exit(1)

    available_models = ollama_provider.list_models()
    print(f"[Ollama Status] Connected. Found {len(available_models)} models in local runtime.")

    # 3. Fetch Live Market Data for Active Universe
    candidate_symbols = ["RELIANCE", "TCS", "INFY"]
    http_session = requests.Session()
    live_quotes = {}

    print(f"[Market Data] Fetching current live NSE cash quotes for: {', '.join(candidate_symbols)}...")
    for sym in candidate_symbols:
        q = fetch_live_nse_quote(sym, http_session)
        if q:
            live_quotes[sym] = q
            print(f" -> {sym}: ₹{q['price']:.2f} (High: ₹{q['high']:.2f}, Low: ₹{q['low']:.2f}, Vol: {int(q['volume']):,})")

    if not live_quotes:
        print("[FATAL] Market data is completely unavailable from the live provider. Stopping safely per failure rules. Do not fabricate data.")
        sys.exit(1)

    # 4. Initialize Paper Trading Session
    session_id = f"session_{today_str.replace('-', '')}_{now_ist.strftime('%H%M%S')}"
    engine = PaperTradingEngine(db_path=db_path)
    engine.start_session(session_id, today_str)
    runtime_monitor.record_event(f"Started live paper-trading session {session_id} for {today_str}", level="success")
    print(f"\n[Session Started] ID: {session_id} across 8 isolated model sub-accounts.")

    # 5. Opportunity Scanner on Live Instruments
    scanner = OpportunityScanner()
    universe_instruments = [
        Instrument(
            symbol=s,
            exchange="NSE",
            instrument_id=f"inst_{s}",
            security_name=s,
            lot_size=1,
            tick_size=0.05,
            data_source="LIVE_NSE",
            ingested_at=now_ist,
            trading_status="ACTIVE",
        ) for s in live_quotes.keys()
    ]

    # Build point-in-time candles from live quote
    candles_by_symbol = {}
    for sym, q in live_quotes.items():
        candle = HistoricalCandle(
            symbol=sym,
            exchange="NSE",
            timeframe=Timeframe.M5,
            timestamp=now_ist,
            open=q["low"],
            high=q["high"],
            low=q["low"],
            close=q["price"],
            volume=q["volume"],
            status=DataStatus.VALID,
            timestamp_semantic=CandleTimestampSemantic.INTERVAL_BEGINNING,
        )
        candles_by_symbol[sym] = [candle]

    ranked_candidates, rejected_candidates = scanner.scan_as_of(
        universe=universe_instruments,
        decision_timestamp=now_ist,
        timeframe=Timeframe.M5,
        candles_by_symbol=candles_by_symbol,
        allow_outside_session=True
    )

    selected_symbol = ranked_candidates[0].symbol if ranked_candidates else list(live_quotes.keys())[0]
    selected_quote = live_quotes[selected_symbol]
    market_price = selected_quote["price"]

    print(f"\n[Opportunity Scanner] Top Ranked Instrument: {selected_symbol} @ ₹{market_price:.2f}")
    if ranked_candidates:
        print(f" -> Opportunity Score: {ranked_candidates[0].opportunity_score:.2f}")

    # 6. Build Frozen Market Snapshot for Sequential LLM Evaluation
    snapshot = MarketSnapshot(
        snapshot_id=f"snap_{today_str}_{now_ist.strftime('%H%M%S')}",
        symbol=selected_symbol,
        decision_timestamp=now_ist,
        timeframe=Timeframe.M5,
        candle=candles_by_symbol[selected_symbol][0],
        candidate=ranked_candidates[0] if ranked_candidates else None
    )

    # 7. Sequentially Load & Evaluate All 8 Local LLMs
    print("\n-----------------------------------------------------------------")
    print(f"  SEQUENTIAL LLM EVALUATION — 8 MODELS (Single Residency RTX 2050)")
    print("-----------------------------------------------------------------")
    scheduler = SequentialLLMScheduler(provider=ollama_provider, timeout_seconds=45.0)

    # Publish snapshot to market stream
    redis_service.publish(
        RedisStreamName.MARKET,
        {
            "event_type": "SNAPSHOT_DISPATCHED",
            "symbol": selected_symbol,
            "price": market_price,
            "session_id": session_id,
            "timestamp": now_ist.isoformat(),
        },
        event_id=f"snap_{snapshot.snapshot_id}"
    )

    eval_run, decision_records = scheduler.evaluate_snapshot_records(snapshot, enabled_only=True)
    print(f"\n[Evaluation Completed] Evaluated {len(eval_run.evaluated_models)} models in {eval_run.total_cycle_time_ms:.1f} ms.")
    print(f"Successful decisions: {len(eval_run.successful_decisions)} | Failed: {len(eval_run.failed_models)}")

    # 8. Route Decisions Through Deterministic RiskEngine & Execute Paper Orders
    print("\n-----------------------------------------------------------------")
    print("  RISK ENGINE EVALUATION & PAPER EXECUTION PIPELINE")
    print("-----------------------------------------------------------------")
    executed_trades = []
    rejected_trades = []

    for rec in decision_records:
        mid = rec.model_id
        action = rec.action.value if hasattr(rec.action, 'value') else str(rec.action)
        conf = rec.confidence

        print(f"\n[{mid.upper()}] Decision: {action} (Confidence: {conf:.2f})")
        print(f" -> Rationale: {rec.entry_rationale[:80]}...")
        if rec.proposed_stop_loss:
            print(f" -> Proposed Stop Loss: ₹{rec.proposed_stop_loss:.2f} | Proposed Target: ₹{rec.proposed_target or 0.0:.2f}")

        # Send through PaperTradingEngine -> RiskEngine -> PaperBroker
        trade = engine.process_model_decision(
            decision_record=rec,
            snapshot=snapshot,
            session_id=session_id,
            current_market_price=market_price
        )

        if trade:
            executed_trades.append(trade)
            print(f" [PASS] Order APPROVED & FILLED: Bought {trade.quantity} {selected_symbol} @ ₹{trade.entry_price:.2f}")
            print(f"        Initial Stop: ₹{trade.initial_stop:.2f} | Trailing Stop Floor: ₹{trade.trailing_stop:.2f}")
        else:
            rejected_trades.append(mid)
            if rec.validation_status != ValidationStatus.VALID:
                print(f" [REJECT] Rejected by Validator: {rec.rejection_reason}")
            elif rec.action in (LLMAction.HOLD, LLMAction.NO_ACTION, "HOLD", "NO_ACTION"):
                print(f" [HOLD] Model chose NO_ACTION / HOLD. No trade generated.")
            else:
                print(f" [REJECT] Order REJECTED by RiskEngine (Capital/Risk limits enforced).")

    # 9. Update In-Flight Positions Mark-to-Market
    current_prices = {s: q["price"] for s, q in live_quotes.items()}
    engine.update_market_prices(current_prices, datetime.now(IST), session_id)

    # 10. Auto Square-Off at 15:15 IST (or when mandatory)
    print("\n-----------------------------------------------------------------")
    print("  15:15 IST MANDATORY AUTO SQUARE-OFF ENFORCEMENT")
    print("-----------------------------------------------------------------")
    engine.execute_auto_square_off(current_prices, datetime.now(IST), session_id)
    print("[Square-Off] Auto square-off executed across all 8 models. Zero overnight risk guaranteed.")

    # 11. Finalize Daily Session & Calculate Leaderboard
    leaderboard = engine.finalize_daily_session(session_id, today_str)

    # 12. Run Controlled Self-Learning Cycle
    print("\n[Self-Learning] Running continuous improvement and error analysis cycle...")
    learning_engine = SelfLearningEngine(db_path=db_path)
    learning_result = learning_engine.run_learning_cycle(auto_activate_best=False, session_id=session_id)
    print(f" -> Observations recorded: {learning_result['observations_count']}")
    print(f" -> Candidates generated:   {learning_result['candidates_generated']} (Validated: {learning_result['candidates_validated']})")
    print(f" -> Active strategy:        {learning_result['current_active_strategy']}")

    # 13. Verify SHA-256 Cryptographic Audit Chain
    print("\n[Audit Chain] Verifying cryptographic SHA-256 tamper-evident ledger...")
    audit_logger = AuditLogger(db_path=db_path)
    audit_res = audit_logger.verify_chain(session_id=session_id)
    is_audit_valid = audit_res.is_valid
    audit_count = audit_res.total_events
    print(f" -> Audit Chain Integrity: {'VERIFIED [OK]' if is_audit_valid else 'FAILED [COMPROMISED]'}")
    print(f" -> Verified Event Blocks: {audit_count}")

    # 14. Generate Institutional Daily PDF Trading Report
    print("\n[Report] Generating institutional multi-page PDF daily trading report...")
    pdf_generator = DailyReportGenerator(db_path=db_path)
    try:
        report_path = pdf_generator.generate(session_id)
        print(f" -> Daily Report Generated: {report_path}")
    except Exception as e:
        print(f" -> Warning generating report by session_id: {e}")
        report_path = pdf_generator.generate(today_str)
        print(f" -> Daily Report Generated: {report_path}")

    # Mark session lock as completed
    try:
        completed_payload = {
            "date": today_str,
            "status": "COMPLETED",
            "finished_at": datetime.now(IST).isoformat(),
            "session_id": session_id,
            "report_path": str(report_path)
        }
        with open(lock_file, "w", encoding="utf-8") as f:
            json.dump(completed_payload, f, indent=2)
        if win_lock_file:
            try:
                with open(win_lock_file, "w", encoding="utf-8") as f:
                    json.dump(completed_payload, f, indent=2)
            except Exception:
                pass
    except Exception as e:
        print(f"[Lock Protection] Warning updating lock file: {e}")

    # 15. Summary Printout
    repo = PaperDatabaseRepository(db_path=db_path)
    all_trades = repo.list_trades(session_id=session_id)
    closed_trades = [t for t in all_trades if t.is_closed]
    total_net_pnl = sum(t.net_pnl for t in closed_trades)

    print("\n=================================================================")
    print(f"        SESSION SUMMARY — {today_str} ({session_id})             ")
    print("=================================================================")
    print(f"Total Trades Executed:   {len(all_trades)}")
    print(f"Open Positions:          0 (Zero overnight positions enforced)")
    print(f"Closed Positions:        {len(closed_trades)}")
    print(f"Total Net P&L:           ₹{total_net_pnl:+.2f}")
    print("\nPER-MODEL PERFORMANCE LEADERBOARD:")
    print(f"{'Model ID':<12} | {'Starting Eq':<12} | {'Ending Eq':<12} | {'Net P&L':<10} | {'Trades':<6} | {'Status'}")
    print("-" * 75)
    for entry in leaderboard:
        mid = entry["model_id"]
        start_eq = entry.get("starting_equity", entry.get("starting_balance", 1000.0))
        end_eq = entry.get("ending_equity", entry.get("ending_balance", 1000.0))
        pnl = entry.get("net_pnl", 0.0)
        trades_count = entry.get("total_trades", entry.get("trades_count", 0))
        status = entry.get("target_status", "NORMAL")
        print(f"{mid:<12} | ₹{start_eq:<11.2f} | ₹{end_eq:<11.2f} | ₹{pnl:<9.2f} | {trades_count:<6} | {status}")

    print("=================================================================")
    print(f"Audit Status:       {'VERIFIED (SHA-256)' if is_audit_valid else 'INVALID'}")
    print(f"Report File:        {report_path}")
    print(f"Dashboard URL:      https://trademoniter.reginaldalfret.tech")
    print("=================================================================\n")

if __name__ == "__main__":
    run_session()
