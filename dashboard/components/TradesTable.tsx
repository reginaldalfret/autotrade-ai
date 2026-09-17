'use client';

import React, { useState } from 'react';
import { Trade } from '../lib/types';

interface TradesTableProps {
  trades: Trade[];
  selectedModel: string;
  onModelSelect: (modelId: string) => void;
}

const MODELS = [
  { id: 'all', label: 'All Models' },
  { id: 'nemotron', label: 'Nemotron' },
  { id: 'qwen', label: 'Qwen' },
  { id: 'gemma', label: 'Gemma' },
  { id: 'llama', label: 'Llama' },
  { id: 'granite', label: 'Granite' },
  { id: 'phi', label: 'Phi' },
  { id: 'smollm', label: 'SmolLM' },
  { id: 'falcon', label: 'Falcon' },
];

export const TradesTable: React.FC<TradesTableProps> = ({
  trades,
  selectedModel,
  onModelSelect,
}) => {
  const filteredTrades = trades.filter((t) => {
    if (selectedModel === 'all') return true;
    return t.model_id?.toLowerCase() === selectedModel.toLowerCase();
  });

  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>Historical Paper Trades</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-trade-border">
              {filteredTrades.length} Recorded
            </span>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Immutable audit record of all entered and closed paper orders with regulatory fee deductions.
          </p>
        </div>

        {/* Model Filter */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-gray-400">Filter Model:</span>
          <select
            value={selectedModel}
            onChange={(e) => onModelSelect(e.target.value)}
            className="bg-gray-900 border border-trade-border text-gray-200 rounded px-2.5 py-1 text-xs font-mono focus:outline-none focus:border-blue-500"
          >
            {MODELS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="border border-trade-border/80 rounded-lg overflow-x-auto max-h-[360px]">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-gray-900 text-gray-400 uppercase text-[10px] border-b border-trade-border sticky top-0 z-10">
            <tr>
              <th className="px-3 py-2.5">Trade ID</th>
              <th className="px-3 py-2.5">Model</th>
              <th className="px-3 py-2.5">Symbol</th>
              <th className="px-3 py-2.5">Qty</th>
              <th className="px-3 py-2.5">Entry ₹</th>
              <th className="px-3 py-2.5">Exit ₹</th>
              <th className="px-3 py-2.5">Net P&L</th>
              <th className="px-3 py-2.5">Exit Reason</th>
              <th className="px-3 py-2.5">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-trade-border/40 text-gray-300">
            {filteredTrades.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-gray-500">
                  No trades recorded for the selected filter.
                </td>
              </tr>
            ) : (
              filteredTrades.map((t) => {
                const pnl = t.pnl ?? (t as any).net_pnl ?? 0.0;
                const isWin = pnl >= 0;
                return (
                  <tr key={t.trade_id} className="hover:bg-gray-900/50 transition">
                    <td className="px-3 py-2 text-gray-500 text-[11px] truncate max-w-[90px]">
                      {t.trade_id}
                    </td>
                    <td className="px-3 py-2 font-semibold text-blue-400 uppercase">{t.model_id}</td>
                    <td className="px-3 py-2 font-bold text-white">{t.symbol}</td>
                    <td className="px-3 py-2 text-gray-300">{t.quantity}</td>
                    <td className="px-3 py-2 text-gray-300">
                      ₹{t.entry_price?.toFixed(2) || '0.00'}
                    </td>
                    <td className="px-3 py-2 text-gray-300">
                      ₹{t.exit_price ? t.exit_price.toFixed(2) : '—'}
                    </td>
                    <td className={`px-3 py-2 font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {isWin ? '+' : ''}₹{pnl.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-gray-400 text-[11px]">
                      {t.exit_reason || (t as any).status || 'CLOSED'}
                    </td>
                    <td className="px-3 py-2 text-gray-500 text-[10px]">
                      {t.exit_time || t.entry_time || '—'}
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
