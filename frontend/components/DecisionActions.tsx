"use client";

import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Send, Lock, FileSignature } from "lucide-react";

interface DecisionActionsProps {
  documentId?: string | null;
  onDecisionSubmitted: (decision: "approve" | "flag" | "reject", notes: string) => Promise<void>;
  loading: boolean;
  disabled?: boolean;
}

export const DecisionActions: React.FC<DecisionActionsProps> = ({
  documentId,
  onDecisionSubmitted,
  loading,
  disabled = false,
}) => {
  const [selectedDecision, setSelectedDecision] = useState<"approve" | "flag" | "reject" | null>(null);
  const [notes, setNotes] = useState<string>("");
  const [submitted, setSubmitted] = useState<string | null>(null);

  const handleSubmit = async (decision: "approve" | "flag" | "reject") => {
    setSelectedDecision(decision);
    try {
      await onDecisionSubmitted(decision, notes || `Decision logged via Officer Console: ${decision.toUpperCase()}`);
      setSubmitted(decision);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <FileSignature className="w-4 h-4 text-cyan-400" />
          <h4 className="text-xs font-bold font-mono tracking-wider text-slate-200 uppercase">
            Official Officer Adjudication Deck
          </h4>
        </div>
        {documentId && (
          <span className="text-[10px] font-mono text-slate-400">
            Target Doc: <strong className="text-slate-200">{documentId.slice(0, 8)}...</strong>
          </span>
        )}
      </div>

      {submitted ? (
        <div className="p-4 rounded-xl bg-slate-900/90 border border-cyan-500/40 text-center space-y-2">
          <div className="inline-flex p-2 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-500/30">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h5 className="text-sm font-bold font-mono text-white">
            DECISION IMMUTABLY COMMITTED TO AUDIT LEDGER
          </h5>
          <p className="text-xs font-mono text-slate-400">
            Action: <strong className="text-cyan-400 uppercase">{submitted}</strong> • Cryptographic block hash linked to chain.
          </p>
          <button
            onClick={() => { setSubmitted(null); setNotes(""); }}
            className="mt-2 text-xs font-mono text-slate-400 hover:text-slate-200 underline"
          >
            Log another entry / edit decision
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="text-[11px] font-mono text-slate-400 block mb-1.5 uppercase">
              Officer Operational Notes / Override Justification
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Physical security features inspected under UV light. Verified visa validity..."
              rows={2}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-lg p-2.5 text-xs font-mono text-slate-200 placeholder-slate-600 focus:border-cyan-500/50 outline-none transition-colors"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Clear & Approve */}
            <button
              onClick={() => handleSubmit("approve")}
              disabled={disabled || loading || !documentId}
              className="flex items-center justify-center gap-2 p-3 rounded-lg bg-emerald-950/60 hover:bg-emerald-900/80 border border-emerald-500/50 text-emerald-300 font-mono text-xs font-bold transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-emerald-950/40 hover:shadow-emerald-500/20"
            >
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>APPROVE CLEARANCE</span>
            </button>

            {/* Flag Secondary */}
            <button
              onClick={() => handleSubmit("flag")}
              disabled={disabled || loading || !documentId}
              className="flex items-center justify-center gap-2 p-3 rounded-lg bg-amber-950/60 hover:bg-amber-900/80 border border-amber-500/50 text-amber-300 font-mono text-xs font-bold transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-amber-950/40 hover:shadow-amber-500/20"
            >
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span>FLAG SECONDARY</span>
            </button>

            {/* Deny Border Entry */}
            <button
              onClick={() => handleSubmit("reject")}
              disabled={disabled || loading || !documentId}
              className="flex items-center justify-center gap-2 p-3 rounded-lg bg-red-950/60 hover:bg-red-900/80 border border-red-500/50 text-red-300 font-mono text-xs font-bold transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-red-950/40 hover:shadow-red-500/20"
            >
              <XCircle className="w-4 h-4 text-red-400" />
              <span>DENY ENTRY</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
