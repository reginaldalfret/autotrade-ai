from datetime import datetime, date, time
from typing import List, Optional, Set
import zoneinfo

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

class IndianMarketCalendar:
    """
    Dedicated, versioned market calendar for Indian Equities (NSE).
    Distinguishes normal sessions, trading days, weekends, holidays,
    and special sessions (e.g. Muhurat trading).
    Configurable and independent of hard-coded assumptions.
    """
    def __init__(
        self,
        holidays: Optional[Set[date]] = None,
        special_sessions: Optional[dict] = None,
        version: str = "1.0.0"
    ):
        self.version = version
        self.holidays = holidays if holidays is not None else {
            date(2026, 1, 26),  # Republic Day
            date(2026, 3, 10),  # Holi
            date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
            date(2026, 5, 1),   # Maharashtra Day
            date(2026, 8, 15),  # Independence Day
            date(2026, 10, 2),  # Mahatma Gandhi Jayanti
            date(2026, 10, 20), # Dussehra
            date(2026, 11, 8),  # Diwali Laxmi Pujan
            date(2026, 12, 25), # Christmas
        }
        self.special_sessions = special_sessions or {}
        self.session_start = time(9, 15)
        self.session_end = time(15, 30)
        self.intraday_square_off = time(15, 15)

    def is_trading_day(self, dt: date) -> bool:
        if isinstance(dt, datetime):
            dt = dt.date()
        if dt.weekday() >= 5: # Saturday/Sunday
            return dt in self.special_sessions
        if dt in self.holidays:
            return dt in self.special_sessions
        return True

    def is_trading_session(self, dt: datetime) -> bool:
        dt_ist = dt.astimezone(IST) if dt.tzinfo else dt.replace(tzinfo=IST)
        d = dt_ist.date()
        t = dt_ist.time()

        if not self.is_trading_day(d):
            return False

        if d in self.special_sessions:
            start_t, end_t = self.special_sessions[d]
            return start_t <= t < end_t

        return self.session_start <= t < self.session_end