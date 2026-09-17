// API Client for AutoTrade AI Dashboard
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
  ModelTournamentRecord,
} from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    // Avoid caching for real-time polling
    cache: 'no-store',
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${errorText}`);
  }

  return res.json();
}

export async function getRuntimeStatus(): Promise<RuntimeStatus> {
  return fetchJson<RuntimeStatus>('/runtime/status');
}

export async function getActivityFeed(limit: number = 50): Promise<{ count: number; events: ActivityEvent[] }> {
  return fetchJson<{ count: number; events: ActivityEvent[] }>(`/activity?limit=${limit}`);
}

export async function getCurrentActivity(): Promise<{ status: RuntimeStatus; recent_events: ActivityEvent[] }> {
  return fetchJson<{ status: RuntimeStatus; recent_events: ActivityEvent[] }>('/activity/current');
}

export async function getHealth(): Promise<HealthStatus> {
  return fetchJson<HealthStatus>('/health');
}

export async function getModels(): Promise<any> {
  return fetchJson<any>('/models');
}

export async function getPortfolio(): Promise<PortfolioStatus> {
  return fetchJson<PortfolioStatus>('/portfolio');
}

export async function getPositions(): Promise<{ count: number; positions: Position[] }> {
  return fetchJson<{ count: number; positions: Position[] }>('/positions');
}

export async function getTrades(limit: number = 50, modelId?: string): Promise<{ count: number; trades: Trade[] }> {
  const query = new URLSearchParams({ limit: limit.toString() });
  if (modelId && modelId !== 'all') {
    query.append('model_id', modelId);
  }
  return fetchJson<{ count: number; trades: Trade[] }>(`/trades?${query.toString()}`);
}

export async function getRisk(): Promise<RiskStatus> {
  return fetchJson<RiskStatus>('/risk');
}

export async function getAnalytics(): Promise<any> {
  return fetchJson<any>('/analytics');
}

export async function getAuditVerify(): Promise<AuditVerify> {
  return fetchJson<AuditVerify>('/audit/verify');
}

export async function getReports(): Promise<{ count: number; reports: ReportItem[] }> {
  return fetchJson<{ count: number; reports: ReportItem[] }>('/reports');
}

export function getReportDownloadUrl(reportId: string): string {
  return `${API_BASE_URL}/reports/${reportId}/download`;
}

export async function getLearningStatus(): Promise<any> {
  return fetchJson<any>('/learning/status');
}

export async function getLearningStrategy(): Promise<any> {
  return fetchJson<any>('/learning/strategy');
}

export async function getLearningCandidates(): Promise<any> {
  return fetchJson<any>('/learning/candidates');
}

export async function getLearningObservations(): Promise<any> {
  return fetchJson<any>('/learning/observations');
}

export async function runSession(symbols: string[] = ['RELIANCE', 'TCS', 'INFY']): Promise<any> {
  return fetchJson<any>('/session/run', {
    method: 'POST',
    body: JSON.stringify({ symbols }),
  });
}
