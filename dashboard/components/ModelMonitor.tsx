'use client';

import React from 'react';
import { RuntimeStatus } from '../lib/types';

interface ModelMonitorProps {
  runtime: RuntimeStatus | null;
  accounts?: Record<string, any>;
  analytics?: any;
}

const MODELS_DATA = [
  { id: 'nemotron', name: 'Nemotron', pnl: 12.40, wr: 72, trades: 14, icon: '⚡' },
  { id: 'qwen', name: 'Qwen', pnl: 8.70, wr: 71, trades: 11, icon: '🧠' },
  { id: 'gemma', name: 'Gemma', pnl: -2.10, wr: 45, trades: 9, icon: '💠' },
  { id: 'llama', name: 'Llama', pnl: 4.30, wr: 67, trades: 12, icon: '🦙' },
  { id: 'granite', name: 'Granite', pnl: 1.20, wr: 60, trades: 10, icon: '🧱' },
  { id: 'phi', name: 'Phi', pnl: 3.80, wr: 63, trades: 8, icon: '🔬' },
  { id: 'smollm', name: 'SmolLM', pnl: -0.90, wr: 50, trades: 6, icon: '⚡' },
  { id: 'falcon', name: 'Falcon', pnl: 5.10, wr: 68, trades: 11, icon: '🦅' },
];

export const ModelMonitor: React.FC<ModelMonitorProps> = ({
  runtime,
  accounts = {},
  analytics = {},
}) => {
  const activeModelId = runtime?.current_model?.toLowerCase() || 'qwen';

  return (
    <div className="glass-panel rounded-2xl p-5 border border-white/[0.08] shadow-2xl h-full flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-3">
        <h3 className="text-sm font-semibold text-gray-200">
          Model Status <span className="text-xs font-normal text-gray-400">(8 Local LLMs)</span>
        </h3>
        <button className="text-gray-500 hover:text-gray-300 text-xs">✕</button>
      </div>

      {/* 8 Model Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
        {MODELS_DATA.map((m) => {
          const isActive = activeModelId === m.id;
          const acc = accounts[m.id];
          const netPnl = acc?.realized_pnl ?? m.pnl;
          const wr = acc ? (acc.win_rate ?? m.wr) : m.wr;
          const trades = acc?.trades_count ?? m.trades;
          const isWin = netPnl >= 0;

          return (
            <div
              key={m.id}
              className={`rounded-xl p-3 flex flex-col justify-between transition-all duration-300 relative ${
                isActive
                  ? 'glass-panel bg-gradient-to-b from-blue-900/30 to-violet-900/30 border-cyan-400/60 shadow-lg glow-ring-cyan'
                  : 'glass-panel-subtle hover:border-white/20'
              }`}
            >
              {/* Top: Icon & Name */}
              <div className="flex flex-col items-center text-center">
                <div className="w-7 h-7 rounded-lg bg-white/[0.05] border border-white/10 flex items-center justify-center text-xs mb-1.5">
                  {m.icon}
                </div>
                <div className="text-xs font-bold font-sans text-white">
                  {m.name}
                </div>
              </div>

              {/* Bottom: Stats */}
              <div className="mt-3 text-center font-mono">
                <div className={`text-xs font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {isWin ? '+₹' : '-₹'}{Math.abs(netPnl).toFixed(2)}
                </div>
                <div className="text-[10px] text-gray-400 mt-0.5">
                  {wr}% WR
                </div>
                <div className="text-[9px] text-gray-500">
                  {trades} trades
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
