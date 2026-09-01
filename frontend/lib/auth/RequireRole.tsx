"use client";

import React, { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthContext";
import type { Role } from "../api/types";
import { ShieldAlert, Lock } from "lucide-react";

interface RequireRoleProps {
  roles?: Role[];
  children: ReactNode;
  fallback?: ReactNode;
}

export function RequireRole({ roles, children, fallback }: RequireRoleProps) {
  const { user, role, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[400px] bg-bg text-text">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-border border-t-brand animate-spin" />
          <span className="font-mono text-xs text-text-muted uppercase tracking-widest">
            Authenticating credentials...
          </span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  if (roles && role && !roles.includes(role)) {
    if (fallback) return <>{fallback}</>;

    return (
      <div className="flex-1 flex items-center justify-center min-h-[400px] p-6">
        <div className="bg-surface border border-border rounded-md p-8 max-w-md w-full text-center flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-risk-critical/10 border border-risk-critical/30 flex items-center justify-center text-risk-critical">
            <ShieldAlert size={24} />
          </div>
          <div>
            <h2 className="font-display text-lg font-bold text-text uppercase tracking-wider">
              Access Restricted
            </h2>
            <p className="font-body text-xs text-text-muted mt-2">
              Your active role (
              <span className="font-mono text-brand uppercase font-bold">
                {role}
              </span>
              ) does not have sufficient security clearance for this terminal
              view.
            </p>
          </div>
          <div className="bg-surface-raised border border-border rounded p-3 w-full text-left font-mono text-[11px] text-text-muted space-y-1">
            <div className="flex items-center gap-2 text-text">
              <Lock size={12} className="text-risk-high" /> Required Clearance:
            </div>
            <div className="text-brand uppercase font-semibold">
              {roles.join(" / ")}
            </div>
            <div>Active Badge: {user?.badge_number || "UNASSIGNED"}</div>
          </div>
          <button
            onClick={() => router.push(role === "auditor" ? "/audit" : "/")}
            className="w-full py-2.5 bg-surface-raised hover:bg-border text-text font-mono text-xs uppercase rounded transition-colors"
          >
            Return to Authorized Workspace
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
