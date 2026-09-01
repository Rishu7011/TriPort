"use client";

import React, { useState } from "react";
import type { TamperingResult } from "../lib/api/types";
import { Sparkles, AlertOctagon, CheckCircle2, Layers } from "lucide-react";

interface TamperingHeatmapProps {
  tampering: TamperingResult | null;
  rawImageUrl?: string;
}

function formatCheckDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (typeof detail === "number" || typeof detail === "boolean") {
    return String(detail);
  }

  if (detail && typeof detail === "object") {
    const summary = (detail as Record<string, unknown>).detail;
    if (typeof summary === "string") return summary;

    try {
      return JSON.stringify(detail);
    } catch {
      return "Structured forensic data available.";
    }
  }

  return "No detail provided.";
}

export function TamperingHeatmap({
  tampering,
  rawImageUrl,
}: TamperingHeatmapProps) {
  const [showHeatmap, setShowHeatmap] = useState(true);

  if (!tampering) {
    return (
      <div className="bg-surface border border-border rounded p-6 text-center">
        <Sparkles size={24} className="mx-auto text-text-muted mb-2" />
        <p className="font-mono text-xs text-text-muted">
          Tampering analysis unavailable.
        </p>
      </div>
    );
  }

  const scorePct = Math.round(tampering.tampering_score * 100);
  const isFlagged = tampering.flagged || scorePct > 35;
  const heatmapData = tampering.ela_heatmap_base64
    ? tampering.ela_heatmap_base64.startsWith("data:")
      ? tampering.ela_heatmap_base64
      : `data:image/png;base64,${tampering.ela_heatmap_base64}`
    : null;

  return (
    <div className="bg-surface border border-border rounded flex flex-col h-full overflow-hidden">
      {/* Header with ELA Toggle */}
      <div className="p-3 border-b border-border bg-surface-raised flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-mono text-[11px] uppercase tracking-wider text-text-muted font-semibold">
            Forensic Tampering & ELA
          </h3>
          {isFlagged ? (
            <span className="font-mono text-[10px] text-risk-critical bg-risk-critical/10 border border-risk-critical/30 px-1.5 py-0.5 rounded">
              ANOMALY DETECTED
            </span>
          ) : (
            <span className="font-mono text-[10px] text-brand bg-brand/10 border border-brand/30 px-1.5 py-0.5 rounded">
              PASS
            </span>
          )}
        </div>

        {/* Toggle View */}
        {heatmapData && (
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-text-muted uppercase">
              ELA Overlay
            </span>
            <button
              type="button"
              onClick={() => setShowHeatmap(!showHeatmap)}
              className={`w-9 h-5 rounded-full relative transition-colors cursor-pointer border ${
                showHeatmap
                  ? "bg-brand/20 border-brand"
                  : "bg-surface-raised border-border"
              }`}
            >
              <div
                className={`w-3.5 h-3.5 rounded-full transition-transform absolute top-[2px] ${
                  showHeatmap
                    ? "right-[3px] bg-brand"
                    : "left-[3px] bg-text-muted"
                }`}
              />
            </button>
          </div>
        )}
      </div>

      {/* Main Forensic Display */}
      <div className="p-4 flex flex-col gap-4 flex-1">
        {/* Heatmap / Scan Preview Container */}
        <div className="relative w-full h-44 bg-bg border border-border rounded overflow-hidden flex items-center justify-center group">
          {heatmapData && showHeatmap ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={heatmapData}
              alt="Error Level Analysis Heatmap"
              className="w-full h-full object-contain mix-blend-screen"
            />
          ) : rawImageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={rawImageUrl}
              alt="Document Scan"
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="flex flex-col items-center gap-2 text-text-muted">
              <Layers size={28} strokeWidth={1.5} className="text-text-muted" />
              <span className="font-mono text-xs">
                Uniform Error Level Distribution
              </span>
            </div>
          )}

          {/* Technical scanline overlay */}
          <div
            className="absolute inset-0 pointer-events-none opacity-30"
            style={{
              background:
                "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(166,255,77,0.08) 2px, rgba(166,255,77,0.08) 4px)",
            }}
          />

          <div className="absolute bottom-2 right-2 bg-bg/90 border border-border px-2 py-0.5 rounded font-mono text-[10px] text-text-muted">
            {showHeatmap && heatmapData ? "Mode: ELA Heatmap (85Q)" : "Mode: Visual Zone"}
          </div>
        </div>

        {/* Score and Checks Breakdown */}
        <div className="space-y-2">
          <div className="flex items-center justify-between font-mono text-xs">
            <span className="text-text-muted">Tampering Score:</span>
            <span
              className={`font-bold ${
                isFlagged ? "text-risk-critical" : "text-brand"
              }`}
            >
              {scorePct}% ({isFlagged ? "Elevated" : "Clean"})
            </span>
          </div>

          <div className="w-full h-1.5 bg-bg rounded-full overflow-hidden border border-border">
            <div
              className={`h-full transition-all duration-300 ${
                isFlagged ? "bg-risk-critical" : "bg-brand"
              }`}
              style={{ width: `${Math.min(100, Math.max(5, scorePct))}%` }}
            />
          </div>

          {/* Forensic Checks List */}
          <div className="pt-2 divide-y divide-border/60">
            {tampering.checks && tampering.checks.length > 0 ? (
              tampering.checks.map((c, i) => (
                <div
                  key={i}
                  className="py-1.5 flex items-start justify-between gap-2 font-mono text-[11px]"
                >
                  <div className="flex items-center gap-1.5 truncate">
                    {c.flagged ? (
                      <AlertOctagon
                        size={12}
                        className="text-risk-critical shrink-0"
                      />
                    ) : (
                      <CheckCircle2 size={12} className="text-brand shrink-0" />
                    )}
                    <span className="uppercase text-text font-medium">
                      {c.check_type.replace(/_/g, " ")}
                    </span>
                  </div>
                  <span
                    className={`text-right truncate ${
                      c.flagged ? "text-risk-critical font-bold" : "text-text-muted"
                    }`}
                  >
                    {formatCheckDetail(c.detail)}
                  </span>
                </div>
              ))
            ) : (
              <div className="py-1.5 flex items-center justify-between font-mono text-[11px] text-text-muted">
                <span>No tampering checks returned</span>
                <span>Unavailable</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
