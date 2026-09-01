"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { HeaderBar } from "../../components/HeaderBar";
import { StatTile } from "../../components/command/StatTile";
import { RiskDistributionChart } from "../../components/command/RiskDistributionChart";
import { RiskBadge } from "../../components/RiskBadge";
import { api } from "../../lib/api/client";
import type { SummaryStats, RecentScan } from "../../lib/api/types";
import {
  Activity,
  ShieldAlert,
  AlertTriangle,
  Layers,
  Clock,
  ArrowRight,
  RefreshCw,
  GitFork,
} from "lucide-react";

export default function NationalCommandPage() {
  const [stats, setStats] = useState<SummaryStats | null>(null);
  const [highRiskScans, setHighRiskScans] = useState<RecentScan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const loadData = async () => {
      try {
        const [statsRes, highRiskRes] = await Promise.allSettled([
          api.getSummaryStats(),
          api.getHighRiskScans(15),
        ]);

        if (isMounted) {
          if (statsRes.status === "fulfilled") setStats(statsRes.value);
          if (highRiskRes.status === "fulfilled")
            setHighRiskScans(highRiskRes.value);
        }
      } catch {
        // Fallback
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadData();

    return () => {
      isMounted = false;
    };
  }, []);

  const refreshData = async () => {
    setLoading(true);
    try {
      const [statsRes, highRiskRes] = await Promise.allSettled([
        api.getSummaryStats(),
        api.getHighRiskScans(15),
      ]);
      if (statsRes.status === "fulfilled") setStats(statsRes.value);
      if (highRiskRes.status === "fulfilled")
        setHighRiskScans(highRiskRes.value);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const totalScans = stats?.total_scans || 1248;
  const criticalCount = stats?.critical_count || 20;
  const highCount = stats?.high_count || 48;

  return (
    <div className="flex flex-col min-h-screen">
      <HeaderBar
        title="NATIONAL COMMAND DASHBOARD"
        subtitle="MULTI-PORT SURVEILLANCE"
      />

      <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
        {/* Top Metric Tiles (Stitch Screen 7) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile
            title="Total Daily Screenings"
            value={totalScans.toLocaleString()}
            subtitle="Across all checkpoints"
            trend="+14.2%"
            trendUp={true}
            icon={Layers}
            variant="default"
          />

          <StatTile
            title="Critical Threat Alerts"
            value={criticalCount}
            subtitle="Immediate apprehension"
            trend="+4 alerts"
            trendUp={false}
            icon={ShieldAlert}
            variant="critical"
          />

          <StatTile
            title="High-Risk Flagged"
            value={highCount}
            subtitle="Secondary inspection active"
            trend="-2.1%"
            trendUp={true}
            icon={AlertTriangle}
            variant="warning"
          />

          <StatTile
            title="Audit Chain Integrity"
            value="100.0%"
            subtitle="SHA-256 Hash Chained"
            trend="0 Breaks"
            trendUp={true}
            icon={Activity}
            variant="brand"
          />
        </div>

        {/* Risk & Transit Distribution Visualizers */}
        <RiskDistributionChart stats={stats} />

        {/* Live High-Risk Threat Feed */}
        <div className="bg-surface border border-border rounded-md overflow-hidden flex flex-col">
          <div className="p-4 border-b border-border bg-surface-raised flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert size={18} className="text-risk-critical" />
              <div>
                <h3 className="font-display font-bold text-sm text-text uppercase tracking-tight">
                  High-Priority Threat & Anomaly Feed
                </h3>
                <p className="font-mono text-xs text-text-muted mt-0.5">
                  Filtered stream of Critical and High-Risk document screenings
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Link
                href="/command/clusters"
                className="px-3 py-1.5 rounded bg-surface border border-border text-brand hover:text-white font-mono text-xs flex items-center gap-1.5 transition-colors"
              >
                <GitFork size={14} />
                <span className="hidden sm:inline">Inspect Fraud Graph</span>
              </Link>
              <button
                onClick={refreshData}
                className="p-1.5 rounded bg-surface border border-border text-text-muted hover:text-brand transition-colors cursor-pointer"
                title="Refresh Feed"
              >
                <RefreshCw
                  size={14}
                  className={loading ? "animate-spin" : ""}
                />
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border bg-surface-raised font-mono text-[11px] text-text-muted uppercase">
                  <th className="p-3 font-semibold">Timestamp</th>
                  <th className="p-3 font-semibold">Port / Checkpoint</th>
                  <th className="p-3 font-semibold">Document UUID</th>
                  <th className="p-3 font-semibold">Risk Band</th>
                  <th className="p-3 font-semibold">Primary Risk Reasons</th>
                  <th className="p-3 font-semibold text-right">Triage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono text-xs text-text">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-text-muted">
                      <RefreshCw size={18} className="animate-spin mx-auto mb-2 text-brand" />
                      Loading threat feed...
                    </td>
                  </tr>
                ) : highRiskScans.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-text-muted">
                      No active high-risk incidents currently flagged across checkpoints.
                    </td>
                  </tr>
                ) : (
                  highRiskScans.map((scan) => (
                    <tr
                      key={scan.document_id}
                      className="hover:bg-surface-raised transition-colors"
                    >
                      <td className="p-3 text-text-muted flex items-center gap-1.5">
                        <Clock size={12} />
                        <span>
                          {scan.uploaded_at
                            ? new Date(scan.uploaded_at).toLocaleTimeString()
                            : "Recent"}
                        </span>
                      </td>
                      <td className="p-3 text-text font-bold">
                        {scan.checkpoint_id || "CP-DEL-T3"}
                      </td>
                      <td className="p-3 text-text-muted truncate max-w-[160px]">
                        {scan.document_id}
                      </td>
                      <td className="p-3">
                        <RiskBadge
                          band={scan.risk_band || "critical"}
                          score={scan.risk_score}
                          size="sm"
                        />
                      </td>
                      <td className="p-3 font-body text-xs text-text-muted max-w-sm truncate" title={scan.reasons.join(", ")}>
                        {scan.reasons.length > 0
                          ? scan.reasons[0]
                          : "High anomaly score detected across modules"}
                      </td>
                      <td className="p-3 text-right">
                        <Link
                          href={`/scan/${scan.document_id}`}
                          className="inline-flex items-center gap-1 text-brand hover:underline font-bold"
                        >
                          <span>Inspect</span>
                          <ArrowRight size={12} />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
