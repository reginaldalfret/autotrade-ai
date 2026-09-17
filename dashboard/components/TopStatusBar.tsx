'use client';

import React, { useState, useEffect } from 'react';
import { HealthStatus, RiskStatus } from '../lib/types';
import { runSession } from '../lib/api';

interface TopStatusBarProps {
  health: HealthStatus | null;
  risk: RiskStatus | null;
  isApiOnline: boolean;
  onRefresh: () => void;
}

export const TopStatusBar: React.FC<TopStatusBarProps> = ({
  health,
  risk,
  isApiOnline,
  onRefresh,
}) => {
  const [istTime, setIstTime] = useState<string>('');
  const [isMarketOpen, setIsMarketOpen] = useState<boolean>(false);
  const [isRunningSession, setIsRunningSession] = useState<boolean>(false);
  const [sessionMsg, setSessionMsg] = useState<string | null>(null);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      // Calculate IST time (UTC+5:30)
      const istOptions: Intl.DateTimeFormatOptions = {
        timeZone: 'Asia/Kolkata',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      };
      const timeStr = now.toLocaleTimeString('en-GB', istOptions);
      setIstTime(timeStr);

      // Check NSE cash market hours 09:15 - 15:30 IST, Mon-Fri
      const istDate = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
      const day = istDate.getDay(); // 0 = Sun, 6 = Sat
      const hours = istDate.getHours();
      const mins = istDate.getMinutes();
      const currentMinOfDay = hours * 60 + mins;

      const isWeekday = day >= 1 && day <= 5;
      const isOpen = isWeekday && currentMinOfDay >= 9 * 60 + 15 && currentMinOfDay <= 15 * 60 + 30;
      setIsMarketOpen(isOpen);
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleRunSession = async () => {
    if (isRunningSession) return;
    try {
      setIsRunningSession(true);
      setSessionMsg('Dispatching paper trading session...');
      const res = await runSession(['RELIANCE', 'TCS', 'INFY']);
      setSessionMsg(`Session started: ${res.session_id || 'OK'}`);
      setTimeout(() => {
        setSessionMsg(null);
        onRefresh();
      }, 3000);
    } catch (err: any) {
      setSessionMsg(`Error: ${err.message}`);
      setTimeout(() => setSessionMsg(null), 4000);
    } finally {
      setIsRunningSession(false);
    }
  };

  const ollamaOnline = health?.ollama?.reachable ?? false;

  return (
    <header className="bg-trade-card border-b border-trade-border px-6 py-3 sticky top-0 z-50">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Brand & Market Status */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xl font-bold tracking-tight text-white flex items-center gap-1.5">
              AUTOTRADE <span className="text-blue-400 font-mono">AI</span>
            </span>
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
              v1.0 Local
            </span>
          </div>

          <div className="hidden md:flex items-center gap-2 pl-4 border-l border-trade-border">
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                isMarketOpen
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  : 'bg-amber-950 text-amber-300 border border-amber-800'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isMarketOpen ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              NSE {isMarketOpen ? 'MARKET OPEN (09:15 - 15:30 IST)' : 'SESSION CLOSED (INTRADAY)'}
            </span>
          </div>
        </div>

        {/* Live System Badges & Clock */}
        <div className="flex items-center flex-wrap gap-3 text-xs font-mono">
          {/* IST Time */}
          <div className="px-3 py-1.5 rounded bg-gray-900 border border-trade-border text-gray-200">
            <span className="text-gray-400 mr-1.5">IST:</span>
            <span className="font-semibold text-emerald-400">{istTime || '09:15:00'}</span>
          </div>

          {/* FastAPI Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-gray-900 border border-trade-border">
            <span className={`w-2 h-2 rounded-full ${isApiOnline ? 'bg-emerald-500' : 'bg-red-500'}`} />
            <span className="text-gray-400">API:</span>
            <span className={isApiOnline ? 'text-emerald-400' : 'text-red-400'}>
              {isApiOnline ? '127.0.0.1:8000' : 'DISCONNECTED'}
            </span>
          </div>

          {/* Ollama Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-gray-900 border border-trade-border">
            <span className={`w-2 h-2 rounded-full ${ollamaOnline ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span className="text-gray-400">Ollama:</span>
            <span className={ollamaOnline ? 'text-emerald-400' : 'text-amber-400'}>
              {ollamaOnline ? 'READY' : 'STANDBY'}
            </span>
          </div>

          {/* RiskEngine Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-gray-900 border border-trade-border">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-gray-400">RiskEngine:</span>
            <span className="text-emerald-400 font-semibold">ENFORCING</span>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 pl-2">
            <button
              onClick={handleRunSession}
              disabled={isRunningSession || !isApiOnline}
              className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium transition duration-150 flex items-center gap-1.5 shadow-sm"
            >
              {isRunningSession ? (
                <>
                  <svg className="animate-spin h-3.5 w-3.5 text-white" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  <span>Running...</span>
                </>
              ) : (
                <>
                  <span>▶ Run Paper Session</span>
                </>
              )}
            </button>

            <button
              onClick={onRefresh}
              className="px-2.5 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium border border-trade-border transition"
              title="Manual Refresh"
            >
              ↻
            </button>
          </div>
        </div>
      </div>

      {sessionMsg && (
        <div className="mt-2 text-xs font-mono py-1 px-3 bg-blue-950/80 border border-blue-800 text-blue-200 rounded animate-fade-in flex items-center justify-between">
          <span>{sessionMsg}</span>
          <button onClick={() => setSessionMsg(null)} className="text-blue-400 hover:text-white ml-2">✕</button>
        </div>
      )}
    </header>
  );
};
