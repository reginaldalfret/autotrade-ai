'use client';

import React from 'react';
import { RiskStatus } from '../lib/types';

interface RiskEnginePanelProps {
  risk: RiskStatus | null;
}

export const RiskEnginePanel: React.FC<RiskEnginePanelProps> = ({ risk }) => {
  const rules = [
    { label: 'Max Daily Loss Limit', value: '-5.0%', status: 'ENFORCED', note: 'Account locked on breach' },
    { label: 'Daily Profit Target Cap', value: '+10.0%', status: 'ENFORCED', note: 'Session halts on target reach' },
    { label: 'Max Trades Per Day', value: '20 Orders', status: 'ENFORCED', note: 'Caps churn and overtrading' },
    { label: 'Mandatory Square-off', value: '15:15 IST', status: 'ENFORCED', note: 'All intraday positions closed' },
    { label: 'Trading Session Window', value: '09:15 - 15:30', status: 'ENFORCED', note: 'Strict NSE market hours' },
    { label: 'Overnight Positions', value: 'DISABLED', status: 'PROHIBITED', note: 'Zero overnight carry risk' },
    { label: 'Leverage / Margin', value: 'DISABLED', status: 'PROHIBITED', note: 'Strict 1x cash market only' },
    { label: 'Live Broker Execution', value: 'DISABLED', status: 'SAFEGUARD', note: 'Paper-trading engine authority' },
  ];

  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>RiskEngine Authority & Guardrails</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
              Final Authority: Active
            </span>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Every AI model trade order must pass RiskEngine validation before paper execution. Zero exceptions.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {rules.map((rule) => {
          const isEnforced = rule.status === 'ENFORCED';
          const isProhibited = rule.status === 'PROHIBITED';

          return (
            <div
              key={rule.label}
              className="bg-gray-900/90 border border-trade-border rounded-lg p-3.5 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-mono text-gray-400 uppercase leading-tight">
                    {rule.label}
                  </span>
                  <span
                    className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-semibold ${
                      isEnforced
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : isProhibited
                        ? 'bg-rose-950 text-rose-300 border border-rose-800'
                        : 'bg-blue-950 text-blue-300 border border-blue-800'
                    }`}
                  >
                    {rule.status}
                  </span>
                </div>
                <div className="text-base font-bold font-mono text-white mt-1.5">
                  {rule.value}
                </div>
              </div>

              <div className="text-[10px] font-mono text-gray-500 mt-2 pt-2 border-t border-trade-border/40">
                {rule.note}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
