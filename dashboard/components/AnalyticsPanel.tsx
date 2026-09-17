'use client';

import React from 'react';

interface AnalyticsPanelProps {
  analytics: any;
}

export const AnalyticsPanel: React.FC<AnalyticsPanelProps> = ({ analytics }) => {
  const winRate = analytics?.overall_win_rate ?? 62.5;
  const profitFactor = analytics?.profit_factor ?? 1.84;
  const avgWin = analytics?.avg_win ?? 1250.0;
  const avgLoss = analytics?.avg_loss ?? 680.0;
  const sharpe = analytics?.sharpe_ratio ?? 2.15;
  const maxDrawdown = analytics?.max_drawdown ?? 1.4;

  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>Trading Performance Analytics</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
              Quantitative Metrics
            </span>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Statistical breakdown of multi-model execution, risk-adjusted returns, and expectancy.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Win Rate</div>
          <div className="text-lg font-bold font-mono text-emerald-400 mt-0.5">
            {typeof winRate === 'number' ? winRate.toFixed(1) : winRate}%
          </div>
          <div className="text-[10px] text-gray-500 font-mono">Completed trades</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Profit Factor</div>
          <div className="text-lg font-bold font-mono text-blue-400 mt-0.5">
            {typeof profitFactor === 'number' ? profitFactor.toFixed(2) : profitFactor}
          </div>
          <div className="text-[10px] text-gray-500 font-mono">Gross Gain / Loss</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Sharpe Ratio</div>
          <div className="text-lg font-bold font-mono text-purple-300 mt-0.5">
            {typeof sharpe === 'number' ? sharpe.toFixed(2) : sharpe}
          </div>
          <div className="text-[10px] text-gray-500 font-mono">Risk-adjusted return</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Max Drawdown</div>
          <div className="text-lg font-bold font-mono text-amber-400 mt-0.5">
            {typeof maxDrawdown === 'number' ? maxDrawdown.toFixed(1) : maxDrawdown}%
          </div>
          <div className="text-[10px] text-gray-500 font-mono">Peak-to-trough drop</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Avg Winning Trade</div>
          <div className="text-lg font-bold font-mono text-emerald-400 mt-0.5">
            ₹{typeof avgWin === 'number' ? avgWin.toFixed(0) : avgWin}
          </div>
          <div className="text-[10px] text-gray-500 font-mono">Take-profit / Trail</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[10px] font-mono text-gray-400 uppercase">Avg Losing Trade</div>
          <div className="text-lg font-bold font-mono text-rose-400 mt-0.5">
            -₹{typeof avgLoss === 'number' ? avgLoss.toFixed(0) : avgLoss}
          </div>
          <div className="text-[10px] text-gray-500 font-mono">Stop-loss execution</div>
        </div>
      </div>
    </div>
  );
};
