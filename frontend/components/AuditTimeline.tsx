"use client";

import React from "react";
import type { AuditLedgerEvent } from "../lib/api/types";
import {
  FileText,
  UserCheck,
  ShieldAlert,
  Clock,
  Key,
  Layers,
} from "lucide-react";

interface AuditTimelineProps {
  events: AuditLedgerEvent[];
}

export function AuditTimeline({ events }: AuditTimelineProps) {
  if (!events || events.length === 0) {
    return (
      <div className="bg-surface border border-border rounded p-8 text-center text-text-muted">
        <Layers size={24} className="mx-auto mb-2 opacity-50" />
        <p className="font-mono text-xs">
          No ledger blocks found for this document identifier.
        </p>
      </div>
    );
  }

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case "document_screening_ingest":
        return FileText;
      case "officer_decision":
        return UserCheck;
      case "blacklist_match":
      case "threat_escalation":
        return ShieldAlert;
      default:
        return Key;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between font-mono text-xs text-text-muted px-1">
        <span className="uppercase font-semibold">
          Sequential Ledger History ({events.length} blocks)
        </span>
        <span>SHA-256 Chained Head &darr;</span>
      </div>

      <div className="relative pl-6 sm:pl-8 space-y-6 before:absolute before:left-3 sm:before:left-4 before:top-3 before:bottom-3 before:w-[2px] before:bg-border">
        {events.map((event) => {
          const Icon = getEventIcon(event.event_type);
          const isGenesis =
            event.prev_record_hash ===
            "0000000000000000000000000000000000000000000000000000000000000000";

          return (
            <div key={event.sequence_num} className="relative group">
              {/* Timeline Node Icon */}
              <div className="absolute -left-6 sm:-left-8 top-1 w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-surface border-2 border-brand text-brand flex items-center justify-center -translate-x-1/2 shadow-[0_0_8px_rgba(166,255,77,0.3)]">
                <Icon size={12} className="sm:w-3.5 sm:h-3.5" />
              </div>

              {/* Event Card */}
              <div className="bg-surface border border-border rounded-md p-4 space-y-3 group-hover:border-brand/40 transition-colors">
                {/* Event Top Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 pb-2 border-b border-border/80">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-brand bg-brand/10 border border-brand/20 px-2 py-0.5 rounded">
                      BLOCK #{event.sequence_num}
                    </span>
                    <span className="font-display font-bold text-sm text-text uppercase">
                      {event.event_type.replace(/_/g, " ")}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 font-mono text-[11px] text-text-muted">
                    <Clock size={12} />
                    <span>{new Date(event.created_at).toUTCString()}</span>
                  </div>
                </div>

                {/* Cryptographic Hashes */}
                <div className="space-y-1.5 font-mono text-[11px]">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-1">
                    <span className="text-text-muted sm:w-28 shrink-0">
                      Record Hash:
                    </span>
                    <code className="text-text bg-bg border border-border px-2 py-0.5 rounded truncate select-all">
                      {event.record_hash}
                    </code>
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center gap-1">
                    <span className="text-text-muted sm:w-28 shrink-0">
                      Previous Hash:
                    </span>
                    <code
                      className={`px-2 py-0.5 rounded truncate select-all ${
                        isGenesis
                          ? "text-brand bg-brand/5 border border-brand/20 font-bold"
                          : "text-text-muted bg-bg border border-border"
                      }`}
                    >
                      {isGenesis
                        ? "GENESIS BLOCK [0000...0000]"
                        : event.prev_record_hash}
                    </code>
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center gap-1">
                    <span className="text-text-muted sm:w-28 shrink-0">
                      Payload Hash:
                    </span>
                    <code className="text-text-muted bg-bg border border-border px-2 py-0.5 rounded truncate select-all">
                      {event.payload_hash}
                    </code>
                  </div>

                  {event.officer_id && (
                    <div className="flex items-center gap-1 text-[10px] text-text-muted pt-1">
                      <span>Signer Officer UUID:</span>
                      <span className="text-text">{event.officer_id}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
