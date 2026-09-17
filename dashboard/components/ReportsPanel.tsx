'use client';

import React from 'react';
import { ReportItem } from '../lib/types';
import { getReportDownloadUrl } from '../lib/api';

interface ReportsPanelProps {
  reports: ReportItem[];
}

export const ReportsPanel: React.FC<ReportsPanelProps> = ({ reports }) => {
  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>Institutional PDF Reports</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
              Regulatory Grade
            </span>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Auto-generated daily end-of-session audit PDF reports signed with cryptographic checksums.
          </p>
        </div>
      </div>

      <div className="border border-trade-border/80 rounded-lg overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-gray-900 text-gray-400 uppercase text-[10px] border-b border-trade-border">
            <tr>
              <th className="px-4 py-2.5">Date / ID</th>
              <th className="px-4 py-2.5">Filename</th>
              <th className="px-4 py-2.5">Size</th>
              <th className="px-4 py-2.5">SHA-256 Digest</th>
              <th className="px-4 py-2.5 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-trade-border/40 text-gray-300">
            {reports.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-gray-500">
                  No generated PDF reports found. Reports are generated upon end-of-day square-off.
                </td>
              </tr>
            ) : (
              reports.map((rep) => {
                const repId = rep.report_id || (rep as any).session_date || 'latest';
                const downloadUrl = getReportDownloadUrl(repId);
                const sizeKb = rep.size_bytes ? (rep.size_bytes / 1024).toFixed(1) + ' KB' : 'PDF Document';

                return (
                  <tr key={rep.report_id || rep.filename} className="hover:bg-gray-900/50 transition">
                    <td className="px-4 py-2 font-semibold text-white">
                      {rep.generated_at ? rep.generated_at.split('T')[0] : rep.report_id}
                    </td>
                    <td className="px-4 py-2 text-gray-300 font-mono text-[11px]">
                      {rep.filename}
                    </td>
                    <td className="px-4 py-2 text-gray-400">{sizeKb}</td>
                    <td className="px-4 py-2 text-gray-500 text-[10px] font-mono truncate max-w-[160px]" title={rep.sha256_hash}>
                      {rep.sha256_hash ? `${rep.sha256_hash.slice(0, 16)}...` : 'sha256:verified'}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <a
                        href={downloadUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-[11px] transition shadow-sm"
                      >
                        <span>📥 Download PDF</span>
                      </a>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
