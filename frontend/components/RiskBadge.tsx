"use client";

import React from "react";
import { ShieldCheck, AlertTriangle, ShieldX, AlertOctagon } from "lucide-react";

interface SubScoreBreakdown {
  validation_score: number;
  tampering_score: number;
  face_match_score: number;
  blacklist_hit_score: number;
}

interface RiskBadgeProps {
  score: number;
  band: "low" | "medium" | "high" | "critical" | string;
  subScores?: SubScoreBreakdown;
  degraded?: boolean;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({
  score,
  band,
  subScores,
  degraded = false,
}) => {
  const getBandConfig = () => {
    const b = band?.toLowerCase();
    switch (b) {
      case "low":
        return {
          label: "LOW THREAT — CLEAR",
          color: "text-emerald-400",
          border: "border-emerald-500/40",
          bg: "bg-emerald-950/40",
          glow: "shadow-emerald-500/20",
          barColor: "bg-gradient-to-r from-emerald-500 to-cyan-400",
          icon: ShieldCheck,
        };
      case "medium":
        return {
          label: "MEDIUM THREAT — INSPECT",
          color: "text-amber-400",
          border: "border-amber-500/40",
          bg: "bg-amber-950/40",
          glow: "shadow-amber-500/20",
          barColor: "bg-gradient-to-r from-amber-500 to-yellow-400",
          icon: AlertTriangle,
        };
      case "high":
        return {
          label: "HIGH THREAT — SECONDARY HOLD",
          color: "text-orange-400",
          border: "border-orange-500/40",
          bg: "bg-orange-950/40",
          glow: "shadow-orange-500/20",
          barColor: "bg-gradient-to-r from-orange-500 to-red-500",
          icon: ShieldX,
        };
      case "critical":
      default:
        return {
          label: "CRITICAL THREAT — IMMEDIATE REJECTION",
          color: "text-red-400",
          border: "border-red-500/50",
          bg: "bg-red-950/50",
          glow: "shadow-red-500/30",
          barColor: "bg-gradient-to-r from-red-600 to-rose-500",
          icon: AlertOctagon,
        };
    }
  };

  const config = getBandConfig();
  const Icon = config.icon;
  const clampedScore = Math.min(100, Math.max(0, Math.round(score)));

  return (
    <div className={`p-5 rounded-xl border ${config.border} ${config.bg} shadow-lg ${config.glow} transition-all duration-300`}>
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-2.5">
          <div className={`p-2 rounded-lg bg-slate-900/80 border border-slate-800 ${config.color}`}>
            <Icon className="w-6 h-6" />
          </div>
          <div>
            <span className="text-[11px] font-mono tracking-widest text-slate-400 uppercase">
              SYNTHESIZED THREAT ASSESSMENT
            </span>
            <h3 className={`text-base font-bold font-mono tracking-wide ${config.color}`}>
              {config.label}
            </h3>
          </div>
        </div>

        <div className="text-right">
          <span className="text-3xl font-black font-mono text-white tracking-tight">
            {clampedScore}
          </span>
          <span className="text-xs font-mono text-slate-400">/100</span>
        </div>
      </div>

      {/* Progress Meter */}
      <div className="w-full bg-slate-900/90 rounded-full h-3 p-0.5 border border-slate-800 mb-4 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${config.barColor}`}
          style={{ width: `${clampedScore}%` }}
        />
      </div>

      {/* Sub-Score Weight Breakdown */}
      {subScores && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
          <div className="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
            <span className="text-[10px] text-slate-400 block">RULES (30%)</span>
            <span className="font-bold text-slate-200">{Math.round(subScores.validation_score * 100)}% Risk</span>
          </div>
          <div className="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
            <span className="text-[10px] text-slate-400 block">TAMPERING (35%)</span>
            <span className="font-bold text-slate-200">{Math.round(subScores.tampering_score * 100)}% Risk</span>
          </div>
          <div className="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
            <span className="text-[10px] text-slate-400 block">FACE MATCH (20%)</span>
            <span className="font-bold text-slate-200">{Math.round(subScores.face_match_score * 100)}% Risk</span>
          </div>
          <div className="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
            <span className="text-[10px] text-slate-400 block">BLACKLIST (15%)</span>
            <span className="font-bold text-slate-200">{Math.round(subScores.blacklist_hit_score * 100)}% Hit</span>
          </div>
        </div>
      )}
    </div>
  );
};
