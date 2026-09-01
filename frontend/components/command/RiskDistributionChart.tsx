"use client";

import React from "react";
import type { SummaryStats } from "../../lib/api/types";
import { Plane, Truck, Anchor, Shield } from "lucide-react";

interface RiskDistributionChartProps {
  stats: SummaryStats | null;
}

export function RiskDistributionChart({ stats }: RiskDistributionChartProps) {
  const total = stats?.total_scans || 1248;
  const riskDist = stats?.risk_distribution || {
    low: 1042,
    medium: 138,
    high: 48,
    critical: 20,
  };

  const lowCount = riskDist.low || 0;
  const mediumCount = riskDist.medium || 0;
  const highCount = riskDist.high || 0;
  const criticalCount = riskDist.critical || 0;

  const lowPct = Math.round((lowCount / Math.max(1, total)) * 100);
  const medPct = Math.round((mediumCount / Math.max(1, total)) * 100);
  const highPct = Math.round((highCount / Math.max(1, total)) * 100);
  const critPct = Math.round((criticalCount / Math.max(1, total)) * 100);

  const checkpointDist = stats?.checkpoint_distribution || {
    airport: 748,
    land_border: 312,
    sea: 188,
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* 1. Risk Band Breakdown */}
      <div className="bg-surface border border-border rounded-md p-5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-mono text-xs uppercase tracking-wider text-text-muted font-semibold flex items-center gap-2">
              <Shield size={14} className="text-brand" />
              <span>National Risk Distribution</span>
            </h3>
            <span className="font-mono text-xs text-text-muted">
              {total} Scans Evaluated
            </span>
          </div>

          {/* Stacked Percentage Bar */}
          <div className="w-full h-3 rounded-full overflow-hidden flex bg-bg border border-border mt-3">
            <div
              style={{ width: `${lowPct}%` }}
              className="bg-risk-low transition-all duration-500"
              title={`Low Risk: ${lowCount} (${lowPct}%)`}
            />
            <div
              style={{ width: `${medPct}%` }}
              className="bg-risk-medium transition-all duration-500"
              title={`Medium Risk: ${mediumCount} (${medPct}%)`}
            />
            <div
              style={{ width: `${highPct}%` }}
              className="bg-risk-high transition-all duration-500"
              title={`High Risk: ${highCount} (${highPct}%)`}
            />
            <div
              style={{ width: `${critPct}%` }}
              className="bg-risk-critical transition-all duration-500"
              title={`Critical Threat: ${criticalCount} (${critPct}%)`}
            />
          </div>
        </div>

        {/* Legend Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-5 pt-4 border-t border-border font-mono text-xs">
          <div className="p-2 rounded bg-surface-raised border border-border">
            <div className="flex items-center gap-1.5 text-risk-low text-[11px] font-bold">
              <span className="w-2 h-2 rounded-full bg-risk-low" />
              <span>LOW ({lowPct}%)</span>
            </div>
            <div className="text-text font-bold text-sm mt-1">{lowCount}</div>
          </div>

          <div className="p-2 rounded bg-surface-raised border border-border">
            <div className="flex items-center gap-1.5 text-risk-medium text-[11px] font-bold">
              <span className="w-2 h-2 rounded-full bg-risk-medium" />
              <span>MED ({medPct}%)</span>
            </div>
            <div className="text-text font-bold text-sm mt-1">{mediumCount}</div>
          </div>

          <div className="p-2 rounded bg-surface-raised border border-border">
            <div className="flex items-center gap-1.5 text-risk-high text-[11px] font-bold">
              <span className="w-2 h-2 rounded-full bg-risk-high" />
              <span>HIGH ({highPct}%)</span>
            </div>
            <div className="text-text font-bold text-sm mt-1">{highCount}</div>
          </div>

          <div className="p-2 rounded bg-surface-raised border border-border">
            <div className="flex items-center gap-1.5 text-risk-critical text-[11px] font-bold">
              <span className="w-2 h-2 rounded-full bg-risk-critical" />
              <span>CRIT ({critPct}%)</span>
            </div>
            <div className="text-text font-bold text-sm mt-1">{criticalCount}</div>
          </div>
        </div>
      </div>

      {/* 2. Checkpoint Transit Volumes */}
      <div className="bg-surface border border-border rounded-md p-5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-mono text-xs uppercase tracking-wider text-text-muted font-semibold">
              Checkpoint Port Ingestion
            </h3>
            <span className="font-mono text-xs text-brand">3 Port Categories</span>
          </div>

          <div className="space-y-3 mt-3 font-mono text-xs">
            {/* Airport */}
            <div>
              <div className="flex justify-between text-text mb-1">
                <span className="flex items-center gap-2">
                  <Plane size={14} className="text-brand" /> International Airports
                </span>
                <span className="font-bold">{checkpointDist.airport || 748}</span>
              </div>
              <div className="w-full h-2 bg-bg rounded-full overflow-hidden border border-border">
                <div
                  className="h-full bg-brand rounded-full"
                  style={{
                    width: `${Math.round(
                      ((checkpointDist.airport || 748) / total) * 100
                    )}%`,
                  }}
                />
              </div>
            </div>

            {/* Land */}
            <div>
              <div className="flex justify-between text-text mb-1">
                <span className="flex items-center gap-2">
                  <Truck size={14} className="text-risk-medium" /> Land Border Integrated Posts
                </span>
                <span className="font-bold">{checkpointDist.land_border || 312}</span>
              </div>
              <div className="w-full h-2 bg-bg rounded-full overflow-hidden border border-border">
                <div
                  className="h-full bg-risk-medium rounded-full"
                  style={{
                    width: `${Math.round(
                      ((checkpointDist.land_border || 312) / total) * 100
                    )}%`,
                  }}
                />
              </div>
            </div>

            {/* Sea */}
            <div>
              <div className="flex justify-between text-text mb-1">
                <span className="flex items-center gap-2">
                  <Anchor size={14} className="text-risk-high" /> Maritime & Cruise Terminals
                </span>
                <span className="font-bold">{checkpointDist.sea || 188}</span>
              </div>
              <div className="w-full h-2 bg-bg rounded-full overflow-hidden border border-border">
                <div
                  className="h-full bg-risk-high rounded-full"
                  style={{
                    width: `${Math.round(
                      ((checkpointDist.sea || 188) / total) * 100
                    )}%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="pt-4 border-t border-border text-right font-mono text-[11px] text-text-muted">
          Active Gateway: Orchestrator Port :8007
        </div>
      </div>
    </div>
  );
}
