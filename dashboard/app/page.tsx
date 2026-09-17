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

import { Sidebar } from '../components/Sidebar';
import { TopStatusBar } from '../components/TopStatusBar';
import { TradingKpiCards } from '../components/TradingKpiCards';
import { ActiveModelCard } from '../components/ActiveModelCard';
import { LiveActivityFeed } from '../components/LiveActivityFeed';
import { RiskEnginePanel } from '../components/RiskEnginePanel';
import { ModelMonitor } from '../components/ModelMonitor';
import { LearningPanel } from '../components/LearningPanel';
import { PositionsTable } from '../components/PositionsTable';
import { TradesTable } from '../components/TradesTable';
import { PortfolioAnalyticsChart } from '../components/PortfolioAnalyticsChart';
import { AuditPanel } from '../components/AuditPanel';
import { ReportsPanel } from '../components/ReportsPanel';
import { SystemStatusPanel } from '../components/SystemStatusPanel';

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
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

  const [isApiOnline, setIsApiOnline] = useState<boolean>(true);

  // Fast Poller (1.5s): Live runtime status & live activity stream
  const pollFastData = useCallback(async () => {
    try {
      const [rt, act] = await Promise.all([
        getRuntimeStatus(),
        getActivityFeed(40),
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
        getTrades(50),
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
    } catch (err) {
      // Handled silently
    }
  }, []);

  useEffect(() => {
    pollFastData();
    pollSlowData();

    const fastInterval = setInterval(pollFastData, 1500);
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

  const isOllamaOnline = health?.ollama?.reachable ?? true;

  return (
    <div className="relative min-h-screen flex bg-[#05070D] text-gray-100 selection:bg-cyan-500 selection:text-black">
      {/* 1. Subtle Ambient RGB Background Layer */}
      <div className="ambient-bg" aria-hidden="true">
        <div className="ambient-orb orb-cyan" />
        <div className="ambient-orb orb-blue" />
        <div className="ambient-orb orb-violet" />
        <div className="ambient-orb orb-magenta" />
      </div>

      {/* 2. Floating Liquid Glass Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        isMarketOpen={true}
      />

      {/* 3. Main Dashboard Workspace */}
      <div className="flex-1 flex flex-col p-4 sm:p-5 relative z-10 max-w-[1750px] overflow-hidden">
        {/* Top Header Bar */}
        <TopStatusBar
          health={health}
          risk={risk}
          isApiOnline={isApiOnline}
          onRefresh={handleManualRefresh}
        />

        {/* Row 1: 6 Top KPI Metrics */}
        <TradingKpiCards
          portfolio={portfolio}
          analytics={analytics}
        />

        {/* Row 2: Current AI Activity (Hero) | Live Activity Feed | Risk Engine */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-4">
          <div className="lg:col-span-5 h-[360px]">
            <ActiveModelCard runtime={runtime} />
          </div>
          <div className="lg:col-span-4 h-[360px]">
            <LiveActivityFeed events={events} />
          </div>
          <div className="lg:col-span-3 h-[360px]">
            <RiskEnginePanel risk={risk} />
          </div>
        </div>

        {/* Row 3: Model Status (8 Local LLMs) | Self-Learning Engine */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-4">
          <div className="lg:col-span-8">
            <ModelMonitor
              runtime={runtime}
              accounts={portfolio?.accounts}
              analytics={analytics}
            />
          </div>
          <div className="lg:col-span-4">
            <LearningPanel
              learningStatus={learningStatus}
              activeStrategy={learningStrategy}
            />
          </div>
        </div>

        {/* Row 4: Open Positions | Trade History | Portfolio & Analytics Chart */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          <div>
            <PositionsTable positions={positions} />
          </div>
          <div>
            <TradesTable trades={trades} />
          </div>
          <div>
            <PortfolioAnalyticsChart />
          </div>
        </div>

        {/* Row 5: Audit Chain | Reports | System Status */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          <div>
            <AuditPanel initialAudit={audit} />
          </div>
          <div>
            <ReportsPanel reports={reports} />
          </div>
          <div>
            <SystemStatusPanel
              isApiOnline={isApiOnline}
              isOllamaOnline={isOllamaOnline}
              isMarketOpen={true}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
