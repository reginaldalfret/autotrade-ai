'use client';

import React from 'react';
import { Position } from '../lib/types';

interface PositionsTableProps {
  positions: Position[];
}

export const PositionsTable: React.FC<PositionsTableProps> = ({ positions }) => {
  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>Open Paper Positions</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
              Active Exposure ({positions.length})
            </span>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Auto-governed by RiskEngine dynamic trailing stops and mandatory 15:15 IST square-off.
          </p>
        </div>
      </div>

      <div className="border border-trade-border/80 rounded-lg overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-gray-900 text-gray-400 uppercase text-[10px] border-b border-trade-border">
            <tr>
              <th className="px-4 py-2.5">Trade ID</th>
              <th className="px-4 py-2.5">Model</th>
              <th className="px-4 py-2.5">Symbol</th>
              <th className="px-4 py-2.5">Quantity</th>
              <th className="px-4 py-2.5">Entry Price</th>
              <th className="px-4 py-2.5">Initial Stop</th>
              <th className="px-4 py-2.5">Trailing Stop</th>
              <th className="px-4 py-2.5">Entry Time</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-trade-border/40 text-gray-300">
            {positions.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-6 text-center text-gray-500">
                  No active open positions. All trades are flat or awaiting signal.
                </td>
              </tr>
            ) : (
              positions.map((pos) => (
                <tr key={pos.position_id || (pos as any).trade_id} className="hover:bg-gray-900/50 transition">
                  <td className="px-4 py-2 text-gray-400 text-[11px] truncate max-w-[100px]">
                    {pos.position_id || (pos as any).trade_id}
                  </td>
                  <td className="px-4 py-2 font-semibold text-blue-400 uppercase">{pos.model_id}</td>
                  <td className="px-4 py-2 font-bold text-white">{pos.symbol}</td>
                  <td className="px-4 py-2 text-gray-200">{pos.quantity}</td>
                  <td className="px-4 py-2 text-gray-200">
                    ₹{pos.entry_price?.toFixed(2) || '0.00'}
                  </td>
                  <td className="px-4 py-2 text-rose-400">
                    ₹{(pos.stop_loss || (pos as any).initial_stop)?.toFixed(2) || '—'}
                  </td>
                  <td className="px-4 py-2 text-amber-400">
                    ₹{((pos as any).trailing_stop)?.toFixed(2) || '—'}
                  </td>
                  <td className="px-4 py-2 text-gray-400 text-[11px]">
                    {pos.entry_time || (pos as any).entry_timestamp || '—'}
                  </td>
                  <td className="px-4 py-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800">
                      OPEN
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
