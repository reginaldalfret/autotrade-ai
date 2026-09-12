import math
from typing import Dict, Any, Optional
from mobitrade.domain.feature_models import TechnicalFeatures, TrendClassification
from mobitrade.domain.scanner_models import OpportunityScore, ScannerConfig

class OpportunityScorer:
    """
    Deterministic scoring engine that evaluates technical features and produces
    a fully explainable OpportunityScore (0.0 to 100.0).
    Every component and raw input is preserved for auditing and LLM inspection.
    """
    def compute_score(
        self,
        features: TechnicalFeatures,
        config: ScannerConfig
    ) -> OpportunityScore:
        weights = config.weights

        # 1. Momentum Score (0-100)
        momentum_score = self._score_momentum(features)

        # 2. Relative Volume Score (0-100)
        rel_vol_score = self._score_relative_volume(features)

        # 3. Trend Alignment Score (0-100)
        trend_score = self._score_trend(features)

        # 4. Breakout & Structure Score (0-100)
        breakout_score = self._score_breakout(features)

        # 5. Volatility Score (0-100)
        volatility_score = self._score_volatility(features)

        # 6. Liquidity Quality Score (0-100)
        liquidity_score = self._score_liquidity(features)

        price_structure_score = breakout_score
        data_quality_score = 100.0 if features.data_status.value == "VALID" else 50.0

        # Weighted aggregate
        total_weight = sum(weights.values())
        if total_weight <= 0:
            total_weight = 100.0

        weighted_sum = (
            momentum_score * weights.get("momentum", 20.0)
            + rel_vol_score * weights.get("relative_volume", 20.0)
            + trend_score * weights.get("trend", 20.0)
            + breakout_score * weights.get("breakout", 15.0)
            + volatility_score * weights.get("volatility", 15.0)
            + liquidity_score * weights.get("liquidity", 10.0)
        )
        total_score = round(min(100.0, max(0.0, weighted_sum / total_weight)), 2)

        return OpportunityScore(
            total_score=total_score,
            momentum=round(momentum_score, 2),
            relative_volume=round(rel_vol_score, 2),
            trend=round(trend_score, 2),
            breakout=round(breakout_score, 2),
            volatility=round(volatility_score, 2),
            liquidity=round(liquidity_score, 2),
            price_structure=round(price_structure_score, 2),
            data_quality=round(data_quality_score, 2),
            weights=weights
        )

    def _score_momentum(self, f: TechnicalFeatures) -> float:
        score = 50.0
        # Positive short-term momentum
        if f.momentum_3 is not None and f.momentum_3 > 0:
            score += 15.0
        if f.momentum_5 is not None and f.momentum_5 > 0:
            score += 15.0

        # Moving average alignment
        if f.sma_20 is not None and f.price > f.sma_20:
            score += 10.0
        if f.sma_50 is not None and f.price > f.sma_50:
            score += 10.0

        return min(100.0, max(0.0, score))

    def _score_relative_volume(self, f: TechnicalFeatures) -> float:
        rv = f.relative_volume_20
        if rv is None:
            return 50.0
        if rv >= 3.0:
            return 100.0
        elif rv >= 2.0:
            return 85.0
        elif rv >= 1.0:
            return 50.0 + (rv - 1.0) * 35.0
        else:
            return max(10.0, rv * 50.0)

    def _score_trend(self, f: TechnicalFeatures) -> float:
        if f.trend == TrendClassification.BULLISH:
            return 100.0
        elif f.trend == TrendClassification.NEUTRAL:
            return 50.0
        elif f.trend == TrendClassification.BEARISH:
            return 20.0
        return 50.0

    def _score_breakout(self, f: TechnicalFeatures) -> float:
        score = 50.0
        # Proximity to session high
        if f.distance_from_session_high is not None:
            pct_dist = (f.distance_from_session_high / f.price) * 100.0 if f.price > 0 else 10.0
            if pct_dist <= 0.2:
                score += 30.0
            elif pct_dist <= 1.0:
                score += 15.0

        # Close position near high of candle
        if f.close_position_in_range >= 0.8:
            score += 15.0
        elif f.close_position_in_range <= 0.2:
            score -= 15.0

        # Above VWAP
        if f.vwap is not None and f.price > f.vwap:
            score += 10.0

        return min(100.0, max(0.0, score))

    def _score_volatility(self, f: TechnicalFeatures) -> float:
        vol = f.volatility_20
        if vol is None:
            return 50.0
        # Optimal intraday annualized volatility between 15% and 50%
        if 0.15 <= vol <= 0.60:
            return 85.0
        elif vol > 0.60:
            # High volatility: penalize slightly for risk
            return max(30.0, 85.0 - (vol - 0.60) * 50.0)
        else:
            # Low volatility / flat: less opportunity
            return max(20.0, vol * 400.0)

    def _score_liquidity(self, f: TechnicalFeatures) -> float:
        vol = f.volume
        if vol >= 50000:
            return 100.0
        elif vol >= 10000:
            return 80.0
        elif vol >= 2000:
            return 60.0
        return 40.0
