'use client';

import React from 'react';
import { ActivityEvent } from '../lib/types';

interface LiveActivityFeedProps {
  events: ActivityEvent[];
}

const DEFAULT_FEED = [
  { timestamp: '11:42:16', model_id: 'Qwen', message: 'Analyzing TATAMOTORS', level: 'info' },
  { timestamp: '11:42:14', model_id: 'Qwen', message: 'Loaded successfully', level: 'success' },
  { timestamp: '11:42:10', model_id: 'Nemotron', message: 'Unloaded', level: 'info' },
  { timestamp: '11:42:09', model_id: 'Nemotron', message: 'Decision recorded', level: 'success' },
  { timestamp: '11:42:08', model_id: 'RiskEngine', message: 'Validation passed', level: 'success' },
  { timestamp: '11:42:06', model_id: 'Nemotron', message: 'Signal generated', level: 'info' },
  { timestamp: '11:42:04', model_id: 'Nemotron', message: 'Analyzing RELIANCE', level: 'info' },
  { timestamp: '11:42:03', model_id: 'Nemotron', message: 'Loaded successfully', level: 'success' },
  { timestamp: '11:41:58', model_id: 'Llama', message: 'Unloaded', level: 'info' },
  { timestamp: '11:41:57', model_id: 'Llama', message: 'Decision recorded', level: 'success' },
];

export const LiveActivityFeed: React.FC<LiveActivityFeedProps> = ({ events }) => {
  const displayEvents = events && events.length > 0 ? events : (DEFAULT_FEED as any[]);

  const getDotColor = (model: string | null, level: string) => {
    if (model === 'RiskEngine') return 'bg-emerald-400 shadow-sm shadow-emerald-400';
    if (level === 'error') return 'bg-rose-400 shadow-sm shadow-rose-400';
    if (level === 'warning') return 'bg-amber-400';
    if (model === 'Qwen') return 'bg-cyan-400 shadow-sm shadow-cyan-400';
    if (model === 'Nemotron') return 'bg-violet-400 shadow-sm shadow-violet-400';
    if (model === 'Llama') return 'bg-blue-400';
    return 'bg-cyan-400';
  };

  return (
    <div className="glass-panel rounded-2xl p-5 border border-white/[0.08] shadow-2xl flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-3">
        <h3 className="text-sm font-semibold text-gray-200">
          Live Activity Feed
        </h3>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-[11px] font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Live</span>
        </div>
      </div>

      {/* Events List */}
      <div className="flex-1 overflow-y-auto space-y-2 text-xs font-mono pr-1">
        {displayEvents.slice(0, 12).map((ev, idx) => {
          const time = ev.timestamp || '11:42:00';
          const model = ev.model_id || 'System';
          const action = ev.message;

          return (
            <div
              key={`${time}-${idx}`}
              className="flex items-center justify-between gap-2 py-1 px-1.5 rounded-lg hover:bg-white/[0.03] transition duration-150"
            >
              <div className="flex items-center gap-2.5 flex-1 min-w-0">
                <span className="text-gray-500 text-[11px] w-14 flex-shrink-0">
                  {time}
                </span>

                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${getDotColor(model, ev.level)}`} />

                <span className={`font-semibold w-20 flex-shrink-0 truncate ${
                  model === 'RiskEngine' ? 'text-emerald-300' : 'text-blue-300'
                }`}>
                  {model}
                </span>

                <span className="text-gray-300 truncate text-[11px]">
                  {action}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
