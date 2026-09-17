// TypeScript type definitions for AutoTrade AI Local Monitoring Dashboard

export interface PipelineStep {
  name: string;
  active: boolean;
}

export interface RuntimeStatus {
  current_model: string;
  current_phase: string;
  current_operation: string;
  session_id: string | null;
  symbol: string | null;
  started_at: string | null;
  elapsed_seconds: number;
  is_active: boolean;
  pipeline_steps: PipelineStep[];
}

export interface ActivityEvent {
  timestamp: string;
  iso_time: string;
  model_id: string | null;
  phase: string;
  message: string;
  level: "info" | "warning" | "error" | "success";
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  version: string;
  environment?: {
    python_version: string;
    platform: string;
    wsl2: boolean;
  };
  ollama?: {
    reachable: boolean;
    models_available: number;
  };
  database?: {
    reachable: boolean;
    total_trades: number;
    total_orders: number;
  };
}

export interface ModelTournamentRecord {
  model_id: string;
  name: string;
  family: string;
  params: string;
  quantization: string;
  role: string;
  state: "IDLE" | "ACTIVE" | "COMPLETED" | "UNLOADED";
  trades: number;
  win_rate: number;
  net_pnl: number;
  drawdown: number;
  consecutive_losses: number;
}

export interface VirtualAccount {
  model_id: string;
  initial_capital: number;
  current_cash: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_equity: number;
  return_pct: number;
}

export interface PortfolioStatus {
  total_initial_capital: number;
  total_current_cash: number;
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  total_portfolio_value: number;
  overall_return_pct: number;
  open_positions_count: number;
  accounts: Record<string, VirtualAccount>;
}

export interface Position {
  position_id: string;
  model_id: string;
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price?: number;
  stop_loss?: number;
  take_profit?: number;
  unrealized_pnl?: number;
  status: string;
  entry_time: string;
}

export interface Trade {
  trade_id: string;
  model_id: string;
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  exit_price?: number;
  pnl?: number;
  pnl_pct?: number;
  status: string;
  entry_time: string;
  exit_time?: string;
  exit_reason?: string;
}

export interface RiskStatus {
  session_status: string;
  daily_loss_limit_pct: number;
  daily_profit_target_pct: number;
  max_trades_per_day: number;
  square_off_time_ist: string;
  session_start_ist: string;
  session_end_ist: string;
  overnight_holding_allowed: boolean;
  leverage_allowed: boolean;
  live_broker_connected: boolean;
  risk_authority: string;
}

export interface AuditVerify {
  valid: boolean;
  verified: boolean;
  total_events: number;
  first_sequence?: number;
  last_sequence?: number;
  hash_chain_valid?: boolean;
  message?: string;
}

export interface ReportItem {
  report_id: string;
  filename: string;
  generated_at: string;
  sha256_hash: string;
  size_bytes: number;
}

export interface LearningStep {
  name: string;
  status: "completed" | "current" | "pending";
}

export interface LearningStatus {
  version: string;
  status: string;
  last_learning_at: string | null;
  active_profile_version: string;
  observations_count: number;
  candidates_evaluated: number;
  rule_safety_status: string;
  flow_steps: LearningStep[];
}
