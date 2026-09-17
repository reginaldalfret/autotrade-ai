'use client';

import React from 'react';
import { ReportItem } from '../lib/types';
import { getReportDownloadUrl } from '../lib/api';

interface ReportsPanelProps {
  reports: ReportItem[];
}

export const ReportsPanel: React.FC<ReportsPanelProps> = ({ reports }) => {
  const latestReport = reports && reports.length > 0 ? reports[0] : null;
  const downloadUrl = latestReport ? getReportDownloadUrl(latestReport.report_id) : '#';

  return (
    <div className="glass-panel rounded-2xl p-5 border border-white/[0.08] shadow-2xl h-full flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-200">
            Reports
          </h3>
          <span className="text-[11px] text-gray-400 font-mono">
            Latest: 24 Apr 2025
          </span>
        </div>
        <button className="text-[11px] text-blue-400 hover:text-blue-300 font-medium">
          View All
        </button>
      </div>

      {/* Report Item Capsule */}
      <div className="flex items-center justify-between gap-3 p-3 rounded-xl glass-panel-subtle border border-white/[0.06]">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-rose-500 to-amber-500 p-[1px] flex-shrink-0 flex items-center justify-center shadow-md shadow-rose-500/20">
            <div className="w-full h-full bg-[#120B0F] rounded-[11px] flex items-center justify-center text-xs">
              📄
            </div>
          </div>

          <div className="min-w-0">
            <div className="text-xs font-bold text-white truncate">
              Daily Trading Report
            </div>
            <div className="text-[10px] text-gray-400 font-mono mt-0.5">
              24 Apr 2025 | Session: Morning
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="text-right hidden sm:block">
            <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              Completed
            </span>
            <div className="text-[9px] font-mono text-gray-500 mt-1">
              SHA-256: a3f9e2...c7d4b8
            </div>
          </div>

          <a
            href={downloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="glass-pill px-3 py-1.5 rounded-xl text-xs font-medium text-cyan-300 hover:text-white hover:bg-cyan-500/20 border border-cyan-500/40 transition shadow-sm"
          >
            Open PDF
          </a>
        </div>
      </div>
    </div>
  );
};
