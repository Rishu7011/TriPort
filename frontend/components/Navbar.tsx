"use client";

import React, { useState, useEffect } from "react";
import { ShieldCheck, ShieldAlert, Cpu, Activity, User, Lock, Radio } from "lucide-react";

interface NavbarProps {
  currentRole: string;
  onRoleChange: (role: string) => void;
  degraded: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ currentRole, onRoleChange, degraded }) => {
  const [timeStr, setTimeStr] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toUTCString().replace("GMT", "UTC"));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl sticky top-0 z-50 px-4 lg:px-8 py-3">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        
        {/* Brand & Station Info */}
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-emerald-600 shadow-lg shadow-cyan-500/20">
            <ShieldCheck className="w-6 h-6 text-slate-950 stroke-[2.5]" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-wider text-white uppercase font-mono">
                BorderGuard<span className="text-cyan-400 font-extrabold">-AI</span>
              </h1>
              <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/30 text-cyan-400 font-mono font-semibold">
                v1.0 DEFENSE
              </span>
            </div>
            <p className="text-xs text-slate-400 flex items-center gap-2">
              <span>Station: <strong className="text-slate-200 font-mono">CP-DEL-T3</strong></span>
              <span>•</span>
              <span className="font-mono text-[11px] text-slate-400">{timeStr || "SYNCING..."}</span>
            </p>
          </div>
        </div>

        {/* Microservices Health Telemetry */}
        <div className="hidden xl:flex items-center gap-2 text-xs font-mono bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800">
          <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
          <span className="text-slate-400">PIPELINE MESH:</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-500/30 text-[10px]">
            OCR/MRZ: 100%
          </span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-500/30 text-[10px]">
            ELA/FORENSICS: 100%
          </span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-500/30 text-[10px]">
            BIOMETRICS: 100%
          </span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-500/30 text-[10px]">
            HASH-CHAIN: ACTIVE
          </span>
        </div>

        {/* Officer Profile & RBAC Role Switcher */}
        <div className="flex items-center gap-3">
          {degraded && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-950/80 border border-amber-500/40 text-amber-400 text-xs font-mono">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>DEGRADED MODE</span>
            </div>
          )}

          <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-800 rounded-lg p-1">
            <User className="w-4 h-4 text-cyan-400 ml-2" />
            <select
              value={currentRole}
              onChange={(e) => onRoleChange(e.target.value)}
              className="bg-transparent text-xs font-mono text-slate-200 pr-2 py-1 outline-none cursor-pointer"
            >
              <option value="officer" className="bg-slate-900 text-slate-200">Officer J. Miller (BG-7492)</option>
              <option value="supervisor" className="bg-slate-900 text-slate-200">Supervisor S. Rao (BG-SUP-014)</option>
              <option value="auditor" className="bg-slate-900 text-slate-200">Auditor M. Chen (BG-AUD-990)</option>
              <option value="admin" className="bg-slate-900 text-slate-200">Administrator (HQ-ADM)</option>
            </select>
          </div>
        </div>

      </div>
    </header>
  );
};
