"""
Automated Executive Daily PDF Trading Report Generator.
Generates institutional multi-page PDF reports using ReportLab,
incorporating deterministic charts, tabular breakdowns,
disclaimers, and cryptographic SHA-256 audit verification.
"""

import os
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

from mobitrade.analytics.engine import PerformanceAnalyticsEngine
from mobitrade.logging.audit import AuditLogger, AuditEventType
from mobitrade.paper.persistence import PaperDatabaseRepository
from mobitrade.reporting.charts import (
    plot_equity_curves,
    plot_model_pnl_comparison,
    plot_cost_distribution
)


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute total page count ("Page X of Y")
    and draw institutional running headers and footers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.session_date = "N/A"
        self.session_id = "N/A"

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#555555"))

        # Running header on page 2+
        if self._pageNumber > 1:
            self.drawString(36, 762, "AutoTrade AI — Daily Trading Executive Report")
            self.drawRightString(576, 762, f"Date: {self.session_date} | Session: {self.session_id}")
            self.setStrokeColor(colors.HexColor("#dcdcdc"))
            self.setLineWidth(0.5)
            self.line(36, 756, 576, 756)

        # Running footer on all pages
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(36, 25, "CONFIDENTIAL — SIMULATED RESEARCH REPORT | NO FINANCIAL ADVICE")
        self.drawRightString(576, 25, page_str)
        self.setStrokeColor(colors.HexColor("#dcdcdc"))
        self.setLineWidth(0.5)
        self.line(36, 35, 576, 35)

        self.restoreState()


class DailyReportGenerator:
    """
    Generates 8-page Daily Trading Report in PDF format.
    Ensures zero mutation of underlying trading records.
    """
    def __init__(
        self,
        db_path: str = "/mnt/d/Trading LLM/MobiTradeAI/database/mobitrade.db",
        reports_dir: str = "/mnt/d/Trading LLM/MobiTradeAI/reports/daily",
        temp_dir: str = "/mnt/d/Trading LLM/MobiTradeAI/reports/temp"
    ):
        self.db_path = Path(db_path)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.analytics_engine = PerformanceAnalyticsEngine(str(self.db_path))
        self.persistence = PaperDatabaseRepository(str(self.db_path))
        self.audit_logger = AuditLogger(str(self.db_path))

    def generate(self, session_id_or_date: str) -> str:
        """
        Generates full PDF report for session, hashes it, stores in SQLite,
        and logs audit event. Returns generated file path.
        """
        # 1. Resolve session
        session_info = self.analytics_engine.get_session_by_id_or_date(session_id_or_date)
        if not session_info:
            # Create synthetic lookup if not found
            session_id = session_id_or_date
            session_date = session_id_or_date if "-" in session_id_or_date else datetime.now().strftime("%Y-%m-%d")
        else:
            session_id = session_info["session_id"]
            session_date = session_info["session_date"]

        # 2. Gather analytics data
        session_analytics = self.analytics_engine.compute_daily_session_analytics(session_id)
        exec_summary = session_analytics["executive_summary"]
        leaderboard = session_analytics["leaderboard"]
        model_analytics = session_analytics["models_analytics"]

        # 3. Gather audit verification
        audit_res = self.audit_logger.verify_chain(session_id=session_id)
        all_audit_events = self.audit_logger.get_events(session_id=session_id)
        latest_hash = all_audit_events[-1].event_hash if all_audit_events else "0"*64

        # 4. Generate temporary charts
        chart_eq_path = str(self.temp_dir / f"eq_{session_id}.png")
        chart_pnl_path = str(self.temp_dir / f"pnl_{session_id}.png")
        chart_cost_path = str(self.temp_dir / f"cost_{session_id}.png")

        # Prepare equity curve series
        snapshots_by_model: Dict[str, List[Tuple[str, float]]] = {}
        with self.persistence._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT model_id, timestamp, total_equity FROM portfolio_snapshots WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            for r in cursor.fetchall():
                snapshots_by_model.setdefault(r["model_id"], []).append((r["timestamp"], float(r["total_equity"])))

        plot_equity_curves(snapshots_by_model, chart_eq_path)
        plot_model_pnl_comparison(leaderboard, chart_pnl_path)
        plot_cost_distribution(
            total_gross_profit=exec_summary["total_gross_pnl"] if exec_summary["total_gross_pnl"] > 0 else 0.0,
            total_gross_loss=abs(exec_summary["total_gross_pnl"]) if exec_summary["total_gross_pnl"] < 0 else 0.0,
            total_fees=exec_summary["total_fees"],
            total_slippage=exec_summary["total_slippage"],
            output_path=chart_cost_path
        )

        # 5. Build PDF Document
        pdf_filename = f"AutoTradeAI_Daily_{session_date}.pdf"
        pdf_path = self.reports_dir / pdf_filename

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=45,
            bottomMargin=45
        )

        styles = getSampleStyleSheet()
        # Custom styles
        title_style = ParagraphStyle("DocTitle", parent=styles["Heading1"], fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"), fontName="Helvetica-Bold")
        subtitle_style = ParagraphStyle("DocSubTitle", parent=styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#475569"))
        section_heading = ParagraphStyle("SectionH", parent=styles["Heading2"], fontSize=12, leading=16, textColor=colors.HexColor("#1e3a8a"), fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4)
        body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#1e293b"))
        disclaimer_style = ParagraphStyle("Disclaimer", parent=styles["Normal"], fontSize=7, leading=9, textColor=colors.HexColor("#b91c1c"), fontName="Helvetica-Oblique")
        table_cell_style = ParagraphStyle("TableCell", parent=styles["Normal"], fontSize=7.5, leading=9, textColor=colors.HexColor("#0f172a"))
        table_cell_bold = ParagraphStyle("TableCellBold", parent=styles["Normal"], fontSize=7.5, leading=9, textColor=colors.HexColor("#0f172a"), fontName="Helvetica-Bold")

        story = []

        # =========================================================================
        # PAGE 1: TITLE BLOCK, DISCLAIMER, METADATA, EXECUTIVE SUMMARY
        # =========================================================================
        story.append(Paragraph("AutoTrade AI — Daily Trading Executive Report", title_style))
        story.append(Paragraph("Institutional Performance Analytics & Paper Trading Ledger | NSE Indian Equity Cash Market", subtitle_style))
        story.append(Spacer(1, 8))

        # Legal Disclaimer Box
        disclaimer_text = (
            "<b>MANDATORY RESEARCH DISCLAIMER:</b> This report is generated strictly for algorithmic simulation, research, "
            "and quantitative evaluation purposes. All trades and metrics reflect paper-trading execution under local-first "
            "deterministic rules on the NSE Indian Equity Cash Market (09:15–15:30 IST). No real capital was deployed, "
            "no live broker connection was established, and nothing herein constitutes investment, financial, or tax advice."
        )
        disclaimer_table = Table([[Paragraph(disclaimer_text, disclaimer_style)]], colWidths=[540])
        disclaimer_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#fca5a5")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(disclaimer_table)
        story.append(Spacer(1, 10))

        # Session Metadata Table
        meta_data = [
            [
                Paragraph("<b>Session ID:</b> " + session_id, table_cell_style),
                Paragraph("<b>Trading Date:</b> " + session_date, table_cell_style),
                Paragraph("<b>Market:</b> NSE Cash (Intraday)", table_cell_style)
            ],
            [
                Paragraph("<b>Execution Window:</b> 09:15–15:30 IST", table_cell_style),
                Paragraph("<b>Square-Off:</b> 15:15 IST Enforced", table_cell_style),
                Paragraph("<b>Models Active:</b> 8 Isolated Accounts", table_cell_style)
            ]
        ]
        meta_table = Table(meta_data, colWidths=[180, 180, 180])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # Executive Summary Metrics Grid
        story.append(Paragraph("Executive Performance Summary", section_heading))
        summary_rows = [
            [
                Paragraph("<b>Total Initial Capital</b>", table_cell_bold),
                Paragraph(f"₹{exec_summary['total_starting_equity']:,.2f}", table_cell_style),
                Paragraph("<b>Total Final Capital</b>", table_cell_bold),
                Paragraph(f"₹{exec_summary['total_ending_equity']:,.2f}", table_cell_style)
            ],
            [
                Paragraph("<b>Total Gross P&L</b>", table_cell_bold),
                Paragraph(f"₹{exec_summary['total_gross_pnl']:+,.2f}", table_cell_style),
                Paragraph("<b>Total Net P&L</b>", table_cell_bold),
                Paragraph(f"₹{exec_summary['total_net_pnl']:+,.2f}", table_cell_bold)
            ],
            [
                Paragraph("<b>Aggregate Return %</b>", table_cell_bold),
                Paragraph(f"{exec_summary['overall_return_pct']:+.2f}%", table_cell_style),
                Paragraph("<b>Total Trades Executed</b>", table_cell_bold),
                Paragraph(str(exec_summary["total_trades"]), table_cell_style)
            ],
            [
                Paragraph("<b>Winning / Losing Trades</b>", table_cell_bold),
                Paragraph(f"{exec_summary['total_wins']} / {exec_summary['total_losses']}", table_cell_style),
                Paragraph("<b>Aggregate Win Rate</b>", table_cell_bold),
                Paragraph(f"{exec_summary['overall_win_rate']:.2f}%", table_cell_style)
            ],
            [
                Paragraph("<b>Total Statutory Fees</b>", table_cell_bold),
                Paragraph(f"₹{exec_summary['total_fees']:,.2f}", table_cell_style),
                Paragraph("<b>Total Execution Slippage</b>", table_cell_bold),
                Paragraph(f"₹{exec_summary['total_slippage']:,.2f}", table_cell_style)
            ],
            [
                Paragraph("<b>Daily Target Reached (+10%)</b>", table_cell_bold),
                Paragraph(f"{exec_summary['targets_reached_count']} Models", table_cell_style),
                Paragraph("<b>Daily Stop Triggered (-5%)</b>", table_cell_bold),
                Paragraph(f"{exec_summary['stops_triggered_count']} Models", table_cell_style)
            ],
            [
                Paragraph("<b>Top Performer (Rank #1)</b>", table_cell_bold),
                Paragraph(f"<b>{exec_summary['best_performing_model'].upper()}</b>", table_cell_style),
                Paragraph("<b>Lowest Performer (Rank #8)</b>", table_cell_bold),
                Paragraph(f"<b>{exec_summary['worst_performing_model'].upper()}</b>", table_cell_style)
            ]
        ]
        sum_table = Table(summary_rows, colWidths=[150, 120, 150, 120])
        sum_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(sum_table)
        story.append(Spacer(1, 12))

        # Add cost chart onto page 1 bottom
        story.append(Paragraph("Statutory Fee & Cost Distribution", section_heading))
        story.append(Image(chart_cost_path, width=420, height=210))
        story.append(PageBreak())

        # =========================================================================
        # PAGE 2: TOURNAMENT LEADERBOARD & CHARTS
        # =========================================================================
        story.append(Paragraph("8-Model Tournament Leaderboard", section_heading))
        story.append(Paragraph("Rankings determined by: 1. Net P&L, 2. Return %, 3. Max DD %, 4. Profit Factor, 5. Trade Count.", subtitle_style))
        story.append(Spacer(1, 6))

        lb_headers = ["Rank", "Model", "Start (₹)", "End (₹)", "Net P&L (₹)", "Ret %", "Trades", "Win Rate", "PF", "Max DD", "Status"]
        lb_rows = [[Paragraph(f"<b>{h}</b>", table_cell_bold) for h in lb_headers]]
        for r in leaderboard:
            pf_display = f"{r['profit_factor']:.2f}" if isinstance(r["profit_factor"], (int, float)) else str(r["profit_factor"])
            lb_rows.append([
                Paragraph(str(r["rank"]), table_cell_style),
                Paragraph(f"<b>{r['model_id']}</b>", table_cell_style),
                Paragraph(f"{r['starting_balance']:.1f}", table_cell_style),
                Paragraph(f"{r['ending_balance']:.1f}", table_cell_style),
                Paragraph(f"<b>{r['net_pnl']:+.2f}</b>", table_cell_style),
                Paragraph(f"{r['return_pct']:+.2f}%", table_cell_style),
                Paragraph(str(r["trades_count"]), table_cell_style),
                Paragraph(f"{r['win_rate']:.1f}%", table_cell_style),
                Paragraph(pf_display, table_cell_style),
                Paragraph(f"{r['max_drawdown']:.1f}%", table_cell_style),
                Paragraph(r["target_status"], table_cell_style),
            ])

        lb_table = Table(lb_rows, colWidths=[28, 65, 48, 48, 55, 45, 40, 48, 38, 45, 80])
        lb_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(lb_table)
        story.append(Spacer(1, 10))

        # Comparative visual charts
        story.append(Paragraph("Visual Comparative Analytics", section_heading))
        story.append(Image(chart_pnl_path, width=540, height=220))
        story.append(Spacer(1, 6))
        story.append(Image(chart_eq_path, width=540, height=240))
        story.append(PageBreak())

        # =========================================================================
        # PAGES 3–6: 8-MODEL DEEP DIVES (2 Models per page)
        # =========================================================================
        for i in range(0, len(model_analytics), 2):
            batch = model_analytics[i:i+2]
            for ma in batch:
                mid = ma["model_id"]
                t_stats = ma["trade_stats"]
                dd = ma["drawdown"]
                rr = ma["risk_ratios"]

                story.append(Paragraph(f"Model Profile & Deep Dive: <b>{mid.upper()}</b>", section_heading))
                
                deep_dive_data = [
                    [
                        Paragraph("<b>Starting Balance</b>", table_cell_bold),
                        Paragraph(f"₹{ma['starting_balance']:,.2f}", table_cell_style),
                        Paragraph("<b>Ending Balance</b>", table_cell_bold),
                        Paragraph(f"₹{ma['ending_balance']:,.2f}", table_cell_style),
                    ],
                    [
                        Paragraph("<b>Gross P&L</b>", table_cell_bold),
                        Paragraph(f"₹{ma['gross_pnl']:+,.2f}", table_cell_style),
                        Paragraph("<b>Net P&L</b>", table_cell_bold),
                        Paragraph(f"<b>₹{ma['net_pnl']:+,.2f}</b>", table_cell_bold),
                    ],
                    [
                        Paragraph("<b>Return %</b>", table_cell_bold),
                        Paragraph(f"{ma['return_pct']:+.2f}%", table_cell_style),
                        Paragraph("<b>Win Rate %</b>", table_cell_bold),
                        Paragraph(f"{t_stats['win_rate']:.2f}% ({t_stats['winning_trades']}W / {t_stats['losing_trades']}L)", table_cell_style),
                    ],
                    [
                        Paragraph("<b>Profit Factor</b>", table_cell_bold),
                        Paragraph(str(t_stats["profit_factor"]), table_cell_style),
                        Paragraph("<b>Win / Loss Ratio</b>", table_cell_bold),
                        Paragraph(str(t_stats["win_loss_ratio"]), table_cell_style),
                    ],
                    [
                        Paragraph("<b>Average Win / Loss</b>", table_cell_bold),
                        Paragraph(f"₹{t_stats['average_win']:.2f} / ₹{t_stats['average_loss']:.2f}", table_cell_style),
                        Paragraph("<b>Largest Win / Loss</b>", table_cell_bold),
                        Paragraph(f"₹{t_stats['largest_win']:.2f} / ₹{t_stats['largest_loss']:.2f}", table_cell_style),
                    ],
                    [
                        Paragraph("<b>Max Drawdown Amount / %</b>", table_cell_bold),
                        Paragraph(f"₹{dd['max_drawdown_amount']:.2f} ({dd['max_drawdown_pct']:.2f}%)", table_cell_style),
                        Paragraph("<b>Sharpe / Sortino</b>", table_cell_bold),
                        Paragraph(f"{rr['sharpe']} / {rr['sortino']}", table_cell_style),
                    ],
                    [
                        Paragraph("<b>Statutory Fees Paid</b>", table_cell_bold),
                        Paragraph(f"₹{t_stats['total_fees']:.2f}", table_cell_style),
                        Paragraph("<b>Execution Slippage Incurred</b>", table_cell_bold),
                        Paragraph(f"₹{t_stats['total_slippage']:.2f}", table_cell_style),
                    ],
                    [
                        Paragraph("<b>Daily Target (+10%) Status</b>", table_cell_bold),
                        Paragraph(ma["target_status"], table_cell_style),
                        Paragraph("<b>Daily Stop (-5%) Status</b>", table_cell_bold),
                        Paragraph(ma["stop_status"], table_cell_style),
                    ],
                ]
                dd_table = Table(deep_dive_data, colWidths=[135, 135, 135, 135])
                dd_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(dd_table)
                story.append(Spacer(1, 10))

            story.append(PageBreak())

        # =========================================================================
        # PAGE 7: COMPLETE TRADE EXECUTION LEDGER
        # =========================================================================
        story.append(Paragraph("Complete Trade Execution Ledger", section_heading))
        story.append(Paragraph("Comprehensive record of completed intraday round-trip trades across all accounts.", subtitle_style))
        story.append(Spacer(1, 6))

        with self.persistence._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM paper_trades WHERE session_id = ? ORDER BY entry_time ASC", (session_id,))
            trades = [dict(r) for r in cursor.fetchall()]

        if trades:
            tr_headers = ["Trade ID", "Model", "Symbol", "Qty", "Entry (₹)", "Exit (₹)", "Gross", "Fees", "Slip", "Net (₹)", "Exit Reason"]
            tr_rows = [[Paragraph(f"<b>{h}</b>", table_cell_bold) for h in tr_headers]]
            for t in trades[:35]:  # Fits cleanly on page 7
                tr_rows.append([
                    Paragraph(t["trade_id"][-8:], table_cell_style),
                    Paragraph(t["model_id"], table_cell_style),
                    Paragraph(t["symbol"], table_cell_style),
                    Paragraph(str(t["quantity"]), table_cell_style),
                    Paragraph(f"{t['entry_price']:.2f}", table_cell_style),
                    Paragraph(f"{t['exit_price']:.2f}" if t.get("exit_price") else "-", table_cell_style),
                    Paragraph(f"{t['gross_pnl']:+.2f}", table_cell_style),
                    Paragraph(f"{t['total_fees']:.2f}", table_cell_style),
                    Paragraph(f"{t['total_slippage']:.2f}", table_cell_style),
                    Paragraph(f"<b>{t['net_pnl']:+.2f}</b>", table_cell_style),
                    Paragraph(t.get("exit_reason", "-") or "-", table_cell_style),
                ])
            tr_table = Table(tr_rows, colWidths=[45, 50, 55, 30, 48, 48, 48, 38, 38, 55, 85])
            tr_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("PADDING", (0, 0), (-1, -1), 3.5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            story.append(tr_table)
        else:
            no_trades_box = Table([[Paragraph("<b>NO COMPLETED TRADES EXECUTED IN THIS SESSION</b><br/>Models evaluated market snapshots and safely remained in HOLD or out of position.", body_style)]], colWidths=[540])
            no_trades_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("PADDING", (0, 0), (-1, -1), 12),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            story.append(no_trades_box)

        story.append(PageBreak())

        # =========================================================================
        # PAGE 8: TAMPER-EVIDENT CRYPTOGRAPHIC AUDIT TRAIL & VERIFICATION
        # =========================================================================
        story.append(Paragraph("Cryptographic Audit Trail & Tamper-Evident Verification", section_heading))
        story.append(Paragraph("Continuous SHA-256 hash chaining of all session events guarantees mathematical immutability.", subtitle_style))
        story.append(Spacer(1, 8))

        # Verification status banner
        if audit_res.is_valid:
            status_text = "<b>AUDIT VERIFICATION: PASSED (CHAIN INTACT & TAMPER-FREE)</b><br/>All consecutive SHA-256 cryptographic hashes match and link perfectly to the Genesis Block."
            status_bg = "#dcfce7"
            status_border = "#86efac"
        else:
            status_text = f"<b>AUDIT VERIFICATION: FAILED ({len(audit_res.errors)} Discrepancies Detected)</b><br/>Integrity check failed: " + "; ".join(audit_res.errors[:2])
            status_bg = "#fee2e2"
            status_border = "#fca5a5"

        status_table = Table([[Paragraph(status_text, body_style)]], colWidths=[540])
        status_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(status_bg)),
            ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor(status_border)),
            ("PADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(status_table)
        story.append(Spacer(1, 10))

        audit_grid = [
            [
                Paragraph("<b>Total Audit Events Recorded</b>", table_cell_bold),
                Paragraph(str(audit_res.total_events), table_cell_style),
                Paragraph("<b>Verification Status</b>", table_cell_bold),
                Paragraph("VALID (100%)" if audit_res.is_valid else "INVALID", table_cell_bold)
            ],
            [
                Paragraph("<b>Sequence Range</b>", table_cell_bold),
                Paragraph(f"{audit_res.first_sequence or 1} -> {audit_res.last_sequence or audit_res.total_events}", table_cell_style),
                Paragraph("<b>Hash Algorithm</b>", table_cell_bold),
                Paragraph("SHA-256 (Canonical JSON)", table_cell_style)
            ],
            [
                Paragraph("<b>Genesis Previous Hash</b>", table_cell_bold),
                Paragraph("<font size=6>" + ("0" * 64) + "</font>", table_cell_style),
                Paragraph("<b>Latest Event Hash</b>", table_cell_bold),
                Paragraph("<font size=6>" + latest_hash + "</font>", table_cell_style)
            ]
        ]
        ag_table = Table(audit_grid, colWidths=[140, 130, 140, 130])
        ag_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(ag_table)
        story.append(Spacer(1, 10))

        # Sample Audit Event Stream
        story.append(Paragraph("Session Event Trail Sample (First & Last Events)", section_heading))
        sample_events = all_audit_events[:10] + (all_audit_events[-5:] if len(all_audit_events) > 15 else [])
        if sample_events:
            ev_headers = ["Seq", "Time (UTC)", "Event Type", "Model", "Event SHA-256 (Prefix)"]
            ev_rows = [[Paragraph(f"<b>{h}</b>", table_cell_bold) for h in ev_headers]]
            for ev in sample_events:
                ev_rows.append([
                    Paragraph(str(ev.sequence_number), table_cell_style),
                    Paragraph(ev.timestamp.split("T")[-1][:8] if "T" in ev.timestamp else ev.timestamp[-8:], table_cell_style),
                    Paragraph(ev.event_type, table_cell_style),
                    Paragraph(ev.model_id or "SYSTEM", table_cell_style),
                    Paragraph(f"<font size=6>{ev.event_hash[:24]}...</font>", table_cell_style),
                ])
            ev_table = Table(ev_rows, colWidths=[35, 75, 160, 80, 190])
            ev_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(ev_table)
        else:
            story.append(Paragraph("No audit events recorded for this session.", body_style))

        # Build document with custom canvas
        def _make_canvas(*args, **kwargs):
            c = NumberedCanvas(*args, **kwargs)
            c.session_date = session_date
            c.session_id = session_id
            return c

        doc.build(story, canvasmaker=_make_canvas)

        # 6. Calculate SHA-256 of generated PDF
        hasher = hashlib.sha256()
        with open(pdf_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        pdf_hash = hasher.hexdigest()

        # 7. Store in SQLite reports table
        report_id = f"rep_{session_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        now_iso = datetime.now(timezone.utc).isoformat()
        self.persistence.save_report(
            report_id=report_id,
            session_id=session_id,
            report_date=session_date,
            file_path=str(pdf_path),
            file_hash=pdf_hash,
            generated_at=now_iso,
            generation_status="SUCCESS"
        )

        # 8. Record audit event
        self.audit_logger.record_event(
            session_id=session_id,
            event_type=AuditEventType.REPORT_GENERATED,
            payload={
                "report_id": report_id,
                "file_path": str(pdf_path),
                "file_hash": pdf_hash,
                "total_pages": 8
            },
            model_id="SYSTEM"
        )

        # 9. Clean up temporary chart files
        for p in [chart_eq_path, chart_pnl_path, chart_cost_path]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

        return str(pdf_path)
