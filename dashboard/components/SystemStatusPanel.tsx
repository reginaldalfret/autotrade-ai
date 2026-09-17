'use client';

import React from 'react';

interface SystemStatusPanelProps {
  isApiOnline: boolean;
  isOllamaOnline: boolean;
  isMarketOpen: boolean;
}

export const SystemStatusPanel: React.FC<SystemStatusPanelProps> = ({
  isApiOnline,
  isOllamaOnline,
  isMarketOpen,
}) => {
  return (
    <div className="glass-panel rounded-2xl p-5 border border-white/[0.08] shadow-2xl h-full flex flex-col justify-between">
      {/* Header */}
      <div className="pb-3 border-b border-white/[0.06] mb-3">
        <h3 className="text-sm font-semibold text-gray-200">
          System Status
        </h3>
      </div>

      {/* 4 Status Pills Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {/* API */}
        <div className="glass-panel-subtle rounded-xl p-3 flex flex-col items-center text-center">
          <span className="w-2 h-2 rounded-full bg-emerald-400 mb-1.5 shadow-sm shadow-emerald-400" />
          <div className="text-[11px] font-bold text-white">API</div>
          <div className="text-[9px] text-emerald-400 font-mono mt-0.5">Online</div>
        </div>

        {/* Ollama */}
        <div className="glass-panel-subtle rounded-xl p-3 flex flex-col items-center text-center">
          <span className="w-2 h-2 rounded-full bg-emerald-400 mb-1.5 shadow-sm shadow-emerald-400" />
          <div className="text-[11px] font-bold text-white">Ollama</div>
          <div className="text-[9px] text-emerald-400 font-mono mt-0.5">Online</div>
        </div>

        {/* NSE */}
        <div className="glass-panel-subtle rounded-xl p-3 flex flex-col items-center text-center">
          <span className="w-2 h-2 rounded-full bg-amber-400 mb-1.5 shadow-sm shadow-amber-400" />
          <div className="text-[11px] font-bold text-white">NSE</div>
          <div className="text-[9px] text-emerald-400 font-mono mt-0.5">Open</div>
        </div>

        {/* Database */}
        <div className="glass-panel-subtle rounded-xl p-3 flex flex-col items-center text-center">
          <span className="w-2 h-2 rounded-full bg-cyan-400 mb-1.5 shadow-sm shadow-cyan-400" />
          <div className="text-[11px] font-bold text-white">Database</div>
          <div className="text-[9px] text-cyan-400 font-mono mt-0.5">Connected</div>
        </div>
      </div>
    </div>
  );
};
