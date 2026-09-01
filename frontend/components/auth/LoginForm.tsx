"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../lib/auth/AuthContext";
import { Shield, Lock, Mail, ArrowRight, AlertCircle, KeyRound } from "lucide-react";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const user = await login(email, password);
      // Route based on role
      if (user.role === "auditor") {
        router.push("/audit");
      } else {
        router.push("/");
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Authentication failed. Please verify credentials or security badge.";
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const quickFill = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setError(null);
  };

  return (
    <div className="w-full max-w-md mx-auto">
      {/* Terminal Card */}
      <div className="bg-surface border border-border rounded-md p-6 sm:p-8 shadow-2xl relative overflow-hidden">
        {/* Subtle top brand hairline */}
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-brand to-transparent" />

        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded bg-surface-raised border border-border text-brand mb-3">
            <Shield size={26} strokeWidth={1.5} />
          </div>
          <h1 className="font-display text-xl sm:text-2xl font-bold tracking-tight text-text uppercase">
            TriPort Access Control
          </h1>
          <p className="font-mono text-xs text-text-muted mt-1 uppercase tracking-wider">
            Restricted National Security Interface
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-5 p-3 rounded bg-risk-critical/10 border border-risk-critical/30 flex items-start gap-2.5 text-risk-critical text-xs">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <span className="font-body">{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label
              htmlFor="email"
              className="block font-mono text-[11px] uppercase tracking-wider text-text-muted mb-1.5"
            >
              Officer Identity / Email
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">
                <Mail size={16} strokeWidth={1.5} />
              </span>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="officer@triport.gov"
                className="w-full h-11 pl-10 pr-3 bg-bg border border-border rounded text-text font-mono text-xs placeholder:text-text-muted/60 focus:border-brand focus:ring-1 focus:ring-brand outline-none transition-colors"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="password"
              className="block font-mono text-[11px] uppercase tracking-wider text-text-muted mb-1.5"
            >
              Security Passcode
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">
                <Lock size={16} strokeWidth={1.5} />
              </span>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full h-11 pl-10 pr-3 bg-bg border border-border rounded text-text font-mono text-xs placeholder:text-text-muted/60 focus:border-brand focus:ring-1 focus:ring-brand outline-none transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full h-11 mt-2 bg-brand hover:bg-white text-bg font-display text-xs font-bold uppercase tracking-wider rounded transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_12px_rgba(166,255,77,0.25)]"
          >
            {loading ? (
              <span className="font-mono text-xs">Authenticating...</span>
            ) : (
              <>
                <span>Access Terminal</span>
                <ArrowRight size={16} strokeWidth={2} />
              </>
            )}
          </button>
        </form>

        {/* Demo Fast Fill Credentials */}
        <div className="mt-6 pt-5 border-t border-border">
          <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase text-text-muted mb-2.5">
            <KeyRound size={12} />
            <span>Pre-Configured Evaluation Profiles:</span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => quickFill("officer@triport.gov", "officer123")}
              className="p-2 bg-surface-raised hover:bg-border border border-border rounded text-left transition-colors cursor-pointer group"
            >
              <div className="font-mono text-[11px] text-brand font-semibold group-hover:text-white">
                Officer
              </div>
              <div className="font-mono text-[10px] text-text-muted truncate">
                officer@triport.gov
              </div>
            </button>

            <button
              type="button"
              onClick={() =>
                quickFill("supervisor@triport.gov", "supervisor123")
              }
              className="p-2 bg-surface-raised hover:bg-border border border-border rounded text-left transition-colors cursor-pointer group"
            >
              <div className="font-mono text-[11px] text-risk-medium font-semibold group-hover:text-white">
                Supervisor
              </div>
              <div className="font-mono text-[10px] text-text-muted truncate">
                supervisor@triport.gov
              </div>
            </button>

            <button
              type="button"
              onClick={() => quickFill("auditor@triport.gov", "auditor123")}
              className="p-2 bg-surface-raised hover:bg-border border border-border rounded text-left transition-colors cursor-pointer group"
            >
              <div className="font-mono text-[11px] text-risk-high font-semibold group-hover:text-white">
                Auditor
              </div>
              <div className="font-mono text-[10px] text-text-muted truncate">
                auditor@triport.gov
              </div>
            </button>

            <button
              type="button"
              onClick={() => quickFill("admin@triport.gov", "admin123")}
              className="p-2 bg-surface-raised hover:bg-border border border-border rounded text-left transition-colors cursor-pointer group"
            >
              <div className="font-mono text-[11px] text-risk-critical font-semibold group-hover:text-white">
                Admin
              </div>
              <div className="font-mono text-[10px] text-text-muted truncate">
                admin@triport.gov
              </div>
            </button>
          </div>
        </div>

        {/* Footer Security Notice */}
        <div className="mt-5 text-center">
          <p className="font-mono text-[10px] text-text-muted/70">
            SHA-256 Audit Chained • ISO 27001 Compliant Terminal
          </p>
        </div>
      </div>
    </div>
  );
}
