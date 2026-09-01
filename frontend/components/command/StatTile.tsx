"use client";

import React from "react";
import { ArrowUpRight, ArrowDownRight, type LucideIcon } from "lucide-react";

interface StatTileProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: string;
  trendUp?: boolean;
  icon: LucideIcon;
  variant?: "default" | "brand" | "warning" | "critical";
}

export function StatTile({
  title,
  value,
  subtitle,
  trend,
  trendUp,
  icon: Icon,
  variant = "default",
}: StatTileProps) {
  const variantStyles = {
    default: "border-border text-text",
    brand: "border-brand/40 text-brand",
    warning: "border-risk-medium/40 text-risk-medium",
    critical: "border-risk-critical/40 text-risk-critical",
  }[variant];

  return (
    <div className={`bg-surface border rounded-md p-4 sm:p-5 flex flex-col justify-between ${variantStyles}`}>
      <div className="flex items-start justify-between">
        <span className="font-mono text-[11px] uppercase tracking-wider text-text-muted">
          {title}
        </span>
        <div className="w-8 h-8 rounded bg-surface-raised border border-border flex items-center justify-center text-text-muted">
          <Icon size={16} strokeWidth={1.5} />
        </div>
      </div>

      <div className="mt-3">
        <div className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-text">
          {value}
        </div>
        {(subtitle || trend) && (
          <div className="mt-1 flex items-center gap-2 font-mono text-[11px] text-text-muted">
            {trend && (
              <span
                className={`inline-flex items-center gap-0.5 font-bold ${
                  trendUp ? "text-brand" : "text-risk-critical"
                }`}
              >
                {trendUp ? (
                  <ArrowUpRight size={12} />
                ) : (
                  <ArrowDownRight size={12} />
                )}
                {trend}
              </span>
            )}
            {subtitle && <span>{subtitle}</span>}
          </div>
        )}
      </div>
    </div>
  );
}
