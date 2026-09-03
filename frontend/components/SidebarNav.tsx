"use client";

import React, { useState, useEffect } from "react";
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
  ChevronLeft,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
  Layers,
  Share2,
  Sliders,
} from "lucide-react";

export function SidebarNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, role, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  // Load pinned state preference from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("triport_sidebar_collapsed");
    if (saved !== null) {
      setIsCollapsed(saved === "true");
    }
  }, []);

  const toggleCollapsed = () => {
    const next = !isCollapsed;
    setIsCollapsed(next);
    localStorage.setItem("triport_sidebar_collapsed", String(next));
  };

  const isAuditor = role === "auditor";
  const isOfficer = role === "officer";

  const navItems = [
    // Primary Screening: Officer, Supervisor, Admin
    ...(!isAuditor
      ? [
          {
            href: "/",
            num: "01",
            label: "SCREENING CONSOLE",
            sublabel: "Doc & Face Match",
            icon: Scan,
            active: pathname === "/" || pathname.startsWith("/scan"),
          },
        ]
      : []),
    // Audit Ledger: Supervisor, Admin, Auditor, Officer
    {
      href: "/audit",
      num: "02",
      label: "CRYPTOGRAPHIC AUDIT",
      sublabel: "SHA-256 Hash Chain",
      icon: History,
      active: pathname.startsWith("/audit"),
    },
    // National Command: Supervisor, Auditor, Admin
    ...(!isOfficer
      ? [
          {
            href: "/command",
            num: "03",
            label: "NATIONAL COMMAND",
            sublabel: "Operations & Telemetry",
            icon: Activity,
            active: pathname === "/command",
          },
          {
            href: "/command/clusters",
            num: "04",
            label: "BIOMETRIC GRAPH",
            sublabel: "pgvector 512-D Sybil",
            icon: Share2,
            active: pathname === "/command/clusters",
          },
        ]
      : []),
    // Admin only
    ...(role === "admin"
      ? [
          {
            href: "/command/admin",
            num: "05",
            label: "RULES & POLICIES",
            sublabel: "YAML & Model Gates",
            icon: Sliders,
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
      {/* Mobile Toggle Button */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label="Toggle Navigation Menu"
        className="md:hidden fixed top-3 left-3 z-50 p-2 bg-[#141517] border border-[#2D3135] text-[#c0f500] hover:bg-[#1B1C1E]"
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Backdrop for mobile */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          className="md:hidden fixed inset-0 bg-black/80 z-40 backdrop-blur-xs"
        />
      )}

      {/* Main Tactical Left Rail */}
      <aside
        className={`flex flex-col z-40 bg-[#0D0E10] border-r border-[#2D3135] transition-all duration-200 select-none ${
          mobileOpen
            ? "fixed left-0 top-0 h-full w-64 translate-x-0 shadow-2xl"
            : isCollapsed
            ? "fixed -translate-x-full md:translate-x-0 md:sticky md:top-0 md:h-screen md:shrink-0 w-16"
            : "fixed -translate-x-full md:translate-x-0 md:sticky md:top-0 md:h-screen md:shrink-0 w-60"
        }`}
      >
        {/* Top Header: Tactical Insignia & Brand Strip */}
        <div className="h-16 flex items-center justify-between px-3.5 border-b border-[#2D3135] bg-[#0A0B0D] shrink-0">
          <Link href="/" className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 bg-[#161f00] border border-[#434933] flex items-center justify-center text-[#c0f500] shrink-0 shadow-sm">
              <Shield size={18} strokeWidth={2} />
            </div>
            {(!isCollapsed || mobileOpen) && (
              <div className="flex flex-col min-w-0">
                <span className="font-mono text-xs font-bold text-[#c0f500] tracking-widest leading-none uppercase">
                  TRIPORT //
                </span>
                <span className="font-mono text-[9px] text-[#8e9479] uppercase leading-none mt-1 truncate">
                  {role ? `${role.toUpperCase()} CONSOLE` : "TACTICAL HUD"}
                </span>
              </div>
            )}
          </Link>

          {/* Pin / Collapse Toggle for Desktop */}
          {(!isCollapsed || mobileOpen) && (
            <button
              onClick={toggleCollapsed}
              title={isCollapsed ? "Expand Sidebar" : "Collapse to Rail"}
              className="hidden md:flex p-1.5 text-[#8e9479] hover:text-[#c0f500] hover:bg-[#1B1C1E] border border-transparent hover:border-[#2D3135] transition-colors cursor-pointer"
            >
              <PanelLeftClose size={15} />
            </button>
          )}
        </div>

        {/* Collapsed Mode Expand Button */}
        {isCollapsed && !mobileOpen && (
          <div className="hidden md:flex justify-center py-2 border-b border-[#2D3135] bg-[#0A0B0D]">
            <button
              onClick={toggleCollapsed}
              title="Expand Sidebar"
              className="p-1.5 text-[#8e9479] hover:text-[#c0f500] hover:bg-[#1B1C1E] transition-colors cursor-pointer"
            >
              <PanelLeftOpen size={16} />
            </button>
          </div>
        )}

        {/* Navigation Items List */}
        <nav className="flex-1 py-3 flex flex-col gap-1 overflow-y-auto overflow-x-hidden">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isHovered = hoveredItem === item.href;

            return (
              <div key={item.href} className="relative group">
                <Link
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  onMouseEnter={() => setHoveredItem(item.href)}
                  onMouseLeave={() => setHoveredItem(null)}
                  className={`flex items-center px-3 py-2.5 transition-all duration-150 border-l-2 cursor-pointer ${
                    item.active
                      ? "border-[#c0f500] bg-[#161f00] text-[#c0f500]"
                      : "border-transparent text-[#c4caac] hover:bg-[#141517] hover:text-white"
                  }`}
                >
                  {/* Icon */}
                  <div className="w-8 flex justify-center shrink-0">
                    <Icon
                      size={18}
                      strokeWidth={item.active ? 2.2 : 1.7}
                      className={item.active ? "text-[#c0f500]" : "text-[#8e9479] group-hover:text-white"}
                    />
                  </div>

                  {/* Labels (visible when expanded) */}
                  {(!isCollapsed || mobileOpen) && (
                    <div className="ml-2.5 flex flex-col min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[9px] text-[#8e9479] opacity-70">
                          {item.num}.
                        </span>
                        <span
                          className={`font-mono text-[11px] font-bold uppercase tracking-wider truncate ${
                            item.active ? "text-[#c0f500]" : "text-[#e3e2e5] group-hover:text-white"
                          }`}
                        >
                          {item.label}
                        </span>
                      </div>
                      <span className="font-mono text-[9px] text-[#8e9479] truncate mt-0.5">
                        {item.sublabel}
                      </span>
                    </div>
                  )}

                  {/* Active Indicator Pip when collapsed */}
                  {isCollapsed && !mobileOpen && item.active && (
                    <span className="absolute right-1 w-1.5 h-1.5 bg-[#c0f500]"></span>
                  )}
                </Link>

                {/* Floating Tactical Tooltip when Collapsed */}
                {isCollapsed && !mobileOpen && isHovered && (
                  <div className="fixed left-18 z-50 bg-[#121315] border border-[#c0f500] p-2 shadow-xl shadow-black/80 pointer-events-none min-w-[170px] animate-in fade-in duration-100">
                    <div className="font-mono text-[10px] text-[#c0f500] font-bold tracking-widest uppercase">
                      {item.num} // {item.label}
                    </div>
                    <div className="font-mono text-[9px] text-[#8e9479] mt-0.5">
                      {item.sublabel}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* User Identity & Terminal Session Footer */}
        <div className="border-t border-[#2D3135] p-2.5 flex flex-col gap-2 shrink-0 bg-[#0A0B0D]">
          {user && (
            <div
              className={`flex items-center gap-2.5 p-2 bg-[#121315] border border-[#2D3135] overflow-hidden ${
                isCollapsed && !mobileOpen ? "justify-center" : ""
              }`}
            >
              <div className="w-7 h-7 bg-[#161f00] border border-[#434933] flex items-center justify-center text-[#c0f500] shrink-0">
                <User size={14} />
              </div>

              {(!isCollapsed || mobileOpen) && (
                <div className="min-w-0 flex-1 font-mono">
                  <div className="text-[11px] font-bold text-white truncate leading-tight">
                    {user.name || user.email}
                  </div>
                  <div className="text-[9px] text-[#8e9479] truncate flex items-center gap-1 mt-0.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#c0f500]"></span>
                    <span>{user.badge_number}</span>
                    <span>•</span>
                    <span className="truncate">{user.checkpoint_id}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tactical Sign Out Action */}
          <button
            onClick={handleSignOut}
            title="Sign Out"
            className={`flex items-center py-2 text-[#8e9479] hover:text-[#ffdad6] hover:bg-[#93000a]/20 border border-transparent hover:border-[#ff3b30]/40 transition-colors font-mono text-xs cursor-pointer ${
              isCollapsed && !mobileOpen ? "justify-center px-1" : "px-2.5"
            }`}
          >
            <LogOut size={15} className="shrink-0 text-[#8e9479] hover:text-[#ff3b30]" />
            {(!isCollapsed || mobileOpen) && (
              <span className="ml-2.5 whitespace-nowrap uppercase tracking-wider text-[10px] font-bold">
                SIGN OUT
              </span>
            )}
          </button>
        </div>
      </aside>
    </>
  );
}
