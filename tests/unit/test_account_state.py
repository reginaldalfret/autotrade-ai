import pytest
from mobitrade.domain.account import Account
from mobitrade.domain.enums import AccountState

def test_account_state_machine_and_locks():
    account = Account(model_id="phi", starting_balance=1000.0, target_pct=0.10, loss_limit_pct=0.05)
    assert account.state == AccountState.READY
    assert account.can_place_order() is False
    
    account.start_session()
    assert account.state == AccountState.TRADING
    assert account.can_place_order() is True
    
    account.check_equity_thresholds(1100.0)
    assert account.state == AccountState.TARGET_REACHED
    assert account.can_place_order() is False
    
    account.execute_shutdown_sequence()
    assert account.state == AccountState.LOCKED
    assert account.can_place_order() is False
