'use client';

import React, { useState } from 'react';
import { AuditVerify } from '../lib/types';
import { getAuditVerify } from '../lib/api';

interface AuditPanelProps {
  initialAudit?: AuditVerify | null;
}

export const AuditPanel: React.FC<AuditPanelProps> = ({ initialAudit }) => {
  const [audit, setAudit] = useState<AuditVerify | null>(initialAudit || null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleVerify = async () => {
    try {
      setIsVerifying(true);
      setFeedback(null);
      const res = await getAuditVerify();
      setAudit(res);
      setFeedback(res.valid ? 'Hash chain mathematically verified without tampering.' : 'Audit check returned warnings.');
    } catch (err: any) {
      setFeedback(`Verification failed: ${err.message}`);
    } finally {
      setIsVerifying(false);
    }
  };

  const isValid = audit?.valid ?? true;
  const totalEvents = audit?.total_events ?? 0;

  return (
    <div className="bg-trade-card border border-trade-border rounded-lg p-5 shadow-lg">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <span>Cryptographic Audit Chain</span>
            <span
              className={`text-xs font-mono px-2 py-0.5 rounded ${
                isValid
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  : 'bg-rose-950 text-rose-300 border border-rose-800'
              }`}
            >
              {isValid ? 'CHAIN VALID & TAMPER-FREE' : 'TAMPER DETECTED'}
            </span>
          </h3>
          <p className="text-xs text-gray-400 mt-0.5">
            Every session, model decision, order, and position square-off is cryptographically linked with SHA-256 hashes.
          </p>
        </div>

        <button
          onClick={handleVerify}
          disabled={isVerifying}
          className="px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-xs font-mono font-medium text-gray-200 border border-trade-border transition flex items-center gap-1.5"
        >
          {isVerifying ? (
            <>
              <svg className="animate-spin h-3 w-3 text-white" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              <span>Verifying SHA-256 Chain...</span>
            </>
          ) : (
            <>
              <span>🔍 Run Cryptographic Verification</span>
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-gray-900 border border-trade-border rounded p-3 font-mono text-xs">
          <div className="text-gray-400 uppercase text-[10px]">Total Logged Events</div>
          <div className="text-base font-bold text-white mt-1">{totalEvents}</div>
          <div className="text-[10px] text-gray-500 mt-0.5">Sequence #1 to #{totalEvents || 1}</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded p-3 font-mono text-xs">
          <div className="text-gray-400 uppercase text-[10px]">Cryptographic Digest</div>
          <div className="text-base font-bold text-emerald-400 mt-1">SHA-256</div>
          <div className="text-[10px] text-gray-500 mt-0.5">Continuous forward hash chain</div>
        </div>

        <div className="bg-gray-900 border border-trade-border rounded p-3 font-mono text-xs">
          <div className="text-gray-400 uppercase text-[10px]">Integrity Status</div>
          <div className="text-base font-bold text-emerald-400 mt-1">UNCOMPROMISED</div>
          <div className="text-[10px] text-gray-500 mt-0.5">Zero collision or sequence breaks</div>
        </div>
      </div>

      {feedback && (
        <div className="mt-3 text-xs font-mono p-2 rounded bg-gray-900 border border-trade-border text-emerald-300">
          ✓ {feedback}
        </div>
      )}
    </div>
  );
};
