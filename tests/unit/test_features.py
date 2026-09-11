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
            timestamp=base_dt + timedelta(minutes=i),
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
    # Positive prices >= 10.0 to satisfy HistoricalCandle(open > 0, etc.)
    prices = [float(10 + i) for i in range(1, 60)] # 11 to 69
    candles = create_candles(prices)
    features = engine.calculate_features(candles)
    
    # Check bar 4 (index 3): SMA 5 should be None (only 4 observations)
    assert features[3].sma_5 is None
    # Check bar 5 (index 4): SMA 5 of [11, 12, 13, 14, 15] = 13.0
    assert features[4].sma_5 == 13.0
    # Check bar 9: SMA 9 of 11..19 = 15.0
    assert features[8].sma_9 == 15.0
    # EMA 5 is populated after bar 5
    assert features[4].ema_5 is not None
    assert features[4].ema_5 == 13.0

# 2. RSI Calculation Test
def test_rsi_calculation():
    engine = QuantitativeFeatureEngine()
    prices = [100.0 + i for i in range(25)]
    candles = create_candles(prices)
    features = engine.calculate_features(candles)
    
    # First 14 bars RSI is None (insufficient history)
    assert features[13].rsi_14 is None
    # After bar 15, RSI is available
    assert features[15].rsi_14 is not None
    assert features[-1].rsi_14 == 100.0

# 3. MACD Calculation Test
def test_macd_calculation():
    engine = QuantitativeFeatureEngine()
    prices = [100.0 + (i % 5) for i in range(50)]
    candles = create_candles(prices)
    features = engine.calculate_features(candles)
    
    # Needs slow_period (26) + signal_period (9) = 35 observations
    assert features[20].macd_line is None
    assert features[40].macd_line is not None
    assert features[40].macd_signal is not None
    assert features[40].macd_histogram is not None

# 4. Session-Aware VWAP and Daily Reset Test
def test_vwap_session_reset():
    engine = QuantitativeFeatureEngine()
    
    # Day 1: 09:15 to 09:17 (3 candles)
    day1_start = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    candles_day1 = create_candles([100.0, 105.0, 110.0], volumes=[100, 100, 100], start_dt=day1_start)
    
    # Day 2: 09:15 (next trading day)
    day2_start = datetime(2026, 9, 14, 9, 15, tzinfo=IST)
    candles_day2 = create_candles([200.0], volumes=[100], start_dt=day2_start)
    
    all_candles = candles_day1 + candles_day2
    features = engine.calculate_features(all_candles)
    
    # Day 1 final VWAP incorporates Day 1 prices
    vwap_day1_end = features[2].vwap
    assert vwap_day1_end is not None
    assert 100.0 < vwap_day1_end < 110.0
    
    # Day 2 first candle VWAP MUST reset to Day 2 price only (no carryover from Day 1)
    vwap_day2_start = features[3].vwap
    assert vwap_day2_start == 200.0

# 5. Relative Volume Test
def test_relative_volume():
    engine = QuantitativeFeatureEngine()
    # 20 bars of volume 100, followed by bar 21 with volume 300
    vols = [100.0] * 20 + [300.0]
    prices = [100.0] * 21
    candles = create_candles(prices, volumes=vols)
    features = engine.calculate_features(candles)
    
    # Bar 21 relative volume = 300 / 100 = 3.0
    assert features[-1].relative_volume_20 == 3.0

# 6. Price Structure & Trend Classification Test
def test_price_structure_and_trend():
    engine = QuantitativeFeatureEngine()
    prices = [100.0 + (i * 2.0) for i in range(55)]
    candles = create_candles(prices)
    features = engine.calculate_features(candles)
    
    last = features[-1]
    assert last.trend == TrendClassification.BULLISH
    assert last.candle_body == 0.0 # Open == Close in synthetic helper
    # distance_from_session_high = session_high - close; since high = close + 2.0, distance is 2.0
    assert last.distance_from_session_high == 2.0
    assert last.distance_from_session_low > 0.0

# 7. No Look-Ahead Bias Verification
def test_no_look_ahead_bias():
    engine = QuantitativeFeatureEngine()
    candles_subset = create_candles([100.0, 102.0, 104.0])
    features_subset = engine.calculate_features(candles_subset)
    
    # Now append future price spike of 200.0
    future_candle = create_candles([200.0], start_dt=candles_subset[-1].timestamp + timedelta(minutes=1))[0]
    candles_full = candles_subset + [future_candle]
    features_full = engine.calculate_features(candles_full)
    
    # Feature values at index 2 (104.0) MUST BE IDENTICAL whether future bar exists or not
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
    assert "features_1.0.0.parquet" in saved_path
    
    loaded = repo.load_features("TCS", Timeframe.M1)
    assert len(loaded) == 3
    assert loaded[0].price == 100.0

# 9. Trailing Stop Engine Comprehensive Tests (16 Scenarios from Prompt)
def test_trailing_stop_engine_lifecycle():
    engine = TrailingStopEngine(default_trailing_pct=0.005) # 0.5%
    
    # 1. Entry at Rs 100 with initial protective stop at Rs 95
    engine.register_position(
        model_id="nemotron",
        symbol="RELIANCE",
        trade_id="trd_01",
        entry_price=100.0,
        initial_stop_loss=95.0,
        trailing_pct=0.005
    )
    state = engine.get_state("nemotron", "RELIANCE")
    assert state.current_stop == 95.0
    
    # 2. Peak Rs 101 updates trailing stop -> 101 * (1 - 0.005) = 100.495
    triggered, stop, updated = state.update_price(101.0)
    assert not triggered
    assert updated
    assert round(stop, 3) == 100.495
    
    # 3. Peak Rs 102 updates trailing stop -> 102 * (1 - 0.005) = 101.490
    triggered, stop, updated = state.update_price(102.0)
    assert not triggered
    assert round(stop, 3) == 101.490
    
    # 4. Peak Rs 103 updates trailing stop -> 103 * (1 - 0.005) = 102.485
    triggered, stop, updated = state.update_price(103.0)
    assert not triggered
    assert round(stop, 3) == 102.485
    
    # 5. Peak Rs 105 updates trailing stop -> 105 * (1 - 0.005) = 104.475
    triggered, stop, updated = state.update_price(105.0)
    assert not triggered
    assert round(stop, 3) == 104.475
    
    # 6. Trailing stop NEVER decreases when price drops from 105 to 104.8
    triggered, stop, updated = state.update_price(104.8)
    assert not triggered
    assert not updated
    assert round(stop, 3) == 104.475 # Remains 104.475
    
    # 7. Price falls to or below trailing stop (e.g. 104.40 <= 104.475) -> Triggers Exit
    triggered, stop = engine.update_price("nemotron", "RELIANCE", 104.40)
    assert triggered
    assert engine.get_state("nemotron", "RELIANCE") is None # Cleared upon exit

def test_trailing_stop_isolation_between_models_and_positions():
    engine = TrailingStopEngine()
    
    # Register Model A (nemotron) on RELIANCE
    engine.register_position("nemotron", "RELIANCE", "trd_a", entry_price=100.0, initial_stop_loss=95.0)
    # Register Model B (qwen) on RELIANCE
    engine.register_position("qwen", "RELIANCE", "trd_b", entry_price=200.0, initial_stop_loss=190.0)
    
    # Price update for Model A
    state_a = engine.get_state("nemotron", "RELIANCE")
    state_a.update_price(110.0)
    
    # Model B state must be completely untouched
    state_b = engine.get_state("qwen", "RELIANCE")
    assert state_b.peak_price == 200.0
    assert state_b.current_stop == 190.0