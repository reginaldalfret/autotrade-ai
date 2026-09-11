from datetime import datetime, date, time
from typing import List, Optional
import zoneinfo

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

class IndianMarketCalendar:
    """
    Dedicated market calendar for Indian Equities (NSE).
    Distinguishes trading days, weekends, official exchange holidays,
    and special sessions (e.g. Muhurat trading).
    """
    def __init__(self, holidays: Optional[List[date]] = None, special_sessions: Optional[dict] = None):
        # Configurable list of official NSE holidays
        self.holidays = set(holidays or [
            date(2026, 1, 26),  # Republic Day
            date(2026, 3, 10),  # Holi
            date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
            date(2026, 5, 1),   # Maharashtra Day
            date(2026, 8, 15),  # Independence Day
            date(2026, 10, 2),  # Mahatma Gandhi Jayanti
            date(2026, 10, 20), # Dussehra
            date(2026, 11, 8),  # Diwali Laxmi Pujan
            date(2026, 12, 25), # Christmas
        ])
        self.special_sessions = special_sessions or {} # e.g. {date(2026, 11, 8): (time(18, 15), time(19, 15))}
        self.session_start = time(9, 15)
        self.session_end = time(15, 30)
        self.intraday_square_off = time(15, 15)

    def is_trading_day(self, dt: date) -> bool:
        if isinstance(dt, datetime):
            dt = dt.date()
        # Weekends
        if dt.weekday() >= 5: # Saturday or Sunday
            # Special weekend trading session check
            return dt in self.special_sessions
        # Holidays
        if dt in self.holidays:
            return dt in self.special_sessions
        return True

    def is_trading_session(self, dt: datetime) -> bool:
        """
        Validates if a specific timezone-aware timestamp falls inside NSE trading hours.
        """
        dt_ist = dt.astimezone(IST) if dt.tzinfo else dt.replace(tzinfo=IST)
        d = dt_ist.date()
        t = dt_ist.time()

        if not self.is_trading_day(d):
            return False

        if d in self.special_sessions:
            start_t, end_t = self.special_sessions[d]
            return start_t <= t < end_t

        return self.session_start <= t < self.session_end