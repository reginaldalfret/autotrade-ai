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
  const [istTime, setIstTime] = useState<string>('11:42:18');
  const [istDate, setIstDate] = useState<string>('Thu, 24 Apr 2025 (IST)');
  const [isMarketOpen, setIsMarketOpen] = useState<boolean>(true);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      // IST time format
      const timeStr = now.toLocaleTimeString('en-GB', {
        timeZone: 'Asia/Kolkata',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      setIstTime(timeStr);

      const dateStr = now.toLocaleDateString('en-GB', {
        timeZone: 'Asia/Kolkata',
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      }) + ' (IST)';
      setIstDate(dateStr);

      // NSE cash market hours 09:15 - 15:30 IST
      const istDateObj = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
      const day = istDateObj.getDay();
      const currentMin = istDateObj.getHours() * 60 + istDateObj.getMinutes();
      const isOpen = day >= 1 && day <= 5 && currentMin >= 9 * 60 + 15 && currentMin <= 15 * 60 + 30;
      setIsMarketOpen(isOpen);
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleRunSession = async () => {
    if (isRunning) return;
    try {
      setIsRunning(true);
      setMsg('Dispatching autonomous paper-trading session...');
      const res = await runSession(['RELIANCE', 'TCS', 'INFY', 'TATAMOTORS']);
      setMsg(`Session launched: ${res.session_id || 'OK'}`);
      setTimeout(() => {
        setMsg(null);
        onRefresh();
      }, 3500);
    } catch (err: any) {
      setMsg(`Error: ${err.message}`);
      setTimeout(() => setMsg(null), 4000);
    } finally {
      setIsRunning(false);
    }
  };

  const ollamaOnline = health?.ollama?.reachable ?? true;

  return (
    <div className="w-full flex items-center justify-between gap-4 py-3 px-6 glass-panel rounded-2xl border border-white/[0.08] shadow-2xl mb-5">
      {/* Left: Liquid Status Badges */}
      <div className="flex items-center flex-wrap gap-2.5">
        {/* API Capsule */}
        <div className="glass-pill px-3 py-1.5 rounded-full flex items-center gap-2 text-xs font-medium text-gray-200">
          <span className={`w-2 h-2 rounded-full ${isApiOnline ? 'bg-emerald-400 shadow-sm shadow-emerald-400/80 animate-pulse' : 'bg-rose-500'}`} />
          <span>{isApiOnline ? 'API Online' : 'API Offline'}</span>
        </div>

        {/* Ollama Capsule */}
        <div className="glass-pill px-3 py-1.5 rounded-full flex items-center gap-2 text-xs font-medium text-gray-200">
          <span className={`w-2 h-2 rounded-full ${ollamaOnline ? 'bg-emerald-400 shadow-sm shadow-emerald-400/80 animate-pulse' : 'bg-amber-400'}`} />
          <span>{ollamaOnline ? 'Ollama Online' : 'Ollama Standby'}</span>
        </div>

        {/* Risk Engine Active Capsule */}
        <div className="glass-pill px-3 py-1.5 rounded-full flex items-center gap-2 text-xs font-medium text-gray-200">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/80 animate-pulse" />
          <span>Risk Engine Active</span>
        </div>

        {/* NSE Market Open Capsule */}
        <div className="glass-pill px-3 py-1.5 rounded-full flex items-center gap-2 text-xs font-medium text-gray-200">
          <span className={`w-2 h-2 rounded-full ${isMarketOpen ? 'bg-emerald-400 shadow-sm shadow-emerald-400/80 animate-pulse' : 'bg-amber-400'}`} />
          <span>{isMarketOpen ? 'NSE Market Open' : 'NSE Session Closed'}</span>
        </div>
      </div>

      {/* Right: Clock & User Avatar */}
      <div className="flex items-center gap-5">
        {/* Run Session Button */}
        <button
          onClick={handleRunSession}
          disabled={isRunning || !isApiOnline}
          className="glass-pill px-3.5 py-1.5 rounded-xl text-xs font-medium text-cyan-300 hover:text-white hover:bg-cyan-500/20 border border-cyan-500/30 transition shadow-sm hover:shadow-cyan-500/30 flex items-center gap-1.5"
        >
          {isRunning ? (
            <>
              <span className="w-3 h-3 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
              <span>Running...</span>
            </>
          ) : (
            <>
              <span>⚡ Run Session</span>
            </>
          )}
        </button>

        {/* IST Clock */}
        <div className="text-right">
          <div className="text-lg font-bold font-mono tracking-tight text-white leading-none">
            {istTime}
          </div>
          <div className="text-[10px] text-gray-400 font-medium mt-0.5">
            {istDate}
          </div>
        </div>

        {/* Glowing Profile Capsule */}
        <div className="flex items-center gap-2.5 glass-pill px-3 py-1.5 rounded-2xl border border-white/[0.08]">
          <div className="relative w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-400 via-violet-500 to-pink-500 p-[1.5px] flex items-center justify-center">
            <div className="w-full h-full bg-[#090D1A] rounded-full flex items-center justify-center overflow-hidden">
              <span className="text-xs">🤖</span>
            </div>
            <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-emerald-400 border border-[#090D1A]" />
          </div>
          <div className="text-left leading-tight hidden sm:block">
            <div className="text-xs font-semibold text-white">AutoTrade AI</div>
            <div className="text-[10px] text-cyan-400 font-mono">Paper Trading Mode</div>
          </div>
        </div>
      </div>

      {msg && (
        <div className="absolute top-16 left-6 right-6 z-50 glass-panel p-2.5 rounded-xl text-xs font-mono text-cyan-300 border border-cyan-500/40 flex items-center justify-between shadow-lg">
          <span>{msg}</span>
          <button onClick={() => setMsg(null)} className="text-gray-400 hover:text-white">✕</button>
        </div>
      )}
    </div>
  );
};
