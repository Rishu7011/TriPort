"use client";

import React from "react";
import { UserCheck, UserX, ScanFace, Users, Link2, AlertTriangle, ShieldCheck } from "lucide-react";

interface DedupHit {
  document_id: string;
  similarity: number;
}

interface FaceMatchPanelProps {
  passportPhotoUrl?: string | null;
  livePhotoUrl?: string | null;
  matched: boolean;
  matchScore: number;
  threshold?: number;
  personClusterId?: string | null;
  dedupHits?: DedupHit[];
  hasLivePhoto?: boolean;
}

export const FaceMatchPanel: React.FC<FaceMatchPanelProps> = ({
  passportPhotoUrl,
  livePhotoUrl,
  matched,
  matchScore,
  threshold = 0.6,
  personClusterId,
  dedupHits = [],
  hasLivePhoto = true,
}) => {
  const percentage = Math.round(matchScore * 100);

  return (
    <div className="space-y-6">
      {/* Biometric Match Header */}
      <div className="glass-panel p-5 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-xl ${
            !hasLivePhoto
              ? "bg-slate-900 text-slate-400 border border-slate-800"
              : matched
              ? "bg-emerald-950/80 text-emerald-400 border border-emerald-500/40"
              : "bg-red-950/80 text-red-400 border border-red-500/40"
          }`}>
            <ScanFace className="w-6 h-6" />
          </div>
          <div>
            <span className="text-[11px] font-mono text-slate-400 uppercase block">
              1:1 BIOMETRIC FACIAL VERIFICATION (FACENET / ARCFACE)
            </span>
            <h3 className="text-base font-bold font-mono text-slate-100">
              {!hasLivePhoto
                ? "Live Webcam Photo Not Provided (1:1 Skipped)"
                : matched
                ? "Biometric Identity Confirmed"
                : "Biometric Impersonation Alert"}
            </h3>
          </div>
        </div>

        {hasLivePhoto && (
          <div className="flex items-center gap-3 self-end sm:self-auto">
            <div className="text-right font-mono">
              <span className="text-2xl font-black text-white">{percentage}%</span>
              <span className="text-xs text-slate-400 block">Match (Threshold: {threshold * 100}%)</span>
            </div>
            <span className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold border ${
              matched
                ? "bg-emerald-950/80 border-emerald-500/50 text-emerald-400"
                : "bg-red-950/80 border-red-500/50 text-red-400"
            }`}>
              {matched ? "VERIFIED" : "MISMATCH"}
            </span>
          </div>
        )}
      </div>

      {/* Visual Portrait Comparison Deck */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Document Portrait */}
        <div className="glass-panel p-4 rounded-xl flex flex-col items-center">
          <span className="text-[11px] font-mono text-slate-400 mb-3 uppercase tracking-wider">
            1. Document Scanned Portrait
          </span>
          <div className="relative w-48 h-56 rounded-xl overflow-hidden bg-slate-950 border border-slate-800 flex items-center justify-center">
            {passportPhotoUrl ? (
              <img
                src={passportPhotoUrl}
                alt="Passport Photo"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center gap-2 text-slate-500">
                <ScanFace className="w-10 h-10 stroke-1" />
                <span className="text-xs font-mono">Passport Portrait</span>
              </div>
            )}
            <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-900/90 text-[10px] font-mono text-cyan-400 border border-cyan-500/30">
              DOC EMBEDDING
            </div>
          </div>
        </div>

        {/* Live Camera Capture */}
        <div className="glass-panel p-4 rounded-xl flex flex-col items-center">
          <span className="text-[11px] font-mono text-slate-400 mb-3 uppercase tracking-wider">
            2. Live Checkpoint Webcam Capture
          </span>
          <div className="relative w-48 h-56 rounded-xl overflow-hidden bg-slate-950 border border-slate-800 flex items-center justify-center">
            {livePhotoUrl ? (
              <img
                src={livePhotoUrl}
                alt="Live Camera Snapshot"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center gap-2 text-slate-500">
                <ScanFace className="w-10 h-10 stroke-1" />
                <span className="text-xs font-mono">Live Snapshot</span>
              </div>
            )}
            <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-900/90 text-[10px] font-mono text-emerald-400 border border-emerald-500/30">
              LIVE EMBEDDING
            </div>
          </div>
        </div>
      </div>

      {/* 1:N Deduplication Cluster Search */}
      <div className="glass-panel p-5 rounded-xl border border-slate-800">
        <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-cyan-400" />
            <h4 className="text-xs font-bold font-mono tracking-wider text-slate-300 uppercase">
              1:N pgvector Deduplication & Alias Cluster Search
            </h4>
          </div>
          {personClusterId && (
            <span className="text-[10px] font-mono text-slate-400">
              Cluster: <strong className="text-slate-200">{personClusterId.slice(0, 8)}...</strong>
            </span>
          )}
        </div>

        {dedupHits.length > 0 ? (
          <div className="p-3.5 rounded-lg bg-red-950/30 border border-red-500/40 space-y-2">
            <div className="flex items-center gap-2 text-xs font-mono font-bold text-red-400">
              <AlertTriangle className="w-4 h-4" />
              <span>Multi-Identity Detection: Facial embedding matched {dedupHits.length} other passport(s)</span>
            </div>
            <div className="space-y-1.5 mt-2">
              {dedupHits.map((hit, idx) => (
                <div key={idx} className="flex items-center justify-between text-xs font-mono bg-slate-900/80 p-2 rounded border border-slate-800">
                  <div className="flex items-center gap-2 text-slate-300">
                    <Link2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Linked Document: <strong className="text-white">{hit.document_id}</strong></span>
                  </div>
                  <span className="text-emerald-400 font-bold">
                    {Math.round(hit.similarity * 100)}% Cosine Match
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400 p-2 rounded bg-slate-900/40">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>No conflicting passport identities found for this biological face in database.</span>
          </div>
        )}
      </div>
    </div>
  );
};
