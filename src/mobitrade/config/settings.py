from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
from pydantic import BaseModel, Field

class ModelConfig(BaseModel):
    id: str
    display_name: str
    runtime_model_name: str
    provider: str = "ollama"
    enabled: bool = True
    temperature: float = 0.1
    context_length: int = 4096
    parameters: Dict[str, Any] = Field(default_factory=dict)

class RiskConfig(BaseModel):
    daily_target_pct: float = 0.10
    daily_loss_limit_pct: float = 0.05
    max_trades_per_session: int = 20
    max_concurrent_positions: int = 1
    max_position_size_pct: float = 1.0
    require_stop_loss: bool = True
    min_confidence_score: float = 0.50
    allow_overnight: bool = False
    allow_leverage: bool = False

class CostConfig(BaseModel):
    brokerage_pct: float = 0.0003
    brokerage_max_per_order: float = 20.0
    stt_pct: float = 0.00025
    exchange_txn_charge_pct: float = 0.0000345
    gst_pct: float = 0.18
    sebi_turnover_pct: float = 0.000001
    stamp_duty_pct: float = 0.00003
    slippage_pct: float = 0.0005

class AppSettings(BaseModel):
    version: str = "1.0.0"
    environment: str = "development"
    base_dir: str = "/root/projects/AutoTradeAI"
    starting_capital: float = 1000.0
    currency: str = "INR"
    risk: RiskConfig = Field(default_factory=RiskConfig)
    costs: CostConfig = Field(default_factory=CostConfig)

def load_yaml_config(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
