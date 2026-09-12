# AutoTrade AI

AutoTrade AI is a local-first AI trading research and paper trading platform for NSE Indian equities.

Current experimental architecture:
- 8 local LLMs
- independent virtual accounts
- ₹1,000 starting capital per model
- identical market snapshots
- sequential inference
- deterministic risk engine
- paper trading
- transaction costs
- slippage
- daily compounding
- complete trade/audit records

## Core Directives
- **Storage**: All data, code, databases, environments, and reports strictly remain on drive `D:\Trading LLM\MobiTradeAI` (`/mnt/d/Trading LLM/MobiTradeAI`).
- **Safety First**: The LLM proposes; the deterministic Risk Engine decides; the Paper Broker executes. No direct broker access.
- **Fairness & Rigor**: Identical capital, identical feeds, strictly zero look-ahead bias, deterministic transaction costs, and complete model account isolation.
