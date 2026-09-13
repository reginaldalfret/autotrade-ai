# AutoTrade AI — Phase 7: Paper Trading, Portfolio Manager & Compounding Engine

## Overview

Phase 7 implements the deterministic simulated execution, multi-account portfolio management, and daily compounding engine for AutoTrade AI.

In accordance with core architectural principles:
- **Subordination Principle**: LLMs propose decisions; they **never** place broker orders directly. All orders must pass through the deterministic `RiskEngine`, be tracked by `PortfolioManager`, and be simulated via `PaperBroker`.
- **Market Scope**: Strictly NSE Indian Equity Cash Market (Intraday only, 09:15–15:30 IST).
- **Auto Square-Off**: Mandated 15:15 IST auto square-off for all open positions. Zero overnight positions permitted.
- **Account Isolation**: 8 independent sub-accounts (₹1,000 starting balance each) corresponding to the 8 local LLMs.
- **Configured Cost Model**: Configured Indian equity cash-market cost model (Brokerage, STT, Exchange transaction charges, GST, SEBI turnover fees, Stamp duty) plus 0.05% slippage model.
- **Capital Compounding**: At 15:30 IST, each model's final realized equity compounds to become the next trading day's starting balance. Daily target (+10%) and stop loss (-5%) thresholds dynamically recalculate from the new starting balance.

---

## 8 Model Isolated Accounts

| Model ID | Display Name | Runtime Model Name | Initial Capital | Daily Target (+10%) | Daily Stop (-5%) | Isolation Policy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `nemotron` | NVIDIA Nemotron 3 Nano | `nemotron-3-nano:latest` | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `qwen` | Qwen 2.5 Coder 1.5B | `qwen2.5-coder:1.5b` | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `gemma` | Google Gemma 3 1B | `gemma3:1b` | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `llama` | Meta Llama 3.2 1B | `llama3.2:1b` | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `granite` | IBM Granite 4 1B-H | `granite4:1b-h` | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `phi` | Microsoft Phi-4 Mini | `phi4-mini:latest` | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `smollm` | SmolLM2 1.7B | `smollm2:1.7b` | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `falcon` | Falcon 3 1B | `falcon3:1b-instruct-q4_K_M` | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |

Each model account possesses its own:
1. `Account` domain object with independent `cash`, `starting_balance`, `state`, and thresholds.
2. `PortfolioManager` with independent position tracking and P&L ledger.
3. Open trade slots keyed by `(model_id, symbol)` in the `PaperBroker`.

---

## Indian Equity Cost Structure

All simulated executions incorporate the configured Indian equity cash-market cost model defined in `configs/costs.yaml`:

```yaml
brokerage:
  rate: 0.0003          # 0.03% or ₹20 per executed order, whichever is lower
  flat_cap: 20.0
stt_ctt:
  intraday_equity_sell: 0.00025  # 0.025% on sell turnover
exchange_turnover_fee:
  rate: 0.0000297       # NSE 0.00297%
gst:
  rate: 0.18            # 18% on (brokerage + exchange charges + SEBI charges)
sebi_turnover_fee:
  rate: 0.000001        # ₹10 per crore (0.0001%)
stamp_duty:
  intraday_equity_buy: 0.00003   # 0.003% on buy turnover
slippage:
  fixed_pct: 0.0005     # 0.05% slippage on executed price
```

### Gross P&L vs Net P&L
- Gross P&L = (Exit Price - Entry Price) * Quantity
- Net P&L = Gross P&L - (Total Statutory Fees + Total Slippage)

All rankings, compounding calculations, and leaderboards are strictly determined by **Net P&L**.

---

## Daily Compounding Engine

Compounding operates between daily session closes:
Starting Balance (Day D+1) = Final Realized Equity (Day D)

### Benchmark Recalculation
- Target Equity (Day D+1) = Starting Balance (Day D+1) * (1 + Target Pct)
- Stop Loss Equity (Day D+1) = Starting Balance (Day D+1) * (1 - Loss Limit Pct)

### Symmetric Behavior
- **Winning Day (+10%)**: Starting balance ₹1,000 -> ₹1,100. Next day target = ₹1,210 (+10%), stop = ₹1,045 (-5%).
- **Losing Day (-5%)**: Starting balance ₹1,000 -> ₹950. Next day target = ₹1,045 (+10%), stop = ₹902.50 (-5%).
- **Zero-Trade Day (Flat)**: Starting balance ₹1,000 -> ₹1,000. Preserves capital without forced trading.

---

## Order Shutdown Sequence & Safety

1. **Daily Target Reached (+10%)**:
   - `trigger_target_reached()` is invoked.
   - All open positions for the model are immediately closed.
   - Account state transitions to `LOCKED` with `DAILY_TARGET_REACHED`.
   - New orders are deterministically rejected by `RiskEngine`.
2. **Daily Stop Loss Triggered (-5%)**:
   - `trigger_daily_stop()` is invoked.
   - All open positions are immediately liquidated.
   - Account state transitions to `LOCKED` with `DAILY_STOP_TRIGGERED`.
   - No further orders permitted for the remainder of the session.
3. **15:15 IST Auto Square-Off**:
   - Mandatory risk window closing any in-flight intraday positions before market close (15:30 IST).
   - Zero overnight carryover.
4. **Trade Limit**:
   - Maximum 20 completed trades per model per session enforced.

---

## Dynamic Trailing Stop Engine

- Initial Stop Loss is set according to `RiskEngine` rules.
- As price moves favorably in trade direction, peak high-water price is updated.
- Trailing stop floor ratchets upward:
  Trailing Stop = Peak Price * (1 - Trailing Pct)
- Trailing stop strictly never ratchets downward.
- If current market price breaches the trailing stop floor, position is liquidated with `ExitReason.TRAILING_STOP`.

---

## SQLite Persistence Schema

All records reside in `/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db`:
- `accounts`: Model account states, starting balances, cash, target/stop levels.
- `daily_sessions`: Session metadata, date, status, opened/closed timestamps.
- `paper_orders`: Order requests, status, pricing, quantities, model IDs.
- `paper_fills`: Execution records with exact statutory fees and slippage breakdown.
- `paper_trades`: Complete trade journals with Gross P&L, fees, slippage, Net P&L, exit reason.
- `daily_performance`: EOD metrics per model (Win Rate, Profit Factor, Drawdown, Net Return).
- `portfolio_snapshots`: Time-series equity, cash, unrealized/realized P&L snapshots.
- `audit_events`: Tamper-evident ledger of lifecycle events (`ORDER_PLACED`, `AUTO_SQUARE_OFF`, `DAILY_TARGET_REACHED`).

---

## CLI Reference

```bash
# Display paper trading engine operational status
mobitrade paper status

# List 8 isolated model accounts and current equity
mobitrade paper accounts

# List current in-flight open positions
mobitrade paper positions

# View completed trade journal with statutory costs
mobitrade paper trades

# View daily performance leaderboard and compounding history
mobitrade paper performance

# Run deterministic end-to-end paper trading replay
mobitrade paper simulate --date 2026-09-11 --symbol TATAMOTORS
```

---

## Example / Demo Replay Walkthrough (2026-09-11)

Below is an illustrative walkthrough of the deterministic paper-trading replay execution and daily compounding for session date **2026-09-11**:

```text
==================================================
AutoTrade AI - Paper Trading Daily Replay: 2026-09-11
Session ID: sim_20260911 | Symbol: TATAMOTORS
==================================================

[10:15 IST] Frozen Snapshot Dispatched -> Sequential Evaluation of 8 Models...
 - nemotron  : BUY APPROVED -> Filled 2 shares @ ₹500.25
 - qwen      : BUY APPROVED -> Filled 2 shares @ ₹500.25
 - gemma     : HOLD -> No trade
 - llama     : BUY APPROVED -> Filled 2 shares @ ₹500.25
 - granite   : HOLD -> No trade
 - phi       : BUY APPROVED -> Filled 2 shares @ ₹500.25
 - smollm    : HOLD -> No trade
 - falcon    : HOLD -> No trade

[13:00 IST] Mid-Session Tick: TATAMOTORS at ₹510.0 (Mark-to-market & trailing stops updated)

[15:15 IST] Auto Square-Off Window Triggered -> Closing all in-flight positions...

[15:30 IST] Session Closed -> Finalizing performance & compounding to next day...

==================================================
AutoTrade AI - Daily Replay Summary (2026-09-11):
==================================================
|   Rank | Model ID   | Start Eq   | End Eq   | Gross P&L   | Costs   | Net P&L   | Return %   | New Day Balance   |
|--------|------------|------------|----------|-------------|---------|-----------|------------|-------------------|
|      1 | nemotron   | ₹1000.00   | ₹1037.88 | ₹38.98      | ₹2.12   | ₹36.86    | +3.79%     | ₹1037.88          |
|      2 | qwen       | ₹1000.00   | ₹1037.88 | ₹38.98      | ₹2.12   | ₹36.86    | +3.79%     | ₹1037.88          |
|      3 | llama      | ₹1000.00   | ₹1037.88 | ₹38.98      | ₹2.12   | ₹36.86    | +3.79%     | ₹1037.88          |
|      4 | phi        | ₹1000.00   | ₹1037.88 | ₹38.98      | ₹2.12   | ₹36.86    | +3.79%     | ₹1037.88          |
|      5 | gemma      | ₹1000.00   | ₹1000.00 | ₹0.00       | ₹0.00   | ₹0.00     | +0.00%     | ₹1000.00          |
|      6 | granite    | ₹1000.00   | ₹1000.00 | ₹0.00       | ₹0.00   | ₹0.00     | +0.00%     | ₹1000.00          |
|      7 | smollm     | ₹1000.00   | ₹1000.00 | ₹0.00       | ₹0.00   | ₹0.00     | +0.00%     | ₹1000.00          |
|      8 | falcon     | ₹1000.00   | ₹1000.00 | ₹0.00       | ₹0.00   | ₹0.00     | +0.00%     | ₹1000.00          |
```

### Daily Leaderboard Output (2026-09-11)

```text
==================================================
AutoTrade AI - Daily Model Leaderboard (2026-09-11)
==================================================
| Date       | Model ID   | Starting Eq   | Ending Eq   | Net P&L   | Return %   |   Trades | Win Rate   | Max DD   |
|------------|------------|---------------|-------------|-----------|------------|----------|------------|----------|
| 2026-09-11 | falcon     | ₹1000.00      | ₹1000.00    | ₹0.00     | +0.00%     |        0 | 0.0%       | 0.00%    |
| 2026-09-11 | smollm     | ₹1000.00      | ₹1000.00    | ₹0.00     | +0.00%     |        0 | 0.0%       | 0.00%    |
| 2026-09-11 | phi        | ₹1000.00      | ₹1037.88    | ₹36.86    | +3.79%     |        1 | 100.0%     | 0.00%    |
| 2026-09-11 | granite    | ₹1000.00      | ₹1000.00    | ₹0.00     | +0.00%     |        0 | 0.0%       | 0.00%    |
| 2026-09-11 | llama      | ₹1000.00      | ₹1037.88    | ₹36.86    | +3.79%     |        1 | 100.0%     | 0.00%    |
| 2026-09-11 | gemma      | ₹1000.00      | ₹1000.00    | ₹0.00     | +0.00%     |        0 | 0.0%       | 0.00%    |
| 2026-09-11 | qwen       | ₹1000.00      | ₹1037.88    | ₹36.86    | +3.79%     |        1 | 100.0%     | 0.00%    |
| 2026-09-11 | nemotron   | ₹1000.00      | ₹1037.88    | ₹36.86    | +3.79%     |        1 | 100.0%     | 0.00%    |
```
