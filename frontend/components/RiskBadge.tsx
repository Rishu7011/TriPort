"use client";

import React from "react";
import type { RiskBand } from "../lib/api/types";
import { ShieldCheck, AlertTriangle, AlertOctagon, ShieldAlert } from "lucide-react";

interface RiskBadgeProps {
  band: RiskBand | string | null | undefined;
  score?: number | null;
  size?: "sm" | "md" | "lg";
  showScore?: boolean;
}

export function RiskBadge({
  band = "low",
  score,
  size = "md",
  showScore = true,
}: RiskBadgeProps) {
  const normalizedBand = (band || "low").toLowerCase() as RiskBand;

  const config = {
    low: {
      label: "Low Risk",
      badgeClass:
        "border-risk-low text-risk-low bg-risk-low/10 glow-low",
      icon: ShieldCheck,
    },
    medium: {
      label: "Medium Risk",
      badgeClass:
        "border-risk-medium text-risk-medium bg-risk-medium/10 glow-medium",
      icon: AlertTriangle,
    },
    high: {
      label: "High Risk",
      badgeClass:
        "border-risk-high text-risk-high bg-risk-high/10 glow-high",
      icon: AlertOctagon,
    },
    critical: {
      label: "Critical Threat",
      badgeClass:
        "border-risk-critical text-risk-critical bg-risk-critical/15 glow-critical font-bold",
      icon: ShieldAlert,
    },
  }[normalizedBand] || {
    label: "Unknown",
    badgeClass: "border-text-muted text-text-muted bg-surface-raised",
    icon: ShieldCheck,
  };

  const Icon = config.icon;

  const sizeClasses = {
    sm: "px-2 py-0.5 text-[10px] gap-1",
    md: "px-3 py-1 text-xs gap-1.5",
    lg: "px-4 py-1.5 text-sm gap-2",
  }[size];

  const iconSizes = {
    sm: 11,
    md: 14,
    lg: 16,
  }[size];

  return (
    <span
      className={`inline-flex items-center rounded-full border font-mono uppercase tracking-wider transition-all duration-200 ${config.badgeClass} ${sizeClasses}`}
    >
      <Icon size={iconSizes} strokeWidth={2} />
      <span>{config.label}</span>
      {showScore && score !== undefined && score !== null && (
        <span className="font-bold border-l border-current/30 pl-1.5 ml-0.5">
          {score.toFixed(1)}
        </span>
      )}
    </span>
  );
}
