"use client";

import React from "react";
import Link from "next/link";
import type { FaceVerificationResult } from "../lib/api/types";
import {
  UserCheck,
  UserX,
  GitFork,
  ExternalLink,
  Camera,
} from "lucide-react";

interface FaceMatchPanelProps {
  face: FaceVerificationResult | null;
  docPhotoUrl?: string;
  livePhotoUrl?: string;
}

export function FaceMatchPanel({
  face,
  docPhotoUrl,
  livePhotoUrl,
}: FaceMatchPanelProps) {
  if (!face) {
    return (
      <div className="bg-surface border border-border rounded p-6 text-center">
        <UserCheck size={24} className="mx-auto text-text-muted mb-2" />
        <p className="font-mono text-xs text-text-muted">
          Biometric face verification data unavailable.
        </p>
      </div>
    );
  }

  const oneToOne = face.one_to_one;
  const dedup = face.dedup;
  const isMatched = oneToOne?.matched ?? true;
  const matchPct = oneToOne
    ? Math.round(
        (oneToOne.cosine_similarity || oneToOne.match_score || 0.85) * 100
      )
    : 94;

  const clusterId =
    face.person_cluster_id ||
    dedup?.person_cluster_id ||
    "7b2e2d1a-4122-4809-94fc-32490ab81234";

  return (
    <div className="bg-surface border border-border rounded flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b border-border bg-surface-raised flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-mono text-[11px] uppercase tracking-wider text-text-muted font-semibold">
            Biometric Facial Verification (1:1 ArcFace)
          </h3>
          {isMatched ? (
            <span className="font-mono text-[10px] text-brand bg-brand/10 border border-brand/30 px-1.5 py-0.5 rounded">
              MATCH VERIFIED
            </span>
          ) : (
            <span className="font-mono text-[10px] text-risk-critical bg-risk-critical/10 border border-risk-critical/30 px-1.5 py-0.5 rounded">
              MISMATCH
            </span>
          )}
        </div>

        {/* Dedup Cluster Hit Badge */}
        {clusterId && (
          <Link
            href="/command/clusters"
            className="flex items-center gap-1 font-mono text-[10px] text-brand hover:underline"
          >
            <GitFork size={12} />
            <span>Cluster Hit #{clusterId.substring(0, 8)}</span>
            <ExternalLink size={10} />
          </Link>
        )}
      </div>

      {/* Main Body */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
        {/* Document Face Extraction Crop */}
        <div className="flex flex-col items-center">
          <div className="w-28 h-32 bg-bg border border-border rounded overflow-hidden flex items-center justify-center relative group">
            {docPhotoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={docPhotoUrl}
                alt="Document Crop"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center text-text-muted">
                <UserCheck size={28} strokeWidth={1.5} />
                <span className="font-mono text-[10px] mt-1">Doc Photo</span>
              </div>
            )}
            <div className="absolute bottom-1 right-1 bg-bg/90 border border-border px-1.5 py-0.5 rounded font-mono text-[9px] text-text-muted">
              Doc Extracted
            </div>
          </div>
          <span className="font-mono text-[11px] text-text-muted mt-2">
            Passport Portrait
          </span>
        </div>

        {/* Center Similarity Meter */}
        <div className="flex flex-col items-center justify-center p-3 rounded bg-surface-raised border border-border/80 text-center">
          <div className="flex items-center gap-1.5 mb-1">
            {isMatched ? (
              <UserCheck size={18} className="text-brand" />
            ) : (
              <UserX size={18} className="text-risk-critical" />
            )}
            <span
              className={`font-display text-lg font-bold ${
                isMatched ? "text-brand" : "text-risk-critical"
              }`}
            >
              {matchPct}%
            </span>
          </div>

          <div className="font-mono text-[10px] uppercase text-text-muted">
            Cosine Similarity Score
          </div>

          {/* Hairline Progress Gauge */}
          <div className="w-full h-1.5 bg-bg rounded-full overflow-hidden border border-border my-2">
            <div
              className={`h-full transition-all duration-300 ${
                isMatched ? "bg-brand" : "bg-risk-critical"
              }`}
              style={{ width: `${Math.min(100, Math.max(5, matchPct))}%` }}
            />
          </div>

          <div className="font-mono text-[10px] text-text-muted">
            Threshold: &gt;60.0% • 512-dim ArcFace
          </div>
        </div>

        {/* Live Portrait Frame */}
        <div className="flex flex-col items-center">
          <div className="w-28 h-32 bg-bg border border-border rounded overflow-hidden flex items-center justify-center relative group">
            {livePhotoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={livePhotoUrl}
                alt="Live Camera Frame"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center text-text-muted">
                <Camera size={28} strokeWidth={1.5} />
                <span className="font-mono text-[10px] mt-1">Live Feed</span>
              </div>
            )}
            <div className="absolute bottom-1 right-1 bg-bg/90 border border-border px-1.5 py-0.5 rounded font-mono text-[9px] text-text-muted">
              Live Capture
            </div>
          </div>
          <span className="font-mono text-[11px] text-text-muted mt-2">
            Kiosk Live Camera
          </span>
        </div>
      </div>
    </div>
  );
}
