import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import zoneinfo

from mobitrade.domain.data_models import Instrument, HistoricalCandle, Timeframe
from mobitrade.domain.scanner_models import (
    OpportunityCandidate,
    ScannerConfig,
    RejectionReason,
)
from mobitrade.data.calendar import IndianMarketCalendar, IST
from mobitrade.features.engine import QuantitativeFeatureEngine
from mobitrade.scanner.filters import (
    EligibilityFilter,
    PriceFilter,
    LiquidityFilter,
    DataQualityFilter,
)
from mobitrade.scanner.scoring import OpportunityScorer

class OpportunityScanner:
    """
    Deterministic Opportunity Scanner for the Indian Equity Cash Market (NSE First).
    Evaluates candidate instruments strictly as of decision_timestamp using point-in-time features.
    Does NOT place trades, generate final BUY/SELL orders, or invoke LLMs.
    Produces ranked, explainable OpportunityCandidate[] for future LLM consumption.
    """
    def __init__(
        self,
        scanner_version: str = "1.0.0",
        feature_engine: Optional[QuantitativeFeatureEngine] = None,
        calendar: Optional[IndianMarketCalendar] = None,
        scorer: Optional[OpportunityScorer] = None,
    ):
        self.scanner_version = scanner_version
        self.feature_engine = feature_engine or QuantitativeFeatureEngine()
        self.calendar = calendar or IndianMarketCalendar()
        self.scorer = scorer or OpportunityScorer()

        self.eligibility_filter = EligibilityFilter(self.calendar)
        self.price_filter = PriceFilter()
        self.liquidity_filter = LiquidityFilter()
        self.data_quality_filter = DataQualityFilter()

    def scan_as_of(
        self,
        universe: List[Instrument],
        decision_timestamp: datetime,
        timeframe: Timeframe,
        candles_by_symbol: Dict[str, List[HistoricalCandle]],
        config: Optional[ScannerConfig] = None,
        allow_outside_session: bool = False,
    ) -> Tuple[List[OpportunityCandidate], List[OpportunityCandidate]]:
        """
        Executes a point-in-time opportunity scan as of decision_timestamp.
        Returns:
            (accepted_candidates, rejected_candidates)
        """
        config = config or ScannerConfig()
        dec_ts = decision_timestamp.astimezone(IST) if decision_timestamp.tzinfo else decision_timestamp.replace(tzinfo=IST)

        accepted: List[OpportunityCandidate] = []
        rejected: List[OpportunityCandidate] = []
        seen_symbols = set()

        for inst in universe:
            sym = inst.symbol
            if sym in seen_symbols:
                continue
            seen_symbols.add(sym)

            # 1. Eligibility Filter
            is_eligible, rej_reason = self.eligibility_filter.filter(
                inst, dec_ts, allow_outside_session=allow_outside_session
            )
            if not is_eligible:
                rejected.append(
                    self._create_rejected_candidate(
                        inst, dec_ts, timeframe, rej_reason, config
                    )
                )
                continue

            # Retrieve candle history for this symbol
            candles = candles_by_symbol.get(sym, [])

            # 2. Point-in-Time Feature Calculation
            # Strictly use calculate_features_as_of to exclude forming and future candles
            features = self.feature_engine.calculate_features_as_of(candles, dec_ts)

            # 3. Data Quality & Historical Sufficiency Filter
            is_valid_data, data_rej_reason = self.data_quality_filter.filter(
                candles, features, config
            )
            if not is_valid_data:
                rejected.append(
                    self._create_rejected_candidate(
                        inst, dec_ts, timeframe, data_rej_reason, config, features=features
                    )
                )
                continue

            # 4. Price Filter
            is_valid_price, price_rej_reason = self.price_filter.filter(
                features.price, config
            )
            if not is_valid_price:
                rejected.append(
                    self._create_rejected_candidate(
                        inst, dec_ts, timeframe, price_rej_reason, config, features=features
                    )
                )
                continue

            # 5. Liquidity Filter
            is_liquid, liq_rej_reason = self.liquidity_filter.filter(
                features.volume, features.relative_volume_20, config
            )
            if not is_liquid:
                rejected.append(
                    self._create_rejected_candidate(
                        inst, dec_ts, timeframe, liq_rej_reason, config, features=features
                    )
                )
                continue

            # 6. Trend Filter (if specific trends are restricted)
            if config.allowed_trends and features.trend not in config.allowed_trends:
                rejected.append(
                    self._create_rejected_candidate(
                        inst, dec_ts, timeframe, RejectionReason.NOT_ELIGIBLE, config, features=features
                    )
                )
                continue

            # 7. Compute Explainable Opportunity Score
            score = self.scorer.compute_score(features, config)

            # 8. Construct Accepted Opportunity Candidate
            candidate = OpportunityCandidate(
                symbol=sym,
                exchange=inst.exchange,
                instrument_id=inst.instrument_id,
                decision_timestamp=dec_ts,
                timeframe=timeframe,
                price=features.price,
                opportunity_score=score.total_score,
                score_components=score.model_dump(),
                candle_timestamp=features.candle_timestamp,
                feature_available_at=features.feature_available_at,
                trend=features.trend,
                momentum=features.momentum_5,
                relative_volume=features.relative_volume_20,
                volatility=features.volatility_20,
                atr=features.atr_14,
                vwap=features.vwap,
                vwap_distance=features.distance_from_vwap,
                breakout_state="NEAR_HIGH" if (features.distance_from_session_high or 1.0) <= 0.0 else "NORMAL",
                rolling_high=features.rolling_high_20,
                rolling_low=features.rolling_low_20,
                liquidity_metrics={
                    "volume": features.volume,
                    "relative_volume_20": features.relative_volume_20,
                },
                data_quality={
                    "status": features.data_status.value,
                    "history_bars": len(candles),
                },
                is_eligible=True,
                rejection_reason=None,
                scanner_version=self.scanner_version,
                feature_version=features.feature_version,
                configuration_version=config.configuration_version,
                universe_version=config.universe_version,
                source_dataset_id=features.source_dataset_id,
            )
            accepted.append(candidate)

        # Rank accepted candidates
        ranked_accepted = self.rank_candidates(accepted)
        return ranked_accepted, rejected

    def rank_candidates(
        self, candidates: List[OpportunityCandidate]
    ) -> List[OpportunityCandidate]:
        """
        Ranks candidates descending by opportunity_score.
        Deterministic tie-breaking using symbol alphabetically.
        """
        return sorted(
            candidates,
            key=lambda c: (-c.opportunity_score, c.symbol)
        )

    def get_top_candidates(
        self, candidates: List[OpportunityCandidate], top_n: int
    ) -> List[OpportunityCandidate]:
        """
        Returns top-N candidates from an already ranked or unranked candidate list.
        """
        ranked = self.rank_candidates(candidates)
        return ranked[:max(0, top_n)]

    def _create_rejected_candidate(
        self,
        inst: Instrument,
        decision_timestamp: datetime,
        timeframe: Timeframe,
        reason: RejectionReason,
        config: ScannerConfig,
        features: Optional[Any] = None,
    ) -> OpportunityCandidate:
        price = features.price if (features and features.price > 0) else 1.0
        candle_ts = features.candle_timestamp if features else decision_timestamp
        avail_ts = features.feature_available_at if features else decision_timestamp
        return OpportunityCandidate(
            symbol=inst.symbol,
            exchange=inst.exchange,
            instrument_id=inst.instrument_id,
            decision_timestamp=decision_timestamp,
            timeframe=timeframe,
            price=price,
            opportunity_score=0.0,
            score_components={},
            candle_timestamp=candle_ts,
            feature_available_at=avail_ts,
            is_eligible=False,
            rejection_reason=reason,
            scanner_version=self.scanner_version,
            feature_version=features.feature_version if features else "1.1.0",
            configuration_version=config.configuration_version,
            universe_version=config.universe_version,
        )
