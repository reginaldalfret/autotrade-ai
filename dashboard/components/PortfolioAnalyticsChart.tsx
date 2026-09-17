'use client';

import React from 'react';

export const PortfolioAnalyticsChart: React.FC = () => {
  return (
    <div className="glass-panel rounded-2xl p-5 border border-white/[0.08] shadow-2xl h-full flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-3">
        <h3 className="text-sm font-semibold text-gray-200">
          Portfolio & Analytics
        </h3>
        <button className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.05] border border-white/10 text-[10px] font-mono text-gray-300 hover:text-white">
          <span>Today</span>
          <span className="text-[8px]">▼</span>
        </button>
      </div>

      {/* Chart Canvas with SVG */}
      <div className="relative flex-1 flex flex-col justify-between py-1">
        {/* Y-Axis Labels + Horizontal Grid Lines */}
        <div className="relative w-full h-40">
          <div className="absolute inset-0 flex flex-col justify-between text-[9px] font-mono text-gray-600 pointer-events-none">
            <div className="flex items-center justify-between">
              <span>1,060</span>
              <div className="flex-1 border-b border-white/[0.03] ml-2" />
            </div>
            <div className="flex items-center justify-between">
              <span>1,040</span>
              <div className="flex-1 border-b border-white/[0.03] ml-2" />
            </div>
            <div className="flex items-center justify-between">
              <span>1,020</span>
              <div className="flex-1 border-b border-white/[0.03] ml-2" />
            </div>
            <div className="flex items-center justify-between">
              <span>1,000</span>
              <div className="flex-1 border-b border-white/[0.03] ml-2" />
            </div>
            <div className="flex items-center justify-between">
              <span>980</span>
              <div className="flex-1 border-b border-white/[0.03] ml-2" />
            </div>
          </div>

          {/* Glowing Neon Chart Curve */}
          <svg className="absolute inset-0 w-full h-full pl-8 overflow-visible" preserveAspectRatio="none" viewBox="0 0 300 120">
            <defs>
              <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00F0FF" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#00F0FF" stopOpacity="0.0" />
              </linearGradient>
              <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#00F0FF" floodOpacity="0.6" />
              </filter>
            </defs>

            {/* Gradient Area */}
            <path
              d="M0,105 Q30,110 60,95 T120,80 T180,55 T240,30 T300,15 L300,120 L0,120 Z"
              fill="url(#chartGradient)"
            />

            {/* Vibrant Line */}
            <path
              d="M0,105 Q30,110 60,95 T120,80 T180,55 T240,30 T300,15"
              fill="none"
              stroke="#00F0FF"
              strokeWidth="2.5"
              strokeLinecap="round"
              filter="url(#neonGlow)"
            />

            {/* Active End Dot */}
            <circle cx="300" cy="15" r="4" fill="#00F0FF" filter="url(#neonGlow)" />
            <circle cx="300" cy="15" r="2" fill="#FFFFFF" />
          </svg>
        </div>

        {/* X-Axis Labels */}
        <div className="flex items-center justify-between text-[9px] font-mono text-gray-500 pl-8 pt-2">
          <span>09:15</span>
          <span>10:00</span>
          <span>11:00</span>
          <span>12:00</span>
          <span>13:00</span>
          <span>14:00</span>
          <span>15:30</span>
        </div>
      </div>
    </div>
  );
};
