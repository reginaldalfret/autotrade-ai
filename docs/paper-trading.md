# AutoTrade AI — Phase 7: Paper Trading, Portfolio Manager & Compounding Engine

## Overview

Phase 7 implements the deterministic simulated execution, multi-account portfolio management, and daily compounding engine for AutoTrade AI.

In accordance with core architectural principles:
- **Subordination Principle**: LLMs propose decisions; they **never** place broker orders directly. All orders must pass through the deterministic \RiskEngine\, be tracked by \PortfolioManager\, and be simulated via \PaperBroker\.
- **Market Scope**: Strictly NSE Indian Equity Cash Market (Intraday only, 09:15–15:30 IST).
- **Auto Square-Off**: Mandated 15:15 IST auto square-off for all open positions. Zero overnight positions permitted.
- **Account Isolation**: 8 independent sub-accounts (₹1,000 starting balance each) corresponding to the 8 local LLMs.
- **Realistic Statutory Costs**: Real-world Indian equity cash charges (Brokerage, STT, Exchange transaction charges, GST, SEBI turnover fees, Stamp duty) plus 0.05% slippage model.
- **Capital Compounding**: At 15:30 IST, each model's final realized equity compounds to become the next trading day's starting balance. Daily target (+10%) and stop loss (-5%) thresholds dynamically recalculate from the new starting balance.

---

## 8 Model Isolated Accounts

| Model ID | Base LLM | Initial Capital | Daily Target (+10%) | Daily Stop (-5%) | Isolation Policy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `nemotron` | Nemotron-Mini-4B | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `qwen` | Qwen2.5-Coder-7B | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `gemma` | Gemma-2-9B | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `llama` | Llama-3.2-3B | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `granite` | Granite-3.0-8B | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `phi` | Phi-3.5-mini | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `smollm` | SmolLM2-1.7B | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |
| `falcon` | Falcon3-7B | ₹1,000.00 | ₹1,100.00 | ₹950.00 | Strict per-model ledger |

Each model account possesses its own:
1. `Account` domain object with independent `cash`, `starting_balance`, `state`, and thresholds.
2. `PortfolioManager` with independent position tracking and P&L ledger.
3. Open trade slots keyed by `(model_id, symbol)` in the `PaperBroker`.

---

## Indian Equity Statutory Cost Structure

All simulated executions incorporate authentic statutory charges defined in `configs/costs.yaml`:

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
