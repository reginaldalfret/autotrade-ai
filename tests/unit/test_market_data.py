import pytest
from datetime import datetime, date, time, timezone
import zoneinfo
from unittest.mock import MagicMock
import requests
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

UTC = timezone.utc

# 1. Existing Phase 2 Tests (Preserved)
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

def test_invalid_ohlc_rejection():
    with pytest.raises(ValueError):
        HistoricalCandle(
            symbol="INFY",
            timeframe=Timeframe.M1,
            timestamp=datetime(2026, 9, 11, 9, 15, tzinfo=IST),
            open=1500.0,
            high=1490.0,
            low=1480.0,
            close=1495.0,
            volume=1000.0
        )

def test_duplicate_detection_and_cleaning():
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    ts = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    
    c1 = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=ts, open=100, high=110, low=95, close=105, volume=10)
    c2 = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=ts, open=100, high=110, low=95, close=105, volume=10)
    
    cleaned, stats = val.validate_and_clean_candles([c1, c2])
    assert len(cleaned) == 1
    assert stats["duplicates"] == 1

def test_market_calendar_rules():
    cal = IndianMarketCalendar()
    assert cal.is_trading_day(date(2026, 9, 14)) is True
    assert cal.is_trading_day(date(2026, 9, 13)) is False
    assert cal.is_trading_day(date(2026, 1, 26)) is False
    assert cal.is_trading_session(datetime(2026, 9, 14, 10, 0, tzinfo=IST)) is True
    assert cal.is_trading_session(datetime(2026, 9, 14, 8, 30, tzinfo=IST)) is False

def test_local_fixture_provider():
    provider = LocalFileMarketDataProvider("tests/fixtures")
    start = datetime(2026, 9, 11, 9, 0, tzinfo=IST)
    end = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    candles = provider.fetch_historical_candles("RELIANCE", Timeframe.M1, start, end)
    assert len(candles) == 5
    assert candles[0].symbol == "RELIANCE"

def test_fyers_provider_unconfigured():
    provider = FyersDataProvider(app_id=None, access_token=None)
    assert provider.is_configured is False
    with pytest.raises(ValueError, match="not configured"):
        provider.fetch_historical_candles("SBIN", Timeframe.M1, datetime.now(IST), datetime.now(IST))

def test_candle_aggregation_1m_to_5m():
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    provider = LocalFileMarketDataProvider("tests/fixtures")
    start = datetime(2026, 9, 11, 9, 0, tzinfo=IST)
    end = datetime(2026, 9, 11, 10, 0, tzinfo=IST)
    one_m_candles = provider.fetch_historical_candles("RELIANCE", Timeframe.M1, start, end)
    
    five_m = val.aggregate_candles(one_m_candles, Timeframe.M5)
    assert len(five_m) == 1
    agg = five_m[0]
    assert agg.status == DataStatus.VALID
    assert agg.open == 2500.0
    assert agg.close == 2510.0
    assert agg.high == 2518.0
    assert agg.low == 2495.0
    assert agg.volume == 64000

def test_end_to_end_data_pipeline_smoke_test(tmp_path):
    repo = ParquetDataRepository(str(tmp_path))
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    manager = DataDownloadManager(repo, val)
    provider = LocalFileMarketDataProvider("tests/fixtures")
    
    start = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    end = datetime(2026, 9, 11, 9, 20, tzinfo=IST)
    raw = provider.fetch_historical_candles("RELIANCE", Timeframe.M1, start, end)
    
    provenance = manager.ingest_candles(
        provider_name="local_fixture",
        symbol="RELIANCE",
        timeframe=Timeframe.M1,
        raw_candles=raw,
        start_date=start,
        end_date=end
    )
    assert provenance.total_candles == 5
    assert len(provenance.checksum_sha256) == 64
    
    loaded = repo.load_candles("RELIANCE", Timeframe.M1)
    assert len(loaded) == 5
    assert loaded[0].symbol == "RELIANCE"
    assert loaded[0].open == 2500.0

# 2. Phase 2.1 Hardening Tests: FYERS Mocking & Errors
def test_fyers_mock_successful_response():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "s": "ok",
        "candles": [
            [1726026300, 2500.0, 2510.0, 2495.0, 2505.0, 15000]
        ]
    }
    mock_session.get.return_value = mock_resp

    provider = FyersDataProvider(app_id="test_app", access_token="test_tok", session=mock_session)
    candles = provider.fetch_historical_candles("RELIANCE", Timeframe.M1, datetime(2026, 9, 11), datetime(2026, 9, 11))
    assert len(candles) == 1
    assert candles[0].close == 2505.0
    assert candles[0].timestamp.tzinfo is not None

def test_fyers_mock_http_failure():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_session.get.return_value = mock_resp

    provider = FyersDataProvider(app_id="test_app", access_token="test_tok", session=mock_session)
    with pytest.raises(RuntimeError, match="FYERS API error 500"):
        provider.fetch_historical_candles("RELIANCE", Timeframe.M1, datetime(2026, 9, 11), datetime(2026, 9, 11))

def test_fyers_mock_timeout():
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.exceptions.Timeout("Connection timed out")

    provider = FyersDataProvider(app_id="test_app", access_token="test_tok", session=mock_session)
    with pytest.raises(TimeoutError, match="timed out"):
        provider.fetch_historical_candles("RELIANCE", Timeframe.M1, datetime(2026, 9, 11), datetime(2026, 9, 11))

def test_fyers_mock_malformed_response():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"s": "ok", "candles": "not_a_list"}
    mock_session.get.return_value = mock_resp

    provider = FyersDataProvider(app_id="test_app", access_token="test_tok", session=mock_session)
    with pytest.raises(ValueError, match="not a list"):
        provider.fetch_historical_candles("RELIANCE", Timeframe.M1, datetime(2026, 9, 11), datetime(2026, 9, 11))

# 3. Real SHA-256 Checksum Tests
def test_real_sha256_checksum_identity():
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    ts = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    c1 = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=ts, open=100, high=110, low=95, close=105, volume=10)
    
    hash1 = val.compute_dataset_sha256([c1])
    hash2 = val.compute_dataset_sha256([c1])
    assert hash1 == hash2
    assert len(hash1) == 64

def test_real_sha256_checksum_divergence():
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    ts = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    c1 = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=ts, open=100, high=110, low=95, close=105, volume=10)
    c2 = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=ts, open=100, high=110, low=95, close=106, volume=10) # close changed
    
    hash1 = val.compute_dataset_sha256([c1])
    hash2 = val.compute_dataset_sha256([c2])
    assert hash1 != hash2

# 4. Missing Interval & Unexpected Interval Detection
def test_missing_and_unexpected_interval_detection():
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    
    # Normal candle at 09:15
    c1 = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=datetime(2026, 9, 11, 9, 15, tzinfo=IST), open=100, high=105, low=98, close=102, volume=10)
    # Weekend candle on Sunday 09:15 (unexpected)
    c_weekend = HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=datetime(2026, 9, 13, 9, 15, tzinfo=IST), open=100, high=105, low=98, close=102, volume=10)
    
    # Expected range has 5 minutes: 09:15 to 09:19
    start = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    end = datetime(2026, 9, 11, 9, 19, tzinfo=IST)
    
    cleaned, stats = val.validate_and_clean_candles([c1, c_weekend], expected_range_start=start, expected_range_end=end)
    assert stats["unexpected"] == 1
    assert stats["anomalies"] == 1
    assert stats["missing_intervals"] == 4 # Expected 5, received 1 valid

# 5. Incomplete Aggregation Tests (5m and 15m)
def test_incomplete_5m_aggregation_flagged():
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    
    # Only 3 candles for the 5-minute interval (09:15 to 09:17)
    candles = [
        HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=datetime(2026, 9, 11, 9, 15, tzinfo=IST), open=100, high=105, low=98, close=102, volume=10),
        HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=datetime(2026, 9, 11, 9, 16, tzinfo=IST), open=102, high=106, low=101, close=104, volume=10),
        HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=datetime(2026, 9, 11, 9, 17, tzinfo=IST), open=104, high=107, low=103, close=105, volume=10),
    ]
    
    agg = val.aggregate_candles(candles, Timeframe.M5)
    assert len(agg) == 1
    assert agg[0].status == DataStatus.INCOMPLETE # Flagged as incomplete

def test_incomplete_15m_aggregation_flagged():
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    
    # Only 5 candles for a 15-minute interval
    candles = [
        HistoricalCandle(symbol="TCS", timeframe=Timeframe.M1, timestamp=datetime(2026, 9, 11, 9, 15 + i, tzinfo=IST), open=100, high=105, low=98, close=102, volume=10)
        for i in range(5)
    ]
    agg = val.aggregate_candles(candles, Timeframe.M15)
    assert len(agg) == 1
    assert agg[0].status == DataStatus.INCOMPLETE

# 6. Timezone Equivalence (UTC vs IST Query Range)
def test_utc_ist_query_range_equivalence(tmp_path):
    repo = ParquetDataRepository(str(tmp_path))
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    manager = DataDownloadManager(repo, val)
    provider = LocalFileMarketDataProvider("tests/fixtures")
    
    start_ist = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    end_ist = datetime(2026, 9, 11, 9, 19, tzinfo=IST)
    raw = provider.fetch_historical_candles("RELIANCE", Timeframe.M1, start_ist, end_ist)
    manager.ingest_candles("local_fixture", "RELIANCE", Timeframe.M1, raw, start_ist, end_ist)
    
    # Query using IST boundaries
    res_ist = repo.load_candles("RELIANCE", Timeframe.M1, start_time=start_ist, end_time=end_ist)
    
    # Equivalent UTC boundaries: 09:15 IST is 03:45 UTC
    start_utc = start_ist.astimezone(UTC)
    end_utc = end_ist.astimezone(UTC)
    res_utc = repo.load_candles("RELIANCE", Timeframe.M1, start_time=start_utc, end_time=end_utc)
    
    assert len(res_ist) == len(res_utc)
    assert [c.timestamp for c in res_ist] == [c.timestamp for c in res_utc]

# 7. Download Chunking & Overlap Deduplication
def test_chunking_and_overlap_deduplication(tmp_path):
    repo = ParquetDataRepository(str(tmp_path))
    cal = IndianMarketCalendar()
    val = DataQualityValidator(cal)
    manager = DataDownloadManager(repo, val)
    
    chunks = manager.generate_chunks(
        datetime(2026, 9, 1, tzinfo=IST), datetime(2026, 9, 30, tzinfo=IST), chunk_days=10
    )
    assert len(chunks) >= 3
    
    # Simulate overlapping ingestion
    ts1 = datetime(2026, 9, 11, 9, 15, tzinfo=IST)
    ts2 = datetime(2026, 9, 11, 9, 16, tzinfo=IST)
    c1 = HistoricalCandle(symbol="INFY", timeframe=Timeframe.M1, timestamp=ts1, open=100, high=105, low=98, close=102, volume=10)
    c2 = HistoricalCandle(symbol="INFY", timeframe=Timeframe.M1, timestamp=ts2, open=102, high=106, low=100, close=104, volume=10)
    
    # Chunk 1 saves [c1, c2]
    manager.ingest_candles("chunker", "INFY", Timeframe.M1, [c1, c2], ts1, ts2)
    # Chunk 2 overlaps and re-saves [c2]
    manager.ingest_candles("chunker", "INFY", Timeframe.M1, [c2], ts2, ts2)
    
    loaded = repo.load_candles("INFY", Timeframe.M1)
    assert len(loaded) == 2 # Deduplicated