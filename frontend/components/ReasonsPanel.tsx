"use client";

import React from "react";
import { CheckCircle2, AlertCircle, ShieldAlert, FileSearch, Sparkles } from "lucide-react";

interface ReasonsPanelProps {
  reasons: string[];
  band: string;
}

export const ReasonsPanel: React.FC<ReasonsPanelProps> = ({ reasons, band }) => {
  const isClean = !reasons || reasons.length === 0 || (reasons.length === 1 && reasons[0].toLowerCase().includes("all checks passed"));

  return (
    <div className="glass-panel p-5 rounded-xl">
      <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <FileSearch className="w-4 h-4 text-cyan-400" />
          <h4 className="text-sm font-bold font-mono tracking-wider text-slate-200 uppercase">
            AI Explainability & Signal Rationale
          </h4>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">
          {reasons.length} FINDING{reasons.length !== 1 ? "S" : ""}
        </span>
      </div>

      {isClean ? (
        <div className="flex items-center gap-3 p-3.5 rounded-lg bg-emerald-950/20 border border-emerald-500/30 text-emerald-400">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          <span className="text-xs font-mono font-medium">
            All forensic indicators nominal. No tampering anomalies, rule violations, or watchlist matches detected.
          </span>
        </div>
      ) : (
        <div className="space-y-2.5">
          {reasons.map((reason, idx) => {
            const isCritical = reason.toLowerCase().includes("blacklist") || reason.toLowerCase().includes("tampering") || reason.toLowerCase().includes("mismatch");
            return (
              <div
                key={idx}
                className={`flex items-start gap-3 p-3 rounded-lg border text-xs font-mono transition-all ${
                  isCritical
                    ? "bg-red-950/30 border-red-500/40 text-red-300"
                    : "bg-amber-950/30 border-amber-500/40 text-amber-300"
                }`}
              >
                {isCritical ? (
                  <ShieldAlert className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                )}
                <div className="flex-1">
                  <span className="leading-relaxed">{reason}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
