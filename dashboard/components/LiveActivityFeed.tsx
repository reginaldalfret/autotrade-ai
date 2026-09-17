'use client';

import React from 'react';
import { ActivityEvent } from '../lib/types';

interface LiveActivityFeedProps {
  events: ActivityEvent[];
}

export const LiveActivityFeed: React.FC<LiveActivityFeedProps> = ({ events }) => {
  const getLevelBadge = (level: string) => {
    switch (level) {
      case 'error':
        return 'bg-rose-950 text-rose-300 border-rose-800';
      case 'warning':
        return 'bg-amber-950 text-amber-300 border-amber-800';
      case 'success':
        return 'bg-emerald-950 text-emerald-300 border-emerald-800';
      default:
        return 'bg-blue-950 text-blue-300 border-blue-800';
    }
  };

  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg flex flex-col h-[420px]">
      <div className="flex items-center justify-between pb-3 border-b border-trade-border/60">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <h3 className="text-base font-bold text-white tracking-tight">Live Activity Stream</h3>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-trade-border">
            1-2s Poll
          </span>
        </div>
        <span className="text-xs font-mono text-gray-400">
          Showing {events.length} latest events
        </span>
      </div>

      {/* Terminal Feed Scroll Container */}
      <div className="flex-1 overflow-y-auto mt-3 space-y-2 pr-1 font-mono text-xs">
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-xs">
            No live events recorded yet. Session is idle.
          </div>
        ) : (
          events.map((ev, idx) => (
            <div
              key={`${ev.timestamp}-${idx}`}
              className="p-2.5 rounded bg-gray-900/80 border border-trade-border/70 hover:border-gray-700 transition flex items-start justify-between gap-3"
            >
              <div className="flex items-start gap-2.5 flex-1 min-w-0">
                <span className="text-gray-500 whitespace-nowrap text-[11px] pt-0.5">
                  [{ev.timestamp}]
                </span>

                {ev.model_id && (
                  <span className="px-1.5 py-0.5 rounded bg-gray-800 text-blue-300 text-[10px] uppercase font-semibold whitespace-nowrap">
                    {ev.model_id}
                  </span>
                )}

                {ev.phase && ev.phase !== 'IDLE' && (
                  <span className="px-1.5 py-0.5 rounded bg-gray-800 text-purple-300 text-[10px] uppercase whitespace-nowrap">
                    {ev.phase}
                  </span>
                )}

                <span className="text-gray-300 break-words flex-1 leading-relaxed">
                  {ev.message}
                </span>
              </div>

              <span
                className={`text-[9px] uppercase px-1.5 py-0.5 rounded border font-semibold whitespace-nowrap ${getLevelBadge(
                  ev.level
                )}`}
              >
                {ev.level}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
