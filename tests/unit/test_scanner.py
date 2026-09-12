import pytest
from datetime import datetime, date, time, timedelta
from typing import List
from mobitrade.domain.data_models import (
    Instrument,
    HistoricalCandle,
    Timeframe,
    DataStatus,
    CandleTimestampSemantic,
)
from mobitrade.domain.scanner_models import (
    RejectionReason,
    ScannerConfig,
    OpportunityCandidate,
)
from mobitrade.data.calendar import IndianMarketCalendar, IST
from mobitrade.scanner.universe import EquityUniverseProvider
from mobitrade.scanner.filters import (
    EligibilityFilter,
    PriceFilter,
    LiquidityFilter,
    DataQualityFilter,
)
from mobitrade.scanner.scoring import OpportunityScorer
from mobitrade.scanner.persistence import ScannerDatabaseRepository
from mobitrade.scanner.scanner import OpportunityScanner

def create_candle_series(
    symbol: str,
    prices: List[float],
    start_dt: datetime,
    timeframe: Timeframe = Timeframe.M1,
    volume: float = 10000.0,
    status: DataStatus = DataStatus.VALID,
) -> List[HistoricalCandle]:
    candles = []
    curr_dt = start_dt
    for p in prices:
        candles.append(
            HistoricalCandle(
                symbol=symbol,
                exchange="NSE",
                timeframe=timeframe,
                timestamp=curr_dt,
                open=p,
                high=p + 1.0,
                low=p - 1.0,
                close=p,
                volume=volume,
                status=status,
                timestamp_semantic=CandleTimestampSemantic.INTERVAL_BEGINNING,
            )
        )
        curr_dt += timedelta(minutes=timeframe.minutes)
    return candles

# ============================================================
# 1. FILTER UNIT TESTS
# ============================================================

def test_eligibility_filter_nse_and_segment():
    filt = EligibilityFilter()
    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST) # Friday 10:00 AM IST

    # Valid NSE equity
    valid_inst = Instrument(
        symbol="TCS", exchange="NSE", segment="EQUITY", security_name="TCS Eq",
        trading_status="ACTIVE", data_source="TEST", ingested_at=dt
    )
    ok, reason = filt.filter(valid_inst, dt)
    assert ok is True
    assert reason is None

    # Invalid exchange BSE
    bse_inst = Instrument(
        symbol="TCS", exchange="BSE", segment="EQUITY", security_name="TCS Eq",
        trading_status="ACTIVE", data_source="TEST", ingested_at=dt
    )
    ok, reason = filt.filter(bse_inst, dt)
    assert ok is False
    assert reason == RejectionReason.NOT_ELIGIBLE

    # Inactive instrument
    suspended_inst = Instrument(
        symbol="TCS", exchange="NSE", segment="EQUITY", security_name="TCS Eq",
        trading_status="SUSPENDED", data_source="TEST", ingested_at=dt
    )
    ok, reason = filt.filter(suspended_inst, dt)
    assert ok is False
    assert reason == RejectionReason.INVALID_INSTRUMENT

def test_eligibility_filter_session_bounds():
    filt = EligibilityFilter()
    inst = Instrument(
        symbol="TCS", exchange="NSE", segment="EQUITY", security_name="TCS Eq",
        trading_status="ACTIVE", data_source="TEST", ingested_at=datetime(2026, 9, 11, 9, 0, tzinfo=IST)
    )

    # 08:30 IST is before market open (09:15)
    pre_market = datetime(2026, 9, 11, 8, 30, tzinfo=IST)
    ok, reason = filt.filter(inst, pre_market)
    assert ok is False
    assert reason == RejectionReason.OUTSIDE_SESSION

    # Allowed if allow_outside_session=True
    ok_override, _ = filt.filter(inst, pre_market, allow_outside_session=True)
    assert ok_override is True

def test_price_filter():
    filt = PriceFilter()
    cfg = ScannerConfig(min_price=10.0, max_price=50000.0)

    # Valid price
    assert filt.filter(1500.0, cfg) == (True, None)

    # Below min_price
    assert filt.filter(5.0, cfg) == (False, RejectionReason.INVALID_PRICE)

    # Above max_price
    assert filt.filter(60000.0, cfg) == (False, RejectionReason.INVALID_PRICE)

    # Non-positive or NaN
    assert filt.filter(0.0, cfg) == (False, RejectionReason.INVALID_PRICE)
    assert filt.filter(float("nan"), cfg) == (False, RejectionReason.INVALID_PRICE)

def test_liquidity_filter():
    filt = LiquidityFilter()
    cfg = ScannerConfig(min_volume=1000.0, relative_volume_threshold=1.0)

    # Normal liquid
    assert filt.filter(5000.0, 1.5, cfg) == (True, None)

    # Below volume threshold
    assert filt.filter(500.0, 1.5, cfg) == (False, RejectionReason.ILLIQUID)

    # Below relative volume threshold
    assert filt.filter(5000.0, 0.5, cfg) == (False, RejectionReason.ILLIQUID)

def test_data_quality_filter():
    filt = DataQualityFilter()
    cfg = ScannerConfig(min_history_bars=20)
    start_dt = datetime(2026, 9, 11, 9, 15, tzinfo=IST)

    # Insufficient history (only 10 bars)
    short_candles = create_candle_series("TCS", [100.0] * 10, start_dt)
    assert filt.filter(short_candles, None, cfg) == (False, RejectionReason.INSUFFICIENT_HISTORY)

# ============================================================
# 2. SCORING & RANKING TESTS
# ============================================================

def test_opportunity_scorer_explainability():
    scorer = OpportunityScorer()
    cfg = ScannerConfig()
    scanner = OpportunityScanner(scorer=scorer)

    # 30 bars of ascending prices
    start_dt = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    prices = [100.0 + i for i in range(30)]
    candles = create_candle_series("TCS", prices, start_dt, volume=25000.0)

    # Features as of bar 29 completed (09:45)
    decision_dt = datetime(2026, 9, 11, 9, 45, tzinfo=IST)
    features = scanner.feature_engine.calculate_features_as_of(candles, decision_dt)
    assert features is not None

    score = scorer.compute_score(features, cfg)
    assert 0.0 <= score.total_score <= 100.0
    assert score.momentum > 0.0
    assert score.trend > 0.0
    assert score.relative_volume > 0.0
    assert "momentum" in score.weights

def test_candidate_ranking_deterministic_ties():
    scanner = OpportunityScanner()
    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    c1 = OpportunityCandidate(
        symbol="TCS", exchange="NSE", decision_timestamp=dt, timeframe=Timeframe.M1,
        price=100.0, opportunity_score=75.0, candle_timestamp=dt, feature_available_at=dt
    )
    c2 = OpportunityCandidate(
        symbol="INFY", exchange="NSE", decision_timestamp=dt, timeframe=Timeframe.M1,
        price=100.0, opportunity_score=85.0, candle_timestamp=dt, feature_available_at=dt
    )
    c3 = OpportunityCandidate(
        symbol="HDFCBANK", exchange="NSE", decision_timestamp=dt, timeframe=Timeframe.M1,
        price=100.0, opportunity_score=75.0, candle_timestamp=dt, feature_available_at=dt
    )

    ranked = scanner.rank_candidates([c1, c2, c3])
    # INFY highest (85.0)
    assert ranked[0].symbol == "INFY"
    # TCS and HDFCBANK tie at 75.0 -> alphabetical tie-breaker (HDFCBANK before TCS)
    assert ranked[1].symbol == "HDFCBANK"
    assert ranked[2].symbol == "TCS"

# ============================================================
# 3. TOP-N SELECTION TESTS
# ============================================================

def test_top_n_selection():
    scanner = OpportunityScanner()
    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    candidates = [
        OpportunityCandidate(
            symbol=f"SYM_{i}", exchange="NSE", decision_timestamp=dt, timeframe=Timeframe.M1,
            price=100.0, opportunity_score=float(i), candle_timestamp=dt, feature_available_at=dt
        )
        for i in range(15)
    ]

    top_5 = scanner.get_top_candidates(candidates, 5)
    assert len(top_5) == 5
    assert top_5[0].opportunity_score == 14.0

    top_10 = scanner.get_top_candidates(candidates, 10)
    assert len(top_10) == 10

    top_50 = scanner.get_top_candidates(candidates, 50)
    assert len(top_50) == 15

# ============================================================
# 4. TEMPORAL SAFETY & NO-LOOKAHEAD REGRESSION TESTS
# ============================================================

def test_temporal_safety_forming_candle_excluded():
    scanner = OpportunityScanner()
    start_dt = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    # Candles at 09:15, 09:16, 09:17
    candles = create_candle_series("TCS", [100.0, 102.0, 104.0], start_dt)

    # Decision at 09:17:30
    decision_dt = datetime(2026, 9, 11, 9, 17, 30, tzinfo=IST)
    feat = scanner.feature_engine.calculate_features_as_of(candles, decision_dt)

    # At 09:17:30, the 09:17 candle (close=104.0) is still forming!
    # Available completed candle is 09:16 (close=102.0)
    assert feat is not None
    assert feat.candle_timestamp == datetime(2026, 9, 11, 9, 16, tzinfo=IST)
    assert feat.feature_available_at == datetime(2026, 9, 11, 9, 17, tzinfo=IST)
    assert feat.price == 102.0

def test_temporal_safety_future_spike_cannot_change_earlier_ranking():
    scanner = OpportunityScanner()
    start_dt = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    
    # 25 morning candles for TCS and INFY
    tcs_morning = create_candle_series("TCS", [100.0 + i * 0.5 for i in range(25)], start_dt, volume=20000.0)
    infy_morning = create_candle_series("INFY", [100.0 + i * 0.2 for i in range(25)], start_dt, volume=15000.0)

    universe_provider = EquityUniverseProvider()
    universe_provider.register_symbols(["TCS", "INFY"])
    universe = universe_provider.get_universe_as_of(start_dt)

    decision_dt = datetime(2026, 9, 11, 9, 40, tzinfo=IST)
    cfg = ScannerConfig(min_history_bars=20)

    # Baseline scan
    accepted_1, _ = scanner.scan_as_of(
        universe, decision_dt, Timeframe.M1,
        candles_by_symbol={"TCS": tcs_morning, "INFY": infy_morning},
        config=cfg
    )
    assert len(accepted_1) == 2
    rank_1 = [c.symbol for c in accepted_1]
    scores_1 = {c.symbol: c.opportunity_score for c in accepted_1}

    # Inject massive afternoon price & volume spike at 14:00 into INFY
    infy_afternoon_spike = create_candle_series(
        "INFY", [1000.0], datetime(2026, 9, 11, 14, 0, tzinfo=IST), volume=5000000.0
    )
    infy_with_future = infy_morning + infy_afternoon_spike

    # Repeat scan at 09:40 with future spike present in feed
    accepted_2, _ = scanner.scan_as_of(
        universe, decision_dt, Timeframe.M1,
        candles_by_symbol={"TCS": tcs_morning, "INFY": infy_with_future},
        config=cfg
    )
    assert len(accepted_2) == 2
    rank_2 = [c.symbol for c in accepted_2]
    scores_2 = {c.symbol: c.opportunity_score for c in accepted_2}

    # Proves future data cannot alter earlier rankings or scores
    assert rank_1 == rank_2
    assert scores_1 == scores_2

def test_instrument_point_in_time_validity():
    provider = EquityUniverseProvider()
    now = datetime(2026, 9, 11, 9, 0, tzinfo=IST)
    
    # Instrument valid only from 2026-09-15 onwards
    future_inst = Instrument(
        symbol="FUTURE_IPO", exchange="NSE", segment="EQUITY", security_name="Future IPO",
        trading_status="ACTIVE", data_source="TEST", ingested_at=now,
        valid_from=date(2026, 9, 15)
    )
    provider.register_instrument(future_inst)

    # At 2026-09-11, FUTURE_IPO must NOT be in universe
    u_early = provider.get_universe_as_of(datetime(2026, 9, 11, 10, 0, tzinfo=IST))
    assert not any(i.symbol == "FUTURE_IPO" for i in u_early)

    # At 2026-09-16, FUTURE_IPO must BE in universe
    u_late = provider.get_universe_as_of(datetime(2026, 9, 16, 10, 0, tzinfo=IST))
    assert any(i.symbol == "FUTURE_IPO" for i in u_late)

# ============================================================
# 5. DATABASE PERSISTENCE TESTS
# ============================================================

def test_scanner_database_persistence_and_idempotence(tmp_path):
    db_file = tmp_path / "test_mobitrade.db"
    repo = ScannerDatabaseRepository(str(db_file))
    dt = datetime(2026, 9, 11, 10, 0, tzinfo=IST)

    candidate = OpportunityCandidate(
        symbol="TCS",
        exchange="NSE",
        decision_timestamp=dt,
        timeframe=Timeframe.M5,
        price=1500.0,
        opportunity_score=78.5,
        score_components={"momentum": 20.0, "relative_volume": 18.0},
        candle_timestamp=dt - timedelta(minutes=5),
        feature_available_at=dt,
        is_eligible=True,
    )

    # Save scan results
    repo.save_scan_results(
        scan_id="scan_001",
        decision_timestamp=dt,
        timeframe="5m",
        scanner_version="1.0.0",
        configuration_version="1.0.0",
        universe_version="1.0.0",
        candidates=[candidate],
        total_universe=10,
        eligible_count=1
    )

    # Query scan
    scan = repo.get_scan("scan_001")
    assert scan is not None
    assert scan["candidate_count"] == 1
    assert scan["timeframe"] == "5m"

    candidates = repo.get_candidates("scan_001")
    assert len(candidates) == 1
    assert candidates[0]["symbol"] == "TCS"
    assert candidates[0]["opportunity_score"] == 78.5

    # Re-run same scan (must be idempotent, not duplicate rows)
    repo.save_scan_results(
        scan_id="scan_001",
        decision_timestamp=dt,
        timeframe="5m",
        scanner_version="1.0.0",
        configuration_version="1.0.0",
        universe_version="1.0.0",
        candidates=[candidate],
        total_universe=10,
        eligible_count=1
    )
    candidates_rerun = repo.get_candidates("scan_001")
    assert len(candidates_rerun) == 1
