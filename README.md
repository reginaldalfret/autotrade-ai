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
- **Deterministic Reproducibility**: All market data, features, candidate rankings, and paper-trading execution cycles maintain strict temporal integrity and cryptographic SHA-256 provenance.

---

## Disclaimer

> [!NOTE]
> AutoTrade AI is an experimental research and paper-trading platform designed for quantitative analysis and comparative local LLM evaluation. It does not provide financial advice, make trade recommendations, or claim guaranteed profits. Live broker connectivity and real-money execution are strictly disabled.
