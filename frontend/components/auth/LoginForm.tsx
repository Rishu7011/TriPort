"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../lib/auth/AuthContext";
import {
  Shield,
  Lock,
  BadgeAlert,
  ArrowRight,
  AlertTriangle,
  KeyRound,
  CheckCircle2,
  Cpu,
  UserCheck,
} from "lucide-react";

const PRECONFIGURED_ACCOUNTS = [
  {
    role: "OFFICER",
    badge: "TP-7492",
    email: "officer@triport.gov",
    pass: "officer123",
    color: "border-[#c0f500] text-[#c0f500]",
    desc: "Primary Screening & Bio Match",
  },
  {
    role: "SUPERVISOR",
    badge: "TP-SUP-014",
    email: "supervisor@triport.gov",
    pass: "supervisor123",
    color: "border-[#feb700] text-[#feb700]",
    desc: "Manual Override & Hold Bays",
  },
  {
    role: "AUDITOR",
    badge: "TP-AUD-990",
    email: "auditor@triport.gov",
    pass: "auditor123",
    color: "border-[#38bdf8] text-[#38bdf8]",
    desc: "Cryptographic Ledger Access",
  },
  {
    role: "ADMINISTRATOR",
    badge: "TP-ADM-001",
    email: "admin@triport.gov",
    pass: "admin123",
    color: "border-[#ff3b30] text-[#ffdad6]",
    desc: "Rule & Threshold Policies",
  },
];

export function LoginForm() {
  const [badgeOrEmail, setBadgeOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hardwareKeyActive, setHardwareKeyActive] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleLogin = async (e?: React.FormEvent, overrideEmail?: string, overridePass?: string) => {
    if (e) e.preventDefault();
    const idToUse = overrideEmail || badgeOrEmail;
    const passToUse = overridePass || password;

    if (!idToUse || !passToUse) {
      setError("ENTER BOTH OFFICER BADGE ID / EMAIL AND SECURITY PASSCODE.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const user = await login(idToUse.trim(), passToUse.trim());
      if (user.role === "auditor") {
        router.push("/audit");
      } else if (user.role === "admin") {
        router.push("/command/admin");
      } else {
        router.push("/");
      }
    } catch (err: unknown) {
      const errMsg =
        err instanceof Error
          ? err.message
          : "Authentication failed. Verify credentials or physical security token.";
      setError(errMsg.toUpperCase());
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPreconfigured = (email: string, pass: string) => {
    setBadgeOrEmail(email);
    setPassword(pass);
    setError(null);
    handleLogin(undefined, email, pass);
  };

  return (
    <div className="relative z-10 w-full max-w-[520px] bg-[#141517] border border-[#2D3135] p-6 shadow-2xl flex flex-col gap-4">
      {/* Top Accent Bar: High Contrast Hard Visual Boundary */}
      <div className="h-1 -mt-6 -mx-6 bg-[#c0f500] shadow-[0_0_12px_#c0f500]"></div>

      {/* Module Header: Insignia + Gateway Pill */}
      <div className="flex items-center justify-between pt-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-[#1B1C1E] border border-[#2D3135] flex items-center justify-center text-[#c0f500]">
            <Shield size={18} />
          </div>
          <div>
            <div className="font-mono text-xs text-[#c0f500] tracking-widest leading-none font-bold uppercase">
              TRIPORT GATEWAY
            </div>
            <div className="font-mono text-[10px] text-[#8e9479] tracking-wider leading-none mt-1">
              ENCLAVE SEC-ZONE // 01
            </div>
          </div>
        </div>
        <div className="bg-[#1B1C1E] border border-[#2D3135] px-2 py-1 flex items-center gap-1.5">
          <span className="w-2 h-2 bg-[#c0f500]"></span>
          <span className="font-mono text-[10px] text-white uppercase tracking-wider">
            STATION-04 ONLINE
          </span>
        </div>
      </div>

      {/* Title & Classification Badge */}
      <div className="mt-2 flex flex-col gap-1">
        <h1 className="font-mono text-sm uppercase text-white tracking-tight font-bold">
          OFFICER AUTHENTICATION // RESTRICTED ACCESS
        </h1>
        <div className="bg-[#0D0E10] border border-[#2D3135] px-2.5 py-1.5 flex items-center justify-between">
          <span className="font-mono text-[10px] text-[#8e9479] uppercase">CLASSIFICATION</span>
          <span className="font-mono text-[10px] text-[#c0f500] font-bold tracking-widest uppercase">
            LEVEL 3: TACTICAL ENCLAVE
          </span>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-[#93000a] border-l-4 border-[#ff3b30] text-[#ffdad6] font-mono text-xs flex items-center gap-2">
          <AlertTriangle size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Form Inputs */}
      <form onSubmit={(e) => handleLogin(e)} className="flex flex-col gap-4 mt-1">
        {/* Badge ID Field */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <label className="font-mono text-[10px] uppercase text-[#8e9479] font-bold">
              01. OFFICER BADGE ID OR EMAIL
            </label>
            <span className="font-mono text-[9px] text-[#c0f500] uppercase tracking-wider flex items-center gap-1">
              <CheckCircle2 size={12} />
              CHIP VERIFIED
            </span>
          </div>
          <div className="relative bg-[#0D0E10] border border-[#2D3135] focus-within:border-[#c0f500] flex items-center px-3 py-2.5 transition-colors">
            <BadgeAlert size={16} className="text-[#8e9479] mr-2 shrink-0" />
            <input
              type="text"
              autoComplete="username"
              required
              value={badgeOrEmail}
              onChange={(e) => setBadgeOrEmail(e.target.value)}
              placeholder="e.g. officer@triport.gov OR TP-7492..."
              className="w-full bg-transparent font-mono text-xs text-white focus:outline-none uppercase tracking-wider placeholder:text-[#8e9479]/40"
            />
            <span className="font-mono text-[10px] text-[#8e9479] bg-[#1B1C1E] px-1.5 py-0.5 ml-2 border border-[#2D3135]">
              UID
            </span>
          </div>
        </div>

        {/* Security Passcode Field */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <label className="font-mono text-[10px] uppercase text-[#8e9479] font-bold">
              02. SECURITY PASSCODE
            </label>
            <span className="font-mono text-[9px] text-[#8e9479] uppercase tracking-wider">
              HSM ENCLAVE PIN
            </span>
          </div>
          <div className="relative bg-[#0D0E10] border border-[#2D3135] focus-within:border-[#c0f500] flex items-center px-3 py-2.5 transition-colors">
            <Lock size={16} className="text-[#8e9479] mr-2 shrink-0" />
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full bg-transparent font-mono text-xs text-white focus:outline-none tracking-widest placeholder:text-[#8e9479]/40"
            />
            <span className="font-mono text-[10px] text-[#8e9479] bg-[#1B1C1E] px-1.5 py-0.5 ml-2 border border-[#2D3135]">
              PIN
            </span>
          </div>
        </div>

        {/* Hardware Smart Card Auth Option */}
        <div
          onClick={() => setHardwareKeyActive(!hardwareKeyActive)}
          className={`p-2.5 border flex items-center justify-between cursor-pointer transition-colors ${
            hardwareKeyActive
              ? "bg-[#161f00] border-[#c0f500] text-[#c0f500]"
              : "bg-[#0D0E10] border-[#2D3135] text-[#8e9479] hover:bg-[#1B1C1E]"
          }`}
        >
          <div className="flex items-center gap-2">
            <Cpu size={15} />
            <span className="font-mono text-[10px] uppercase font-bold">
              FIPS 140-3 HARDWARE TOKEN ENCLAVE
            </span>
          </div>
          <span className="font-mono text-[9px] uppercase px-1.5 py-0.5 bg-[#141517] border border-[#2D3135]">
            {hardwareKeyActive ? "INSERTED" : "OPTIONAL"}
          </span>
        </div>

        {/* Submit Action */}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-[#c0f500] hover:bg-white text-[#121315] font-mono text-xs font-bold tracking-widest uppercase flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-md disabled:opacity-50 mt-1"
        >
          {loading ? (
            <span>VERIFYING CRYPTOGRAPHIC BADGE...</span>
          ) : (
            <>
              <span>ESTABLISH SECURE TERMINAL SESSION</span>
              <ArrowRight size={15} />
            </>
          )}
        </button>
      </form>

      {/* 1-CLICK QUICK LOGIN WITH ANY OF THE 4 OPERATIONAL ACCOUNTS */}
      <div className="mt-2 pt-3 border-t border-[#2D3135] flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase text-[#8e9479] font-bold tracking-wider flex items-center gap-1.5">
            <KeyRound size={12} className="text-[#c0f500]" />
            ONE-CLICK ACCOUNT ACCESS (CLICK TO LOGIN)
          </span>
          <span className="font-mono text-[9px] text-[#8e9479]">4 ACTIVE ROLES</span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {PRECONFIGURED_ACCOUNTS.map((acc) => (
            <button
              key={acc.role}
              type="button"
              onClick={() => handleSelectPreconfigured(acc.email, acc.pass)}
              className="p-2.5 bg-[#0D0E10] hover:bg-[#1B1C1E] border border-[#2D3135] hover:border-[#c0f500] text-left transition-all cursor-pointer flex flex-col justify-between group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`font-mono text-[11px] font-bold uppercase tracking-wider ${acc.color}`}>
                  {acc.role}
                </span>
                <span className="font-mono text-[9px] text-[#8e9479] bg-[#141517] px-1 py-0.5 border border-[#2D3135]">
                  {acc.badge}
                </span>
              </div>
              <div className="font-mono text-[10px] text-[#c4caac] truncate">
                {acc.email}
              </div>
              <div className="font-mono text-[9px] text-[#8e9479] flex items-center justify-between mt-1 pt-1 border-t border-[#1B1C1E]">
                <span>PASS: {acc.pass}</span>
                <ArrowRight size={10} className="text-[#8e9479] group-hover:text-[#c0f500] transition-colors" />
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Bottom Footer Notice */}
      <div className="pt-2 border-t border-[#2D3135] text-center font-mono text-[10px] text-[#8e9479] leading-relaxed">
        AUTHORIZED IMMIGRATION & BORDER GUARD PERSONNEL ONLY.
        <br />
        UNAUTHORIZED ACCESS ATTEMPTS ARE LOGGED TO THE IMMUTABLE AUDIT LEDGER.
      </div>
    </div>
  );
}
