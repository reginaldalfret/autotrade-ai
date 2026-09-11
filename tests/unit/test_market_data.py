import pytest
from datetime import datetime, date, time
import zoneinfo
from mobitrade.domain.data_models import (
    HistoricalCandle, Timeframe, DataStatus, CandleTimestampSemantic,
    Instrument, CorporateAction, CorporateActionType
)
from mobitrade.data.calendar import IndianMarketCalendar, IST
from mobitrade.data.validator import DataQualityValidator
from mobitrade.data.local_provider import LocalFileMarketDataProvider
from mobitrade.data.fyers_provider import FyersDataProvider
from mobitrade.data.repository import ParquetDataRepository
from mobitrade.data.manager import DataDownloadManager

# Test 1 & 29: Instrument master parsing & validity
def test_instrument_master_creation():
    inst = Instrument(
        symbol="RELIANCE",
        exchange="NSE",
        segment="EQUITY",
        instrument_id="NSE:RELIANCE-EQ",
        isin="INE002A01018",
        security_name="Reliance Industries Limited",
        trading_status="ACTIVE",
        data_source="master_feed",
        ingested_at=datetime.now(IST)
    )
    assert inst.symbol == "RELIANCE"
    assert inst.isin == "INE002A01018"
    assert inst.trading_status == "ACTIVE"

# Test 4: Candle timestamp semantics (interval beginning)
def test_candle_timestamp_semantics():
    candle = HistoricalCandle(
        symbol="TCS",
        timeframe=Timeframe.M1,
        timestamp=datetime(2026, 9, 11, 9, 15, tzinfo=IST),
        open=3500.0,
        high=3510.0,
        low=3495.0,
        close=3505.0,
        volume=5000.0,
        timestamp_semantic=CandleTimestampSemantic.INTERVAL_BEGINNING
    )
    assert candle.timestamp_semantic == CandleTimestampSemantic.INTERVAL_BEGINNING
    assert candle.timestamp.hour == 9
    assert candle.timestamp.minute == 15

# Test 5 & 30: OHLC validation and invalid candle rejection
def test_invalid_ohlc_rejection():
    with pytest.raises(ValueError):
        HistoricalCandle(
            symbol="INFY",
            timeframe=Timeframe.M1,
            timestamp=datetime(2026, 9, 11, 9, 15, tzinfo=IST),
            open=1500.0,
            high=1490.0, # High < Open: INVALID
            low=1480.0,
            close=1495.0,
            volume=1000.0
        )

# Test 6 & 7: Duplicate detection and chronological ordering
def test_duplicate_detection_and_cleaning():
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    ts = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    
    c1 = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=ts, open=100, high=110, low=95, close=105, volume=10)
    c2 = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=ts, open=100, high=110, low=95, close=105, volume=10)
    
    cleaned, stats = val.validate_and_clean_candles([c1, c2])
    assert len(cleaned) == 1
    assert stats["duplicates"] == 1

# Test 9, 10, 11: Market calendar, weekend and holiday handling
def test_market_calendar_rules():
    cal = IndianMarketCalendar()
    # Monday trading day
    assert cal.is_trading_day(date(2026, 9, 14)) is True
    # Sunday weekend
    assert cal.is_trading_day(date(2026, 9, 13)) is False
    # Holiday (Republic Day: 2026-01-26)
    assert cal.is_trading_day(date(2026, 1, 26)) is False
    # Intraday hours
    assert cal.is_trading_session(datetime(2026, 9, 14, 10, 0, tzinfo=IST)) is True
    assert cal.is_trading_session(datetime(2026, 9, 14, 8, 30, tzinfo=IST)) is False

# Test 15: Local fixture provider loads offline candles
def test_local_fixture_provider():
    provider = LocalFileMarketDataProvider("tests/fixtures")
    start = datetime(2026, 9, 11, 9, 0, tzinfo=IST)
    end = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    candles = provider.fetch_historical_candles("RELIANCE", Timeframe.M1, start, end)
    assert len(candles) == 5
    assert candles[0].symbol == "RELIANCE"

# Test 16: FYERS provider graceful degradation without credentials
def test_fyers_provider_unconfigured():
    provider = FyersDataProvider(app_id=None, access_token=None)
    assert provider.is_configured is False
    with pytest.raises(ValueError, match="not configured"):
        provider.fetch_historical_candles("SBIN", Timeframe.M1, datetime.now(IST), datetime.now(IST))

# Test 25 & 26: 1-minute aggregation to 5-minute
def test_candle_aggregation_1m_to_5m():
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    provider = LocalFileMarketDataProvider("tests/fixtures")
    start = datetime(2026, 9, 11, 9, 0, tzinfo=IST)
    end = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    one_m_candles = provider.fetch_historical_candles("RELIANCE", Timeframe.M1, start, end)
    
    # 5 one-minute candles should aggregate into 1 five-minute candle
    five_m = val.aggregate_candles(one_m_candles, Timeframe.M5)
    assert len(five_m) == 1
    agg = five_m[0]
    assert agg.open == 2500.0 # Open of first (09:15)
    assert agg.close == 2510.0 # Close of last (09:19)
    assert agg.high == 2518.0 # Highest high (09:18)
    assert agg.low == 2495.0 # Lowest low (09:15)
    assert agg.volume == 64000 # Sum of volumes

# Test 12, 13, 14: End-to-end Smoke Test (Ingest -> Validate -> Parquet -> Repository Query)
def test_end_to_end_data_pipeline_smoke_test(tmp_path):
    repo = ParquetDataRepository(str(tmp_path))
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    manager = DataDownloadManager(repo, val)
    provider = LocalFileMarketDataProvider("tests/fixtures")
    
    start = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    end = datetime(2026, 9, 11, 9, 20, tzinfo=IST)
    raw = provider.fetch_historical_candles("RELIANCE", Timeframe.M1, start, end)
    
    # Ingest and save
    provenance = manager.ingest_candles(
        provider_name="local_fixture",
        symbol="RELIANCE",
        timeframe=Timeframe.M1,
        raw_candles=raw,
        start_date=start,
        end_date=end
    )
    assert provenance.total_candles == 5
    
    # Read back from Parquet
    loaded = repo.load_candles("RELIANCE", Timeframe.M1)
    assert len(loaded) == 5
    assert loaded[0].symbol == "RELIANCE"
    assert loaded[0].open == 2500.0