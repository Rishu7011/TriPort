"use client";

import React, { useState } from "react";
import type { DecisionVerdict } from "../lib/api/types";
import {
  AlertOctagon,
  AlertTriangle,
  X,
  Lock,
  CheckSquare,
  Square,
} from "lucide-react";

interface DecisionConfirmModalProps {
  isOpen: boolean;
  verdict: DecisionVerdict;
  documentId: string;
  travelerName: string;
  riskScore: number;
  onClose: () => void;
  onConfirm: (notes: string) => Promise<void>;
}

export function DecisionConfirmModal({
  isOpen,
  verdict,
  documentId,
  travelerName,
  riskScore,
  onClose,
  onConfirm,
}: DecisionConfirmModalProps) {
  const [notes, setNotes] = useState("");
  const [protocolChecked, setProtocolChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const isDetain = verdict === "detain";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!protocolChecked) return;
    setSubmitting(true);
    try {
      await onConfirm(notes);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs"
    >
      <div className="bg-surface border border-border rounded-md max-w-lg w-full overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-150 relative">
        {/* Top Warning Accent Bar */}
        <div
          className={`h-1.5 w-full ${
            isDetain ? "bg-risk-critical" : "bg-risk-high"
          }`}
        />

        {/* Modal Header */}
        <div className="p-5 border-b border-border bg-surface-raised flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                isDetain
                  ? "bg-risk-critical/15 text-risk-critical border border-risk-critical/40"
                  : "bg-risk-high/15 text-risk-high border border-risk-high/40"
              }`}
            >
              {isDetain ? <AlertOctagon size={22} /> : <AlertTriangle size={22} />}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display font-bold text-base text-text uppercase tracking-tight">
                  CONFIRM {verdict.toUpperCase()} PROTOCOL
                </h3>
              </div>
              <p className="font-mono text-xs text-text-muted mt-0.5">
                Target: {travelerName} • Doc UUID: {documentId.substring(0, 8)}...
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="text-text-muted hover:text-text p-1 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Risk Alert Box */}
          <div
            className={`p-3 rounded border font-mono text-xs ${
              isDetain
                ? "bg-risk-critical/10 border-risk-critical/30 text-risk-critical"
                : "bg-risk-high/10 border-risk-high/30 text-risk-high"
            }`}
          >
            <div className="font-bold flex items-center justify-between">
              <span>Automated Risk Score: {riskScore.toFixed(1)}/100</span>
              <span className="uppercase">
                {isDetain ? "CRITICAL THREAT LEVEL" : "ELEVATED ANOMALY"}
              </span>
            </div>
            <p className="mt-1 font-body text-text text-xs leading-relaxed">
              {isDetain
                ? "Apprehension protocol triggered. Security dispatch and supervisory units will receive immediate push dispatch."
                : "Traveler routed to secondary biometric interrogation kiosk for physical document substrate review."}
            </p>
          </div>

          {/* Officer Mandatory Notes */}
          <div>
            <label className="block font-mono text-[11px] uppercase tracking-wider text-text-muted mb-1.5 font-semibold">
              Officer Enforcement Justification / Notes (Immutable Record)
            </label>
            <textarea
              required
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Detail reasons for detainment/escalation, physical observations, or interview discrepancy..."
              className="w-full p-3 bg-bg border border-border rounded text-text font-mono text-xs placeholder:text-text-muted/60 focus:border-brand focus:ring-1 focus:ring-brand outline-none resize-none"
            />
          </div>

          {/* Verification Protocol Checkbox */}
          <div
            onClick={() => setProtocolChecked(!protocolChecked)}
            className="flex items-start gap-3 p-3 rounded bg-surface-raised border border-border cursor-pointer select-none"
          >
            <div className="mt-0.5 text-brand">
              {protocolChecked ? (
                <CheckSquare size={18} className="text-brand" />
              ) : (
                <Square size={18} className="text-text-muted" />
              )}
            </div>
            <div className="text-xs">
              <span className="font-display font-bold uppercase text-text block">
                Mandatory Officer Acknowledgment
              </span>
              <span className="font-body text-text-muted text-[11px] leading-snug">
                I verify that I have reviewed the forensic ELA heatmap, ICAO
                checksum results, and biometric facial match before committing this
                verdict to the permanent ledger.
              </span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded bg-surface-raised hover:bg-border text-text font-mono text-xs uppercase tracking-wider transition-colors cursor-pointer"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={!protocolChecked || submitting}
              className={`px-5 py-2 rounded font-display text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-2 cursor-pointer ${
                isDetain
                  ? "bg-risk-critical hover:bg-white text-white hover:text-bg disabled:opacity-40"
                  : "bg-risk-high hover:bg-white text-bg disabled:opacity-40"
              }`}
            >
              <Lock size={14} />
              <span>
                {submitting
                  ? "Writing to Ledger..."
                  : `Commit ${verdict.toUpperCase()}`}
              </span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
