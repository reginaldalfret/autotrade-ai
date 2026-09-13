"""
Deterministic Matplotlib Chart Generator for Daily PDF Reports.
Uses headless 'Agg' backend to generate crisp visualizations for PDF inclusion.
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

MODEL_COLORS = {
    "nemotron": "#1f77b4",
    "qwen": "#ff7f0e",
    "gemma": "#2ca02c",
    "llama": "#d62728",
    "granite": "#9467bd",
    "phi": "#8c564b",
    "smollm": "#e377c2",
    "falcon": "#17becf"
}


def plot_equity_curves(
    snapshots_by_model: Dict[str, List[Tuple[str, float]]],
    output_path: str,
    title: str = "Intraday Equity Curves (8 Models)"
) -> str:
    """
    Renders multi-line equity curve comparison chart.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 4.2), dpi=150)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    has_data = False
    for mid, points in snapshots_by_model.items():
        if not points:
            continue
        has_data = True
        times = [p[0].split("T")[-1][:5] if "T" in str(p[0]) else str(p[0])[-8:-3] for p in points]
        equities = [p[1] for p in points]
        color = MODEL_COLORS.get(mid, "#333333")
        plt.plot(times, equities, label=mid, color=color, linewidth=1.8, marker="o", markersize=3)

    if not has_data:
        # Placeholder flat line
        plt.plot(["09:15", "15:30"], [1000.0, 1000.0], label="Base Equity (₹1,000)", color="#888888", linestyle="--")

    plt.title(title, fontsize=12, fontweight="bold", pad=10)
    plt.xlabel("IST Time", fontsize=9)
    plt.ylabel("Portfolio Equity (₹)", fontsize=9)
    plt.axhline(1000.0, color="#888888", linestyle=":", alpha=0.7, label="Initial Capital")
    plt.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=8, frameon=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def plot_model_pnl_comparison(
    leaderboard: List[Dict[str, Any]],
    output_path: str,
    title: str = "Net P&L Comparison Across Models"
) -> str:
    """
    Renders horizontal bar chart comparing net P&L of all models.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 3.8), dpi=150)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Invert so rank 1 is on top
    models = [r["model_id"] for r in reversed(leaderboard)]
    net_pnls = [r["net_pnl"] for r in reversed(leaderboard)]
    colors = ["#2ca02c" if pnl >= 0 else "#d62728" for pnl in net_pnls]

    bars = plt.barh(models, net_pnls, color=colors, height=0.6, alpha=0.85)

    plt.axvline(0, color="#333333", linestyle="-", linewidth=0.8)
    plt.title(title, fontsize=12, fontweight="bold", pad=10)
    plt.xlabel("Net P&L (₹)", fontsize=9)
    plt.ylabel("Model", fontsize=9)

    # Value labels on bars
    for bar in bars:
        w = bar.get_width()
        ha = "left" if w >= 0 else "right"
        offset = 0.5 if w >= 0 else -0.5
        plt.text(w + offset, bar.get_y() + bar.get_height() / 2, f"₹{w:+.2f}", va="center", ha=ha, fontsize=8, fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def plot_cost_distribution(
    total_gross_profit: float,
    total_gross_loss: float,
    total_fees: float,
    total_slippage: float,
    output_path: str
) -> str:
    """
    Renders component breakdown of gross profits, losses, statutory fees, and slippage.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(6, 3.5), dpi=150)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    categories = ["Gross Profit", "Gross Loss", "Statutory Fees", "Slippage"]
    values = [abs(total_gross_profit), abs(total_gross_loss), abs(total_fees), abs(total_slippage)]
    colors = ["#2ca02c", "#d62728", "#ff7f0e", "#17becf"]

    # Avoid zero-all error
    if sum(values) == 0:
        values = [1, 0, 0, 0]
        categories = ["No Trades", "", "", ""]

    bars = plt.bar(categories, values, color=colors, width=0.5, alpha=0.85)
    plt.title("Financial Cost & Return Breakdown", fontsize=11, fontweight="bold", pad=8)
    plt.ylabel("Amount (₹)", fontsize=8)

    for bar in bars:
        h = bar.get_height()
        if h > 0:
            plt.text(bar.get_x() + bar.get_width() / 2, h + 0.1, f"₹{h:.2f}", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path
