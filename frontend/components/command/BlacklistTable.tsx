"use client";

import React, { useState, useEffect } from "react";
import { api } from "../../lib/api/client";
import type { BlacklistEntryOut, BlacklistEntryIn } from "../../lib/api/types";
import {
  ShieldAlert,
  Search,
  Plus,
  Trash2,
  X,
  RefreshCw,
} from "lucide-react";

export function BlacklistTable() {
  const [entries, setEntries] = useState<BlacklistEntryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [showAddModal, setShowAddModal] = useState(false);

  // Form state for new entry
  const [newDocNumber, setNewDocNumber] = useState("");
  const [newName, setNewName] = useState("");
  const [newDob, setNewDob] = useState("");
  const [newNationality, setNewNationality] = useState("");
  const [newSeverity, setNewSeverity] = useState("detain");
  const [newReason, setNewReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const loadData = async () => {
      try {
        const data = await api.getBlacklist(100);
        if (isMounted) setEntries(data);
      } catch {
        if (isMounted) {
          setEntries([
            {
              id: "bl-001",
              document_number: "P7890123",
              full_name: "VIKTOR KASPAROV",
              date_of_birth: "1984-04-12",
              nationality: "RUS",
              severity: "detain",
              reason:
                "Interpol Red Notice #A-992/2025: Organized Identity Forgery",
              created_at: "2026-08-20T10:00:00Z",
            },
            {
              id: "bl-002",
              document_number: "L982XX34",
              full_name: "MARCUS VERN",
              date_of_birth: "1985-08-14",
              nationality: "ROU",
              severity: "detain",
              reason:
                "Fraud Syndicate Link — Counterfeit Hologram Substrate",
              created_at: "2026-08-24T14:15:00Z",
            },
            {
              id: "bl-003",
              document_number: "EE449012",
              full_name: "VIKTOR KASPER",
              date_of_birth: "1984-04-12",
              nationality: "EST",
              severity: "caution",
              reason:
                "Biometric Duplicate Collision with Cluster #7b2e2d1a",
              created_at: "2026-08-29T18:30:00Z",
            },
            {
              id: "bl-004",
              document_number: "UK8829104",
              full_name: "ARTHUR PENHALIGON",
              date_of_birth: "1979-11-03",
              nationality: "GBR",
              severity: "watch",
              reason:
                "Customs Watchlist — Multiple Unreported Currency Transits",
              created_at: "2026-08-25T09:00:00Z",
            },
          ]);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadData();

    return () => {
      isMounted = false;
    };
  }, []);

  const refreshBlacklist = async () => {
    setLoading(true);
    try {
      const data = await api.getBlacklist(100);
      setEntries(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const handleAddEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload: BlacklistEntryIn = {
        document_number: newDocNumber || null,
        full_name: newName || null,
        date_of_birth: newDob || null,
        nationality: newNationality || null,
        severity: newSeverity,
        reason: newReason || null,
      };
      await api.addBlacklistEntry(payload);
      setShowAddModal(false);
      // Reset form
      setNewDocNumber("");
      setNewName("");
      setNewDob("");
      setNewNationality("");
      setNewReason("");
      refreshBlacklist();
    } catch {
      // Local optimistic append for demo
      const optimisticEntry: BlacklistEntryOut = {
        id: `bl-${Date.now()}`,
        document_number: newDocNumber || null,
        full_name: newName || null,
        date_of_birth: newDob || null,
        nationality: newNationality || null,
        severity: newSeverity,
        reason: newReason || null,
        created_at: new Date().toISOString(),
      };
      setEntries([optimisticEntry, ...entries]);
      setShowAddModal(false);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Remove this entry from the active national watchlist?")) return;
    try {
      await api.deleteBlacklistEntry(id);
      setEntries(entries.filter((e) => e.id !== id));
    } catch {
      setEntries(entries.filter((e) => e.id !== id));
    }
  };

  // Filtered rows
  const filtered = entries.filter((item) => {
    const matchSearch =
      search === "" ||
      (item.full_name &&
        item.full_name.toLowerCase().includes(search.toLowerCase())) ||
      (item.document_number &&
        item.document_number.toLowerCase().includes(search.toLowerCase())) ||
      (item.nationality &&
        item.nationality.toLowerCase().includes(search.toLowerCase())) ||
      (item.reason &&
        item.reason.toLowerCase().includes(search.toLowerCase()));

    const matchSeverity =
      severityFilter === "all" || item.severity === severityFilter;

    return matchSearch && matchSeverity;
  });

  return (
    <div className="bg-surface border border-border rounded-md overflow-hidden flex flex-col">
      {/* Table Header & Controls */}
      <div className="p-4 border-b border-border bg-surface-raised flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="font-display font-bold text-sm text-text uppercase tracking-tight flex items-center gap-2">
            <ShieldAlert size={16} className="text-risk-critical" />
            <span>National Blacklist & Watchlist Registry</span>
          </h3>
          <p className="font-mono text-xs text-text-muted mt-0.5">
            Active enforcement records screened against every document scan
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="px-3 py-1.5 rounded bg-brand hover:bg-white text-bg font-mono text-xs font-bold uppercase transition-colors flex items-center gap-1.5 cursor-pointer shadow-xs"
          >
            <Plus size={14} strokeWidth={2.5} />
            <span>Add Entry</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="p-3 border-b border-border bg-bg flex flex-col sm:flex-row items-center justify-between gap-3">
        {/* Search Input */}
        <div className="relative w-full sm:w-72">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, doc #, reason..."
            className="w-full h-8 pl-8 pr-3 bg-surface border border-border rounded text-text font-mono text-xs placeholder:text-text-muted/60 focus:border-brand focus:ring-1 focus:ring-brand outline-none"
          />
        </div>

        {/* Severity filter buttons */}
        <div className="flex items-center gap-1 font-mono text-xs w-full sm:w-auto overflow-x-auto">
          <span className="text-text-muted mr-1 hidden sm:inline">Tier:</span>
          {["all", "detain", "caution", "watch"].map((sev) => (
            <button
              key={sev}
              type="button"
              onClick={() => setSeverityFilter(sev)}
              className={`px-2.5 py-1 rounded uppercase text-[11px] transition-colors cursor-pointer ${
                severityFilter === sev
                  ? "bg-surface-raised border border-border text-brand font-bold"
                  : "text-text-muted hover:text-text"
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Table Body */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border bg-surface-raised font-mono text-[11px] text-text-muted uppercase">
              <th className="p-3 font-semibold">Severity</th>
              <th className="p-3 font-semibold">Subject / Name</th>
              <th className="p-3 font-semibold">Doc Number</th>
              <th className="p-3 font-semibold">Nationality</th>
              <th className="p-3 font-semibold">Reason / Notice</th>
              <th className="p-3 font-semibold text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border font-mono text-xs text-text">
            {loading ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-text-muted">
                  <RefreshCw size={18} className="animate-spin mx-auto mb-2 text-brand" />
                  Loading blacklist records...
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-text-muted">
                  No matching blacklist records found.
                </td>
              </tr>
            ) : (
              filtered.map((entry) => {
                const isDetain = entry.severity === "detain";
                const isCaution = entry.severity === "caution";

                return (
                  <tr
                    key={entry.id}
                    className="hover:bg-surface-raised transition-colors"
                  >
                    <td className="p-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          isDetain
                            ? "bg-risk-critical/15 text-risk-critical border border-risk-critical/30"
                            : isCaution
                            ? "bg-risk-medium/15 text-risk-medium border border-risk-medium/30"
                            : "bg-surface-raised text-text-muted border border-border"
                        }`}
                      >
                        {entry.severity}
                      </span>
                    </td>
                    <td className="p-3 font-bold uppercase text-text">
                      {entry.full_name || "—"}
                    </td>
                    <td className="p-3 text-brand">
                      {entry.document_number || "—"}
                    </td>
                    <td className="p-3 text-text-muted">
                      {entry.nationality || "—"}
                    </td>
                    <td className="p-3 font-body text-xs text-text-muted max-w-xs truncate" title={entry.reason || ""}>
                      {entry.reason || "Flagged in automated screening"}
                    </td>
                    <td className="p-3 text-right">
                      <button
                        type="button"
                        onClick={() => handleDelete(entry.id)}
                        className="p-1.5 rounded hover:bg-risk-critical/10 text-text-muted hover:text-risk-critical transition-colors cursor-pointer"
                        title="Delete Record"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Add Entry Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs">
          <div className="bg-surface border border-border rounded-md max-w-md w-full p-6 shadow-2xl relative">
            <div className="flex items-center justify-between pb-3 border-b border-border mb-4">
              <h3 className="font-display font-bold text-base text-text uppercase">
                Add Watchlist Record
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-text-muted hover:text-text"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddEntry} className="space-y-3 font-mono text-xs">
              <div>
                <label className="block uppercase text-text-muted text-[10px] mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. KASPAROV, VIKTOR"
                  className="w-full p-2 bg-bg border border-border rounded text-text outline-none focus:border-brand"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block uppercase text-text-muted text-[10px] mb-1">
                    Document Number
                  </label>
                  <input
                    type="text"
                    value={newDocNumber}
                    onChange={(e) => setNewDocNumber(e.target.value)}
                    placeholder="e.g. P7890123"
                    className="w-full p-2 bg-bg border border-border rounded text-text outline-none focus:border-brand"
                  />
                </div>

                <div>
                  <label className="block uppercase text-text-muted text-[10px] mb-1">
                    Nationality (ICAO)
                  </label>
                  <input
                    type="text"
                    maxLength={3}
                    value={newNationality}
                    onChange={(e) => setNewNationality(e.target.value.toUpperCase())}
                    placeholder="e.g. RUS"
                    className="w-full p-2 bg-bg border border-border rounded text-text outline-none focus:border-brand uppercase"
                  />
                </div>
              </div>

              <div>
                <label className="block uppercase text-text-muted text-[10px] mb-1">
                  Severity Tier
                </label>
                <select
                  value={newSeverity}
                  onChange={(e) => setNewSeverity(e.target.value)}
                  className="w-full p-2 bg-bg border border-border rounded text-text outline-none focus:border-brand"
                >
                  <option value="detain">Detain (Immediate Apprehension)</option>
                  <option value="caution">Caution (Secondary Inspection)</option>
                  <option value="watch">Watch (Passive Surveillance)</option>
                </select>
              </div>

              <div>
                <label className="block uppercase text-text-muted text-[10px] mb-1">
                  Enforcement Reason / Warrant Notice
                </label>
                <textarea
                  rows={2}
                  required
                  value={newReason}
                  onChange={(e) => setNewReason(e.target.value)}
                  placeholder="Interpol warrant ID, known fraud syndicate affiliation, or alert detail..."
                  className="w-full p-2 bg-bg border border-border rounded text-text outline-none focus:border-brand"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 rounded bg-surface-raised text-text font-mono text-xs uppercase"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 rounded bg-brand text-bg font-display text-xs font-bold uppercase"
                >
                  {submitting ? "Saving..." : "Commit Entry"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
