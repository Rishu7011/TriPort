"use client";

import React, { useState } from "react";
import { HeaderBar } from "../../../components/HeaderBar";
import { BlacklistTable } from "../../../components/command/BlacklistTable";
import { RuleConfigViewer } from "../../../components/command/RuleConfigViewer";
import { RequireRole } from "../../../lib/auth/RequireRole";
import { ShieldAlert, FileCode } from "lucide-react";

export default function AdminConfigPage() {
  const [activeTab, setActiveTab] = useState<"blacklist" | "rules">("blacklist");

  return (
    <RequireRole roles={["admin"]}>
      <div className="flex flex-col min-h-screen">
        <HeaderBar
          title="ADMINISTRATION & SECURITY CONFIG"
          subtitle="SYSTEM CONFIGURATION"
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          {/* Admin Tabs */}
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <button
              type="button"
              onClick={() => setActiveTab("blacklist")}
              className={`flex items-center gap-2 px-4 py-2 rounded text-xs font-display uppercase tracking-wider font-bold transition-colors cursor-pointer ${
                activeTab === "blacklist"
                  ? "bg-brand text-bg shadow-xs"
                  : "text-text-muted hover:text-text hover:bg-surface-raised"
              }`}
            >
              <ShieldAlert size={15} />
              <span>Watchlist & Blacklist</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("rules")}
              className={`flex items-center gap-2 px-4 py-2 rounded text-xs font-display uppercase tracking-wider font-bold transition-colors cursor-pointer ${
                activeTab === "rules"
                  ? "bg-brand text-bg shadow-xs"
                  : "text-text-muted hover:text-text hover:bg-surface-raised"
              }`}
            >
              <FileCode size={15} />
              <span>Validation Rules YAML</span>
            </button>
          </div>

          {/* Active Tab View */}
          {activeTab === "blacklist" ? (
            <BlacklistTable />
          ) : (
            <RuleConfigViewer />
          )}
        </main>
      </div>
    </RequireRole>
  );
}
