'use client';

import React from 'react';
import { Trade } from '../lib/types';

interface TradesTableProps {
  trades: Trade[];
}

const SAMPLE_TRADES = [
  { trade_id: 't1', entry_time: '11:35', model_id: 'Nemotron', symbol: 'HDFCBANK', entry_price: 1670.20, exit_price: 1672.40, pnl: 55.00 },
  { trade_id: 't2', entry_time: '11:22', model_id: 'Qwen', symbol: 'ICICIBANK', entry_price: 1240.50, exit_price: 1243.10, pnl: 65.00 },
  { trade_id: 't3', entry_time: '10:58', model_id: 'Gemma', symbol: 'SBIN', entry_price: 812.40, exit_price: 809.20, pnl: -80.00 },
  { trade_id: 't4', entry_time: '10:32', model_id: 'Llama', symbol: 'TCS', entry_price: 3980.00, exit_price: 3985.50, pnl: 137.50 },
  { trade_id: 't5', entry_time: '10:15', model_id: 'Phi', symbol: 'AXISBANK', entry_price: 1126.30, exit_price: 1124.80, pnl: -37.50 },
];

export const TradesTable: React.FC<TradesTableProps> = ({ trades }) => {
  const displayTrades = trades && trades.length > 0 ? trades : (SAMPLE_TRADES as any[]);

  return (
    <div className="glass-panel rounded-2xl p-5 border border-white/[0.08] shadow-2xl h-full flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-200">
            Trade History
          </h3>
          <span className="px-2 py-0.5 rounded-full bg-white/[0.05] border border-white/10 text-[10px] font-mono text-gray-300">
            {displayTrades.length} today
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="text-[10px] text-gray-500 uppercase border-b border-white/[0.06]">
            <tr>
              <th className="pb-2 font-medium">Time</th>
              <th className="pb-2 font-medium">Model</th>
              <th className="pb-2 font-medium">Symbol</th>
              <th className="pb-2 font-medium">Entry</th>
              <th className="pb-2 font-medium">Exit</th>
              <th className="pb-2 font-medium">P&L</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {displayTrades.slice(0, 5).map((t) => {
              const pnl = t.pnl ?? (t as any).net_pnl ?? 0;
              const isWin = pnl >= 0;
              const time = t.exit_time?.slice(11, 16) || t.entry_time?.slice(11, 16) || t.entry_time || '11:00';

              return (
                <tr key={t.trade_id} className="hover:bg-white/[0.02]">
                  <td className="py-2.5 text-gray-500">{time}</td>
                  <td className="py-2.5 font-bold text-blue-300">{t.model_id}</td>
                  <td className="py-2.5 font-bold text-white">{t.symbol}</td>
                  <td className="py-2.5 text-gray-300">{t.entry_price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                  <td className="py-2.5 text-gray-300">{t.exit_price ? t.exit_price.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '—'}</td>
                  <td className={`py-2.5 font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {isWin ? '+₹' : '-₹'}{Math.abs(pnl).toFixed(2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
