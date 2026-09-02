"use client";

import React, { useEffect } from "react";
import { CheckCircle, AlertTriangle, ShieldAlert, Lock } from "lucide-react";
import { useAuth } from "../lib/auth/AuthContext";

interface DecisionActionsProps {
  onApprove: () => void;
  onEscalate: () => void;
  onDetain: () => void;
  isSubmitting?: boolean;
  disabled?: boolean;
  disabledReason?: string;
}

export function DecisionActions({
  onApprove,
  onEscalate,
  onDetain,
  isSubmitting = false,
  disabled = false,
  disabledReason,
}: DecisionActionsProps) {
  const { role } = useAuth();
  const isAuditor = role === "auditor";
  const isActionBlocked = isAuditor || isSubmitting || disabled;

  // Keyboard shortcut listener for rapid officer triage
  useEffect(() => {
    if (isActionBlocked) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input/textarea
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;

      if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        onApprove();
      } else if (e.key === "e" || e.key === "E") {
        e.preventDefault();
        onEscalate();
      } else if (e.key === "d" || e.key === "D") {
        e.preventDefault();
        onDetain();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onApprove, onEscalate, onDetain, isActionBlocked]);

  if (isAuditor) {
    return (
      <div className="p-3 bg-surface-raised border border-border rounded text-center font-mono text-xs text-text-muted">
        Auditor Mode: Read-only inspection clearance (decision recording restricted).
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {disabled && (
        <div className="p-2.5 rounded bg-risk-medium/10 border border-risk-medium/30 flex items-center gap-2 text-risk-medium font-mono text-[11px]">
          <Lock size={13} className="shrink-0" />
          <span>{disabledReason || "Biometric facial verification required before recording final decision."}</span>
        </div>
      )}

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        {/* 1. Detain (Critical Action) */}
        <button
          type="button"
          disabled={isActionBlocked}
          onClick={onDetain}
          className="flex-1 h-11 px-4 rounded bg-surface border border-risk-critical/60 hover:bg-risk-critical/15 text-risk-critical font-display text-xs font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ShieldAlert size={16} strokeWidth={2} />
          <span>Detain [D]</span>
        </button>

        {/* 2. Escalate to Secondary */}
        <button
          type="button"
          disabled={isActionBlocked}
          onClick={onEscalate}
          className="flex-1 h-11 px-4 rounded bg-surface border border-risk-medium/60 hover:bg-risk-medium/15 text-risk-medium font-display text-xs font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <AlertTriangle size={16} strokeWidth={2} />
          <span>Escalate [E]</span>
        </button>

        {/* 3. Approve Entry (Primary) */}
        <button
          type="button"
          disabled={isActionBlocked}
          onClick={onApprove}
          className="flex-1 sm:flex-[1.4] h-11 px-6 rounded bg-brand hover:bg-white text-bg font-display text-xs font-bold uppercase tracking-wider transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_12px_rgba(166,255,77,0.3)] disabled:shadow-none"
        >
          <CheckCircle size={16} strokeWidth={2.5} />
          <span>Approve Entry [↵]</span>
        </button>
      </div>
    </div>
  );
}

