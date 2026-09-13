"""
Daily PDF Trading Reporting package.
Provides automated generation of multi-page executive reports with ReportLab.
"""

from mobitrade.reporting.generator import DailyReportGenerator
from mobitrade.reporting.models import DailyTradingReport

__all__ = ["DailyReportGenerator", "DailyTradingReport"]
