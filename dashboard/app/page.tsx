'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  RuntimeStatus,
  ActivityEvent,
  HealthStatus,
  PortfolioStatus,
  Position,
  Trade,
  RiskStatus,
  AuditVerify,
  ReportItem,
} from '../lib/types';
import {
  getRuntimeStatus,
  getActivityFeed,
  getHealth,
  getPortfolio,
  getPositions,
  getTrades,
  getRisk,
  getAnalytics,
  getAuditVerify,
  getReports,
  getLearningStatus,
  getLearningStrategy,
} from '../lib/api';

import { TopStatusBar } from '../components/TopStatusBar';
import { ActiveModelCard } from '../components/ActiveModelCard';
import { ModelMonitor } from '../components/ModelMonitor';
import { LiveActivityFeed } from '../components/LiveActivityFeed';
import { TradingMonitor } from '../components/TradingMonitor';
import { PositionsTable } from '../components/PositionsTable';
import { TradesTable } from '../components/TradesTable';
import { LearningPanel } from '../components/LearningPanel';
import { RiskEnginePanel } from '../components/RiskEnginePanel';
import { AuditPanel } from '../components/AuditPanel';
import { AnalyticsPanel } from '../components/AnalyticsPanel';
import { ReportsPanel } from '../components/ReportsPanel';

export default function DashboardPage() {
  // State definitions
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioStatus | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [risk, setRisk] = useState<RiskStatus | null>(null);
  const [analytics, setAnalytics] = useState<any>(null);
  const [audit, setAudit] = useState<AuditVerify | null>(null);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [learningStatus, setLearningStatus] = useState<any>(null);
  const [learningStrategy, setLearningStrategy] = useState<any>(null);

  const [selectedModel, setSelectedModel] = useState<string>('all');
  const [isApiOnline, setIsApiOnline] = useState<boolean>(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  // Fast Poller (1.5s): Live runtime status & live activity stream
  const pollFastData = useCallback(async () => {
    try {
      const [rt, act] = await Promise.all([
        getRuntimeStatus(),
        getActivityFeed(60),
      ]);
      setRuntime(rt);
      if (act?.events) {
        setEvents(act.events);
      }
      setIsApiOnline(true);
    } catch (err) {
      setIsApiOnline(false);
    }
  }, []);

  // Slower Poller (5s): Portfolio, Positions, Trades, Analytics, Risk
  const pollSlowData = useCallback(async () => {
    try {
      const [
        hlth,
        port,
        pos,
        trd,
        rsk,
        anl,
        aud,
        rep,
        lrn,
        strat,
      ] = await Promise.allSettled([
        getHealth(),
        getPortfolio(),
        getPositions(),
        getTrades(100),
        getRisk(),
        getAnalytics(),
        getAuditVerify(),
        getReports(),
        getLearningStatus(),
        getLearningStrategy(),
      ]);

      if (hlth.status === 'fulfilled') setHealth(hlth.value);
      if (port.status === 'fulfilled') setPortfolio(port.value);
      if (pos.status === 'fulfilled') setPositions(pos.value?.positions || []);
      if (trd.status === 'fulfilled') setTrades(trd.value?.trades || []);
      if (rsk.status === 'fulfilled') setRisk(rsk.value);
      if (anl.status === 'fulfilled') setAnalytics(anl.value);
      if (aud.status === 'fulfilled') setAudit(aud.value);
      if (rep.status === 'fulfilled') setReports(rep.value?.reports || []);
      if (lrn.status === 'fulfilled') setLearningStatus(lrn.value);
      if (strat.status === 'fulfilled') setLearningStrategy(strat.value);

      setLastUpdated(new Date());
    } catch (err) {
      // Handled silently by Promise.allSettled
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    pollFastData();
    pollSlowData();

    // Fast timer: 1500ms
    const fastInterval = setInterval(pollFastData, 1500);

    // Slow timer: 5000ms
    const slowInterval = setInterval(pollSlowData, 5000);

    return () => {
      clearInterval(fastInterval);
      clearInterval(slowInterval);
    };
  }, [pollFastData, pollSlowData]);

  const handleManualRefresh = () => {
    pollFastData();
    pollSlowData();
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* 1. TOP STATUS BAR */}
      <TopStatusBar
        health={health}
        risk={risk}
        isApiOnline={isApiOnline}
        onRefresh={handleManualRefresh}
      />

      {/* Disconnection Notice Banner if API is offline */}
      {!isApiOnline && (
        <div className="bg-rose-950/80 border-b border-rose-800 text-rose-200 px-6 py-2 text-xs font-mono flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
            <span>FastAPI service at 127.0.0.1:8000 is unreachable. Make sure backend is running: <code>python -m mobitrade.cli serve</code></span>
          </div>
          <button
            onClick={handleManualRefresh}
            className="px-2 py-0.5 rounded bg-rose-800 hover:bg-rose-700 text-white text-[11px]"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Main Container */}
      <main className="flex-1 p-6 space-y-6 max-w-[1800px] mx-auto w-full">
        {/* Row 1: Active Model Pipeline Card & Live Terminal Feed */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 flex flex-col justify-between">
            <ActiveModelCard runtime={runtime} />
            <div className="mt-6">
              <AnalyticsPanel analytics={analytics} />
            </div>
          </div>
          <div className="lg:col-span-5">
            <LiveActivityFeed events={events} />
          </div>
        </div>

        {/* Row 2: 8-Model Tournament Roster Monitor */}
        <ModelMonitor
          runtime={runtime}
          accounts={portfolio?.accounts}
          analytics={analytics}
        />

        {/* Row 3: Trading Monitor (KPIs & 8 Virtual Accounts) */}
        <TradingMonitor portfolio={portfolio} />

        {/* Row 4: Open Positions Table & Historical Trades Table */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PositionsTable positions={positions} />
          <TradesTable
            trades={trades}
            selectedModel={selectedModel}
            onModelSelect={setSelectedModel}
          />
        </div>

        {/* Row 5: Self-Learning Continuous Improvement Panel */}
        <LearningPanel
          learningStatus={learningStatus}
          activeStrategy={learningStrategy}
        />

        {/* Row 6: RiskEngine Hard Rules Panel */}
        <RiskEnginePanel risk={risk} />

        {/* Row 7: Audit Chain Verification & Reports Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <AuditPanel initialAudit={audit} />
          <ReportsPanel reports={reports} />
        </div>
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-trade-border px-6 py-3 bg-trade-card text-xs font-mono text-gray-500 flex items-center justify-between">
        <div>AutoTrade AI · Local Autonomous Multi-Model Paper Trading Console · Phase 12</div>
        <div>Last polled: {lastUpdated.toLocaleTimeString()}</div>
      </footer>
    </div>
  );
}
