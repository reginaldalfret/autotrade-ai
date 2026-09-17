'use client';

import React from 'react';
import { RuntimeStatus } from '../lib/types';

interface ActiveModelCardProps {
  runtime: RuntimeStatus | null;
}

const STEPS = ['LOAD', 'INFER', 'VALIDATE', 'RECORD', 'UNLOAD'];

export const ActiveModelCard: React.FC<ActiveModelCardProps> = ({ runtime }) => {
  const isIdle = !runtime || !runtime.is_active || runtime.current_phase === 'IDLE';

  const modelName = runtime?.current_model && runtime.current_model !== 'IDLE'
    ? `${runtime.current_model.toUpperCase()} 2.5 CODER 1.5B`
    : 'QWEN 2.5 CODER 1.5B';

  const currentPhase = isIdle ? 'INFERENCE' : runtime.current_phase;
  const currentSymbol = runtime?.symbol || 'TATAMOTORS';
  const sessionId = runtime?.session_id || 'session_20250424_001';
  const startedAt = runtime?.started_at ? runtime.started_at.split('T')[1]?.slice(0, 8) : '11:42:16';
  const elapsed = runtime?.elapsed_seconds ? `${runtime.elapsed_seconds.toFixed(2)}s` : '1.42s';

  // Determine active step index
  let activeIndex = 1; // default 'INFER'
  if (runtime?.current_phase === 'LOAD') activeIndex = 0;
  else if (runtime?.current_phase === 'INFERENCE') activeIndex = 1;
  else if (runtime?.current_phase === 'VALIDATION') activeIndex = 2;
  else if (runtime?.current_phase === 'RECORD') activeIndex = 3;
  else if (runtime?.current_phase === 'UNLOAD') activeIndex = 4;

  return (
    <div className="glass-panel rounded-2xl p-6 relative overflow-hidden border border-white/[0.09] shadow-2xl flex flex-col justify-between h-full">
      {/* Background radial gradient glow */}
      <div className="absolute -top-20 -right-20 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-20 -left-20 w-80 h-80 bg-violet-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-300 tracking-wide">
          Current AI Activity
        </h3>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-sm shadow-cyan-400" />
          <span className="text-xs font-mono text-cyan-400">Sequential Single-LLM</span>
        </div>
      </div>

      {/* Centerpiece: Glowing Circular Dial & Model Info */}
      <div className="flex items-center gap-6 my-auto py-2">
        {/* Futuristic glowing circular dial */}
        <div className="relative w-24 h-24 flex-shrink-0 flex items-center justify-center">
          {/* Outer gradient ring */}
          <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-cyan-400 via-violet-500 to-pink-500 p-[2.5px] animate-spin-slow glow-ring-cyan">
            <div className="w-full h-full bg-[#080C17] rounded-full" />
          </div>
          {/* Inner ring */}
          <div className="relative w-16 h-16 rounded-full bg-[#0E1322] border border-white/10 flex items-center justify-center shadow-inner">
            <div className="w-3 h-3 rounded-full bg-cyan-400 shadow-md shadow-cyan-400/80 animate-ping" />
          </div>
        </div>

        {/* Model Execution Details */}
        <div className="space-y-1.5 flex-1">
          <div className="flex items-center gap-2.5">
            <span className="text-xl sm:text-2xl font-extrabold text-white tracking-tight font-sans">
              {modelName}
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
              LLM
            </span>
          </div>

          <div className="flex items-center gap-2 text-sm font-mono font-semibold">
            <span className="w-2 h-2 rounded-full bg-violet-400 shadow-sm shadow-violet-400 animate-pulse" />
            <span className="text-violet-300">{currentPhase}</span>
          </div>

          <div className="text-xs text-gray-400 font-mono">
            Analyzing <span className="text-gray-200 font-semibold">{currentSymbol}</span>
          </div>
        </div>
      </div>

      {/* Pipeline Stepper */}
      <div className="my-5 pt-3 border-t border-white/[0.06]">
        <div className="relative flex items-center justify-between">
          {/* Connecting Line */}
          <div className="absolute top-1/2 left-0 right-0 h-[2px] bg-white/[0.08] -translate-y-1/2 z-0" />
          <div
            className="absolute top-1/2 left-0 h-[2px] bg-gradient-to-r from-cyan-400 to-blue-500 -translate-y-1/2 z-0 transition-all duration-500"
            style={{ width: `${(activeIndex / (STEPS.length - 1)) * 100}%` }}
          />

          {STEPS.map((step, idx) => {
            const isCompleted = idx < activeIndex;
            const isCurrent = idx === activeIndex;

            return (
              <div key={step} className="relative z-10 flex flex-col items-center">
                <div
                  className={`w-4 h-4 rounded-full border-2 transition-all duration-300 flex items-center justify-center ${
                    isCurrent
                      ? 'bg-cyan-400 border-white shadow-md shadow-cyan-400/90 scale-125'
                      : isCompleted
                      ? 'bg-blue-600 border-blue-400'
                      : 'bg-[#0E1322] border-white/20'
                  }`}
                >
                  {isCompleted && <span className="text-[8px] text-white">✓</span>}
                </div>
                <span
                  className={`mt-2 text-[10px] font-mono tracking-wider transition-colors ${
                    isCurrent
                      ? 'text-cyan-300 font-bold'
                      : isCompleted
                      ? 'text-gray-300'
                      : 'text-gray-600'
                  }`}
                >
                  {step}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom Metadata Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3 border-t border-white/[0.06] text-xs font-mono">
        <div>
          <div className="text-[10px] text-gray-500">Session ID</div>
          <div className="text-gray-300 truncate font-semibold" title={sessionId}>{sessionId}</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500">Started At</div>
          <div className="text-gray-300 font-semibold">{startedAt}</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500">Elapsed</div>
          <div className="text-cyan-400 font-semibold">{elapsed}</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500">Current Symbol</div>
          <div className="text-gray-200 font-semibold">{currentSymbol}</div>
        </div>
      </div>
    </div>
  );
};
