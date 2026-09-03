"use client";

import React from "react";
import { useAuth } from "../lib/auth/AuthContext";
import { Activity } from "lucide-react";

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
    <header className="h-16 border-b border-[#2D3135] bg-[#121315] flex items-center justify-between px-4 sm:px-6 shrink-0 z-20">
      {/* Title & Subtitle */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 bg-[#161f00] border border-[#434933] font-mono text-[11px] text-[#c0f500]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#c0f500] animate-pulse" />
          <span className="font-bold">GATEWAY ONLINE</span>
        </div>

        <div className="min-w-0">
          <h1 className="font-mono font-bold text-xs sm:text-sm tracking-tight text-white uppercase truncate">
            {title}
          </h1>
          {subtitle && (
            <div className="font-mono text-[10px] sm:text-[11px] text-[#8e9479] truncate uppercase tracking-wider">
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
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-[#0D0E10] border border-[#2D3135] font-mono text-xs text-[#8e9479]">
            <Activity size={14} className="text-[#c0f500]" />
            <span>
              NODE: <strong className="text-white">{user.checkpoint_id}</strong>
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
