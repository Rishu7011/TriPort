"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { SidebarNav } from "../../components/SidebarNav";
import { HeaderBar } from "../../components/HeaderBar";
import { ChainVerifyBanner } from "../../components/ChainVerifyBanner";
import { RequireRole } from "../../lib/auth/RequireRole";
import {
  Search,
  ArrowRight,
  Hash,
} from "lucide-react";

export default function AuditSearchPage() {
  const [searchDocId, setSearchDocId] = useState("");
  const router = useRouter();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchDocId.trim()) return;
    router.push(`/audit/${encodeURIComponent(searchDocId.trim())}`);
  };

  const sampleDocIds = [
    {
      id: "3e365d37-623b-40fa-8a02-1e0cdfa58799",
      label: "ELARA VANCE (Approved Genuine Passport)",
    },
    {
      id: "7b2e2d1a-4122-4809-94fc-32490ab81234",
      label: "VIKTOR KASPAROV (Multi-Identity Syndicate)",
    },
    {
      id: "d1-8849-kasparov",
      label: "KASPAROV (Attari Land Border Anomaly)",
    },
  ];

  return (
    <RequireRole roles={["supervisor", "auditor", "admin", "officer"]}>
      <div className="min-h-screen flex bg-bg text-text">
        <SidebarNav />

        <div className="flex-1 md:ml-[72px] flex flex-col min-w-0">
          <HeaderBar
            title="IMMUTABLE AUDIT LEDGER"
            subtitle="INTEGRITY VERIFICATION"
          />

          <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-5xl w-full mx-auto space-y-8">
            {/* Global Chain Verification Banner */}
            <ChainVerifyBanner />

            {/* Document Investigation Search */}
            <div className="bg-surface border border-border rounded-md p-6 sm:p-8 space-y-6">
              <div>
                <h2 className="font-display font-bold text-lg text-text uppercase tracking-tight flex items-center gap-2">
                  <Search size={18} className="text-brand" />
                  <span>Document Audit Trail Lookup</span>
                </h2>
                <p className="font-mono text-xs text-text-muted mt-1">
                  Retrieve immutable cryptographic event sequence from genesis
                  block to current head for any document scan UUID.
                </p>
              </div>

              <form onSubmit={handleSearch} className="flex gap-3">
                <div className="relative flex-1">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted">
                    <Hash size={16} strokeWidth={1.5} />
                  </span>
                  <input
                    type="text"
                    required
                    value={searchDocId}
                    onChange={(e) => setSearchDocId(e.target.value)}
                    placeholder="Enter Document UUID (e.g. 3e365d37-623b-40fa-8a02-1e0cdfa58799)..."
                    className="w-full h-11 pl-10 pr-3 bg-bg border border-border rounded text-text font-mono text-xs placeholder:text-text-muted/60 focus:border-brand focus:ring-1 focus:ring-brand outline-none"
                  />
                </div>

                <button
                  type="submit"
                  className="px-6 h-11 bg-brand hover:bg-white text-bg font-display text-xs font-bold uppercase tracking-wider rounded transition-colors flex items-center gap-2 cursor-pointer shadow-xs"
                >
                  <span>Query Trail</span>
                  <ArrowRight size={14} />
                </button>
              </form>

              {/* Sample Investigation Queries */}
              <div className="pt-4 border-t border-border">
                <div className="font-mono text-[11px] uppercase tracking-wider text-text-muted mb-2">
                  Sample Investigation Documents:
                </div>
                <div className="space-y-2">
                  {sampleDocIds.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => router.push(`/audit/${item.id}`)}
                      className="w-full p-2.5 rounded bg-surface-raised hover:bg-border border border-border flex items-center justify-between font-mono text-xs transition-colors cursor-pointer text-left group"
                    >
                      <div className="min-w-0 pr-2">
                        <div className="text-text font-bold group-hover:text-brand">
                          {item.label}
                        </div>
                        <div className="text-text-muted text-[11px] truncate">
                          UUID: {item.id}
                        </div>
                      </div>
                      <ArrowRight
                        size={14}
                        className="text-text-muted group-hover:text-brand shrink-0"
                      />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </RequireRole>
  );
}
