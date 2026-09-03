"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { SidebarNav } from "../../components/SidebarNav";
import { HeaderBar } from "../../components/HeaderBar";
import { RequireRole } from "../../lib/auth/RequireRole";
import {
  Activity,
  ShieldAlert,
  AlertTriangle,
  Layers,
  Clock,
  ArrowRight,
  RefreshCw,
  Search,
  ExternalLink,
  Sliders,
  Share2,
  CheckCircle2,
  UserCheck,
  Building,
  Plane,
  Anchor,
} from "lucide-react";

interface SummaryStats {
  total_scans: number;
  risk_distribution: Record<string, number>;
  checkpoint_distribution: Record<string, number>;
  flagged_today: number;
  critical_count: number;
  high_count: number;
}

interface RecentScan {
  document_id: string;
  document_type: string;
  checkpoint_id: string | null;
  uploaded_at: string | null;
  risk_score: number | null;
  risk_band: string | null;
  reasons: string[];
}

export default function CommandCenterDashboard() {
  const [stats, setStats] = useState<SummaryStats | null>(null);
  const [recentScans, setRecentScans] = useState<RecentScan[]>([]);
  const [loading, setLoading] = useState(true);
  const [clock, setClock] = useState("");

  // Live UTC Clock
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setClock(now.toISOString().substring(11, 19) + "." + String(now.getMilliseconds()).padStart(3, "0") + " UTC");
    };
    updateClock();
    const timer = setInterval(updateClock, 100);
    return () => clearInterval(timer);
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, scansRes] = await Promise.allSettled([
        fetch("http://localhost:8000/api/v1/analytics/summary"),
        fetch("http://localhost:8000/api/v1/analytics/scans/recent?limit=25"),
      ]);

      if (statsRes.status === "fulfilled" && statsRes.value.ok) {
        const sData: SummaryStats = await statsRes.value.json();
        setStats(sData);
      }

      if (scansRes.status === "fulfilled" && scansRes.value.ok) {
        const scData: RecentScan[] = await scansRes.value.json();
        setRecentScans(scData);
      }
    } catch (err) {
      console.error("Failed to load command analytics:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // 10s auto-refresh
    return () => clearInterval(interval);
  }, []);

  const totalScans = stats?.total_scans ?? 0;
  const criticalCount = stats?.critical_count ?? 0;
  const highCount = stats?.high_count ?? 0;
  const flaggedToday = stats?.flagged_today ?? 0;
  const normalCount = totalScans - (criticalCount + highCount + flaggedToday);
  const autoClearanceRate = totalScans > 0 ? (((totalScans - flaggedToday) / totalScans) * 100).toFixed(1) : "100.0";

  return (
    <RequireRole roles={["officer", "supervisor", "admin"]}>
      <div className="min-h-screen flex bg-[#0B0C0E] text-[#e3e2e5]">
        <SidebarNav />

        <div className="flex-1 flex flex-col min-w-0">
          <HeaderBar
            title="NATIONAL COMMAND DASHBOARD"
            subtitle="CENTRAL OPERATIONS & TELEMETRY HUB"
          />

          <main className="flex-1 flex flex-col w-full bg-[#0B0C0E]">
            {/* TOP CONSOLE TICKER & STATUS STRIP */}
            <div className="w-full bg-[#0D0E10] px-6 py-2 flex flex-wrap items-center justify-between gap-2 border-b border-[#2D3135]">
              <div className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-[#c0f500] animate-ping"></span>
                  <span className="font-mono text-xs font-bold text-[#c0f500] uppercase tracking-wider">
                    TRIPORT // MISSION-CRITICAL OPS
                  </span>
                </div>
                <div className="h-3 w-px bg-[#2D3135] hidden sm:block"></div>
                <span className="font-mono text-xs text-[#8e9479] uppercase">
                  TELEMETRY OVERVIEW: ALL ACTIVE BORDER CHECKPOINTS
                </span>
                <div className="h-3 w-px bg-[#2D3135] hidden md:block"></div>
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 ${criticalCount > 0 ? "bg-[#ff3b30]" : "bg-[#c0f500]"}`}></span>
                  <span className={`font-mono text-[11px] font-bold uppercase tracking-tight ${criticalCount > 0 ? "text-[#ff3b30]" : "text-[#c0f500]"}`}>
                    GLOBAL THREAT: {criticalCount > 0 ? "DEFCON 2 (CRITICAL INTERCEPT)" : "DEFCON 4 (NORMAL OPERATION)"}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="font-mono text-xs text-[#8e9479]">
                  SYS_CLK: <span className="text-[#c0f500] font-bold">{clock || "INITIALIZING..."}</span>
                </div>
                <button
                  onClick={loadData}
                  className="px-2.5 py-1 bg-[#1B1C1E] hover:bg-[#292a2c] text-[#8e9479] hover:text-white border border-[#2D3135] font-mono text-[11px] flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
                  <span>REFRESH</span>
                </button>
              </div>
            </div>

            {/* MAIN DASHBOARD CONTENT */}
            <div className="p-6 flex flex-col gap-6 flex-1">
              {/* TOP METRIC KPI RIBBON (4 TACTICAL TELEMETRY CARDS) */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* CARD 1: PASSENGER THROUGHPUT */}
                <div className="bg-[#141517] p-5 flex flex-col justify-between border-l-2 border-[#c0f500] border border-[#2D3135]">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex flex-col">
                      <span className="font-mono text-[11px] text-[#8e9479] uppercase tracking-wider">
                        PASSENGER THROUGHPUT (24H)
                      </span>
                      <span className="font-mono text-xs text-[#c0f500] font-bold mt-1">
                        LIVE TELEMETRY
                      </span>
                    </div>
                    <span className="bg-[#1B1C1E] px-2 py-0.5 font-mono text-[10px] text-[#c0f500] uppercase border border-[#434933]">
                      OPTIMAL FLOW
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between my-2">
                    <span className="font-mono text-3xl font-bold tracking-tight text-white">
                      {totalScans.toLocaleString()}
                    </span>
                    <span className="font-mono text-xs text-[#8e9479]">DOCUMENTS</span>
                  </div>
                  <div className="font-mono text-xs text-[#8e9479] flex justify-between pt-2 border-t border-[#2D3135]">
                    <span>STATUS: ACTIVE</span>
                    <span>ALL GATES OPEN</span>
                  </div>
                </div>

                {/* CARD 2: AUTO-CLEARANCE RATE */}
                <div className="bg-[#141517] p-5 flex flex-col justify-between border-l-2 border-[#c0f500] border border-[#2D3135]">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex flex-col">
                      <span className="font-mono text-[11px] text-[#8e9479] uppercase tracking-wider">
                        AUTO-CLEARANCE RATE
                      </span>
                      <span className="font-mono text-xs text-[#8e9479] mt-1">TARGET: ≥92.0%</span>
                    </div>
                    <span className="font-mono text-[10px] text-[#c0f500] bg-[#161f00] border border-[#434933] px-2 py-0.5">
                      E-GATE SECURE
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between my-2">
                    <span className="font-mono text-3xl font-bold tracking-tight text-[#c0f500]">
                      {autoClearanceRate}%
                    </span>
                    <span className="font-mono text-xs text-[#8e9479]">
                      {Math.max(0, normalCount)} PASSED
                    </span>
                  </div>
                  <div className="w-full flex gap-0.5 h-1.5 bg-[#292a2c] my-1">
                    <div
                      className="bg-[#c0f500] h-full transition-all duration-500"
                      style={{ width: `${Math.min(100, Math.max(0, Number(autoClearanceRate)))}%` }}
                    ></div>
                  </div>
                  <div className="font-mono text-xs text-[#8e9479] flex justify-between pt-2 border-t border-[#2D3135]">
                    <span>ZERO-TOUCH BIO</span>
                    <span>FAILOVER: 0.0%</span>
                  </div>
                </div>

                {/* CARD 3: SECONDARY INSPECTION QUEUE */}
                <div className="bg-[#141517] p-5 flex flex-col justify-between border-l-2 border-[#feb700] border border-[#2D3135]">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex flex-col">
                      <span className="font-mono text-[11px] text-[#feb700] uppercase tracking-wider">
                        SECONDARY INSPECTION
                      </span>
                      <span className="font-mono text-xs text-[#feb700] mt-1">HOLDING BAY MONITOR</span>
                    </div>
                    <span className="font-mono text-[10px] text-[#feb700] bg-[#1F2022] border border-[#feb700]/30 px-2 py-0.5 uppercase">
                      FLAGGED
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between my-2">
                    <span className="font-mono text-3xl font-bold tracking-tight text-[#feb700]">
                      {flaggedToday} <span className="text-sm font-normal text-[#8e9479]">PAX</span>
                    </span>
                    <span className="font-mono text-xs text-[#feb700]">ACTIVE QUEUE</span>
                  </div>
                  <div className="font-mono text-xs text-[#8e9479] flex justify-between pt-2 border-t border-[#2D3135]">
                    <span>AVG HOLD: ~4 MIN</span>
                    <span>BOOTH 3 & 4</span>
                  </div>
                </div>

                {/* CARD 4: CRITICAL THREAT INTERCEPTS */}
                <div className="bg-[#141517] p-5 flex flex-col justify-between border-l-2 border-[#ff3b30] border border-[#2D3135]">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex flex-col">
                      <span className="font-mono text-[11px] text-[#ffdad6] uppercase tracking-wider">
                        CRITICAL INTERCEPTS
                      </span>
                      <span className="font-mono text-xs text-[#ffb4ab] mt-1">WATCHLIST & FORGERY</span>
                    </div>
                    <span className="font-mono text-[10px] text-[#ffdad6] bg-[#93000a] px-2 py-0.5 uppercase font-bold">
                      {criticalCount > 0 ? "ACTION REQ" : "STANDBY"}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between my-2">
                    <span className="font-mono text-3xl font-bold tracking-tight text-[#ff3b30]">
                      {criticalCount}
                    </span>
                    <span className="font-mono text-xs text-[#ffb4ab]">INTERCEPT ALERTS</span>
                  </div>
                  <div className="font-mono text-xs text-[#8e9479] flex justify-between pt-2 border-t border-[#2D3135]">
                    <span>HIGH RISK: {highCount}</span>
                    <span>PGVECTOR ESCALATIONS</span>
                  </div>
                </div>
              </div>

              {/* MIDDLE SECTION: TERMINAL FLOW MATRIX & RISK DISTRIBUTION */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* LEFT 70%: LIVE RECENT SCANS & INTERCEPTS FEED */}
                <div className="lg:col-span-8 flex flex-col gap-4">
                  <div className="flex items-center justify-between bg-[#1B1C1E] px-4 py-2 border border-[#2D3135]">
                    <div className="flex items-center gap-2">
                      <Activity size={16} className="text-[#c0f500]" />
                      <span className="font-mono text-xs text-white uppercase tracking-wider font-bold">
                        LIVE SCREENING STREAM & THREAT AUDIT ({recentScans.length} RECORDS)
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Link
                        href="/audit"
                        className="font-mono text-xs text-[#c0f500] hover:underline flex items-center gap-1"
                      >
                        <span>VIEW FULL LEDGER</span>
                        <ArrowRight size={12} />
                      </Link>
                    </div>
                  </div>

                  <div className="bg-[#141517] border border-[#2D3135] overflow-x-auto">
                    <table className="w-full text-left font-mono text-xs border-collapse">
                      <thead>
                        <tr className="bg-[#1B1C1E] text-[#8e9479] border-b border-[#2D3135] text-[10px] uppercase tracking-wider">
                          <th className="p-3">SCAN UUID / TIME</th>
                          <th className="p-3">DOCUMENT TYPE</th>
                          <th className="p-3">CHECKPOINT</th>
                          <th className="p-3">RISK SCORE</th>
                          <th className="p-3">BAND / REASONS</th>
                          <th className="p-3 text-right">ACTION</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#2D3135]">
                        {recentScans.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="p-8 text-center text-[#8e9479]">
                              NO RECENT SCANS LOGGED IN SUPABASE DATABASE
                            </td>
                          </tr>
                        ) : (
                          recentScans.map((scan) => {
                            const isCritical = scan.risk_band === "critical";
                            const isHigh = scan.risk_band === "high";
                            const isMedium = scan.risk_band === "medium";

                            return (
                              <tr
                                key={scan.document_id}
                                className="hover:bg-[#1F2022] transition-colors"
                              >
                                <td className="p-3">
                                  <div className="text-white font-bold truncate max-w-[140px]">
                                    {scan.document_id}
                                  </div>
                                  <div className="text-[10px] text-[#8e9479]">
                                    {scan.uploaded_at ? new Date(scan.uploaded_at).toLocaleTimeString() : "RECENT"}
                                  </div>
                                </td>
                                <td className="p-3">
                                  <span className="px-2 py-0.5 bg-[#0D0E10] border border-[#2D3135] text-white uppercase text-[10px]">
                                    {scan.document_type.replace(/_/g, " ")}
                                  </span>
                                </td>
                                <td className="p-3 text-[#c4caac]">
                                  {scan.checkpoint_id || "TERMINAL 3 ICP"}
                                </td>
                                <td className="p-3">
                                  <span
                                    className={`font-bold ${
                                      isCritical || isHigh
                                        ? "text-[#ff3b30]"
                                        : isMedium
                                        ? "text-[#feb700]"
                                        : "text-[#c0f500]"
                                    }`}
                                  >
                                    {scan.risk_score !== null ? (scan.risk_score * 100).toFixed(1) + "%" : "0.0%"}
                                  </span>
                                </td>
                                <td className="p-3">
                                  <span
                                    className={`px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                                      isCritical
                                        ? "bg-[#93000a] text-[#ffdad6]"
                                        : isHigh
                                        ? "bg-[#feb700]/20 text-[#feb700] border border-[#feb700]/40"
                                        : "bg-[#161f00] text-[#c0f500]"
                                    }`}
                                  >
                                    {scan.risk_band || "LOW"}
                                  </span>
                                  {scan.reasons && scan.reasons.length > 0 && (
                                    <div className="text-[10px] text-[#8e9479] truncate max-w-[180px] mt-0.5">
                                      {scan.reasons[0]}
                                    </div>
                                  )}
                                </td>
                                <td className="p-3 text-right">
                                  <Link
                                    href={`/audit?query=${scan.document_id}`}
                                    className="px-2 py-1 bg-[#1B1C1E] hover:bg-[#c0f500] hover:text-[#121315] text-[#e3e2e5] border border-[#2D3135] text-[10px] font-bold uppercase transition-colors inline-flex items-center gap-1"
                                  >
                                    <span>AUDIT</span>
                                    <ArrowRight size={10} />
                                  </Link>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* RIGHT 30%: NAVIGATION & SYSTEM QUICK LINKS */}
                <div className="lg:col-span-4 flex flex-col gap-4">
                  <div className="flex items-center justify-between bg-[#1B1C1E] px-4 py-2 border border-[#2D3135]">
                    <div className="flex items-center gap-2">
                      <Sliders size={16} className="text-[#c0f500]" />
                      <span className="font-mono text-xs text-white uppercase tracking-wider font-bold">
                        TACTICAL CONTROLS & MODULES
                      </span>
                    </div>
                  </div>

                  <div className="bg-[#141517] border border-[#2D3135] p-4 flex flex-col gap-3">
                    <Link
                      href="/command/clusters"
                      className="p-3 bg-[#1B1C1E] hover:bg-[#292a2c] border border-[#2D3135] hover:border-[#c0f500] transition-colors flex items-center justify-between group"
                    >
                      <div className="flex items-center gap-3">
                        <Share2 size={18} className="text-[#c0f500]" />
                        <div>
                          <div className="font-mono text-xs font-bold text-white group-hover:text-[#c0f500]">
                            BIOMETRIC INTELLIGENCE GRAPH
                          </div>
                          <div className="font-mono text-[10px] text-[#8e9479]">
                            Sybil Ring Detection & Velocity Anomalies
                          </div>
                        </div>
                      </div>
                      <ArrowRight size={14} className="text-[#8e9479] group-hover:text-white" />
                    </Link>

                    <Link
                      href="/command/admin"
                      className="p-3 bg-[#1B1C1E] hover:bg-[#292a2c] border border-[#2D3135] hover:border-[#c0f500] transition-colors flex items-center justify-between group"
                    >
                      <div className="flex items-center gap-3">
                        <Sliders size={18} className="text-[#c0f500]" />
                        <div>
                          <div className="font-mono text-xs font-bold text-white group-hover:text-[#c0f500]">
                            RULES & POLICY ENGINE INSPECTOR
                          </div>
                          <div className="font-mono text-[10px] text-[#8e9479]">
                            Live YAML Document Policies & AI Thresholds
                          </div>
                        </div>
                      </div>
                      <ArrowRight size={14} className="text-[#8e9479] group-hover:text-white" />
                    </Link>

                    <Link
                      href="/audit"
                      className="p-3 bg-[#1B1C1E] hover:bg-[#292a2c] border border-[#2D3135] hover:border-[#c0f500] transition-colors flex items-center justify-between group"
                    >
                      <div className="flex items-center gap-3">
                        <Layers size={18} className="text-[#c0f500]" />
                        <div>
                          <div className="font-mono text-xs font-bold text-white group-hover:text-[#c0f500]">
                            CRYPTOGRAPHIC AUDIT LEDGER
                          </div>
                          <div className="font-mono text-[10px] text-[#8e9479]">
                            SHA-256 Hash Chain Explorer & CLI Proofs
                          </div>
                        </div>
                      </div>
                      <ArrowRight size={14} className="text-[#8e9479] group-hover:text-white" />
                    </Link>

                    <Link
                      href="/screening"
                      className="p-3 bg-[#161f00] hover:bg-[#c0f500] text-[#c0f500] hover:text-[#121315] border border-[#434933] transition-colors flex items-center justify-between group"
                    >
                      <div className="flex items-center gap-3">
                        <UserCheck size={18} />
                        <div>
                          <div className="font-mono text-xs font-bold">
                            PRIMARY SCREENING CONSOLE
                          </div>
                          <div className="font-mono text-[10px] opacity-80">
                            Launch Document & Facial Verification
                          </div>
                        </div>
                      </div>
                      <ArrowRight size={14} />
                    </Link>
                  </div>

                  {/* CHECKPOINT SUMMARY BREAKDOWN */}
                  <div className="bg-[#141517] border border-[#2D3135] p-4 flex flex-col gap-3">
                    <div className="font-mono text-xs font-bold text-white uppercase tracking-wider mb-1">
                      PORT INFRASTRUCTURE HEALTH
                    </div>
                    <div className="space-y-2 font-mono text-xs">
                      <div className="flex items-center justify-between p-2 bg-[#0D0E10] border border-[#2D3135]">
                        <span className="flex items-center gap-2 text-white">
                          <Plane size={14} className="text-[#c0f500]" />
                          AIRPORT E-GATES (DEL-T3)
                        </span>
                        <span className="text-[#c0f500] font-bold">ONLINE (100%)</span>
                      </div>
                      <div className="flex items-center justify-between p-2 bg-[#0D0E10] border border-[#2D3135]">
                        <span className="flex items-center gap-2 text-white">
                          <Building size={14} className="text-[#c0f500]" />
                          LAND BORDER ICP (IN-NP)
                        </span>
                        <span className="text-[#c0f500] font-bold">ONLINE (100%)</span>
                      </div>
                      <div className="flex items-center justify-between p-2 bg-[#0D0E10] border border-[#2D3135]">
                        <span className="flex items-center gap-2 text-white">
                          <Anchor size={14} className="text-[#c0f500]" />
                          SEAPORT CARGO ICP (BOM)
                        </span>
                        <span className="text-[#c0f500] font-bold">ONLINE (100%)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </RequireRole>
  );
}
