'use client';

import React from 'react';
import { RuntimeStatus } from '../lib/types';

interface ActiveModelCardProps {
  runtime: RuntimeStatus | null;
}

export const ActiveModelCard: React.FC<ActiveModelCardProps> = ({ runtime }) => {
  const isIdle = !runtime || !runtime.is_active || runtime.current_phase === 'IDLE';

  const steps = runtime?.pipeline_steps || [
    { name: 'Load Model', active: false },
    { name: 'Infer', active: false },
    { name: 'Validate', active: false },
    { name: 'Record', active: false },
    { name: 'Unload', active: false },
  ];

  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg relative overflow-hidden">
      {/* Subtle top indicator bar */}
      <div
        className={`absolute top-0 left-0 right-0 h-1 ${
          isIdle ? 'bg-gray-700' : 'bg-gradient-to-r from-blue-500 via-emerald-500 to-indigo-500 animate-pulse'
        }`}
      />

      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-trade-border/60">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase font-mono tracking-wider text-gray-400">
              Live AI Orchestration
            </span>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium ${
                isIdle
                  ? 'bg-gray-800 text-gray-400'
                  : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isIdle ? 'bg-gray-500' : 'bg-emerald-400 animate-ping'}`} />
              {isIdle ? 'IDLE' : 'EXECUTING'}
            </span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight mt-1 flex items-center gap-3">
            {isIdle ? (
              <span className="text-gray-400 font-mono">STANDBY / IDLE</span>
            ) : (
              <span className="text-blue-400 font-mono uppercase">{runtime?.current_model}</span>
            )}
            {runtime?.symbol && (
              <span className="text-sm px-2 py-0.5 rounded bg-gray-800 text-gray-300 font-mono border border-trade-border">
                {runtime.symbol}
              </span>
            )}
          </h2>
        </div>

        {/* Phase & Elapsed Timer */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="bg-gray-900 border border-trade-border px-3 py-2 rounded">
            <div className="text-gray-400">Current Phase</div>
            <div className={`font-semibold text-sm ${isIdle ? 'text-gray-400' : 'text-emerald-400'}`}>
              {runtime?.current_phase || 'IDLE'}
            </div>
          </div>

          <div className="bg-gray-900 border border-trade-border px-3 py-2 rounded">
            <div className="text-gray-400">Elapsed Time</div>
            <div className="font-semibold text-sm text-blue-400">
              {runtime ? `${runtime.elapsed_seconds.toFixed(1)}s` : '0.0s'}
            </div>
          </div>

          {runtime?.session_id && (
            <div className="hidden sm:block bg-gray-900 border border-trade-border px-3 py-2 rounded">
              <div className="text-gray-400">Session ID</div>
              <div className="font-mono text-gray-300 truncate max-w-[140px]" title={runtime.session_id}>
                {runtime.session_id}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Operation Description */}
      <div className="mt-3 flex items-center justify-between text-xs font-mono text-gray-300">
        <span className="text-gray-400">Action:</span>
        <span className="font-mono text-gray-200">{runtime?.current_operation || 'Waiting for next session'}</span>
      </div>

      {/* Step Pipeline Flow */}
      <div className="mt-4 pt-3 border-t border-trade-border/40">
        <div className="text-xs font-mono text-gray-400 mb-2">Sequential Model Execution Pipeline:</div>
        <div className="grid grid-cols-5 gap-2">
          {steps.map((step, idx) => (
            <div
              key={step.name}
              className={`flex flex-col items-center justify-center p-2 rounded border text-center transition-all ${
                step.active
                  ? 'bg-blue-950/80 border-blue-500 text-blue-200 shadow-md shadow-blue-900/30'
                  : 'bg-gray-900/60 border-trade-border text-gray-400'
              }`}
            >
              <span className="text-[10px] font-mono text-gray-500 mb-0.5">0{idx + 1}</span>
              <span className={`text-xs font-mono font-medium ${step.active ? 'text-white' : 'text-gray-400'}`}>
                {step.name}
              </span>
              {step.active && (
                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
