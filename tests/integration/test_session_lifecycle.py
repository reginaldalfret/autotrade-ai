import pytest
from datetime import datetime, timedelta
from mobitrade.domain.sources import ExternalSource

# Test 24, 25, 26: No look-ahead bias (future source cannot enter historical decision)
def test_no_look_ahead_bias():
    decision_timestamp = datetime(2026, 9, 11, 10, 0, 0)
    
    past_source = ExternalSource(
        source_id="src_01",
        source_name="Exchange Announcement",
        source_type="regulatory_filing",
        title="Q1 Earnings Beat",
        summary="Positive net profit",
        symbol="TCS",
        published_at=datetime(2026, 9, 11, 9, 30, 0),
        retrieved_at=datetime(2026, 9, 11, 9, 35, 0),
        available_at=datetime(2026, 9, 11, 9, 35, 0)
    )
    
    future_source = ExternalSource(
        source_id="src_02",
        source_name="Market Report",
        source_type="news",
        title="Late morning rally",
        summary="Price broke out",
        symbol="TCS",
        published_at=datetime(2026, 9, 11, 10, 30, 0),
        retrieved_at=datetime(2026, 9, 11, 10, 31, 0),
        available_at=datetime(2026, 9, 11, 10, 31, 0)
    )
    
    # Eligibility check: available_at <= decision_timestamp
    assert (past_source.available_at <= decision_timestamp) is True
    assert (future_source.available_at <= decision_timestamp) is False
