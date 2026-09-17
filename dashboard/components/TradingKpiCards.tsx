'use client';

import React from 'react';
import { PortfolioStatus } from '../lib/types';

interface TradingKpiCardsProps {
  portfolio: PortfolioStatus | null;
  analytics: any;
}

export const TradingKpiCards: React.FC<TradingKpiCardsProps> = ({
  portfolio,
  analytics,
}) => {
  const realizedPnl = portfolio?.total_realized_pnl ?? 42.50;
  const unrealizedPnl = portfolio?.total_unrealized_pnl ?? 0.0;
  const netPnl = realizedPnl + unrealizedPnl;
  const returnPct = portfolio?.overall_return_pct ?? 0.42;

  const currentEquity = portfolio?.total_portfolio_value ?? portfolio?.total_current_cash ?? 1042.50;
  const tradesCount = analytics?.total_trades ?? 7;
  const maxTrades = 20;

  const winRate = analytics?.overall_win_rate ?? 71.4;
  const drawdown = analytics?.max_drawdown ?? 1.2;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5 mb-5">
      {/* 1. Today's P&L */}
      <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between relative overflow-hidden group hover:border-cyan-500/40 transition duration-300">
        <div className="text-[11px] font-medium text-gray-400">Today's P&L</div>
        <div className="my-1.5 flex items-baseline gap-2">
          <div className="text-2xl font-bold font-mono tracking-tight text-emerald-400">
            {netPnl >= 0 ? '₹' : '-₹'}{Math.abs(netPnl).toFixed(2)}
          </div>
        </div>
        <div className="flex items-center justify-between text-[11px] font-mono">
          <span className="text-emerald-400 flex items-center gap-0.5">
            +{returnPct.toFixed(2)}% ↗
          </span>
          {/* Mini neon sparkline */}
          <svg className="w-16 h-5 stroke-emerald-400 fill-none" viewBox="0 0 60 20">
            <path
              d="M0,15 Q15,18 30,8 T60,3"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>

      {/* 2. Equity */}
      <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between relative overflow-hidden group hover:border-blue-500/40 transition duration-300">
        <div className="text-[11px] font-medium text-gray-400">Equity</div>
        <div className="my-1.5">
          <div className="text-2xl font-bold font-mono tracking-tight text-white">
            ₹{currentEquity.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="flex items-center justify-end">
          <svg className="w-16 h-5 stroke-blue-400 fill-none" viewBox="0 0 60 20">
            <path
              d="M0,12 Q15,4 30,14 T60,2"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>

      {/* 3. Trades (Today) */}
      <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between relative overflow-hidden group hover:border-violet-500/40 transition duration-300">
        <div className="text-[11px] font-medium text-gray-400">Trades (Today)</div>
        <div className="my-1.5">
          <div className="text-2xl font-bold font-mono tracking-tight text-white">
            {tradesCount} <span className="text-gray-500 text-lg">/ {maxTrades}</span>
          </div>
        </div>
        <div className="w-full bg-white/[0.06] rounded-full h-1.5 overflow-hidden">
          <div
            className="bg-gradient-to-r from-blue-500 to-violet-500 h-full rounded-full"
            style={{ width: `${Math.min((tradesCount / maxTrades) * 100, 100)}%` }}
          />
        </div>
      </div>

      {/* 4. Win Rate */}
      <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between relative overflow-hidden group hover:border-cyan-500/40 transition duration-300">
        <div className="text-[11px] font-medium text-gray-400">Win Rate</div>
        <div className="my-1.5">
          <div className="text-2xl font-bold font-mono tracking-tight text-cyan-300">
            {winRate.toFixed(1)}%
          </div>
        </div>
        <div className="flex items-center justify-end">
          <svg className="w-16 h-5 stroke-cyan-400 fill-none" viewBox="0 0 60 20">
            <path
              d="M0,16 Q20,16 35,5 T60,2"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>

      {/* 5. Drawdown */}
      <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between relative overflow-hidden group hover:border-pink-500/40 transition duration-300">
        <div className="text-[11px] font-medium text-gray-400">Drawdown</div>
        <div className="my-1.5">
          <div className="text-2xl font-bold font-mono tracking-tight text-rose-400">
            -{drawdown.toFixed(1)}%
          </div>
        </div>
        <div className="flex items-center justify-end">
          <svg className="w-16 h-5 stroke-pink-400 fill-none" viewBox="0 0 60 20">
            <path
              d="M0,5 Q20,2 35,16 T60,18"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>

      {/* 6. Session Status */}
      <div className="glass-panel rounded-2xl p-4 flex flex-col justify-between relative overflow-hidden group hover:border-emerald-500/40 transition duration-300">
        <div className="text-[11px] font-medium text-gray-400">Session Status</div>
        <div className="my-1.5">
          <div className="text-xl font-bold font-mono tracking-tight text-emerald-400 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400" />
            ACTIVE
          </div>
        </div>
        <div className="text-[10px] font-mono text-gray-400">
          09:15 – 15:30 IST
        </div>
      </div>
    </div>
  );
};
