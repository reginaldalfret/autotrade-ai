import pytest
from datetime import datetime, date, timedelta
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

# ============================================================
# PHASE 3.1 HARDENING TESTS: TEMPORAL INTEGRITY & AVAILABILITY
# ============================================================

# Test 1, 2, 3, 4: Candle available_at semantics across 1m, 5m, 15m
def test_candle_available_at_timing():
    ts = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    
    c_1m = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=ts, open=100, high=105, low=98, close=102, volume=10)
    assert c_1m.available_at == datetime(2026, 9, 11, 9, 16, tzinfo=IST)
    
    c_5m = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M5, timestamp=ts, open=100, high=105, low=98, close=102, volume=10)
    assert c_5m.available_at == datetime(2026, 9, 11, 9, 20, tzinfo=IST)
    
    c_15m = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M15, timestamp=ts, open=100, high=105, low=98, close=102, volume=10)
    assert c_15m.available_at == datetime(2026, 9, 11, 9, 30, tzinfo=IST)

# Test 5 & 6: Current forming candle exclusion & completed previous candle inclusion
def test_calculate_features_as_of_temporal_boundary():
    engine = QuantitativeFeatureEngine()
    # 3 one-minute candles starting at 09:15:
    # Candle 0: 09:15 (available_at 09:16)
    # Candle 1: 09:16 (available_at 09:17)
    # Candle 2: 09:17 (available_at 09:18)
    candles = create_candles([100.0, 102.0, 104.0], start_dt=datetime(2026, 9, 11, 9, 15, tzinfo=IST))
    
    # At 09:15:30 -> Candle 0 (09:15) is STILL FORMING -> Must return None!
    snapshot_915_30 = engine.calculate_features_as_of(candles, datetime(2026, 9, 11, 9, 15, 30, tzinfo=IST))
    assert snapshot_915_30 is None
    
    # At 09:16:00 -> Candle 0 is NOW COMPLETED -> Returns Candle 0 features
    snapshot_916 = engine.calculate_features_as_of(candles, datetime(2026, 9, 11, 9, 16, 0, tzinfo=IST))
    assert snapshot_916 is not None
    assert snapshot_916.candle_timestamp == datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    assert snapshot_916.feature_available_at == datetime(2026, 9, 11, 9, 16, tzinfo=IST)
    assert snapshot_916.price == 100.0
    
    # At 09:17:30 -> Candle 1 (09:16) is completed, but Candle 2 (09:17) is still forming
    snapshot_917_30 = engine.calculate_features_as_of(candles, datetime(2026, 9, 11, 9, 17, 30, tzinfo=IST))
    assert snapshot_917_30 is not None
    assert snapshot_917_30.price == 102.0 # Candle 1 close (NOT Candle 2 close of 104.0)

# Test 7, 8, 9: Future session statistics (high, low, VWAP) excluded
def test_future_session_stats_leak_prevention():
    engine = QuantitativeFeatureEngine()
    start_dt = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    # Morning candles 09:15-09:19 prices around 100.0
    morning_candles = create_candles([100.0, 101.0, 102.0, 101.5, 102.0], start_dt=start_dt)
    
    # Afternoon candle at 14:00 with massive spike to 300.0
    afternoon_candle = create_candles([300.0], start_dt=datetime(2026, 9, 11, 14, 0, tzinfo=IST))[0]
    all_candles = morning_candles + [afternoon_candle]
    
    # Query features at 09:20 (after 09:19 candle finishes)
    snap = engine.calculate_features_as_of(all_candles, datetime(2026, 9, 11, 9, 20, tzinfo=IST))
    assert snap is not None
    # Distance from session high must be relative to morning peak (102.0 + 2.0 = 104.0), NOT afternoon 300.0!
    assert snap.distance_from_session_high < 10.0
    assert snap.vwap < 105.0

# Test 11: Timeframe-aware realized volatility annualization
def test_timeframe_aware_volatility():
    engine = QuantitativeFeatureEngine()
    prices = [100.0 + (i % 3) for i in range(30)]
    
    candles_1m = create_candles(prices, timeframe=Timeframe.M1)
    candles_5m = create_candles(prices, timeframe=Timeframe.M5)
    candles_15m = create_candles(prices, timeframe=Timeframe.M15)
    
    feat_1m = engine.calculate_features(candles_1m)[-1]
    feat_5m = engine.calculate_features(candles_5m)[-1]
    feat_15m = engine.calculate_features(candles_15m)[-1]
    
    # Volatility should scale with sqrt(bars_per_session): 375 > 75 > 25
    assert feat_1m.volatility_20 > feat_5m.volatility_20
    assert feat_5m.volatility_20 > feat_15m.volatility_20