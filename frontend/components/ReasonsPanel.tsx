"use client";

import React from "react";
import type { RiskScoreResponse, ValidationResult } from "../lib/api/types";
import { RiskBadge } from "./RiskBadge";
import { AlertCircle, Shield, Info } from "lucide-react";

interface ReasonsPanelProps {
  riskScore: RiskScoreResponse | null;
  validation?: ValidationResult | null;
}

export function ReasonsPanel({ riskScore, validation }: ReasonsPanelProps) {
  if (!riskScore) {
    return (
      <div className="bg-surface border border-border rounded p-6 text-center">
        <Shield size={24} className="mx-auto text-text-muted mb-2" />
        <p className="font-mono text-xs text-text-muted">
          Risk scoring breakdown unavailable.
        </p>
      </div>
    );
  }

  const score = riskScore.score || 0;
  const reasons = riskScore.reasons || [];
  const rawSubScores = (riskScore.sub_scores as any) || {};

  const validationScore = Number(rawSubScores.validation_score ?? 0);
  const tamperingScore = Number(rawSubScores.tampering_score ?? 0);
  const faceScore = Number(rawSubScores.face_match_score ?? 0);
  const watchlistScore = Number(
    rawSubScores.blacklist_score ??
    rawSubScores.blacklist_hit_score ??
    rawSubScores.watchlist_score ??
    0
  );

  const formatPct = (val: number) => {
    const num = isNaN(val) ? 0 : val;
    return `${(num * 100).toFixed(0)}%`;
  };

  return (
    <div className="bg-surface border border-border rounded flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b border-border bg-surface-raised flex items-center justify-between">
        <h3 className="font-mono text-[11px] uppercase tracking-wider text-text-muted font-semibold">
          Composite Risk Assessment
        </h3>
        <RiskBadge band={riskScore.band} score={score} size="sm" showScore={false} />
      </div>

      {/* Main Score Centerpiece */}
      <div className="p-4 flex-1 flex flex-col gap-4">
        <div className="flex items-center justify-between bg-bg border border-border rounded p-3">
          <div>
            <div className="font-mono text-[10px] text-text-muted uppercase">
              Calculated Risk Index
            </div>
            <div className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-text mt-0.5">
              {score.toFixed(1)}
              <span className="font-mono text-xs text-text-muted font-normal">
                {" "}
                / 100
              </span>
            </div>
          </div>
          <div className="text-right">
            <RiskBadge band={riskScore.band} score={score} size="md" />
          </div>
        </div>

        {/* Contributing Sub-Scores */}
        <div>
          <h4 className="font-mono text-[10px] uppercase text-text-muted tracking-wider mb-2">
            Module Sub-Scores:
          </h4>
          <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
            <div className="p-2 rounded bg-surface-raised border border-border flex justify-between items-center">
              <span className="text-text-muted">Validation:</span>
              <span
                className={
                  validationScore > 0
                    ? "text-risk-critical font-bold"
                    : "text-brand"
                }
              >
                {formatPct(validationScore)}
              </span>
            </div>

            <div className="p-2 rounded bg-surface-raised border border-border flex justify-between items-center">
              <span className="text-text-muted">Tampering:</span>
              <span
                className={
                  tamperingScore > 0.3
                    ? "text-risk-critical font-bold"
                    : "text-brand"
                }
              >
                {formatPct(tamperingScore)}
              </span>
            </div>

            <div className="p-2 rounded bg-surface-raised border border-border flex justify-between items-center">
              <span className="text-text-muted">Biometrics:</span>
              <span
                className={
                  faceScore > 0.4
                    ? "text-risk-critical font-bold"
                    : "text-brand"
                }
              >
                {formatPct(faceScore)}
              </span>
            </div>

            <div className="p-2 rounded bg-surface-raised border border-border flex justify-between items-center">
              <span className="text-text-muted">Watchlist:</span>
              <span
                className={
                  watchlistScore > 0
                    ? "text-risk-critical font-bold"
                    : "text-brand"
                }
              >
                {formatPct(watchlistScore)}
              </span>
            </div>
          </div>
        </div>


        {/* Human Readable Finding Reasons */}
        <div className="flex-1">
          <h4 className="font-mono text-[10px] uppercase text-text-muted tracking-wider mb-2">
            Automated Findings:
          </h4>
          <div className="space-y-1.5 overflow-y-auto max-h-48">
            {reasons.length > 0 ? (
              reasons.map((reason, idx) => (
                <div
                  key={idx}
                  className="p-2 rounded bg-bg border border-border/80 flex items-start gap-2 text-xs font-body"
                >
                  <Info
                    size={14}
                    className="text-brand shrink-0 mt-0.5"
                    strokeWidth={1.5}
                  />
                  <span className="text-text leading-snug">{reason}</span>
                </div>
              ))
            ) : (
              <div className="p-2 rounded bg-bg border border-border flex items-center gap-2 text-xs text-brand font-body">
                <Info size={14} className="shrink-0" />
                <span>No explanatory findings were returned by the risk service.</span>
              </div>
            )}

            {/* If validation failed rules exist */}
            {validation &&
              validation.failed_rules &&
              validation.failed_rules.length > 0 && (
                <div className="p-2 rounded bg-risk-critical/10 border border-risk-critical/30 space-y-1">
                  <div className="font-mono text-[10px] uppercase text-risk-critical font-bold flex items-center gap-1.5">
                    <AlertCircle size={12} />
                    Failed Validation Rules:
                  </div>
                  {validation.failed_rules.map((ruleName, rIdx) => (
                    <div
                      key={rIdx}
                      className="font-mono text-[11px] text-risk-critical pl-4"
                    >
                      • {ruleName}
                    </div>
                  ))}
                </div>
              )}
          </div>
        </div>
      </div>
    </div>
  );
}
