# NSE-First Market Data & Trading Architecture (Hardened)

## Current Scope: Indian Equities (NSE First)
- **Primary Exchange**: National Stock Exchange of India (NSE) - Equity / Capital Market (CM) segment.
- **Trading Session**: 09:15:00 IST to 15:30:00 IST.
- **Intraday Square-off**: 15:15:00 IST.
- **Strictly Excluded**: Bitcoin, cryptocurrency, futures, options, derivatives, leverage, margin borrowing.
- **BSE Position**: Decoupled via generic interfaces; zero BSE code active.

## Experimental Parameters
- **Initial Capital**: ₹1,000 per model (8 isolated LLM accounts, ₹8,000 total virtual capital).
- **Daily Target**: +10% of starting day balance (`starting_day_balance * 0.10`). Target reached $\rightarrow$ immediate position close & lock. Not forced.
- **Daily Stop**: -5% of starting day balance (`starting_day_balance * 0.05`). Stop hit $\rightarrow$ immediate position close & lock.
- **Max Trades**: Up to 20 completed trades per session (0 allowed, never forced).
- **Overnight Positions**: Strictly zero. EOD market close forces simulated fills and locks the session.
- **Compounding**: Gains and losses compound from previous session's final equity (`starting_day_balance = previous_session_final_equity`).