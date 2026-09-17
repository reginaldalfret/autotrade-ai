'use client';

import React from 'react';
import { RuntimeStatus } from '../lib/types';

interface ModelInfo {
  id: string;
  name: string;
  family: string;
  size: string;
  role: string;
}

const MODELS_CONFIG: ModelInfo[] = [
  { id: 'nemotron', name: 'Nemotron Mini', family: 'NVIDIA', size: '4B / 8B', role: 'Trend Following' },
  { id: 'qwen', name: 'Qwen 2.5', family: 'Alibaba', size: '7B', role: 'Multi-Timeframe' },
  { id: 'gemma', name: 'Gemma 2', family: 'Google', size: '9B', role: 'Support / Resistance' },
  { id: 'llama', name: 'Llama 3.1', family: 'Meta', size: '8B', role: 'Momentum Breakout' },
  { id: 'granite', name: 'Granite 3.0', family: 'IBM', size: '8B', role: 'Statistical Reversion' },
  { id: 'phi', name: 'Phi 3.5', family: 'Microsoft', size: '3.8B', role: 'Microstructure Scalp' },
  { id: 'smollm', name: 'SmolLM 2', family: 'HuggingFace', size: '1.7B', role: 'Rapid Confirmation' },
  { id: 'falcon', name: 'Falcon 2', family: 'TII', size: '7B', role: 'Volatility Expansion' },
];

interface ModelMonitorProps {
  runtime: RuntimeStatus | null;
  accounts?: Record<string, any>;
  analytics?: Record<string, any>;
}

export const ModelMonitor: React.FC<ModelMonitorProps> = ({
  runtime,
  accounts = {},
  analytics = {},
}) => {
  const activeModelId = runtime?.current_model?.toLowerCase();

  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>8-Model Tournament Roster</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
              Zero-VRAM Sequential Swap
            </span>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Single active model loaded into VRAM at any time. Eviction occurs immediately after inference.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {MODELS_CONFIG.map((m) => {
          const isActive = activeModelId === m.id;
          const acc = accounts[m.id] || {};
          const stat = analytics?.models?.[m.id] || {};

          const netPnl = acc.realized_pnl ?? stat.net_pnl ?? 0.0;
          const trades = acc.trades_count ?? stat.total_trades ?? 0;
          const winRate = stat.win_rate ?? (trades > 0 ? 50.0 : 0.0);
          const drawdown = stat.max_drawdown ?? 0.0;

          return (
            <div
              key={m.id}
              className={`rounded-lg p-3.5 border transition-all ${
                isActive
                  ? 'bg-blue-950/70 border-blue-500 ring-1 ring-blue-500/50 shadow-md shadow-blue-900/40'
                  : 'bg-gray-900/70 border-trade-border hover:border-gray-700'
              }`}
            >
              {/* Header: Name + Badge */}
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono font-bold text-sm text-white">{m.name}</span>
                  </div>
                  <div className="text-[11px] font-mono text-gray-400">
                    {m.family} · {m.size}
                  </div>
                </div>

                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium ${
                    isActive
                      ? 'bg-emerald-500 text-black font-bold animate-pulse'
                      : 'bg-gray-800 text-gray-400'
                  }`}
                >
                  {isActive ? 'IN VRAM' : 'UNLOADED'}
                </span>
              </div>

              <div className="mt-2 text-[11px] text-gray-400 italic">
                Role: <span className="text-gray-300 not-italic">{m.role}</span>
              </div>

              {/* Stats Grid */}
              <div className="mt-3 pt-2.5 border-t border-trade-border/60 grid grid-cols-2 gap-2 text-xs font-mono">
                <div>
                  <div className="text-[10px] text-gray-500">NET P&L</div>
                  <div className={`font-semibold ${netPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    ₹{netPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                </div>

                <div>
                  <div className="text-[10px] text-gray-500">TRADES / WIN%</div>
                  <div className="font-semibold text-gray-200">
                    {trades} · {winRate.toFixed(0)}%
                  </div>
                </div>

                <div>
                  <div className="text-[10px] text-gray-500">EQUITY</div>
                  <div className="font-semibold text-gray-300">
                    ₹{(acc.total_equity ?? 100000).toLocaleString('en-IN')}
                  </div>
                </div>

                <div>
                  <div className="text-[10px] text-gray-500">MAX DD</div>
                  <div className="font-semibold text-gray-300">
                    {drawdown.toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
