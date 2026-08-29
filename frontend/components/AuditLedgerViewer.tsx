"use client";

import React, { useState } from "react";
import { Link2, ShieldCheck, ShieldAlert, RefreshCw, Bug, Check, AlertOctagon, Hash } from "lucide-react";

interface LedgerEvent {
  id: string;
  sequence_num: number;
  document_id?: string | null;
  event_type: string;
  payload_hash: string;
  prev_record_hash: string;
  record_hash: string;
  officer_id?: string | null;
  created_at: string;
}

interface VerificationReport {
  valid: boolean;
  total_events: number;
  first_invalid_sequence: number | null;
  detail: string;
}

interface AuditLedgerViewerProps {
  events: LedgerEvent[];
  onVerifyChain: () => Promise<VerificationReport>;
  onCorruptTest?: () => void;
  loading: boolean;
}

export const AuditLedgerViewer: React.FC<AuditLedgerViewerProps> = ({
  events = [],
  onVerifyChain,
  onCorruptTest,
  loading,
}) => {
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [verifying, setVerifying] = useState<boolean>(false);

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await onVerifyChain();
      setReport(res);
    } catch (e) {
      console.error(e);
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Verification Action Header */}
      <div className="glass-panel p-5 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <span className="text-[11px] font-mono text-slate-400 uppercase block">
            MODULE 6 — IMMUTABLE CRYPTOGRAPHIC AUDIT LEDGER
          </span>
          <h3 className="text-base font-bold font-mono text-slate-100 mt-1">
            SHA-256 Merkle-Style Hash Chain
          </h3>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Every scan and officer decision is mathematically linked. Zero unauthorized retroactive mutations.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-end sm:self-auto">
          {onCorruptTest && (
            <button
              onClick={onCorruptTest}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-950/60 hover:bg-red-900/80 border border-red-500/40 text-red-300 text-xs font-mono transition-all"
              title="Simulates tampering with a past block to prove detection"
            >
              <Bug className="w-3.5 h-3.5 text-red-400" />
              <span>Simulate Attack</span>
            </button>
          )}

          <button
            onClick={handleVerify}
            disabled={verifying || loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-bold shadow-lg shadow-cyan-600/30 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${verifying ? "animate-spin" : ""}`} />
            <span>Verify Chain Integrity</span>
          </button>
        </div>
      </div>

      {/* Verification Report Banner */}
      {report && (
        <div className={`p-4 rounded-xl border font-mono text-xs transition-all ${
          report.valid
            ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-300"
            : "bg-red-950/40 border-red-500/50 text-red-300"
        }`}>
          <div className="flex items-center gap-3">
            {report.valid ? (
              <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
            ) : (
              <AlertOctagon className="w-5 h-5 text-red-400 shrink-0" />
            )}
            <div className="flex-1">
              <span className="font-bold block text-sm">
                {report.valid ? "✅ CRYPTOGRAPHIC INTEGRITY VERIFIED: 100% VALID" : "🚨 TAMPERING DETECTED! HASH CHAIN BROKEN"}
              </span>
              <span className="text-xs opacity-90 mt-0.5 block">{report.detail}</span>
              <span className="text-[10px] opacity-75 mt-1 block">
                Total blocks audited: <strong>{report.total_events}</strong>
                {report.first_invalid_sequence && (
                  <> • First corrupt sequence: <strong>#{report.first_invalid_sequence}</strong></>
                )}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Hash Chain Block Sequence */}
      <div className="glass-panel rounded-xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link2 className="w-4 h-4 text-cyan-400" />
            <h4 className="text-xs font-bold font-mono tracking-wider text-slate-300 uppercase">
              Sequential Ledger Blocks
            </h4>
          </div>
          <span className="text-[10px] font-mono text-slate-500">
            {events.length} RECORDED BLOCKS
          </span>
        </div>

        {events.length === 0 ? (
          <div className="p-8 text-center text-xs font-mono text-slate-500">
            No audit ledger events recorded yet. Run a document scan or log an officer decision.
          </div>
        ) : (
          <div className="divide-y divide-slate-800/60 font-mono text-xs">
            {events.map((evt, idx) => (
              <div key={idx} className="p-4 hover:bg-slate-900/30 transition-colors space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 font-bold text-[11px]">
                      BLOCK #{evt.sequence_num}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] uppercase font-semibold">
                      {evt.event_type}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500">
                    {new Date(evt.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px] bg-slate-950/60 p-2.5 rounded-lg border border-slate-900">
                  <div>
                    <span className="text-[9px] text-slate-500 block uppercase">Payload SHA-256</span>
                    <span className="text-slate-300 font-mono break-all">{evt.payload_hash.slice(0, 16)}...</span>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 block uppercase">Previous Record Hash</span>
                    <span className="text-slate-400 font-mono break-all">{evt.prev_record_hash.slice(0, 16)}...</span>
                  </div>
                  <div>
                    <span className="text-[9px] text-cyan-400 block uppercase">Block Record Hash</span>
                    <span className="text-cyan-300 font-bold font-mono break-all">{evt.record_hash.slice(0, 16)}...</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
