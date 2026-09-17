'use client';

import React from 'react';
import { PortfolioStatus } from '../lib/types';

interface TradingMonitorProps {
  portfolio: PortfolioStatus | null;
}

export const TradingMonitor: React.FC<TradingMonitorProps> = ({ portfolio }) => {
  const totalInitial = portfolio?.total_initial_capital || 800000;
  const currentEquity = portfolio?.total_portfolio_value || portfolio?.total_current_cash || 800000;
  const cash = portfolio?.total_current_cash || 800000;
  const realizedPnl = portfolio?.total_realized_pnl || 0.0;
  const unrealizedPnl = portfolio?.total_unrealized_pnl || 0.0;
  const netPnl = realizedPnl + unrealizedPnl;
  const returnPct = totalInitial > 0 ? (netPnl / totalInitial) * 100 : 0.0;
  const openPositions = portfolio?.open_positions_count || 0;

  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>Trading & Portfolio Monitor</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
              NSE Cash Intraday
            </span>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Strict non-margin 1x cash market execution across 8 isolated virtual trading accounts.
          </p>
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Initial Capital</div>
          <div className="text-lg font-bold font-mono text-white mt-1">
            ₹{totalInitial.toLocaleString('en-IN')}
          </div>
          <div className="text-[10px] text-gray-500 font-mono mt-0.5">₹1L × 8 models</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Total Equity</div>
          <div className="text-lg font-bold font-mono text-blue-400 mt-1">
            ₹{currentEquity.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[10px] text-gray-500 font-mono mt-0.5">Live Mark-to-Market</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Available Cash</div>
          <div className="text-lg font-bold font-mono text-gray-200 mt-1">
            ₹{cash.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[10px] text-emerald-400 font-mono mt-0.5">100% Unleveraged</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Realized P&L</div>
          <div className={`text-lg font-bold font-mono mt-1 ${realizedPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            ₹{realizedPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[10px] text-gray-500 font-mono mt-0.5">Net of statutory STT/brokerage</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Total Return</div>
          <div className={`text-lg font-bold font-mono mt-1 ${returnPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(2)}%
          </div>
          <div className="text-[10px] text-gray-500 font-mono mt-0.5">Target: +10% | Max Loss: -5%</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded-lg p-3">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Open Positions</div>
          <div className="text-lg font-bold font-mono text-purple-300 mt-1">
            {openPositions}
          </div>
          <div className="text-[10px] text-gray-500 font-mono mt-0.5">Hard 15:15 IST Square-off</div>
        </div>
      </div>

      {/* Virtual Accounts Table */}
      <div className="border border-trade-border/80 rounded-lg overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-gray-900 text-gray-400 uppercase text-[10px] border-b border-trade-border">
            <tr>
              <th className="px-4 py-2.5">Virtual Account / Model</th>
              <th className="px-4 py-2.5">Allocated Capital</th>
              <th className="px-4 py-2.5">Current Cash</th>
              <th className="px-4 py-2.5">Realized P&L</th>
              <th className="px-4 py-2.5">Total Equity</th>
              <th className="px-4 py-2.5">Return %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-trade-border/40 text-gray-300">
            {portfolio?.accounts && Object.keys(portfolio.accounts).length > 0 ? (
              Object.entries(portfolio.accounts).map(([id, acc]: [string, any]) => {
                const pnl = acc.realized_pnl || 0;
                const ret = acc.return_pct || (pnl / (acc.initial_capital || 100000)) * 100;
                return (
                  <tr key={id} className="hover:bg-gray-900/50 transition">
                    <td className="px-4 py-2 font-semibold text-white uppercase">{id}</td>
                    <td className="px-4 py-2">₹{(acc.initial_capital || 100000).toLocaleString('en-IN')}</td>
                    <td className="px-4 py-2">₹{(acc.current_cash || 100000).toLocaleString('en-IN')}</td>
                    <td className={`px-4 py-2 font-semibold ${pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      ₹{pnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-2">₹{(acc.total_equity || 100000).toLocaleString('en-IN')}</td>
                    <td className={`px-4 py-2 font-semibold ${ret >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {ret >= 0 ? '+' : ''}{ret.toFixed(2)}%
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={6} className="px-4 py-4 text-center text-gray-500">
                  8 virtual accounts initialized at ₹1,00,000 each.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
