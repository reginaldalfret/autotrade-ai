# Performance Analytics Engine & Tournament Leaderboard

## Overview
The Performance Analytics Engine is a pure, read-only analytical module designed to compute financial returns, trade distributions, peak-to-trough drawdowns, and risk-adjusted ratios without state mutation. It serves as the single source of truth for model performance evaluation, 8-model tournament rankings, and mathematical ledger reconciliation.

---

## Core Mathematical Formulations

### 1. Profit and Loss
$$\text{Gross P\&L} = (\text{Exit Price} - \text{Entry Price}) \times \text{Quantity}$$
$$\text{Net P\&L} = \text{Gross P\&L} - \text{Total Statutory Fees} - \text{Total Slippage}$$
$$\text{Return \%} = \left(\frac{\text{Net P\&L}}{\text{Starting Balance}}\right) \times 100$$

### 2. Trade Distribution Metrics
- **Win Rate \%**: $\left(\frac{\text{Winning Trades}}{\text{Total Trades}}\right) \times 100$
- **Loss Rate \%**: $\left(\frac{\text{Losing Trades}}{\text{Total Trades}}\right) \times 100$
- **Win / Loss Ratio**: $\frac{\text{Average Winning Trade}}{\lvert \text{Average Losing Trade} \rvert}$ (returns `"N/A"` if zero losses)
- **Profit Factor**: $\frac{\sum \text{Gross Profits}}{\sum \lvert \text{Gross Losses} \rvert}$
  - When Gross Losses $= 0$: displays as `"N/A"` for reporting and $999.0$ for numerical tie-breaking.

### 3. Maximum Drawdown (Equity Curve)
From a discrete equity time-series $E_t$:
$$\text{Peak}_t = \max_{0 \le \tau \le t} E_\tau$$
$$\text{Drawdown Amount}_t = \text{Peak}_t - E_t$$
$$\text{Drawdown \%}_t = \left(\frac{\text{Peak}_t - E_t}{\text{Peak}_t}\right) \times 100$$
$$\text{Max Drawdown} = \max_t (\text{Drawdown \%}_t)$$
- Tracks exact timestamps for **Peak Equity**, **Trough Equity**, and **Full Equity Recovery**.

### 4. Risk-Adjusted Return Ratios
- **Statistical Safety Constraints**:
  - Sample size $N < 3 \longrightarrow$ returns `"N/A"`.
  - Sample variance $\sigma^2 = 0 \longrightarrow$ returns `"N/A"`.
  - Drawdown $= 0 \longrightarrow$ Calmar returns `"N/A"`.
- **Sharpe Ratio**:
  $$\text{Sharpe} = \frac{\bar{R} - R_f}{\sigma_R} \times \sqrt{252}$$
  Where $R_f = \frac{0.06}{252}$ (annual risk-free benchmark 6%).
- **Sortino Ratio**:
  $$\text{Sortino} = \frac{\bar{R} - R_f}{\sigma_{\text{down}}} \times \sqrt{252}$$
  Where $\sigma_{\text{down}}$ is computed exclusively over negative excess returns.
- **Calmar Ratio**:
  $$\text{Calmar} = \frac{\text{Annualized Return \%}}{\text{Max Drawdown \%}}$$

---

## Deterministic Tournament Leaderboard Hierarchy

Models are ranked strictly and deterministically using a 5-tier tie-breaking hierarchy:
1. **Net P&L** (Descending)
2. **Return %** (Descending)
3. **Maximum Drawdown %** (Ascending / Smallest Loss)
4. **Profit Factor** (Descending)
5. **Total Trade Count** (Descending)

---

## Strict Mathematical Data Reconciliation

To prevent data desynchronization or fabricated analytics, the engine provides `reconcile_trading_data(session_id)`:
1. **Fills vs Orders**: Every fill execution maps to a validated order ID in `paper_orders`.
2. **Trades vs Fills**: Every closed trade references valid entry and exit execution IDs in `paper_fills`.
3. **Ledger Equation**:
   $$\text{Starting Equity} + \sum \text{Net P\&L} + \sum \text{Slippage} = \text{Ending Equity}$$
   *(Note: slippage is embedded in fill prices, ensuring mathematical equality down to the paisa).*

---

## CLI Usage

```bash
# View 8-model leaderboard for today or specific session
mobitrade analytics leaderboard
mobitrade analytics leaderboard --date 2026-09-11

# Executive summary of day's session
mobitrade analytics daily

# In-depth profile and metrics for single model
mobitrade analytics model nemotron

# Breakdown by equity symbol
mobitrade analytics symbol

# Run mathematical data reconciliation
mobitrade analytics reconcile sim_20260911
```
