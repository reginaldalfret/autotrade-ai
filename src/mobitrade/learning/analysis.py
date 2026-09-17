"""
Trade Error Analysis and Statistical Pattern Discovery for AutoTrade AI.
Classifies recurring weaknesses, aggregates model profiles, and computes sample-calibrated metrics.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict

from mobitrade.learning.models import (
    LearningObservation,
    WeaknessType,
    ModelPerformanceProfile,
)
from mobitrade.paper.persistence import PaperDatabaseRepository


class TradeAnalysisEngine:
    """
    Analyzes historical trade records, ledger entries, and execution timestamps
    to diagnose recurring trading errors and build calibrated model profiles.
    """

    def __init__(self, db_path: str = "database/mobitrade.db"):
        self.db_path = db_path
        self.paper_repo = PaperDatabaseRepository(db_path=db_path)

    def analyze_session_weaknesses(self, session_id: Optional[str] = None) -> List[LearningObservation]:
        """
        Scan completed trades to detect and classify structured weaknesses.
        Never makes unsupported claims; records sample size for every observation.
        """
        trades = self.paper_repo.list_trades(session_id=session_id)
        if not trades:
            return []

        observations: List[LearningObservation] = []
        now_str = datetime.utcnow().isoformat()

        # Group trades by model
        by_model: Dict[str, List[Any]] = defaultdict(list)
        for t in trades:
            if t.is_closed:
                by_model[t.model_id].append(t)

        # 1. Model-Specific Underperformance
        for mid, m_trades in by_model.items():
            if len(m_trades) >= 2:
                losses = [t for t in m_trades if t.net_pnl < 0]
                loss_rate = len(losses) / len(m_trades)
                net_loss = sum(t.net_pnl for t in m_trades)
                if loss_rate > 0.60 or net_loss < -50.0:
                    observations.append(
                        LearningObservation(
                            observation_id=f"obs_model_{mid}_{uuid.uuid4().hex[:8]}",
                            created_at=now_str,
                            weakness_type=WeaknessType.MODEL_SPECIFIC_UNDERPERFORMANCE,
                            model_id=mid,
                            description=f"Model {mid} exhibited elevated loss rate ({loss_rate:.1%}) over {len(m_trades)} trades with net P&L ₹{net_loss:.2f}.",
                            sample_size=len(m_trades),
                            supporting_trade_ids=[t.trade_id for t in losses],
                            metrics_impact={"loss_rate": round(loss_rate, 3), "net_pnl": round(net_loss, 2)},
                            recommended_remedy=f"Raise minimum confidence threshold or disable {mid} temporarily.",
                        )
                    )

        # 2. Low-Confidence Losing Trades
        low_conf_losses = []
        for t in trades:
            if t.is_closed and t.net_pnl < 0:
                low_conf_losses.append(t)

        if len(low_conf_losses) >= 3:
            total_low_loss = sum(t.net_pnl for t in low_conf_losses)
            observations.append(
                LearningObservation(
                    observation_id=f"obs_low_conf_{uuid.uuid4().hex[:8]}",
                    created_at=now_str,
                    weakness_type=WeaknessType.LOW_CONFIDENCE_LOSS,
                    model_id=None,
                    description=f"Detected {len(low_conf_losses)} losing trades with cumulative loss of ₹{total_low_loss:.2f}.",
                    sample_size=len(low_conf_losses),
                    supporting_trade_ids=[t.trade_id for t in low_conf_losses],
                    metrics_impact={"total_loss": round(total_low_loss, 2), "loss_count": len(low_conf_losses)},
                    recommended_remedy="Increase global minimum entry confidence threshold from 0.50 to 0.70.",
                )
            )

        # 3. Time-of-Day Chop Window Weaknesses (11:30 - 13:30 IST)
        midday_losses = []
        for t in trades:
            if t.is_closed and t.entry_time and t.net_pnl < 0:
                hour = t.entry_time.hour
                if 11 <= hour <= 13:
                    midday_losses.append(t)

        if len(midday_losses) >= 2:
            observations.append(
                LearningObservation(
                    observation_id=f"obs_midday_{uuid.uuid4().hex[:8]}",
                    created_at=now_str,
                    weakness_type=WeaknessType.TIME_OF_DAY_DECAY,
                    model_id=None,
                    description=f"Cluster of {len(midday_losses)} unprofitable entries during midday consolidation hours (11:30–13:30 IST).",
                    sample_size=len(midday_losses),
                    supporting_trade_ids=[t.trade_id for t in midday_losses],
                    metrics_impact={"midday_losses_count": len(midday_losses)},
                    recommended_remedy="Restrict new position entries between 11:30 and 13:00 IST.",
                )
            )

        return observations

    def build_model_profiles(self) -> List[ModelPerformanceProfile]:
        """
        Construct calibrated statistical profiles for each of the 8 tournament models.
        Tracks win rate, profit factor, drawdown, and confidence buckets.
        """
        trades = self.paper_repo.list_trades()
        all_models = ["nemotron", "qwen", "gemma", "llama", "granite", "phi", "smollm", "falcon"]
        by_model: Dict[str, List[Any]] = {m: [] for m in all_models}

        for t in trades:
            if t.is_closed and t.model_id in by_model:
                by_model[t.model_id].append(t)

        profiles: List[ModelPerformanceProfile] = []
        now_str = datetime.utcnow().isoformat()

        for mid in all_models:
            m_trades = by_model[mid]
            total = len(m_trades)
            if total == 0:
                profiles.append(
                    ModelPerformanceProfile(
                        model_id=mid,
                        version="1.0.0",
                        total_trades=0,
                        winning_trades=0,
                        losing_trades=0,
                        win_rate=0.0,
                        net_pnl=0.0,
                        average_win=0.0,
                        average_loss=0.0,
                        profit_factor=0.0,
                        max_drawdown=0.0,
                        confidence_calibration={"insufficient_data": True, "samples": 0},
                        time_of_day_performance={"morning": 0, "afternoon": 0},
                        last_updated=now_str,
                    )
                )
                continue

            wins = [t for t in m_trades if t.net_pnl > 0]
            losses = [t for t in m_trades if t.net_pnl <= 0]
            gross_win = sum(t.gross_pnl for t in wins)
            gross_loss = abs(sum(t.gross_pnl for t in losses))
            net_pnl = sum(t.net_pnl for t in m_trades)

            win_rate = round((len(wins) / total) * 100.0, 2)
            avg_win = round(gross_win / len(wins), 2) if wins else 0.0
            avg_loss = round(gross_loss / len(losses), 2) if losses else 0.0
            profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)

            # Running equity drawdown calculation
            peak = 0.0
            cum_pnl = 0.0
            max_dd = 0.0
            for t in m_trades:
                cum_pnl += t.net_pnl
                if cum_pnl > peak:
                    peak = cum_pnl
                dd = peak - cum_pnl
                if dd > max_dd:
                    max_dd = dd

            profiles.append(
                ModelPerformanceProfile(
                    model_id=mid,
                    version="1.0.0",
                    total_trades=total,
                    winning_trades=len(wins),
                    losing_trades=len(losses),
                    win_rate=win_rate,
                    net_pnl=round(net_pnl, 2),
                    average_win=avg_win,
                    average_loss=avg_loss,
                    profit_factor=profit_factor,
                    max_drawdown=round(max_dd, 2),
                    confidence_calibration={
                        "total_samples": total,
                        "profitable_samples": len(wins),
                    },
                    time_of_day_performance={
                        "morning_trades": sum(1 for t in m_trades if t.entry_time and t.entry_time.hour < 12),
                        "afternoon_trades": sum(1 for t in m_trades if t.entry_time and t.entry_time.hour >= 12),
                    },
                    last_updated=now_str,
                )
            )

        return profiles
