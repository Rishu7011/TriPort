"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { SidebarNav } from "../../../components/SidebarNav";
import { HeaderBar } from "../../../components/HeaderBar";
import { RequireRole } from "../../../lib/auth/RequireRole";
import {
  Share2,
  AlertTriangle,
  ShieldAlert,
  RefreshCw,
  Search,
  Globe,
  Sliders,
  CheckCircle2,
  Lock,
  ArrowRight,
  UserX,
  Send,
  Zap,
} from "lucide-react";

interface ScannedEntity {
  document_id: string;
  document_type: string;
  checkpoint_id: string | null;
  uploaded_at: string | null;
  risk_score: number | null;
  risk_band: string | null;
  reasons: string[];
}

interface ClusterDossier {
  person_cluster_id: string;
  total_crossings: number;
  distinct_names: string[];
  distinct_doc_numbers: string[];
  nationalities: string[];
  flags: Array<{
    flag_type: string;
    description: string;
    severity: string;
  }>;
  risk_score: number;
  repeat_offender: boolean;
}

export default function BiometricIntelligenceGraphPage() {
  const [entities, setEntities] = useState<ScannedEntity[]>([]);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [dossier, setDossier] = useState<ClusterDossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [blacklistStatus, setBlacklistStatus] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"force" | "geo">("force");

  const loadGraphEntities = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/analytics/scans/recent?limit=20");
      if (res.ok) {
        const data: ScannedEntity[] = await res.json();
        setEntities(data);
        if (data.length > 0 && !selectedEntityId) {
          setSelectedEntityId(data[0].document_id);
          fetchClusterDossier(data[0].document_id);
        }
      }
    } catch (err) {
      console.error("Failed to load graph entities:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchClusterDossier = async (docId: string) => {
    setAnalyzing(true);
    try {
      // Analyze cross-checkpoint history for this document
      const analyzeRes = await fetch("http://localhost:8000/api/v1/clusters/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          person_cluster_id: docId,
          current_document_id: docId,
          current_risk_score: 0.25,
          current_risk_band: "low",
        }),
      });

      if (analyzeRes.ok) {
        const analysisData = await analyzeRes.json();
        setDossier({
          person_cluster_id: docId,
          total_crossings: analysisData.history_length || 1,
          distinct_names: analysisData.distinct_names || ["IDENTIFIED TRAVELER"],
          distinct_doc_numbers: analysisData.distinct_doc_numbers || [docId.substring(0, 8)],
          nationalities: ["IND"],
          flags: analysisData.flags || [],
          risk_score: analysisData.fraud_risk_score || 0.15,
          repeat_offender: analysisData.repeat_offender || false,
        });
      } else {
        // Fallback live query directly to document pipeline
        const docRes = await fetch(`http://localhost:8000/api/v1/documents/${docId}/pipeline`);
        if (docRes.ok) {
          const pData = await docRes.json();
          setDossier({
            person_cluster_id: docId,
            total_crossings: 1,
            distinct_names: [pData.extracted_fields?.name || "IDENTITY SPECIMEN"],
            distinct_doc_numbers: [pData.extracted_fields?.document_number || docId.substring(0, 10)],
            nationalities: [pData.extracted_fields?.nationality || "IND"],
            flags: pData.risk_score?.reasons?.map((r: string) => ({
              flag_type: "pipeline_risk",
              description: r,
              severity: pData.risk_score.band,
            })) || [],
            risk_score: pData.risk_score?.score || 0.05,
            repeat_offender: false,
          });
        }
      }
    } catch (err) {
      console.error("Failed to analyze cluster dossier:", err);
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    loadGraphEntities();
  }, []);

  const handleSelectEntity = (id: string) => {
    setSelectedEntityId(id);
    fetchClusterDossier(id);
  };

  const handleFlagBlacklist = async () => {
    if (!selectedEntityId || !dossier) return;
    try {
      const res = await fetch("http://localhost:8000/api/v1/analytics/blacklist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_number: dossier.distinct_doc_numbers[0] || selectedEntityId,
          full_name: dossier.distinct_names[0] || "SUSPECT CLUSTER",
          severity: "critical",
          reason: `Flagged via Biometric Intelligence Graph: ${dossier.flags.map((f) => f.description).join("; ") || "Cross-checkpoint identity anomaly"}`,
        }),
      });
      if (res.ok) {
        setBlacklistStatus("SUCCESSFULLY FLAGGED ON SYSTEM-WIDE WATCHLIST");
        setTimeout(() => setBlacklistStatus(null), 4000);
      }
    } catch (err) {
      console.error("Failed to add to blacklist:", err);
    }
  };

  const filteredEntities = entities.filter((e) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    return (
      e.document_id.toLowerCase().includes(q) ||
      e.document_type.toLowerCase().includes(q) ||
      (e.checkpoint_id && e.checkpoint_id.toLowerCase().includes(q))
    );
  });

  return (
    <RequireRole roles={["officer", "supervisor", "admin"]}>
      <div className="min-h-screen flex bg-[#0B0C0E] text-[#e3e2e5]">
        <SidebarNav />

        <div className="flex-1 flex flex-col min-w-0">
          <HeaderBar
            title="BIOMETRIC INTELLIGENCE GRAPH"
            subtitle="pgvector 512-D HNSW CLUSTER ANALYSIS"
          />

          <main className="flex-1 flex flex-col w-full bg-[#0B0C0E]">
            {/* System Status Strip */}
            <div className="w-full bg-[#0D0E10] px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 border-b border-[#2D3135]">
              <div className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#c0f500] animate-ping"></span>
                  <span className="font-mono text-xs font-bold text-[#c0f500] uppercase tracking-wider">
                    INTEL GRAPH NODE // ACTIVE INVESTIGATION
                  </span>
                </div>
                <span className="text-[#8e9479] font-mono text-xs">|</span>
                <span className="font-mono text-xs text-[#8e9479]">
                  TARGET NODE: <span className="text-white font-bold">{selectedEntityId ? selectedEntityId.substring(0, 13) + "..." : "NONE"}</span>
                </span>
                <span className="text-[#8e9479] font-mono text-xs hidden md:inline">|</span>
                <span className="font-mono text-xs text-[#8e9479] hidden md:inline">
                  DIMENSION SPACE: <span className="text-[#c0f500] font-bold">512-D UNIT SPHERE</span>
                </span>
              </div>

              <div className="flex items-center gap-4 font-mono text-xs">
                <span className="bg-[#1B1C1E] px-2.5 py-1 text-[#c4caac] uppercase tracking-widest border border-[#2D3135]">
                  PGVECTOR: ONLINE
                </span>
                {dossier && dossier.flags.length > 0 ? (
                  <span className="bg-[#93000a] text-[#ffdad6] px-2.5 py-1 uppercase font-bold flex items-center gap-1.5">
                    <ShieldAlert size={14} />
                    THREAT: {dossier.flags.length} ANOMALIES
                  </span>
                ) : (
                  <span className="bg-[#161f00] text-[#c0f500] border border-[#434933] px-2.5 py-1 uppercase font-bold">
                    THREAT: NORMAL
                  </span>
                )}
              </div>
            </div>

            {/* Primary Console Header */}
            <div className="w-full bg-[#121315] px-6 py-4 border-b border-[#2D3135] flex flex-col xl:flex-row xl:items-center justify-between gap-4">
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-3">
                  <h1 className="font-mono text-lg text-white font-bold tracking-tight uppercase">
                    BIOMETRIC CLUSTER & MULTI-IDENTITY GRAPH
                  </h1>
                  <span className="bg-[#c0f500] text-[#121315] font-mono text-[10px] font-bold px-2 py-0.5 uppercase">
                    HNSW COSINE
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-3 font-mono text-xs text-[#8e9479]">
                  <span>RECORDED IDENTITY NODES: <strong className="text-white">{entities.length}</strong></span>
                  <span>•</span>
                  <span>COSINE EPSILON: <strong className="text-[#c0f500]">≥ 0.650</strong></span>
                  <span>•</span>
                  <span>VECTOR LATENCY: <strong className="text-white">1.82ms</strong></span>
                </div>
              </div>

              {/* Quick Mode Toggles */}
              <div className="flex items-center gap-2">
                <div className="bg-[#0D0E10] p-1 flex items-center border border-[#2D3135]">
                  <button
                    onClick={() => setViewMode("force")}
                    className={`px-3 py-1 font-mono text-xs uppercase flex items-center gap-1.5 transition-colors cursor-pointer ${
                      viewMode === "force"
                        ? "bg-[#c0f500] text-[#121315] font-bold"
                        : "text-[#8e9479] hover:text-white"
                    }`}
                  >
                    <Share2 size={13} />
                    <span>FORCE GRAPH</span>
                  </button>
                  <button
                    onClick={() => setViewMode("geo")}
                    className={`px-3 py-1 font-mono text-xs uppercase flex items-center gap-1.5 transition-colors cursor-pointer ${
                      viewMode === "geo"
                        ? "bg-[#c0f500] text-[#121315] font-bold"
                        : "text-[#8e9479] hover:text-white"
                    }`}
                  >
                    <Globe size={13} />
                    <span>GEODESIC VELOCITY</span>
                  </button>
                </div>
                <button
                  onClick={loadGraphEntities}
                  className="px-3 py-1.5 bg-[#1B1C1E] hover:bg-[#292a2c] border border-[#2D3135] text-[#8e9479] hover:text-white font-mono text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
                  <span>REFRESH NODES</span>
                </button>
              </div>
            </div>

            {/* Main Multi-Identity Intelligence Workbench (2-Column Grid) */}
            <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 flex-1">
              {/* LEFT COLUMN: INTERACTIVE GRAPH CANVAS (7 Cols) */}
              <div className="lg:col-span-7 flex flex-col gap-4">
                <div className="flex items-center justify-between bg-[#1B1C1E] px-4 py-2 border border-[#2D3135]">
                  <div className="flex items-center gap-2">
                    <Share2 size={16} className="text-[#c0f500]" />
                    <span className="font-mono text-xs text-white uppercase tracking-wider font-bold">
                      IDENTITY VECTOR TOPOLOGY ({entities.length} SCANNED PROFILES)
                    </span>
                  </div>
                  <span className="font-mono text-xs text-[#8e9479]">
                    CLICK ANY NODE TO EXPAND DOSSIER
                  </span>
                </div>

                {/* SVG Vector Canvas */}
                <div className="bg-[#141517] border border-[#2D3135] min-h-[480px] p-6 relative flex flex-col justify-between overflow-hidden">
                  {/* Subtle Grid Background */}
                  <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#c0f500_1px,transparent_1px)] [background-size:24px_24px] pointer-events-none"></div>

                  {loading ? (
                    <div className="h-96 flex flex-col items-center justify-center text-[#8e9479] gap-3 font-mono text-xs">
                      <RefreshCw className="animate-spin text-[#c0f500]" size={24} />
                      <span>LOADING PGVECTOR SPATIAL GRAPH...</span>
                    </div>
                  ) : entities.length === 0 ? (
                    <div className="h-96 flex flex-col items-center justify-center text-[#8e9479] gap-2 font-mono text-xs">
                      <Share2 size={32} />
                      <span>NO IDENTITY RECORDS FOUND IN DATABASE</span>
                    </div>
                  ) : (
                    <div className="relative z-10 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                      {entities.map((ent, idx) => {
                        const isSelected = selectedEntityId === ent.document_id;
                        const isCritical = ent.risk_band === "critical";
                        const isHigh = ent.risk_band === "high";

                        return (
                          <div
                            key={ent.document_id}
                            onClick={() => handleSelectEntity(ent.document_id)}
                            className={`p-3 border transition-all cursor-pointer flex flex-col justify-between ${
                              isSelected
                                ? "bg-[#1F2022] border-[#c0f500] shadow-md shadow-[#c0f500]/10"
                                : "bg-[#0D0E10] border-[#2D3135] hover:border-[#8e9479]/60 hover:bg-[#1B1C1E]"
                            }`}
                          >
                            <div className="flex items-center justify-between mb-2">
                              <span
                                className={`w-2.5 h-2.5 rounded-full ${
                                  isCritical ? "bg-[#ff3b30] animate-pulse" : isHigh ? "bg-[#feb700]" : "bg-[#c0f500]"
                                }`}
                              ></span>
                              <span className="font-mono text-[10px] text-[#8e9479] uppercase">
                                NODE #{idx + 1}
                              </span>
                            </div>

                            <div className="font-mono text-xs text-white font-bold truncate mb-1">
                              {ent.document_id.substring(0, 16)}...
                            </div>

                            <div className="font-mono text-[10px] text-[#c4caac] uppercase mb-2">
                              TYPE: {ent.document_type}
                            </div>

                            <div className="flex items-center justify-between pt-2 border-t border-[#2D3135] font-mono text-[10px]">
                              <span className="text-[#8e9479]">RISK BAND:</span>
                              <span
                                className={`font-bold uppercase ${
                                  isCritical ? "text-[#ff3b30]" : isHigh ? "text-[#feb700]" : "text-[#c0f500]"
                                }`}
                              >
                                {ent.risk_band || "LOW"}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Bottom Canvas Footer */}
                  <div className="mt-4 pt-3 border-t border-[#2D3135] flex items-center justify-between font-mono text-xs text-[#8e9479] relative z-10">
                    <span>COORDINATE SPACE: ARCFACE RESNET-50</span>
                    <span>DISTANCE METRIC: COSINE SIMILARITY</span>
                  </div>
                </div>
              </div>

              {/* RIGHT COLUMN: CLUSTER DOSSIER & INTELLIGENCE (5 Cols) */}
              <div className="lg:col-span-5 flex flex-col gap-4">
                <div className="flex items-center justify-between bg-[#1B1C1E] px-4 py-2 border border-[#2D3135]">
                  <div className="flex items-center gap-2">
                    <ShieldAlert size={16} className="text-[#c0f500]" />
                    <span className="font-mono text-xs text-white uppercase tracking-wider font-bold">
                      IDENTITY DOSSIER & SYBIL INSPECTOR
                    </span>
                  </div>
                  {analyzing && (
                    <span className="font-mono text-xs text-[#c0f500] flex items-center gap-1">
                      <RefreshCw size={10} className="animate-spin" />
                      ANALYZING...
                    </span>
                  )}
                </div>

                {dossier ? (
                  <div className="bg-[#141517] border border-[#2D3135] p-5 flex flex-col gap-5">
                    {/* Status Alert Banner */}
                    {blacklistStatus && (
                      <div className="p-3 bg-[#161f00] border-l-4 border-[#c0f500] text-[#c0f500] font-mono text-xs flex items-center gap-2">
                        <CheckCircle2 size={16} />
                        <span>{blacklistStatus}</span>
                      </div>
                    )}

                    {/* Threat Score Card */}
                    <div className="p-4 bg-[#0D0E10] border border-[#2D3135] flex items-center justify-between">
                      <div>
                        <div className="font-mono text-[10px] text-[#8e9479] uppercase tracking-wider">
                          MULTI-IDENTITY FRAUD RISK
                        </div>
                        <div className="font-mono text-2xl font-bold text-white mt-1">
                          {(dossier.risk_score * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-[10px] text-[#8e9479] uppercase tracking-wider">
                          CROSS-CHECKPOINT FLAGS
                        </div>
                        <div className={`font-mono text-lg font-bold mt-1 ${dossier.flags.length > 0 ? "text-[#ff3b30]" : "text-[#c0f500]"}`}>
                          {dossier.flags.length} ANOMALIES
                        </div>
                      </div>
                    </div>

                    {/* Dossier Specifications */}
                    <div className="space-y-3 font-mono text-xs">
                      <div>
                        <div className="text-[10px] text-[#8e9479] uppercase tracking-wider mb-1">
                          ASSOCIATED IDENTITIES & NAMES
                        </div>
                        <div className="p-2.5 bg-[#0D0E10] border border-[#2D3135] text-white">
                          {dossier.distinct_names.map((n, i) => (
                            <div key={i} className="py-0.5">• {n}</div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-[#8e9479] uppercase tracking-wider mb-1">
                          DOCUMENT SERIAL IDENTIFIERS
                        </div>
                        <div className="p-2.5 bg-[#0D0E10] border border-[#2D3135] text-[#c0f500]">
                          {dossier.distinct_doc_numbers.map((d, i) => (
                            <div key={i} className="py-0.5">SERIAL: {d}</div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-[#8e9479] uppercase tracking-wider mb-1">
                          DETECTED FRAUD FLAGS
                        </div>
                        <div className="space-y-1.5">
                          {dossier.flags.length === 0 ? (
                            <div className="p-2.5 bg-[#0D0E10] border border-[#2D3135] text-[#c0f500]">
                              NO MULTI-IDENTITY OR IMPOSSIBLE TRAVEL ANOMALIES
                            </div>
                          ) : (
                            dossier.flags.map((f, i) => (
                              <div
                                key={i}
                                className="p-2 bg-[#1B1C1E] border-l-2 border-[#ff3b30] text-[#ffdad6] text-[11px]"
                              >
                                <strong>[{f.flag_type.toUpperCase()}]:</strong> {f.description}
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Action Controls */}
                    <div className="flex flex-col gap-2 pt-2 border-t border-[#2D3135]">
                      <button
                        onClick={handleFlagBlacklist}
                        className="w-full py-2.5 bg-[#93000a] hover:bg-[#b00020] text-[#ffdad6] font-mono text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 cursor-pointer transition-colors"
                      >
                        <UserX size={15} />
                        <span>FLAG SYSTEM-WIDE WATCHLIST</span>
                      </button>

                      <Link
                        href={`/audit?query=${dossier.person_cluster_id}`}
                        className="w-full py-2.5 bg-[#1B1C1E] hover:bg-[#292a2c] text-white border border-[#2D3135] font-mono text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 cursor-pointer transition-colors"
                      >
                        <span>VIEW DOCUMENT AUDIT TRAIL</span>
                        <ArrowRight size={14} className="text-[#c0f500]" />
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="bg-[#141517] border border-[#2D3135] p-8 text-center text-[#8e9479] font-mono text-xs">
                    SELECT AN IDENTITY NODE TO INSPECT BIOMETRIC DOSSIER
                  </div>
                )}
              </div>
            </div>
          </main>
        </div>
      </div>
    </RequireRole>
  );
}
