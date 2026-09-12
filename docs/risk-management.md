# Risk Management Rules

## 1. Capital Preservation & Shutdown Rules
- **Starting Virtual Balance**: ₹1,000 per model (sub-account isolation).
- **Daily Target**: +10% shutdown (session halted upon target hit).
- **Daily Stop Loss**: -5% hard stop (session halted immediately upon reaching loss limit).
- **Session Max Trades**: 20 completed trades maximum per model per day.
- **Holding Horizon**: Intraday only (09:15 to 15:30 IST); strictly NO overnight carryover.

## 2. LLM Authority Boundaries
- **No Direct Broker Access**: LLMs have zero direct broker or execution capabilities.
- **Subordinate Proposals**: LLMs output structured proposals (`BUY`, `SELL`, `HOLD`) only.
- **Non-Negotiable Risk Limits**: The deterministic `RiskEngine` evaluates every LLM proposal. If a proposal violates stop loss rules, max trade count, loss limits, or capital constraints, it is rejected regardless of model confidence.
- **Fail-Safe Fallback**: Any malformed, unparseable, or out-of-bounds LLM decision is immediately converted to `HOLD`.
- **Trailing Stop Enforcement**: The deterministic `TrailingStopEngine` manages in-flight risk and stops dynamically without LLM interference.

