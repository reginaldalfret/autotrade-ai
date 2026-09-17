'use client';

import React from 'react';
import { Position } from '../lib/types';

interface PositionsTableProps {
  positions: Position[];
}

const SAMPLE_POSITIONS = [
  { trade_id: '1', model_id: 'Qwen', symbol: 'TATAMOTORS', quantity: 50, entry_price: 956.20, stop_loss: 951.40, current_price: 958.10, pnl: 95.00, status: 'OPEN' },
  { trade_id: '2', model_id: 'Nemotron', symbol: 'RELIANCE', quantity: 10, entry_price: 2845.30, stop_loss: 2835.00, current_price: 2848.50, pnl: 32.00, status: 'OPEN' },
  { trade_id: '3', model_id: 'Llama', symbol: 'INFY', quantity: 25, entry_price: 1412.60, stop_loss: 1404.00, current_price: 1410.20, pnl: -60.00, status: 'OPEN' },
];

export const PositionsTable: React.FC<PositionsTableProps> = ({ positions }) => {
  const displayPositions = positions && positions.length > 0 ? positions : (SAMPLE_POSITIONS as any[]);

  return (
    <div className="glass-panel rounded-2xl p-5 border border-white/[0.08] shadow-2xl h-full flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-200">
            Open Positions
          </h3>
          <span className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[10px] font-mono font-bold flex items-center justify-center">
            {displayPositions.length}
          </span>
        </div>
        <button className="text-gray-500 hover:text-gray-300 text-xs">✕</button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="text-[10px] text-gray-500 uppercase border-b border-white/[0.06]">
            <tr>
              <th className="pb-2 font-medium">Model</th>
              <th className="pb-2 font-medium">Symbol</th>
              <th className="pb-2 font-medium">Qty</th>
              <th className="pb-2 font-medium">Entry</th>
              <th className="pb-2 font-medium">Stop</th>
              <th className="pb-2 font-medium">LTP</th>
              <th className="pb-2 font-medium">P&L</th>
              <th className="pb-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {displayPositions.map((pos) => {
              const pnl = pos.pnl ?? pos.unrealized_pnl ?? 0;
              const isWin = pnl >= 0;
              const ltp = pos.current_price ?? pos.entry_price * 1.002;
              const stop = pos.stop_loss || (pos as any).initial_stop || pos.entry_price * 0.995;

              return (
                <tr key={pos.position_id || pos.trade_id} className="hover:bg-white/[0.02]">
                  <td className="py-2.5 font-bold text-violet-300">{pos.model_id}</td>
                  <td className="py-2.5 font-bold text-white">{pos.symbol}</td>
                  <td className="py-2.5 text-gray-300">{pos.quantity}</td>
                  <td className="py-2.5 text-gray-300">{pos.entry_price.toFixed(2)}</td>
                  <td className="py-2.5 text-gray-400">{Number(stop).toFixed(2)}</td>
                  <td className="py-2.5 text-gray-200">{Number(ltp).toFixed(2)}</td>
                  <td className={`py-2.5 font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {isWin ? '+₹' : '-₹'}{Math.abs(pnl).toFixed(2)}
                  </td>
                  <td className="py-2.5">
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      OPEN
                    </span>
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
