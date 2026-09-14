"""
LLM Performance Profile module for AutoTrade AI.
Defines runtime configurations, hardware resource allocations, and benchmark results
for local LLM candidates.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Union
import yaml


@dataclass
class LLMPerformanceProfile:
    """
    Performance and execution profile for a local LLM candidate.
    Governs runtime parameters, VRAM allocation, and tracks benchmarking results.
    """
    model_id: str
    runtime: str = "ollama"
    context_size: int = 2048
    gpu_layers: int = -1
    flash_attention: bool = True
    kv_cache_type: str = "f16"
    threads: int = 4
    batch_size: int = 512
    recommended_configuration: Dict[str, Any] = field(default_factory=dict)
    benchmark_result: Dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert performance profile to a plain dictionary representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMPerformanceProfile":
        """
        Create a performance profile from dictionary data with safe defaults.
        Handles missing or corrupted keys gracefully.
        """
        return cls(
            model_id=str(data.get("model_id", "")),
            runtime=str(data.get("runtime", "ollama")),
            context_size=int(data.get("context_size", 2048)),
            gpu_layers=int(data.get("gpu_layers", -1)),
            flash_attention=bool(data.get("flash_attention", True)),
            kv_cache_type=str(data.get("kv_cache_type", "f16")),
            threads=int(data.get("threads", 4)),
            batch_size=int(data.get("batch_size", 512)),
            recommended_configuration=dict(data.get("recommended_configuration") or {}),
            benchmark_result=dict(data.get("benchmark_result") or {}),
            updated_at=data.get("updated_at"),
        )


def _resolve_config_dir(config_dir: Union[str, Path] = "configs/llm-performance") -> Path:
    """
    Locates the configuration directory using candidate search paths.
    """
    p = Path(config_dir)
    if p.is_dir():
        return p.resolve()

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    candidates = [
        p,
        repo_root / config_dir,
        Path("D:/Trading LLM/MobiTradeAI") / config_dir,
        Path("/root/projects/AutoTradeAI") / config_dir,
    ]
    for cand in candidates:
        if cand.is_dir():
            return cand.resolve()

    # Fallback to repo_root / config_dir if repo_root exists, else p
    return (repo_root / config_dir).resolve() if repo_root.exists() else p.resolve()


def load_performance_profile(
    model_id: str,
    config_dir: str = "configs/llm-performance"
) -> LLMPerformanceProfile:
    """
    Load an LLM performance profile from a YAML file.
    If the YAML file does not exist, fails to open, or is corrupted, returns
    a safe default LLMPerformanceProfile instance for the requested model_id.
    """
    resolved_dir = _resolve_config_dir(config_dir)
    file_path = resolved_dir / f"{model_id}.yaml"

    if not file_path.exists():
        alt_path = resolved_dir / f"{model_id}.yml"
        if alt_path.exists():
            file_path = alt_path

    if not file_path.exists():
        return LLMPerformanceProfile(model_id=model_id)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            return LLMPerformanceProfile(model_id=model_id)

        if "model_id" not in data or not data["model_id"]:
            data["model_id"] = model_id

        return LLMPerformanceProfile.from_dict(data)
    except Exception:
        return LLMPerformanceProfile(model_id=model_id)


def save_performance_profile(
    profile: LLMPerformanceProfile,
    config_dir: str = "configs/llm-performance"
) -> str:
    """
    Save an LLM performance profile to a YAML file.
    Ensures directory existence and returns the string path to the saved file.
    """
    resolved_dir = _resolve_config_dir(config_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)

    file_path = resolved_dir / f"{profile.model_id}.yaml"
    data = profile.to_dict()

    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)

    return str(file_path.resolve())
