# AGENTS.md

## Agent Architecture & Guidelines

### The Layered Pipeline
1. **Market Data & Adapters**: Ingests ticks and OHLCV bars (Indian Equities, Bitcoin Spot).
2. **Feature Engine**: Computes deterministic technical indicators.
3. **Opportunity Scanner**: Filters universe down to high-conviction candidate setups.
4. **Source Manager**: Supplies external news and filings timestamped at or before decision time $T$.
5. **LLM Reasoning Layer**: Evaluates market snapshot and proposes structured BUY/SELL/HOLD decision.
6. **Risk Engine**: Deterministically validates target, loss limits, trade frequency, exposure, and sizing.
7. **Paper Broker**: Simulates executions incorporating realistic slippage, spreads, and taxes/fees.
8. **Portfolio & Accounting**: Manages daily balance compounding and isolated model ledgers.
9. **Auditing & Reporting**: Generates EOD audit logs and tamper-proof PDF performance reports.
