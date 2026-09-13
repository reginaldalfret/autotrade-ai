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

## 3. Mandatory 15:15 IST Auto Square-Off & Cutoffs
- **New Order Entry Cutoff**: At or after 15:15 IST, all new entry orders are strictly rejected (`AFTER_SQUARE_OFF_CUTOFF`).
- **Auto Square-Off Window**: At 15:15 IST, all open positions across all model accounts are liquidated at market price.
- **Overnight Prohibition**: Under no circumstances may any position be held overnight. All models must be flat by 15:30 IST.

## 4. Deterministic Position Sizing
- **Cash Reservation**: Quantity = `floor(available_cash / current_market_price)`.
- **Zero Leverage / Zero Margin**: Cash must fully cover the position value. LLM cannot dictate leverage, margin, or arbitrary quantities.
- **Minimum Allocation**: If available cash is less than the price of a single share, order is rejected for insufficient capital.

## 5. Daily Capital Compounding
- **Compounding Anchor**: `starting_balance(Day D+1) = final_realized_equity(Day D)`
- **Dynamic Recalculation**:
  - `Daily Target = starting_balance * 1.10`
  - `Daily Stop Loss = starting_balance * 0.95`
- **Symmetric Application**: Applied uniformly to winning days (+10%), losing days (-5%), and flat/zero-trade days.


