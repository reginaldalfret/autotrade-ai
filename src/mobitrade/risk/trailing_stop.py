from typing import Dict, Optional

class TrailingStopState:
    """
    Deterministic Position-Level Trailing Stop Tracker.
    - Tracks trade peak price.
    - Trailing stop = peak * (1 - trailing_pct).
    - Trailing stop NEVER moves downward.
    - Fully isolated per model and per position.
    """
    def __init__(
        self,
        trade_id: str,
        symbol: str,
        entry_price: float,
        initial_stop_loss: float,
        trailing_stop_pct: float = 0.005,
        activation_threshold_pct: float = 0.0
    ):
        self.trade_id = trade_id
        self.symbol = symbol
        self.entry_price = entry_price
        self.initial_stop_loss = initial_stop_loss
        self.trailing_stop_pct = trailing_stop_pct
        self.activation_threshold_pct = activation_threshold_pct
        
        self.peak_price = entry_price
        self.is_active = False
        self.current_stop = initial_stop_loss

    def update_price(self, current_price: float) -> tuple[bool, float, bool]:
        """
        Updates peak and trailing stop.
        Returns: (is_triggered, current_stop, was_updated)
        """
        was_updated = False

        if not self.is_active:
            if current_price >= self.entry_price * (1.0 + self.activation_threshold_pct):
                self.is_active = True

        if self.is_active:
            if current_price > self.peak_price:
                self.peak_price = current_price
                new_trail = self.peak_price * (1.0 - self.trailing_stop_pct)
                if new_trail > self.current_stop:
                    self.current_stop = new_trail
                    was_updated = True

        is_triggered = current_price <= self.current_stop
        return is_triggered, self.current_stop, was_updated

class TrailingStopEngine:
    """
    Manages isolated trailing stop states for each model account and symbol position.
    Strictly isolated: Model A cannot affect Model B.
    """
    def __init__(self, default_trailing_pct: float = 0.005):
        self.default_trailing_pct = default_trailing_pct
        self._states: Dict[tuple[str, str], TrailingStopState] = {}

    def register_position(
        self,
        model_id: str,
        symbol: str,
        trade_id: str,
        entry_price: float,
        initial_stop_loss: float,
        trailing_pct: Optional[float] = None,
        activation_threshold: float = 0.0
    ):
        pct = trailing_pct if trailing_pct is not None else self.default_trailing_pct
        key = (model_id, symbol)
        self._states[key] = TrailingStopState(
            trade_id=trade_id,
            symbol=symbol,
            entry_price=entry_price,
            initial_stop_loss=initial_stop_loss,
            trailing_stop_pct=pct,
            activation_threshold_pct=activation_threshold
        )

    def get_state(self, model_id: str, symbol: str) -> Optional[TrailingStopState]:
        return self._states.get((model_id, symbol))

    def update_price(self, model_id: str, symbol: str, current_price: float) -> tuple[bool, float]:
        key = (model_id, symbol)
        state = self._states.get(key)
        if not state:
            return False, 0.0

        is_triggered, stop_val, _ = state.update_price(current_price)
        if is_triggered:
            del self._states[key]
        return is_triggered, stop_val

    def clear_model_positions(self, model_id: str):
        keys_to_del = [k for k in self._states if k[0] == model_id]
        for k in keys_to_del:
            del self._states[k]