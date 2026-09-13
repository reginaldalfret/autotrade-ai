"""
Unit tests for PDF Report Generation and Visualizations.
"""

import os
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from mobitrade.reporting.charts import (
    plot_equity_curves,
    plot_model_pnl_comparison,
    plot_cost_distribution
)
from mobitrade.reporting.generator import DailyReportGenerator
from mobitrade.paper.persistence import PaperDatabaseRepository
from mobitrade.domain.models import PortfolioSnapshot


def test_chart_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        eq_file = str(tmp_path / "eq.png")
        pnl_file = str(tmp_path / "pnl.png")
        cost_file = str(tmp_path / "cost.png")

        # Test equity curves
        snapshots = {
            "nemotron": [("2026-09-11T09:15:00", 1000.0), ("2026-09-11T12:00:00", 1050.0), ("2026-09-11T15:30:00", 1080.0)],
            "qwen": [("2026-09-11T09:15:00", 1000.0), ("2026-09-11T15:30:00", 970.0)]
        }
        res_eq = plot_equity_curves(snapshots, eq_file)
        assert os.path.exists(res_eq)
        assert os.path.getsize(res_eq) > 1000

        # Test PnL comparison
        leaderboard = [
            {"model_id": "nemotron", "net_pnl": 80.0},
            {"model_id": "qwen", "net_pnl": -30.0}
        ]
        res_pnl = plot_model_pnl_comparison(leaderboard, pnl_file)
        assert os.path.exists(res_pnl)
        assert os.path.getsize(res_pnl) > 1000

        # Test cost distribution
        res_cost = plot_cost_distribution(120.0, 40.0, 15.0, 5.0, cost_file)
        assert os.path.exists(res_cost)
        assert os.path.getsize(res_cost) > 1000


def test_daily_pdf_report_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = str(tmp_path / "test_report.db")
        reports_dir = str(tmp_path / "reports")
        temp_dir = str(tmp_path / "temp")

        repo = PaperDatabaseRepository(db_path=db_path)
        session_id = "SES_TEST_REPORT_01"
        session_date = "2026-09-11"

        # 1. Setup session
        repo.save_session_start(session_id, session_date, 2)

        # 2. Add performance records
        perf_a = {
            "model_id": "nemotron",
            "starting_balance": 1000.0,
            "ending_balance": 1080.0,
            "gross_pnl": 100.0,
            "net_pnl": 80.0,
            "daily_pnl": 80.0,
            "return_pct": 8.0,
            "total_fees": 15.0,
            "total_slippage": 5.0,
            "trades_count": 3,
            "winning_trades_count": 2,
            "losing_trades_count": 1,
            "win_rate": 66.7,
            "average_winning_trade": 45.0,
            "average_losing_trade": -10.0,
            "largest_win": 50.0,
            "largest_loss": -10.0,
            "profit_factor": 4.5,
            "max_drawdown": 1.2,
            "target_status": "NORMAL",
            "stop_status": "NORMAL"
        }
        repo.save_daily_performance(perf_a, session_id)

        # 3. Add audit event
        repo.record_audit_event(
            session_id=session_id,
            model_id="nemotron",
            event_type="ORDER_FILLED",
            payload={"symbol": "INFY", "fill_price": 1800.0},
            timestamp=datetime.now(timezone.utc)
        )

        # 4. Generate report
        generator = DailyReportGenerator(db_path=db_path, reports_dir=reports_dir, temp_dir=temp_dir)
        pdf_file = generator.generate(session_id)

        assert os.path.exists(pdf_file)
        assert os.path.getsize(pdf_file) > 5000  # PDF exists and has content

        # Verify SQLite reports record
        report_record = repo.get_report_by_date(session_date)
        assert report_record is not None
        assert report_record["session_id"] == session_id
        assert report_record["file_hash"] is not None
        assert len(report_record["file_hash"]) == 64  # Valid SHA-256
