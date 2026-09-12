from datetime import datetime, date
from typing import List, Optional, Dict, Any
from mobitrade.domain.data_models import Instrument

class EquityUniverseProvider:
    """
    Decoupled provider for the NSE equity trading universe.
    Supports arbitrary symbol universes and point-in-time instrument validity filtering.
    """
    def __init__(
        self,
        instruments: Optional[List[Instrument]] = None,
        universe_version: str = "1.0.0"
    ):
        self.universe_version = universe_version
        self._instruments: Dict[str, Instrument] = {}
        if instruments:
            for inst in instruments:
                self._instruments[inst.symbol] = inst

    def register_instrument(self, instrument: Instrument) -> None:
        self._instruments[instrument.symbol] = instrument

    def register_symbols(
        self,
        symbols: List[str],
        exchange: str = "NSE",
        segment: str = "EQUITY",
        trading_status: str = "ACTIVE",
        data_source: str = "LOCAL"
    ) -> None:
        """
        Convenience helper to register a list of NSE equity symbols.
        """
        now = datetime.now()
        for sym in symbols:
            inst = Instrument(
                symbol=sym,
                exchange=exchange,
                segment=segment,
                security_name=f"{sym} Equity",
                trading_status=trading_status,
                data_source=data_source,
                ingested_at=now,
                source_version="1.0"
            )
            self._instruments[sym] = inst

    def get_universe_as_of(
        self,
        decision_timestamp: datetime,
        exchange: str = "NSE"
    ) -> List[Instrument]:
        """
        Point-in-time universe query.
        Returns only instruments that were active and valid at decision_timestamp.
        """
        dec_date = decision_timestamp.date() if isinstance(decision_timestamp, datetime) else decision_timestamp
        eligible = []
        for inst in self._instruments.values():
            if inst.exchange != exchange:
                continue
            if inst.segment != "EQUITY":
                continue
            if inst.trading_status != "ACTIVE":
                continue
            # Point-in-time validity bounds
            if inst.valid_from and dec_date < inst.valid_from:
                continue
            if inst.valid_to and dec_date > inst.valid_to:
                continue
            eligible.append(inst)
        return eligible

    def list_all_instruments(self) -> List[Instrument]:
        return list(self._instruments.values())
