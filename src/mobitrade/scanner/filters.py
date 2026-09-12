from datetime import datetime
from typing import Tuple, Optional, List
from mobitrade.domain.data_models import Instrument, HistoricalCandle, DataStatus
from mobitrade.domain.feature_models import TechnicalFeatures
from mobitrade.domain.scanner_models import RejectionReason, ScannerConfig
from mobitrade.data.calendar import IndianMarketCalendar

class EligibilityFilter:
    """
    Validates instrument eligibility:
    - Exchange must be NSE
    - Segment must be EQUITY
    - Trading status must be ACTIVE
    - Instrument validity period (valid_from <= decision_timestamp <= valid_to)
    - Decision timestamp must fall within active NSE trading session (unless allow_outside_session=True)
    """
    def __init__(self, calendar: Optional[IndianMarketCalendar] = None):
        self.calendar = calendar or IndianMarketCalendar()

    def filter(
        self,
        instrument: Instrument,
        decision_timestamp: datetime,
        allow_outside_session: bool = False
    ) -> Tuple[bool, Optional[RejectionReason]]:
        if instrument.exchange != "NSE":
            return False, RejectionReason.NOT_ELIGIBLE
        if instrument.segment != "EQUITY":
            return False, RejectionReason.NOT_ELIGIBLE
        if instrument.trading_status != "ACTIVE":
            return False, RejectionReason.INVALID_INSTRUMENT

        dec_date = decision_timestamp.date()
        if instrument.valid_from and dec_date < instrument.valid_from:
            return False, RejectionReason.INVALID_INSTRUMENT
        if instrument.valid_to and dec_date > instrument.valid_to:
            return False, RejectionReason.INVALID_INSTRUMENT

        if not allow_outside_session and not self.calendar.is_trading_session(decision_timestamp):
            return False, RejectionReason.OUTSIDE_SESSION

        return True, None

class PriceFilter:
    """
    Validates price boundaries:
    - Must be positive and non-zero
    - Must fall between config.min_price and config.max_price
    """
    def filter(
        self,
        price: float,
        config: ScannerConfig
    ) -> Tuple[bool, Optional[RejectionReason]]:
        if price <= 0 or price != price: # NaN check
            return False, RejectionReason.INVALID_PRICE
        if price < config.min_price or price > config.max_price:
            return False, RejectionReason.INVALID_PRICE
        return True, None

class LiquidityFilter:
    """
    Validates liquidity thresholds:
    - Current bar volume >= config.min_volume
    - Relative volume >= config.relative_volume_threshold (when configured/available)
    """
    def filter(
        self,
        volume: float,
        relative_volume: Optional[float],
        config: ScannerConfig
    ) -> Tuple[bool, Optional[RejectionReason]]:
        if volume < config.min_volume:
            return False, RejectionReason.ILLIQUID
        if relative_volume is not None and relative_volume < config.relative_volume_threshold:
            return False, RejectionReason.ILLIQUID
        return True, None

class DataQualityFilter:
    """
    Validates technical data quality and historical sufficiency:
    - Sufficient history bars
    - Status not ANOMALY
    - Critical features present and non-null
    - Feature temporal availability ordering
    """
    def filter(
        self,
        candles: List[HistoricalCandle],
        features: Optional[TechnicalFeatures],
        config: ScannerConfig
    ) -> Tuple[bool, Optional[RejectionReason]]:
        if len(candles) < config.min_history_bars:
            return False, RejectionReason.INSUFFICIENT_HISTORY

        if not features:
            return False, RejectionReason.MISSING_FEATURE

        if features.data_status == DataStatus.ANOMALY:
            return False, RejectionReason.DATA_ANOMALY

        # Check critical indicator presence
        if features.price <= 0:
            return False, RejectionReason.INVALID_PRICE

        # Check temporal availability
        if features.feature_available_at < features.candle_timestamp:
            return False, RejectionReason.DATA_ANOMALY

        return True, None
