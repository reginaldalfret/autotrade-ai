from enum import Enum

class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

class AccountState(str, Enum):
    READY = "READY"
    TRADING = "TRADING"
    TARGET_REACHED = "TARGET_REACHED"
    DAILY_STOP_TRIGGERED = "DAILY_STOP_TRIGGERED"
    MARKET_CLOSED = "MARKET_CLOSED"
    SESSION_COMPLETE = "SESSION_COMPLETE"
    LOCKED = "LOCKED"

class RiskDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class MarketType(str, Enum):
    INDIAN_EQUITY = "INDIAN_EQUITY"
    BITCOIN_SPOT = "BITCOIN_SPOT"

class ExitReason(str, Enum):
    TARGET = "TARGET"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    DAILY_TARGET = "DAILY_TARGET"
    DAILY_STOP = "DAILY_STOP"
    MARKET_CLOSE = "MARKET_CLOSE"
    MANUAL_SIMULATION_EXIT = "MANUAL_SIMULATION_EXIT"
    RISK_REJECTION = "RISK_REJECTION"

