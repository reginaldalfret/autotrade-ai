'use client';

import React from 'react';

interface LearningPanelProps {
  learningStatus: any;
  activeStrategy: any;
}

const FLOW_STEPS = [
  { name: 'OBSERVE', desc: 'Scan trade log & anomalies' },
  { name: 'ANALYZE', desc: 'Diagnose systematic loss patterns' },
  { name: 'CANDIDATE', desc: 'Generate parametric tweaks' },
  { name: 'REPLAY', desc: 'Deterministic backtest replay' },
  { name: 'VALIDATE', desc: 'Out-of-sample statistical gate' },
  { name: 'ACTIVATE', desc: 'Versioned promotion with audit hash' },
];

export const LearningPanel: React.FC<LearningPanelProps> = ({
  learningStatus,
  activeStrategy,
}) => {
  const activeVersion = activeStrategy?.active_version || learningStatus?.active_strategy_version || 'strategy_v1';
  const totalObs = learningStatus?.total_observations_recorded || 0;
  const calibratedProfiles = learningStatus?.model_profiles_calibrated || 0;
  const versionsCount = learningStatus?.total_strategy_versions || 1;

  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>Self-Learning & Continuous Improvement</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
              Deterministic Replay Gate
            </span>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Controlled parametric strategy calibration through historical replay. Autonomous code rewriting is prohibited.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-gray-400">Active Version:</span>
          <span className="px-2.5 py-1 rounded bg-blue-950 text-blue-300 border border-blue-800 text-xs font-mono font-bold">
            {activeVersion}
          </span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Strategy Versions</div>
          <div className="text-lg font-bold font-mono text-white mt-0.5">{versionsCount}</div>
          <div className="text-[10px] text-gray-500 font-mono">Immutable config chain</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Observations</div>
          <div className="text-lg font-bold font-mono text-blue-400 mt-0.5">{totalObs}</div>
          <div className="text-[10px] text-gray-500 font-mono">Diagnosed trade slips</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Calibrated Profiles</div>
          <div className="text-lg font-bold font-mono text-emerald-400 mt-0.5">{calibratedProfiles}</div>
          <div className="text-[10px] text-gray-500 font-mono">Model behavior weights</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Safety Enforcer</div>
          <div className="text-lg font-bold font-mono text-emerald-400 mt-0.5">ACTIVE</div>
          <div className="text-[10px] text-gray-500 font-mono">Zero-leakage boundary</div>
        </div>
      </div>

      {/* Self-Learning Sequential Pipeline Flow */}
      <div className="mb-4">
        <div className="text-xs font-mono text-gray-400 mb-2">Self-Learning Verification Flow:</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {FLOW_STEPS.map((step, idx) => (
            <div
              key={step.name}
              className="bg-gray-900/90 border border-trade-border rounded p-2.5 text-center flex flex-col justify-between"
            >
              <div>
                <span className="text-[10px] font-mono text-blue-400 font-bold block">
                  0{idx + 1}. {step.name}
                </span>
                <span className="text-[10px] text-gray-400 mt-1 block leading-tight">
                  {step.desc}
                </span>
              </div>
              <span className="mt-2 text-[9px] font-mono text-emerald-400 bg-emerald-950/80 px-1.5 py-0.5 rounded border border-emerald-900">
                LOCKED SAFE
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Hard Safety Note */}
      <div className="p-3 bg-amber-950/40 border border-amber-900/60 rounded text-xs font-mono text-amber-200/90 leading-relaxed flex items-start gap-2.5">
        <span className="text-amber-400 text-base leading-none">⚠️</span>
        <div>
          <span className="font-bold text-amber-300">RiskEngine Immutability Invariant:</span> Hard safety limits
          (-5% max daily loss, +10% profit cap, 20 max trades, 15:15 IST square-off, 09:15–15:30 IST session, unleveraged intraday)
          are hardcoded in Python and CANNOT be learned, relaxed, or overridden by any machine learning model or candidate strategy.
        </div>
      </div>
    </div>
  );
};
