'use client';

import React from 'react';
import { RiskStatus } from '../lib/types';

interface RiskEnginePanelProps {
  risk: RiskStatus | null;
}

export const RiskEnginePanel: React.FC<RiskEnginePanelProps> = ({ risk }) => {
  const items = [
    { label: 'Daily Loss Limit', val: '-5%', color: 'text-rose-400', icon: '🛑' },
    { label: 'Daily Target', val: '+10%', color: 'text-emerald-400', icon: '🎯' },
    { label: 'Max Trades', val: '20', color: 'text-cyan-400', icon: '⚡' },
    { label: 'Trailing Stop', val: '0.5%', color: 'text-cyan-400', icon: '🛡️' },
    { label: 'Auto Square-Off', val: '15:15 IST', color: 'text-amber-400', icon: '⏰' },
    { label: 'Session', val: '09:15 - 15:30 IST', color: 'text-emerald-400', icon: '📅' },
    { label: 'Overnight Positions', val: 'DISABLED', isBadge: true, icon: '🌙' },
    { label: 'Leverage', val: 'DISABLED', isBadge: true, icon: '⚖️' },
    { label: 'Live Trading', val: 'DISABLED', isBadge: true, icon: '🚫' },
  ];

  return (
    <div className="glass-panel rounded-2xl p-5 border border-white/[0.08] shadow-2xl flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 pb-3 border-b border-white/[0.06] mb-3">
        <span className="text-sm">🛡️</span>
        <h3 className="text-sm font-semibold text-gray-200">
          Risk Engine <span className="text-xs font-normal text-gray-400">(Authoritative)</span>
        </h3>
      </div>

      {/* Rules List */}
      <div className="space-y-2.5 text-xs font-mono">
        {items.map((it) => (
          <div key={it.label} className="flex items-center justify-between py-0.5">
            <div className="flex items-center gap-2 text-gray-300">
              <span className="text-xs opacity-75">{it.icon}</span>
              <span>{it.label}</span>
            </div>

            {it.isBadge ? (
              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-500/10 text-rose-300 border border-rose-500/20">
                {it.val}
              </span>
            ) : (
              <span className={`font-semibold ${it.color}`}>
                {it.val}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
