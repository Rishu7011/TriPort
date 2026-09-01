"use client";

import React from "react";
import { useAuth } from "../lib/auth/AuthContext";
import {
  Activity,
} from "lucide-react";

interface HeaderBarProps {
  title?: string;
  subtitle?: string;
  children?: React.ReactNode;
}

export function HeaderBar({
  title = "TRIPORT SCREENING CONSOLE",
  subtitle = "BORDER CONTROL TERMINAL",
  children,
}: HeaderBarProps) {
  const { user } = useAuth();

  return (
    <header className="h-16 border-b border-border bg-surface flex items-center justify-between px-4 sm:px-6 shrink-0 z-20">
      {/* Title & Subtitle */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded bg-surface-raised border border-border font-mono text-[11px] text-brand">
          <span className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse" />
          <span>GATEWAY ONLINE</span>
        </div>

        <div className="min-w-0">
          <h1 className="font-display font-bold text-sm sm:text-base tracking-tight text-text uppercase truncate">
            {title}
          </h1>
          {subtitle && (
            <div className="font-mono text-[10px] sm:text-[11px] text-text-muted truncate uppercase tracking-wider">
              {subtitle}
            </div>
          )}
        </div>
      </div>

      {/* Center/Right Custom Content & System Pulse */}
      <div className="flex items-center gap-3 sm:gap-4 shrink-0">
        {children}

        {/* Checkpoint & Officer info badge */}
        {user && (
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-surface-raised border border-border rounded font-mono text-xs text-text-muted">
            <Activity size={14} className="text-brand" />
            <span>
              NODE: <strong className="text-text">{user.checkpoint_id}</strong>
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
