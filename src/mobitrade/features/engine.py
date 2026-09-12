import math
from datetime import datetime, date
from typing import List, Optional
import zoneinfo
from mobitrade.domain.data_models import HistoricalCandle, Timeframe, DataStatus
from mobitrade.domain.feature_models import TechnicalFeatures, TrendClassification

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

class QuantitativeFeatureEngine:
    """
    Deterministic Quantitative Feature Calculator with Strict Temporal Integrity.
    - Explicitly computes feature_available_at = candle_timestamp + timeframe_duration.
    - Zero look-ahead: calculate_features_as_of() filters out any candle where available_at > decision_timestamp.
    - Timeframe-aware realized volatility annualization:
        Annual factor = sqrt(252 * bars_per_session)
        1m  = 375 bars/session
        5m  = 75 bars/session
        15m = 25 bars/session
    """
    def __init__(self, version: str = "1.1.0"):
        self.version = version

    def calculate_features_as_of(
        self,
        candles: List[HistoricalCandle],
        decision_timestamp: datetime,
        source_dataset_id: Optional[str] = None
    ) -> Optional[TechnicalFeatures]:
        """
        TEMPORAL-SAFE DECISION API (Opportunity Scanner / Decision Gate):
        Calculates the feature snapshot available strictly as of decision_timestamp.
        Excludes any forming/incomplete candle where candle.available_at > decision_timestamp.
        Returns the latest completed feature set up to decision_timestamp, or None if no completed candle exists.
        """
        dec_ts = decision_timestamp.astimezone(IST) if decision_timestamp.tzinfo else decision_timestamp.replace(tzinfo=IST)
        # Filter candles completed at or before decision_timestamp
        eligible_candles = [
            c for c in candles
            if (c.available_at.astimezone(IST) if c.available_at.tzinfo else c.available_at.replace(tzinfo=IST)) <= dec_ts
        ]
        if not eligible_candles:
            return None

        # Compute full sequence over eligible candles and return the latest available
        features = self.calculate_features(eligible_candles, source_dataset_id=source_dataset_id)
        return features[-1] if features else None

    def calculate_features(
        self,
        candles: List[HistoricalCandle],
        source_dataset_id: Optional[str] = None
    ) -> List[TechnicalFeatures]:
        """
        OFFLINE / BATCH CALCULATION PRIMITIVE:
        Calculates a sequential time-series of features across the provided candles.

        WARNING:
        This is a batch/offline calculation primitive. Do NOT use this method directly
        at decision time in the Opportunity Scanner or live execution loop without
        pre-filtering completed candles (candle.available_at <= decision_time), as
        including forming or future candles will introduce lookahead bias.
        For simulated real-time decision making or scanning, ALWAYS call:
            `calculate_features_as_of(candles, decision_timestamp)`
        """
        if not candles:
            return []

        sorted_candles = sorted(candles, key=lambda c: c.timestamp)
        features_list: List[TechnicalFeatures] = []

        current_session_date: Optional[date] = None
        cum_pv = 0.0
        cum_volume = 0.0
        session_high = -math.inf
        session_low = math.inf

        for i, candle in enumerate(sorted_candles):
            ts = candle.timestamp.astimezone(IST) if candle.timestamp.tzinfo else candle.timestamp.replace(tzinfo=IST)
            avail_at = candle.available_at.astimezone(IST) if candle.available_at.tzinfo else candle.available_at.replace(tzinfo=IST)
            bar_date = ts.date()

            # Session Reset for VWAP and Session High/Low at day boundary
            if current_session_date != bar_date:
                current_session_date = bar_date
                cum_pv = 0.0
                cum_volume = 0.0
                session_high = -math.inf
                session_low = math.inf

            typical_price = (candle.high + candle.low + candle.close) / 3.0
            cum_pv += typical_price * candle.volume
            cum_volume += candle.volume

            vwap = (cum_pv / cum_volume) if cum_volume > 0 else candle.close
            session_high = max(session_high, candle.high)
            session_low = min(session_low, candle.low)

            # Historical slice up to and including completed candle i (strictly point-in-time)
            history_slice = sorted_candles[:i + 1]
            closes = [c.close for c in history_slice]
            volumes = [c.volume for c in history_slice]

            # 1. Moving Averages
            sma_5 = self._calculate_sma(closes, 5)
            sma_9 = self._calculate_sma(closes, 9)
            sma_20 = self._calculate_sma(closes, 20)
            sma_50 = self._calculate_sma(closes, 50)

            ema_5 = self._calculate_ema(closes, 5)
            ema_9 = self._calculate_ema(closes, 9)
            ema_20 = self._calculate_ema(closes, 20)
            ema_50 = self._calculate_ema(closes, 50)

            # 2. Oscillators & Volatility
            rsi_14 = self._calculate_rsi(closes, 14)
            macd_line, macd_signal, macd_hist = self._calculate_macd(closes, 12, 26, 9)
            atr_14 = self._calculate_atr(history_slice, 14)
            vol_20 = self._calculate_volatility(closes, candle.timeframe, 20)

            # 3. Relative Volume
            rel_vol_20 = self._calculate_relative_volume(volumes, 20)

            # 4. Momentum
            mom_1 = (candle.close - closes[-2]) if len(closes) >= 2 else None
            mom_3 = (candle.close - closes[-4]) if len(closes) >= 4 else None
            mom_5 = (candle.close - closes[-6]) if len(closes) >= 6 else None
            mom_10 = (candle.close - closes[-11]) if len(closes) >= 11 else None
            mom_20 = (candle.close - closes[-21]) if len(closes) >= 21 else None

            # 5. Price Structure
            dist_high = session_high - candle.close
            dist_low = candle.close - session_low
            dist_vwap = candle.close - vwap
            roll_high_20 = max(c.high for c in history_slice[-20:]) if len(history_slice) >= 20 else None
            roll_low_20 = min(c.low for c in history_slice[-20:]) if len(history_slice) >= 20 else None

            candle_body = abs(candle.close - candle.open)
            candle_range = candle.high - candle.low
            upper_wick = candle.high - max(candle.open, candle.close)
            lower_wick = min(candle.open, candle.close) - candle.low
            close_pos = ((candle.close - candle.low) / candle_range) if candle_range > 0 else 0.5

            # 6. Trend Classification
            trend = TrendClassification.NEUTRAL
            if ema_20 is not None and candle.close > ema_20:
                if sma_50 is not None and candle.close > sma_50:
                    trend = TrendClassification.BULLISH
                elif sma_50 is None:
                    trend = TrendClassification.BULLISH
            elif ema_20 is not None and candle.close < ema_20:
                if sma_50 is not None and candle.close < sma_50:
                    trend = TrendClassification.BEARISH
                elif sma_50 is None:
                    trend = TrendClassification.BEARISH

            feature = TechnicalFeatures(
                symbol=candle.symbol,
                exchange=candle.exchange,
                candle_timestamp=ts,
                feature_available_at=avail_at,
                timeframe=candle.timeframe,
                data_status=candle.status,
                feature_version=self.version,
                source_dataset_id=source_dataset_id,
                price=candle.close,
                volume=candle.volume,
                sma_5=sma_5,
                sma_9=sma_9,
                sma_20=sma_20,
                sma_50=sma_50,
                ema_5=ema_5,
                ema_9=ema_9,
                ema_20=ema_20,
                ema_50=ema_50,
                rsi_14=rsi_14,
                macd_line=macd_line,
                macd_signal=macd_signal,
                macd_histogram=macd_hist,
                atr_14=atr_14,
                volatility_20=vol_20,
                vwap=vwap,
                relative_volume_20=rel_vol_20,
                momentum_1=mom_1,
                momentum_3=mom_3,
                momentum_5=mom_5,
                momentum_10=mom_10,
                momentum_20=mom_20,
                distance_from_session_high=dist_high,
                distance_from_session_low=dist_low,
                distance_from_vwap=dist_vwap,
                rolling_high_20=roll_high_20,
                rolling_low_20=roll_low_20,
                candle_body=candle_body,
                candle_range=candle_range,
                upper_wick=upper_wick,
                lower_wick=lower_wick,
                close_position_in_range=close_pos,
                trend=trend
            )
            features_list.append(feature)

        return features_list

    def _calculate_sma(self, data: List[float], period: int) -> Optional[float]:
        if len(data) < period:
            return None
        return sum(data[-period:]) / float(period)

    def _calculate_ema(self, data: List[float], period: int) -> Optional[float]:
        if len(data) < period:
            return None
        multiplier = 2.0 / (period + 1.0)
        ema = sum(data[:period]) / float(period)
        for val in data[period:]:
            ema = (val - ema) * multiplier + ema
        return ema

    def _calculate_rsi(self, data: List[float], period: int = 14) -> Optional[float]:
        if len(data) <= period:
            return None
        changes = [data[i] - data[i - 1] for i in range(1, len(data))]
        if len(changes) < period:
            return None

        gains = [max(c, 0.0) for c in changes]
        losses = [max(-c, 0.0) for c in changes]

        avg_gain = sum(gains[:period]) / float(period)
        avg_loss = sum(losses[:period]) / float(period)

        for i in range(period, len(changes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / float(period)
            avg_loss = (avg_loss * (period - 1) + losses[i]) / float(period)

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _calculate_macd(
        self, data: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if len(data) < slow_period + signal_period:
            return None, None, None

        fast_mult = 2.0 / (fast_period + 1.0)
        slow_mult = 2.0 / (slow_period + 1.0)

        slow_ema = sum(data[:slow_period]) / float(slow_period)
        fast_ema = sum(data[:fast_period]) / float(fast_period)
        for val in data[fast_period:slow_period]:
            fast_ema = (val - fast_ema) * fast_mult + fast_ema

        macd_series = [fast_ema - slow_ema]
        for val in data[slow_period:]:
            fast_ema = (val - fast_ema) * fast_mult + fast_ema
            slow_ema = (val - slow_ema) * slow_mult + slow_ema
            macd_series.append(fast_ema - slow_ema)

        if len(macd_series) < signal_period:
            return None, None, None

        signal_mult = 2.0 / (signal_period + 1.0)
        signal_ema = sum(macd_series[:signal_period]) / float(signal_period)
        for m in macd_series[signal_period:]:
            signal_ema = (m - signal_ema) * signal_mult + signal_ema

        current_macd = macd_series[-1]
        histogram = current_macd - signal_ema
        return current_macd, signal_ema, histogram

    def _calculate_atr(self, candles: List[HistoricalCandle], period: int = 14) -> Optional[float]:
        if len(candles) <= period:
            return None

        tr_list = []
        for i in range(1, len(candles)):
            curr = candles[i]
            prev = candles[i - 1]
            tr = max(
                curr.high - curr.low,
                abs(curr.high - prev.close),
                abs(curr.low - prev.close)
            )
            tr_list.append(tr)

        if len(tr_list) < period:
            return None

        atr = sum(tr_list[:period]) / float(period)
        for tr in tr_list[period:]:
            atr = (atr * (period - 1) + tr) / float(period)
        return atr

    def _calculate_volatility(
        self, closes: List[float], timeframe: Timeframe, period: int = 20
    ) -> Optional[float]:
        """
        Timeframe-aware realized volatility:
        Annual factor = sqrt(252 trading days * bars_per_session)
        1m: 375 bars -> sqrt(252 * 375)
        5m: 75 bars  -> sqrt(252 * 75)
        15m: 25 bars -> sqrt(252 * 25)
        """
        if len(closes) < period + 1:
            return None

        returns = [
            math.log(closes[i] / closes[i - 1])
            for i in range(len(closes) - period, len(closes))
        ]
        mean = sum(returns) / float(period)
        variance = sum((r - mean) ** 2 for r in returns) / float(period - 1)
        daily_stdev = math.sqrt(variance)
        annualization_factor = math.sqrt(252.0 * timeframe.intraday_bars_per_session)
        return daily_stdev * annualization_factor

    def _calculate_relative_volume(self, volumes: List[float], period: int = 20) -> Optional[float]:
        if len(volumes) < period + 1:
            return None
        # Mean of previous 20 completed bars (excluding current bar)
        reference_mean = sum(volumes[-(period + 1):-1]) / float(period)
        if reference_mean <= 0:
            return 1.0
        return volumes[-1] / reference_mean