import pytest
from datetime import datetime, date, timedelta
from pathlib import Path
import zoneinfo
from mobitrade.domain.data_models import HistoricalCandle, Timeframe, DataStatus, CandleTimestampSemantic
from mobitrade.domain.feature_models import TechnicalFeatures, TrendClassification
from mobitrade.features.engine import QuantitativeFeatureEngine
from mobitrade.features.repository import ParquetFeatureRepository
from mobitrade.risk.trailing_stop import TrailingStopEngine, TrailingStopState

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# Helper to build synthetic candles
def create_candles(prices, volumes=None, start_dt=None, symbol="TCS", timeframe=Timeframe.M1):
    candles = []
    base_dt = start_dt or datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    for i, p in enumerate(prices):
        v = volumes[i] if volumes else 1000.0
        c = HistoricalCandle(
            symbol=symbol,
            exchange="NSE",
            timeframe=timeframe,
            timestamp=base_dt + timedelta(minutes=i * timeframe.minutes),
            open=p,
            high=p + 2.0,
            low=p - 2.0,
            close=p,
            volume=v,
            status=DataStatus.VALID,
            timestamp_semantic=CandleTimestampSemantic.INTERVAL_BEGINNING
        )
        candles.append(c)
    return candles

# 1. Moving Averages Tests (SMA, EMA, Insufficient History)
def test_sma_and_ema_calculation():
    engine = QuantitativeFeatureEngine()
    prices = [float(10 + i) for i in range(1, 60)]
    candles = create_candles(prices)
    features = engine.calculate_features(candles)
    
    assert features[3].sma_5 is None
    assert features[4].sma_5 == 13.0
    assert features[8].sma_9 == 15.0
    assert features[4].ema_5 is not None
    assert features[4].ema_5 == 13.0

# 2. RSI Calculation Test
def test_rsi_calculation():
    engine = QuantitativeFeatureEngine()
    prices = [100.0 + i for i in range(25)]
    candles = create_candles(prices)
    features = engine.calculate_features(candles)
    
    assert features[13].rsi_14 is None
    assert features[15].rsi_14 is not None
    assert features[-1].rsi_14 == 100.0

# 3. MACD Calculation Test
def test_macd_calculation():
    engine = QuantitativeFeatureEngine()
    prices = [100.0 + (i % 5) for i in range(50)]
    candles = create_candles(prices)
    features = engine.calculate_features(candles)
    
    assert features[20].macd_line is None
    assert features[40].macd_line is not None
    assert features[40].macd_signal is not None
    assert features[40].macd_histogram is not None

# 4. Session-Aware VWAP and Daily Reset Test
def test_vwap_session_reset():
    engine = QuantitativeFeatureEngine()
    
    day1_start = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    candles_day1 = create_candles([100.0, 105.0, 110.0], volumes=[100, 100, 100], start_dt=day1_start)
    
    day2_start = datetime(2026, 9, 14, 9, 15, tzinfo=IST)
    candles_day2 = create_candles([200.0], volumes=[100], start_dt=day2_start)
    
    all_candles = candles_day1 + candles_day2
    features = engine.calculate_features(all_candles)
    
    vwap_day1_end = features[2].vwap
    assert vwap_day1_end is not None
    assert 100.0 < vwap_day1_end < 110.0
    
    vwap_day2_start = features[3].vwap
    assert vwap_day2_start == 200.0

# 5. Relative Volume Test
def test_relative_volume():
    engine = QuantitativeFeatureEngine()
    vols = [100.0] * 20 + [300.0]
    prices = [100.0] * 21
    candles = create_candles(prices, volumes=vols)
    features = engine.calculate_features(candles)
    
    assert features[-1].relative_volume_20 == 3.0

# 6. Price Structure & Trend Classification Test
def test_price_structure_and_trend():
    engine = QuantitativeFeatureEngine()
    prices = [100.0 + (i * 2.0) for i in range(55)]
    candles = create_candles(prices)
    features = engine.calculate_features(candles)
    
    last = features[-1]
    assert last.trend == TrendClassification.BULLISH
    assert last.candle_body == 0.0
    assert last.distance_from_session_high == 2.0
    assert last.distance_from_session_low > 0.0

# 7. No Look-Ahead Bias Verification
def test_no_look_ahead_bias():
    engine = QuantitativeFeatureEngine()
    candles_subset = create_candles([100.0, 102.0, 104.0])
    features_subset = engine.calculate_features(candles_subset)
    
    future_candle = create_candles([200.0], start_dt=candles_subset[-1].timestamp + timedelta(minutes=1))[0]
    candles_full = candles_subset + [future_candle]
    features_full = engine.calculate_features(candles_full)
    
    assert features_subset[2].price == features_full[2].price
    assert features_subset[2].vwap == features_full[2].vwap
    assert features_subset[2].distance_from_session_high == features_full[2].distance_from_session_high

# 8. Parquet Feature Repository Test
def test_parquet_feature_repository(tmp_path):
    repo = ParquetFeatureRepository(str(tmp_path))
    engine = QuantitativeFeatureEngine()
    candles = create_candles([100.0, 102.0, 104.0])
    features = engine.calculate_features(candles, source_dataset_id="ds_test")
    
    saved_path = repo.save_features(features)
    assert "features_1.1.0.parquet" in saved_path
    
    loaded = repo.load_features("TCS", Timeframe.M1)
    assert len(loaded) == 3
    assert loaded[0].price == 100.0
    assert loaded[0].candle_timestamp is not None
    assert loaded[0].feature_available_at is not None

# 9. Trailing Stop Engine Comprehensive Tests
def test_trailing_stop_engine_lifecycle():
    engine = TrailingStopEngine(default_trailing_pct=0.005)
    
    engine.register_position(
        model_id="nemotron", symbol="RELIANCE", trade_id="trd_01",
        entry_price=100.0, initial_stop_loss=95.0, trailing_pct=0.005
    )
    state = engine.get_state("nemotron", "RELIANCE")
    assert state.current_stop == 95.0
    
    triggered, stop, updated = state.update_price(101.0)
    assert not triggered and updated and round(stop, 3) == 100.495
    
    triggered, stop, updated = state.update_price(102.0)
    assert not triggered and updated and round(stop, 3) == 101.490
    
    triggered, stop, updated = state.update_price(103.0)
    assert not triggered and updated and round(stop, 3) == 102.485
    
    triggered, stop, updated = state.update_price(105.0)
    assert not triggered and updated and round(stop, 3) == 104.475
    
    triggered, stop, updated = state.update_price(104.8)
    assert not triggered and not updated and round(stop, 3) == 104.475
    
    triggered, stop = engine.update_price("nemotron", "RELIANCE", 104.40)
    assert triggered
    assert engine.get_state("nemotron", "RELIANCE") is None

def test_trailing_stop_isolation_between_models_and_positions():
    engine = TrailingStopEngine()
    engine.register_position("nemotron", "RELIANCE", "trd_a", entry_price=100.0, initial_stop_loss=95.0)
    engine.register_position("qwen", "RELIANCE", "trd_b", entry_price=200.0, initial_stop_loss=190.0)
    
    state_a = engine.get_state("nemotron", "RELIANCE")
    state_a.update_price(110.0)
    
    state_b = engine.get_state("qwen", "RELIANCE")
    assert state_b.peak_price == 200.0
    assert state_b.current_stop == 190.0

# 10. Candle available_at semantics across 1m, 5m, 15m
def test_candle_available_at_timing():
    ts = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    
    c_1m = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=ts, open=100, high=105, low=98, close=102, volume=10)
    assert c_1m.available_at == datetime(2026, 9, 11, 9, 16, tzinfo=IST)
    
    c_5m = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M5, timestamp=ts, open=100, high=105, low=98, close=102, volume=10)
    assert c_5m.available_at == datetime(2026, 9, 11, 9, 20, tzinfo=IST)
    
    c_15m = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M15, timestamp=ts, open=100, high=105, low=98, close=102, volume=10)
    assert c_15m.available_at == datetime(2026, 9, 11, 9, 30, tzinfo=IST)

# 11. Current forming candle exclusion & completed previous candle inclusion
def test_calculate_features_as_of_temporal_boundary():
    engine = QuantitativeFeatureEngine()
    candles = create_candles([100.0, 102.0, 104.0], start_dt=datetime(2026, 9, 11, 9, 15, tzinfo=IST))
    
    snapshot_915_30 = engine.calculate_features_as_of(candles, datetime(2026, 9, 11, 9, 15, 30, tzinfo=IST))
    assert snapshot_915_30 is None
    
    snapshot_916 = engine.calculate_features_as_of(candles, datetime(2026, 9, 11, 9, 16, 0, tzinfo=IST))
    assert snapshot_916 is not None
    assert snapshot_916.candle_timestamp == datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    assert snapshot_916.feature_available_at == datetime(2026, 9, 11, 9, 16, tzinfo=IST)
    assert snapshot_916.price == 100.0
    
    snapshot_917_30 = engine.calculate_features_as_of(candles, datetime(2026, 9, 11, 9, 17, 30, tzinfo=IST))
    assert snapshot_917_30 is not None
    assert snapshot_917_30.price == 102.0

# 12. Future session statistics leak prevention
def test_future_session_stats_leak_prevention():
    engine = QuantitativeFeatureEngine()
    start_dt = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    morning_candles = create_candles([100.0, 101.0, 102.0, 101.5, 102.0], start_dt=start_dt)
    afternoon_candle = create_candles([300.0], start_dt=datetime(2026, 9, 11, 14, 0, tzinfo=IST))[0]
    all_candles = morning_candles + [afternoon_candle]
    
    snap = engine.calculate_features_as_of(all_candles, datetime(2026, 9, 11, 9, 20, tzinfo=IST))
    assert snap is not None
    assert snap.distance_from_session_high < 10.0
    assert snap.vwap < 105.0

# 13. Timeframe-aware volatility
def test_timeframe_aware_volatility():
    engine = QuantitativeFeatureEngine()
    prices = [100.0 + (i % 3) for i in range(30)]
    
    candles_1m = create_candles(prices, timeframe=Timeframe.M1)
    candles_5m = create_candles(prices, timeframe=Timeframe.M5)
    candles_15m = create_candles(prices, timeframe=Timeframe.M15)
    
    feat_1m = engine.calculate_features(candles_1m)[-1]
    feat_5m = engine.calculate_features(candles_5m)[-1]
    feat_15m = engine.calculate_features(candles_15m)[-1]
    
    assert feat_1m.volatility_20 > feat_5m.volatility_20
    assert feat_5m.volatility_20 > feat_15m.volatility_20

# ============================================================
# PHASE 3.2 REGRESSION TESTS: STORAGE IDEMPOTENCE & SCANNER GATE
# ============================================================

# Test 14 & 15: Incremental batch merge and duplicate prevention
def test_feature_batch_merge_and_deduplication(tmp_path):
    repo = ParquetFeatureRepository(str(tmp_path))
    engine = QuantitativeFeatureEngine(version="1.1.0")
    
    # Batch A: candles at 09:15 and 09:16
    candles_a = create_candles([100.0, 102.0], start_dt=datetime(2026, 9, 11, 9, 15, tzinfo=IST))
    feat_a = engine.calculate_features(candles_a)
    repo.save_features(feat_a)
    
    # Save Batch A a second time (must not duplicate)
    repo.save_features(feat_a)
    loaded_1 = repo.load_features("TCS", Timeframe.M1)
    assert len(loaded_1) == 2
    
    # Batch B: candle at 09:17
    candles_b = create_candles([104.0], start_dt=datetime(2026, 9, 11, 9, 17, tzinfo=IST))
    feat_b = engine.calculate_features(candles_b)
    repo.save_features(feat_b)
    
    # Verify merged result: Batch A + Batch B both preserved and sorted
    loaded_2 = repo.load_features("TCS", Timeframe.M1)
    assert len(loaded_2) == 3
    assert [f.price for f in loaded_2] == [100.0, 102.0, 104.0]

# Test 16: Feature version isolation
def test_feature_version_isolation(tmp_path):
    repo = ParquetFeatureRepository(str(tmp_path))
    engine_v1 = QuantitativeFeatureEngine(version="1.1.0")
    engine_v2 = QuantitativeFeatureEngine(version="1.2.0")
    
    candles = create_candles([100.0, 102.0])
    feat_v1 = engine_v1.calculate_features(candles)
    feat_v2 = engine_v2.calculate_features(candles)
    
    p1 = repo.save_features(feat_v1)
    p2 = repo.save_features(feat_v2)
    assert "features_1.1.0.parquet" in p1
    assert "features_1.2.0.parquet" in p2
    assert p1 != p2

# Test 17: Pure read does not create storage directories
def test_read_does_not_create_directories(tmp_path):
    repo = ParquetFeatureRepository(str(tmp_path))
    non_existent_symbol = "UNTRADED_SYM"
    
    # Partition directory must not exist
    part_dir = (
        Path(str(tmp_path))
        / "processed"
        / "market=indian_equity"
        / "features"
        / "exchange=NSE"
        / f"symbol={non_existent_symbol}"
        / "timeframe=1m"
    )
    assert not part_dir.exists()
    
    # Pure read query
    loaded = repo.load_features(non_existent_symbol, Timeframe.M1)
    assert loaded == []
    
    # Must STILL NOT exist after read operation
    assert not part_dir.exists()

# Test 18: Scanner temporal safety contract at 09:17:30
def test_scanner_temporal_safety_at_91730():
    engine = QuantitativeFeatureEngine()
    # Candles at 09:15, 09:16, 09:17
    candles = create_candles([100.0, 102.0, 104.0], start_dt=datetime(2026, 9, 11, 9, 15, tzinfo=IST))
    # Future afternoon spike at 14:00
    future_candle = create_candles([500.0], start_dt=datetime(2026, 9, 11, 14, 0, tzinfo=IST))[0]
    all_candles = candles + [future_candle]
    
    decision_time = datetime(2026, 9, 11, 9, 17, 30, tzinfo=IST)
    snapshot = engine.calculate_features_as_of(all_candles, decision_time)
    
    assert snapshot is not None
    # Must be the completed 09:16 candle (close=102.0), NOT forming 09:17 candle (104.0) or 14:00 spike (500.0)
    assert snapshot.candle_timestamp == datetime(2026, 9, 11, 9, 16, tzinfo=IST)
    assert snapshot.feature_available_at == datetime(2026, 9, 11, 9, 17, tzinfo=IST)
    assert snapshot.price == 102.0

# Test 19: Temporal ordering invariant enforcement
def test_feature_temporal_ordering_validation():
    ts = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    
    # Valid: available_at (09:16) >= candle_timestamp (09:15)
    valid_feat = TechnicalFeatures(
        symbol="TCS",
        exchange="NSE",
        candle_timestamp=ts,
        feature_available_at=ts + timedelta(minutes=1),
        timeframe=Timeframe.M1,
        price=100.0,
        volume=1000.0
    )
    assert valid_feat.feature_available_at > valid_feat.candle_timestamp
    
    # Invalid: available_at before candle_timestamp -> Must raise ValueError
    with pytest.raises(ValueError, match="Temporal violation"):
        TechnicalFeatures(
            symbol="TCS",
            exchange="NSE",
            candle_timestamp=ts,
            feature_available_at=ts - timedelta(minutes=1), # Violation!
            timeframe=Timeframe.M1,
            price=100.0,
            volume=1000.0
        )