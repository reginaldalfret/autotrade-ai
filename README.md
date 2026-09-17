# AutoTrade AI

AutoTrade AI is a local-first AI trading research and paper trading platform for NSE Indian equities.

```
NSE Indian Equities
        ↓
Historical Market Data
        ↓
Technical Features
        ↓
Opportunity Scanner
        ↓
External Financial Information
        ↓
MarketSnapshot
        ↓
8 Local LLMs
        ↓
Deterministic RiskEngine
        ↓
Paper Trading
        ↓
Performance Analytics
```

## Overview & Architecture

AutoTrade AI evaluates 8 open-weights local small language models (SLMs) in a competitive, deterministic paper-trading tournament under strictly simulated Indian equity cash market conditions.

### Core Principles

- **8 Local LLMs**: Evaluates NVIDIA Nemotron 3 Nano, Qwen 2.5 Coder 1.5B, Google Gemma 3 1B, Meta Llama 3.2 1B, IBM Granite 4 1B-H, Microsoft Phi-4 Mini, SmolLM2 1.7B, and Falcon 3 1B via local Ollama inference.
- **Sequential Inference**: Only one model is loaded into VRAM at a time (`Load → Infer → Validate → Record → Unload`), enabling full execution on consumer hardware (8 GB system RAM, NVIDIA RTX 2050 4 GB VRAM).
- **Identical Frozen MarketSnapshot**: All 8 models receive the identical point-in-time snapshot with frozen simulation timestamp, technical indicators, and external news context.
- **Independent Model Accounts**: Each model begins with ₹1,000.00 initial capital in a completely isolated sub-account ledger.
- **Subordination Principle**: LLMs output structured trade proposals only (`BUY`, `SELL`, `HOLD`). They have **zero direct broker access**.
- **Deterministic RiskEngine**: Evaluates all proposals against cash limits, stop-loss feasibility, session limits, and cutoffs. LLMs cannot bypass or override risk parameters.
- **Market Scope**: Strictly NSE Indian Equity Cash Market (09:15 to 15:30 IST). Intraday only.
- **No Leverage / No Margin**: All trades are 100% cash covered. Zero futures, zero options, zero crypto.
- **No Overnight Positions**: Mandated 15:15 IST auto square-off closes all open positions before the 15:30 market close.
- **Realistic Cost Model**: Configured Indian equity cash cost schedule (brokerage, STT, exchange turnover fees, GST, SEBI turnover fees, stamp duty) plus 0.05% slippage.
- **Dynamic Trailing Stop**: High-water mark ratcheting floor protects accumulated intraday gains without LLM interference.
- **Daily Compounding**: At session close, realized Net P&L compounds into the next trading day's starting balance. Daily target (+10%) and stop loss (-5%) dynamically recalculate each morning.
- **Zero-Trade Days Allowed**: Models proposing `HOLD` or failing risk checks preserve capital without penalty. Maximum 20 completed trades per session.
- **Tamper-Evident Audit Trail**: Every event across session, model inference, risk checks, orders, fills, and compounding is cryptographically chained using SHA-256 to an immutable Genesis Block with zero-mutation guarantees.
- **Performance Analytics Engine**: Deterministic calculations of Net P&L, Drawdowns, Win Rate, and safe Sharpe/Sortino/Calmar ratios with multi-way data reconciliation.
- **Automated Daily PDF Reports**: Executive 8-page daily trading report with visual equity curves, leaderboard rankings, deep dives, complete trade ledgers, and SHA-256 validation badges.
- **Deterministic Reproducibility**: All market data, features, candidate rankings, and paper-trading execution cycles maintain strict temporal integrity and cryptographic SHA-256 provenance.

---

## Command Line Interface (CLI)

AutoTrade AI provides a unified CLI tool:

```bash
# Platform & Model Status
mobitrade status
mobitrade models

# Performance Analytics & Leaderboard
mobitrade analytics leaderboard
mobitrade analytics daily
mobitrade analytics model nemotron
mobitrade analytics symbol
mobitrade analytics reconcile <session_id>

# Cryptographic Audit Log & Verification
mobitrade audit status
mobitrade audit verify
mobitrade audit inspect <event_id>
mobitrade audit session <session_id>
mobitrade audit trade <trade_id>

# Daily PDF Trading Reports
mobitrade report generate --date 2026-09-11
mobitrade report validate 2026-09-11
```

---

## Local Operator API (Phase 9)

AutoTrade AI provides a local-first, deterministic FastAPI control layer bound strictly to `127.0.0.1`. It exposes the paper trading engine, portfolio, positions, risk boundaries, performance analytics, PDF reports, and cryptographic audit logs for local operator / agent integration.

### Startup Commands

```bash
# Via autotrade_ai wrapper:
python -m autotrade_ai.api

# Or via mobitrade module:
python -m mobitrade.api

# Or via CLI command:
mobitrade api --host 127.0.0.1 --port 8000
```

### Available Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Market session status (09:15–15:30 IST), Ollama LLM provider status, DB connectivity |
| `GET` | `/models` | List configured tournament models and runtime inference parameters |
| `GET` | `/portfolio` | Aggregated paper trading portfolio, balances, and isolated model accounts |
| `GET` | `/positions` | Active open paper positions across models |
| `GET` | `/trades` | Completed trade journal with gross/net P&L and statutory cost breakdowns |
| `GET` | `/risk` | Authoritative RiskEngine parameters (-5% hard loss, 20 max trades, 15:15 IST square-off) |
| `GET` | `/analytics` | Computed session analytics, win rates, drawdown, and model leaderboard |
| `GET` | `/reports` | Generated daily PDF trading reports with SHA-256 integrity fingerprints |
| `GET` | `/audit/verify` | Cryptographic SHA-256 hash chain verification of tamper-evident audit log |
| `POST` | `/session/run` | Execute deterministic intraday paper trading replay under strict RiskEngine enforcement |

### Example Queries

```bash
# Query health status
curl -s http://127.0.0.1:8000/health

# Query risk safety boundaries
curl -s http://127.0.0.1:8000/risk

# Execute safe paper session replay
curl -s -X POST http://127.0.0.1:8000/session/run \
  -H "Content-Type: application/json" \
  -d '{"session_date": "2026-09-17", "symbol": "TATAMOTORS", "mock_llm": true}'
```

---

## Hermes Operator Integration (Phase 10)

Hermes operates as an external supervisor/operator tool layer interacting with AutoTrade AI exclusively through the localhost API (`127.0.0.1:8000`). Hermes has no direct database access and cannot bypass RiskEngine safety boundaries.

### Operational Boundaries

- **Segment**: NSE Cash Intraday Only (09:15–15:30 IST)
- **Cutoff**: 15:15 IST mandatory auto square-off
- **Risk Hard Stop**: -5.0% daily maximum loss limit
- **Trade Cap**: Maximum 20 completed trades per model per session
- **Overnight**: Zero overnight positions allowed
- **Authority**: RiskEngine is deterministic and final; background loops prohibited

### Usage in Hermes

```python
from autotrade_ai.hermes import AutoTradeOperatorClient, get_hermes_tools, run_daily_session_workflow

# 1. Connect client to localhost API
client = AutoTradeOperatorClient(base_url="http://127.0.0.1:8000")
health = client.get_health()
risk = client.get_risk()

# 2. Register tools with Hermes agent
tools = get_hermes_tools(base_url="http://127.0.0.1:8000")
tool_definitions = tools.get_tool_definitions()

# 3. Standard operator workflow ("Run today's paper session for AutoTrade AI")
summary = run_daily_session_workflow(
    session_date="2026-09-17",
    symbol="TATAMOTORS",
    mock_llm=True,
    client=client
)
print(summary["operator_message"])
```

---

## Disclaimer

> [!NOTE]
> AutoTrade AI is an experimental research and paper-trading platform designed for quantitative analysis and comparative local LLM evaluation. It does not provide financial advice, make trade recommendations, or claim guaranteed profits. Live broker connectivity and real-money execution are strictly disabled.
