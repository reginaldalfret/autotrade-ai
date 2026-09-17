"""
Candidate Strategy Improvement Generator for AutoTrade AI.
Generates structured candidate parameter proposals based on verified learning observations.
Never rewrites source code or overrides RiskEngine boundaries.
"""

import uuid
from typing import List, Optional
from datetime import datetime

from mobitrade.learning.models import (
    StrategyConfig,
    CandidateStatus,
    LearningObservation,
    WeaknessType,
)


class CandidateGenerator:
    """
    Generates versioned, testable candidate strategy configurations.
    Proposals modify parameters (confidence thresholds, model filtering, entry windows)
    while preserving hard RiskEngine invariants.
    """

    def generate_candidates(
        self,
        active_strategy: StrategyConfig,
        observations: List[LearningObservation],
    ) -> List[StrategyConfig]:
        """
        Generate candidate strategy improvements addressing identified observations.
        """
        if not observations:
            return []

        candidates: List[StrategyConfig] = []
        now_str = datetime.utcnow().isoformat()

        # Group observations by weakness type
        obs_by_type = {}
        for o in observations:
            obs_by_type.setdefault(o.weakness_type, []).append(o)

        # 1. Candidate based on LOW_CONFIDENCE_LOSS: Raise confidence threshold
        if WeaknessType.LOW_CONFIDENCE_LOSS in obs_by_type:
            low_obs = obs_by_type[WeaknessType.LOW_CONFIDENCE_LOSS]
            sample = sum(o.sample_size for o in low_obs)
            new_threshold = min(0.80, max(0.65, active_strategy.min_confidence_threshold + 0.15))
            candidate_id = f"strategy_v{int(active_strategy.version_id.replace('strategy_v', '1')) + len(candidates) + 1}"
            candidates.append(
                StrategyConfig(
                    version_id=candidate_id,
                    parent_version_id=active_strategy.version_id,
                    created_at=now_str,
                    min_confidence_threshold=round(new_threshold, 2),
                    allowed_models=list(active_strategy.allowed_models),
                    model_confidence_thresholds=dict(active_strategy.model_confidence_thresholds),
                    allowed_trading_windows=list(active_strategy.allowed_trading_windows),
                    max_trades_per_model=active_strategy.max_trades_per_model,
                    status=CandidateStatus.PROPOSED,
                    reason=f"Raise minimum entry confidence to {new_threshold:.2f} to mitigate {len(low_obs)} low-confidence loss clusters.",
                    supporting_observations=[o.observation_id for o in low_obs],
                    sample_size=sample,
                )
            )

        # 2. Candidate based on MODEL_SPECIFIC_UNDERPERFORMANCE: Model selective filtering
        if WeaknessType.MODEL_SPECIFIC_UNDERPERFORMANCE in obs_by_type:
            model_obs = obs_by_type[WeaknessType.MODEL_SPECIFIC_UNDERPERFORMANCE]
            underperforming_models = {o.model_id for o in model_obs if o.model_id}
            if underperforming_models:
                remaining_models = [m for m in active_strategy.allowed_models if m not in underperforming_models]
                if remaining_models:  # Keep at least some models active
                    sample = sum(o.sample_size for o in model_obs)
                    candidate_id = f"strategy_v{int(active_strategy.version_id.replace('strategy_v', '1')) + len(candidates) + 1}"
                    candidates.append(
                        StrategyConfig(
                            version_id=candidate_id,
                            parent_version_id=active_strategy.version_id,
                            created_at=now_str,
                            min_confidence_threshold=active_strategy.min_confidence_threshold,
                            allowed_models=remaining_models,
                            model_confidence_thresholds=dict(active_strategy.model_confidence_thresholds),
                            allowed_trading_windows=list(active_strategy.allowed_trading_windows),
                            max_trades_per_model=active_strategy.max_trades_per_model,
                            status=CandidateStatus.PROPOSED,
                            reason=f"Exclude chronically underperforming models ({', '.join(sorted(underperforming_models))}) based on empirical loss rates.",
                            supporting_observations=[o.observation_id for o in model_obs],
                            sample_size=sample,
                        )
                    )

        # 3. Candidate based on TIME_OF_DAY_DECAY: Adjust trading windows
        if WeaknessType.TIME_OF_DAY_DECAY in obs_by_type:
            tod_obs = obs_by_type[WeaknessType.TIME_OF_DAY_DECAY]
            sample = sum(o.sample_size for o in tod_obs)
            candidate_id = f"strategy_v{int(active_strategy.version_id.replace('strategy_v', '1')) + len(candidates) + 1}"
            candidates.append(
                StrategyConfig(
                    version_id=candidate_id,
                    parent_version_id=active_strategy.version_id,
                    created_at=now_str,
                    min_confidence_threshold=active_strategy.min_confidence_threshold,
                    allowed_models=list(active_strategy.allowed_models),
                    model_confidence_thresholds=dict(active_strategy.model_confidence_thresholds),
                    allowed_trading_windows=[
                        {"start": "09:30", "end": "11:30"},
                        {"start": "13:30", "end": "15:00"},
                    ],
                    max_trades_per_model=active_strategy.max_trades_per_model,
                    status=CandidateStatus.PROPOSED,
                    reason="Bypass midday chop window (11:30–13:30 IST) to curtail consolidation drawdowns.",
                    supporting_observations=[o.observation_id for o in tod_obs],
                    sample_size=sample,
                )
            )

        return candidates
