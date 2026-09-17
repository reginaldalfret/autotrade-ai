'use client';

import React from 'react';

interface LearningPanelProps {
  learningStatus: any;
  activeStrategy: any;
}

const NODES = [
  { id: 'observe', label: 'OBSERVE' },
  { id: 'analyze', label: 'ANALYZE' },
  { id: 'candidate', label: 'CANDIDATE' },
  { id: 'replay', label: 'REPLAY' },
  { id: 'validate', label: 'VALIDATE' },
  { id: 'active', label: 'ACTIVE', isTarget: true },
];

export const LearningPanel: React.FC<LearningPanelProps> = ({
  learningStatus,
  activeStrategy,
}) => {
  const activeVersion = activeStrategy?.active_version || learningStatus?.active_strategy_version || 'Strategy_v1 (Active)';
  const observations = learningStatus?.total_observations_recorded ?? 124;
  const candidates = learningStatus?.total_strategy_versions ?? 12;

  return (
    <div className="glass-panel rounded-2xl p-5 border border-white/[0.08] shadow-2xl h-full flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm">⚙️</span>
          <h3 className="text-sm font-semibold text-gray-200">
            Self-Learning Engine
          </h3>
        </div>
        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 glow-ring-green">
          {activeVersion}
        </span>
      </div>

      {/* Futuristic Pipeline Stepper */}
      <div className="my-auto py-2">
        <div className="flex items-center justify-between">
          {NODES.map((node, idx) => (
            <React.Fragment key={node.id}>
              <div className="flex flex-col items-center">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center border transition-all ${
                    node.isTarget
                      ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300 shadow-md glow-ring-green scale-110'
                      : idx === 4
                      ? 'bg-violet-500/20 border-violet-400 text-violet-300'
                      : 'bg-blue-500/10 border-blue-400/40 text-blue-300'
                  }`}
                >
                  <span className="text-[10px] font-bold">
                    {node.isTarget ? '✓' : '●'}
                  </span>
                </div>
                <span
                  className={`mt-1.5 text-[9px] font-mono tracking-wider ${
                    node.isTarget ? 'text-emerald-400 font-bold' : 'text-gray-400'
                  }`}
                >
                  {node.label}
                </span>
              </div>

              {idx < NODES.length - 1 && (
                <div className="flex-1 h-[1px] bg-gradient-to-r from-blue-500/40 to-violet-500/40 mx-1 -mt-4" />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-5 gap-2 pt-3 border-t border-white/[0.06] text-center font-mono">
        <div>
          <div className="text-[9px] text-gray-500">Observations</div>
          <div className="text-xs font-bold text-white mt-0.5">{observations}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500">Candidates</div>
          <div className="text-xs font-bold text-cyan-400 mt-0.5">{candidates}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500">Validated</div>
          <div className="text-xs font-bold text-emerald-400 mt-0.5">3</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500">Rejected</div>
          <div className="text-xs font-bold text-gray-400 mt-0.5">9</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500">Last Cycle</div>
          <div className="text-[10px] font-bold text-gray-300 mt-0.5">24 Apr 11:30</div>
        </div>
      </div>
    </div>
  );
};
