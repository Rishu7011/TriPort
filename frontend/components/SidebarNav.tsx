"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../lib/auth/AuthContext";
import {
  Shield,
  Scan,
  History,
  Activity,
  GitFork,
  Settings,
  LogOut,
  User,
  Menu,
  X,
} from "lucide-react";

export function SidebarNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, role, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isAuditor = role === "auditor";
  const isOfficer = role === "officer";

  const navItems = [
    // Officer, Supervisor, Admin only (NOT auditor)
    ...(!isAuditor
      ? [
          {
            href: "/",
            label: "New Screening",
            icon: Scan,
            active: pathname === "/" || pathname.startsWith("/scan"),
          },
        ]
      : []),
    // Supervisor, Admin, Auditor, Officer can view audit/search
    {
      href: "/audit",
      label: "Audit Ledger",
      icon: History,
      active: pathname.startsWith("/audit"),
    },
    // Command dashboard (Supervisor, Auditor, Admin)
    ...(!isOfficer
      ? [
          {
            href: "/command",
            label: "National Command",
            icon: Activity,
            active: pathname === "/command",
          },
          {
            href: "/command/clusters",
            label: "Fraud Clusters",
            icon: GitFork,
            active: pathname === "/command/clusters",
          },
        ]
      : []),
    // Admin only
    ...(role === "admin"
      ? [
          {
            href: "/command/admin",
            label: "Rules & Watchlist",
            icon: Settings,
            active: pathname === "/command/admin",
          },
        ]
      : []),
  ];

  const handleSignOut = () => {
    logout();
    router.push("/login");
  };

  return (
    <>
      {/* Mobile Toggle Button (Tablet/Mobile) */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label="Toggle Navigation Menu"
        className="md:hidden fixed top-3 left-3 z-50 p-2 bg-surface border border-border rounded text-text hover:text-brand"
      >
        {mobileOpen ? <X size={20} strokeWidth={1.5} /> : <Menu size={20} strokeWidth={1.5} />}
      </button>

      {/* Backdrop for mobile */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          className="md:hidden fixed inset-0 bg-black/70 z-40 backdrop-blur-xs"
        />
      )}

      {/* Main Left Rail */}
      <aside
        className={`fixed left-0 top-0 h-full flex flex-col z-40 bg-surface border-r border-border transition-all duration-300 group
          ${mobileOpen ? "translate-x-0 w-64" : "-translate-x-full md:translate-x-0 md:w-[72px] md:hover:w-60"}
        `}
      >
        {/* Terminal Header */}
        <div className="h-16 flex items-center px-4 border-b border-border whitespace-nowrap overflow-hidden shrink-0">
          <div className="w-10 h-10 rounded bg-surface-raised border border-border flex items-center justify-center text-brand shrink-0">
            <Shield size={22} strokeWidth={1.5} />
          </div>
          <div className="ml-3 opacity-0 md:group-hover:opacity-100 transition-opacity duration-200 min-w-0">
            <div className="font-display font-bold text-sm tracking-tight text-text uppercase">
              TriPort Core
            </div>
            <div className="font-mono text-[10px] text-brand uppercase tracking-wider">
              {role ? `${role.toUpperCase()} CONSOLE` : "ACTIVE DUTY"}
            </div>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 py-4 flex flex-col gap-1 overflow-y-auto overflow-x-hidden">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center px-4 py-3 border-l-2 transition-all duration-150 ${
                  item.active
                    ? "border-brand bg-surface-raised text-brand font-semibold"
                    : "border-transparent text-text-muted hover:bg-surface-raised hover:text-text"
                }`}
              >
                <div className="w-6 flex justify-center shrink-0">
                  <Icon
                    size={20}
                    strokeWidth={1.5}
                    className={item.active ? "text-brand" : "text-text-muted"}
                  />
                </div>
                <span className="ml-4 whitespace-nowrap opacity-0 md:group-hover:opacity-100 transition-opacity duration-200 font-body text-xs font-medium">
                  {item.label}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* User Badge & Sign Out Footer */}
        <div className="border-t border-border p-3 flex flex-col gap-2 shrink-0 bg-surface">
          {user && (
            <div className="flex items-center gap-3 px-1 py-1 rounded bg-surface-raised/60 border border-border/60 overflow-hidden">
              <div className="w-8 h-8 rounded-full bg-brand/10 border border-brand/40 flex items-center justify-center text-brand shrink-0">
                <User size={16} strokeWidth={1.5} />
              </div>
              <div className="opacity-0 md:group-hover:opacity-100 transition-opacity duration-200 min-w-0 flex-1">
                <div className="font-body text-xs font-semibold text-text truncate">
                  {user.name || user.email}
                </div>
                <div className="font-mono text-[10px] text-text-muted truncate">
                  {user.badge_number} • {user.checkpoint_id}
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <button
              onClick={handleSignOut}
              aria-label="Sign Out"
              className="flex items-center w-full px-2 py-2 text-text-muted hover:text-risk-critical hover:bg-risk-critical/10 rounded transition-colors text-xs font-mono"
            >
              <div className="w-6 flex justify-center shrink-0">
                <LogOut size={16} strokeWidth={1.5} />
              </div>
              <span className="ml-3 whitespace-nowrap opacity-0 md:group-hover:opacity-100 transition-opacity duration-200 uppercase tracking-wider text-[11px]">
                Sign Out
              </span>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
