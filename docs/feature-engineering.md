# Quantitative Feature Engineering

## Overview
The Quantitative Feature Engine deterministically generates technical indicators over validated historical candle data.
The LLM does NOT calculate numerical market indicators.

## Implemented Features
1. **Simple Moving Averages (SMA)**:
   - Periods: 5, 9, 20, 50.
   - Handled: Returns `None` for observations prior to period length (no fake values).
2. **Exponential Moving Averages (EMA)**:
   - Periods: 5, 9, 20, 50.
   - Formula: Multiplier $k = \frac{2}{N + 1}$. Initial seed: SMA of first $N$ values.
3. **Relative Strength Index (RSI)**:
   - Period: 14.
   - Wilder smoothing methodology over price deltas. Returns `None` during warm-up.
4. **Moving Average Convergence Divergence (MACD)**:
   - Parameters: Fast 12, Slow 26, Signal 9.
   - Outputs: MACD line, signal line, and histogram.
5. **Average True Range (ATR)**:
   - Period: 14.
   - True Range: $\max(\text{high} - \text{low}, |\text{high} - \text{prev\_close}|, |\text{low} - \text{prev\_close}|)$.
6. **Session-Aware VWAP**:
   - Resets strictly at `09:15:00 IST` for each new trading day. Zero carryover from previous sessions.
7. **Relative Volume**:
   - Compares current candle volume against the mean of the preceding 20 historical bars. Strictly zero future bars included.
8. **Momentum**:
   - Lookback bars: 1, 3, 5, 10, 20 ($P_t - P_{t - k}$).
9. **Realized Volatility**:
   - 20-period log-return standard deviation annualized across 252 trading days $\times$ 375 intraday minutes.
10. **Price Structure**:
    - Distances from session high, session low, and VWAP.
    - Rolling 20-period high/low.
    - Candle body, range, upper wick, lower wick, and close position within range.
11. **Trend Classification**:
    - Categorized into `BULLISH`, `BEARISH`, or `NEUTRAL` based on price relation to EMA(20) and SMA(50).

## Deterministic Trailing Stop Engine
- Position-level trailing stop with peak tracking.
- Formula: $\text{Trailing Stop} = \text{Peak Price} \times (1 - \text{trailing\_pct})$ (default 0.5%).
- Invariant: Trailing stop strictly NEVER decreases.
- Isolation: Independent per model and per position.
- Precedence: Account daily -5% stop overrides all trade-level trailing stops.