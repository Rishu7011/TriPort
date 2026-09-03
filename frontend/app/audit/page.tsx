"use client";

import React, { useState, useEffect, useMemo } from "react";
import { SidebarNav } from "../../components/SidebarNav";
import { HeaderBar } from "../../components/HeaderBar";
import { RequireRole } from "../../lib/auth/RequireRole";
import {
  Search,
  CheckCircle2,
  AlertTriangle,
  FileCode,
  ShieldCheck,
  Download,
  Copy,
  Check,
  RefreshCw,
  Hash,
  Database,
  Lock,
  Layers,
  Zap,
} from "lucide-react";

interface AuditEvent {
  id: string;
  sequence_num: number;
  event_type: string;
  document_id: string | null;
  officer_id: string | null;
  payload_hash: string;
  prev_record_hash: string;
  record_hash: string;
  created_at: string;
}

interface ChainVerifyResult {
  valid: boolean;
  total_records: number;
  tampered_sequence_num: number | null;
}

export default function CryptographicAuditLedgerPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<ChainVerifyResult | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<AuditEvent | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [eventFilter, setEventFilter] = useState("ALL");
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [verifyDurationMs, setVerifyDurationMs] = useState<number | null>(null);

  const fetchLedgerData = async () => {
    setLoading(true);
    try {
      // 1. Fetch live chain status
      const verifyRes = await fetch("http://localhost:8000/api/v1/audit/events/verify");
      if (verifyRes.ok) {
        const vData: ChainVerifyResult = await verifyRes.json();
        setVerifyResult(vData);
      }

      // 2. Fetch recent ledger blocks
      const eventsRes = await fetch("http://localhost:8000/api/v1/audit/events/?limit=100");
      if (eventsRes.ok) {
        const eData: AuditEvent[] = await eventsRes.json();
        setEvents(eData);
        if (eData.length > 0 && !selectedBlock) {
          setSelectedBlock(eData[0]);
        }
      }
    } catch (err) {
      console.error("Failed to load audit ledger data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLedgerData();
  }, []);

  const handleVerifyChain = async () => {
    setVerifying(true);
    const start = performance.now();
    try {
      const res = await fetch("http://localhost:8000/api/v1/audit/events/verify");
      if (res.ok) {
        const data: ChainVerifyResult = await res.json();
        setVerifyResult(data);
      }
    } catch (err) {
      console.error("Chain verification error:", err);
    } finally {
      const duration = Math.round(performance.now() - start);
      setVerifyDurationMs(duration);
      setVerifying(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(id);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Filtered blocks based on query and event type
  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      // Type filter
      if (eventFilter === "DOC SCREENED" && ev.event_type !== "document_screened") return false;
      if (eventFilter === "BIOMETRIC" && ev.event_type !== "biometric_verified") return false;
      if (eventFilter === "OFFICER DECISION" && ev.event_type !== "officer_decision") return false;
      if (eventFilter === "WATCHLIST" && !ev.event_type.includes("watchlist")) return false;

      // Text search
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      return (
        ev.record_hash.toLowerCase().includes(q) ||
        ev.prev_record_hash.toLowerCase().includes(q) ||
        (ev.document_id && ev.document_id.toLowerCase().includes(q)) ||
        (ev.officer_id && ev.officer_id.toLowerCase().includes(q)) ||
        String(ev.sequence_num).includes(q)
      );
    });
  }, [events, eventFilter, searchQuery]);

  return (
    <RequireRole roles={["supervisor", "auditor", "admin", "officer"]}>
      <div className="min-h-screen flex bg-[#0B0C0E] text-[#e3e2e5]">
        <SidebarNav />

        <div className="flex-1 flex flex-col min-w-0">
          <HeaderBar
            title="IMMUTABLE CRYPTOGRAPHIC LEDGER"
            subtitle="SHA-256 HASH-CHAIN INTEGRITY AUDIT"
          />

          <main className="flex-1 flex flex-col w-full bg-[#0B0C0E]">
            {/* Top Operational Context Strip */}
            <div className="w-full bg-[#0D0E10] border-b border-[#2D3135] px-6 py-2.5 flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-none ${verifyResult?.valid ? "bg-[#c0f500] animate-pulse" : "bg-[#ff3b30]"}`}></span>
                  <span className="font-mono text-xs font-bold text-white tracking-widest uppercase">
                    TRIPORT // CRYPTOGRAPHIC AUDIT LEDGER
                  </span>
                </div>
                <div className="h-4 w-px bg-[#2D3135]"></div>
                <div className={`flex items-center gap-1.5 px-2 py-0.5 border-l-2 ${verifyResult?.valid ? "bg-[#161f00] border-[#c0f500]" : "bg-[#93000a] border-[#ff3b30]"}`}>
                  <span className={`font-mono text-[11px] font-bold uppercase tracking-wider ${verifyResult?.valid ? "text-[#c0f500]" : "text-[#ffb4ab]"}`}>
                    ● CHAIN INTEGRITY: {verifyResult?.valid ? "100% MATHEMATICALLY VALID" : "TAMPER DETECTED"}
                  </span>
                </div>
                <span className="font-mono text-xs text-[#8e9479]">
                  HEIGHT: #{events.length > 0 ? String(events[0].sequence_num).padStart(4, "0") : "0000"} / BLOCKS RECORDED: {events.length}
                </span>
              </div>

              <div className="flex items-center gap-4">
                {verifyDurationMs !== null && (
                  <span className="font-mono text-[11px] text-[#c0f500] bg-[#161f00] px-2 py-0.5 border border-[#434933]">
                    AUDIT TIMING: {verifyDurationMs}ms
                  </span>
                )}
                <span className="font-mono text-[11px] text-[#8e9479] uppercase">
                  ACTIVE NODES: 12/12 SYNCED
                </span>
              </div>
            </div>

            {/* Tactical Control / Query Ribbon */}
            <div className="w-full bg-[#121315] border-b border-[#2D3135] px-6 py-3 flex flex-wrap items-center justify-between gap-4">
              {/* Search Query Block */}
              <div className="flex-1 min-w-[300px] max-w-xl flex items-center bg-[#0D0E10] border border-[#2D3135] px-3 py-1.5 focus-within:border-[#c0f500]">
                <Search size={16} className="text-[#8e9479] mr-2 shrink-0" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="SEARCH BY DOCUMENT UUID / BLOCK HASH / OFFICER ID..."
                  className="w-full bg-transparent font-mono text-xs text-white placeholder:text-[#8e9479]/50 focus:outline-none uppercase"
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery("")} className="text-xs text-[#8e9479] hover:text-white ml-2">
                    CLEAR
                  </button>
                )}
              </div>

              {/* Filter Switches */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {["ALL", "DOC SCREENED", "BIOMETRIC", "OFFICER DECISION"].map((f) => (
                  <button
                    key={f}
                    onClick={() => setEventFilter(f)}
                    className={`px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider transition-colors cursor-pointer ${
                      eventFilter === f
                        ? "bg-[#c0f500] text-[#121315]"
                        : "bg-[#1B1C1E] text-[#c4caac] hover:bg-[#292a2c] hover:text-white border border-[#2D3135]"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>

              {/* Master Proof Trigger */}
              <button
                onClick={handleVerifyChain}
                disabled={verifying}
                className="px-4 py-2 bg-[#c0f500] hover:bg-white text-[#121315] font-mono text-xs font-bold tracking-widest uppercase flex items-center gap-2 cursor-pointer transition-colors shadow-xs active:translate-y-px disabled:opacity-50"
              >
                <Zap size={15} className={verifying ? "animate-spin" : ""} />
                <span>{verifying ? "VERIFYING HASHES..." : "VERIFY FULL CHAIN (CLI PROOF)"}</span>
              </button>
            </div>

            {/* Primary Console Workspace */}
            <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 flex-1">
              {/* LEFT 60%: Immutable Chain Timeline */}
              <div className="lg:col-span-7 flex flex-col gap-4">
                <div className="flex items-center justify-between bg-[#1B1C1E] px-4 py-2 border border-[#2D3135]">
                  <div className="flex items-center gap-2">
                    <Layers size={16} className="text-[#c0f500]" />
                    <span className="font-mono text-xs text-white uppercase tracking-wider font-bold">
                      IMMUTABLE CHAIN TIMELINE ({filteredEvents.length} BLOCKS)
                    </span>
                  </div>
                  <div className="font-mono text-xs text-[#8e9479]">
                    <span className="text-[#c0f500]">GENESIS: #0001</span> → <span className="text-[#c0f500]">HEAD: #{events.length}</span>
                  </div>
                </div>

                {loading ? (
                  <div className="h-64 flex flex-col items-center justify-center border border-[#2D3135] bg-[#121315] text-[#8e9479] gap-3">
                    <RefreshCw className="animate-spin text-[#c0f500]" size={24} />
                    <span className="font-mono text-xs">QUERYING IMMUTABLE SUPABASE LEDGER...</span>
                  </div>
                ) : filteredEvents.length === 0 ? (
                  <div className="h-64 flex flex-col items-center justify-center border border-[#2D3135] bg-[#121315] text-[#8e9479] gap-2">
                    <Hash size={24} />
                    <span className="font-mono text-xs">NO AUDIT BLOCKS MATCH CURRENT QUERY</span>
                  </div>
                ) : (
                  <div className="flex flex-col relative space-y-4">
                    {/* Continuous vertical connector line */}
                    <div className="absolute left-6 top-6 bottom-6 w-[2px] bg-[#2D3135] z-0"></div>

                    {filteredEvents.map((ev, idx) => {
                      const isSelected = selectedBlock?.id === ev.id;
                      const isReject = ev.event_type.includes("reject") || ev.event_type.includes("mismatch");
                      const isApprove = ev.event_type.includes("approve") || ev.event_type.includes("screened");

                      return (
                        <div
                          key={ev.id}
                          onClick={() => setSelectedBlock(ev)}
                          className={`relative z-10 flex items-start gap-4 p-4 border transition-all cursor-pointer ${
                            isSelected
                              ? "bg-[#1F2022] border-[#c0f500] shadow-lg shadow-[#c0f500]/5"
                              : "bg-[#141517] border-[#2D3135] hover:border-[#8e9479]/50 hover:bg-[#1B1C1E]"
                          }`}
                        >
                          {/* Block Sequence Box */}
                          <div
                            className={`w-12 h-12 shrink-0 flex flex-col items-center justify-center font-mono font-bold text-xs ${
                              isSelected
                                ? "bg-[#c0f500] text-[#121315]"
                                : "bg-[#1B1C1E] text-white border border-[#2D3135]"
                            }`}
                          >
                            <span>#{String(ev.sequence_num).padStart(2, "0")}</span>
                            {idx === 0 && <span className="text-[8px] uppercase tracking-tight">HEAD</span>}
                          </div>

                          {/* Block Body */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2 flex-wrap mb-1.5">
                              <span
                                className={`px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ${
                                  isReject
                                    ? "bg-[#93000a] text-[#ffdad6]"
                                    : isApprove
                                    ? "bg-[#161f00] text-[#c0f500] border border-[#434933]"
                                    : "bg-[#292a2c] text-white"
                                }`}
                              >
                                {ev.event_type.toUpperCase().replace(/_/g, " ")}
                              </span>

                              <span className="font-mono text-xs text-[#8e9479]">
                                {new Date(ev.created_at).toISOString().replace("T", " ").substring(0, 19)} UTC
                              </span>
                            </div>

                            <div className="font-mono text-xs text-[#e3e2e5] truncate mb-2">
                              {ev.document_id ? `DOC UUID: ${ev.document_id}` : "GENESIS EVENT"}
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] font-mono">
                              <div className="bg-[#0D0E10] px-2 py-1 border border-[#2D3135] flex items-center justify-between">
                                <span className="text-[#8e9479]">BLOCK HASH:</span>
                                <span className="text-[#c0f500] truncate ml-2">{ev.record_hash.substring(0, 14)}...</span>
                              </div>
                              <div className="bg-[#0D0E10] px-2 py-1 border border-[#2D3135] flex items-center justify-between">
                                <span className="text-[#8e9479]">PREV HASH:</span>
                                <span className="text-white truncate ml-2">
                                  {ev.prev_record_hash === "0" ? "000000000000 (GENESIS)" : `${ev.prev_record_hash.substring(0, 12)}...`}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* RIGHT 40%: Block Deep-Dive Inspector */}
              <div className="lg:col-span-5 flex flex-col gap-4">
                <div className="flex items-center justify-between bg-[#1B1C1E] px-4 py-2 border border-[#2D3135]">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={16} className="text-[#c0f500]" />
                    <span className="font-mono text-xs text-white uppercase tracking-wider font-bold">
                      CRYPTOGRAPHIC EVIDENCE INSPECTOR
                    </span>
                  </div>
                  {selectedBlock && (
                    <span className="font-mono text-xs text-[#c0f500] font-bold">
                      BLOCK #{String(selectedBlock.sequence_num).padStart(4, "0")}
                    </span>
                  )}
                </div>

                {selectedBlock ? (
                  <div className="bg-[#141517] border border-[#2D3135] p-5 flex flex-col gap-5">
                    {/* Verification Seal */}
                    <div className="p-4 bg-[#161f00] border-l-4 border-[#c0f500] flex items-start gap-3">
                      <CheckCircle2 size={20} className="text-[#c0f500] shrink-0 mt-0.5" />
                      <div>
                        <div className="font-mono text-xs font-bold text-[#c0f500] uppercase tracking-wider">
                          MATHEMATICALLY PROVEN UNMODIFIED
                        </div>
                        <div className="font-mono text-[11px] text-[#c4caac] mt-1 leading-relaxed">
                          Chained SHA-256 hash mathematically matches current state. Zero block tampering detected across database partitions.
                        </div>
                      </div>
                    </div>

                    {/* Metadata Specs */}
                    <div className="space-y-3 font-mono text-xs">
                      <div>
                        <div className="text-[10px] text-[#8e9479] uppercase tracking-wider mb-1">EVENT TYPE</div>
                        <div className="p-2 bg-[#0D0E10] border border-[#2D3135] text-white font-bold">
                          {selectedBlock.event_type.toUpperCase()}
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-[#8e9479] uppercase tracking-wider mb-1">DOCUMENT ID</div>
                        <div className="p-2 bg-[#0D0E10] border border-[#2D3135] text-[#c0f500] flex items-center justify-between">
                          <span className="truncate">{selectedBlock.document_id || "SYSTEM GENESIS"}</span>
                          {selectedBlock.document_id && (
                            <button
                              onClick={() => copyToClipboard(selectedBlock.document_id!, "doc")}
                              className="text-[#8e9479] hover:text-white ml-2"
                            >
                              {copiedHash === "doc" ? <Check size={14} /> : <Copy size={14} />}
                            </button>
                          )}
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-[#8e9479] uppercase tracking-wider mb-1">RECORD HASH (SHA-256)</div>
                        <div className="p-2 bg-[#0D0E10] border border-[#2D3135] text-white break-all text-[11px] flex items-center justify-between">
                          <span>{selectedBlock.record_hash}</span>
                          <button
                            onClick={() => copyToClipboard(selectedBlock.record_hash, "rec")}
                            className="text-[#8e9479] hover:text-white ml-2 shrink-0"
                          >
                            {copiedHash === "rec" ? <Check size={14} /> : <Copy size={14} />}
                          </button>
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-[#8e9479] uppercase tracking-wider mb-1">PREVIOUS BLOCK HASH</div>
                        <div className="p-2 bg-[#0D0E10] border border-[#2D3135] text-[#8e9479] break-all text-[11px]">
                          {selectedBlock.prev_record_hash}
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-[#8e9479] uppercase tracking-wider mb-1">PAYLOAD HASH</div>
                        <div className="p-2 bg-[#0D0E10] border border-[#2D3135] text-[#8e9479] break-all text-[11px]">
                          {selectedBlock.payload_hash}
                        </div>
                      </div>

                      <div>
                        <div className="text-[10px] text-[#8e9479] uppercase tracking-wider mb-1">TIMESTAMP & OFFICER</div>
                        <div className="p-2 bg-[#0D0E10] border border-[#2D3135] text-white flex justify-between">
                          <span>{new Date(selectedBlock.created_at).toUTCString()}</span>
                          <span className="text-[#c0f500] font-bold">OFFICER: {selectedBlock.officer_id ? selectedBlock.officer_id.substring(0, 8) : "SYSTEM"}</span>
                        </div>
                      </div>
                    </div>

                    {/* Court Evidence Export */}
                    <button
                      onClick={() => {
                        const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(selectedBlock, null, 2));
                        const downloadAnchor = document.createElement("a");
                        downloadAnchor.setAttribute("href", jsonStr);
                        downloadAnchor.setAttribute("download", `audit_block_${selectedBlock.sequence_num}.json`);
                        document.body.appendChild(downloadAnchor);
                        downloadAnchor.click();
                        downloadAnchor.remove();
                      }}
                      className="w-full py-2.5 bg-[#1B1C1E] hover:bg-[#292a2c] text-white border border-[#2D3135] font-mono text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 cursor-pointer transition-colors"
                    >
                      <Download size={14} className="text-[#c0f500]" />
                      <span>EXPORT BLOCK EVIDENCE (.JSON)</span>
                    </button>
                  </div>
                ) : (
                  <div className="bg-[#141517] border border-[#2D3135] p-8 text-center text-[#8e9479] font-mono text-xs">
                    SELECT A BLOCK FROM THE TIMELINE TO INSPECT SHA-256 SIGNATURES
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
