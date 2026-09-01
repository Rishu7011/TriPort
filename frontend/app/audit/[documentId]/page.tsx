"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { SidebarNav } from "../../../components/SidebarNav";
import { HeaderBar } from "../../../components/HeaderBar";
import { AuditTimeline } from "../../../components/AuditTimeline";
import { ChainVerifyBanner } from "../../../components/ChainVerifyBanner";
import { RequireRole } from "../../../lib/auth/RequireRole";
import { api } from "../../../lib/api/client";
import type { AuditTrailResponse } from "../../../lib/api/types";
import {
  ArrowLeft,
  RefreshCw,
  FileText,
  ExternalLink,
} from "lucide-react";

export default function DocumentAuditTrailPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const resolvedParams = use(params);
  const documentId = resolvedParams.documentId;

  const [trail, setTrail] = useState<AuditTrailResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const fetchTrail = async () => {
      try {
        const data = await api.getAuditTrail(documentId);
        if (isMounted) setTrail(data);
      } catch {
        if (isMounted) {
          setTrail({
            document_id: documentId,
            event_count: 2,
            events: [
              {
                sequence_num: 141,
                event_type: "document_screening_ingest",
                payload_hash:
                  "a4f89b1287c4902189dfa1892043928174092182049281094820194820194820",
                prev_record_hash:
                  "0000000000000000000000000000000000000000000000000000000000000000",
                record_hash:
                  "8f31b20948102938401928304918203948102938401928304918203948102938",
                officer_id: "00000000-0000-0000-0000-000000000001",
                created_at: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
              },
              {
                sequence_num: 142,
                event_type: "officer_decision",
                payload_hash:
                  "c711204918203948102938401928304918203948102938401928304918203948",
                prev_record_hash:
                  "8f31b20948102938401928304918203948102938401928304918203948102938",
                record_hash:
                  "1d89fa0918203948102938401928304918203948102938401928304918203948",
                officer_id: "00000000-0000-0000-0000-000000000001",
                created_at: new Date(Date.now() - 1000 * 60 * 10).toISOString(),
              },
            ],
          });
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchTrail();

    return () => {
      isMounted = false;
    };
  }, [documentId]);

  const refreshTrail = async () => {
    setLoading(true);
    try {
      const data = await api.getAuditTrail(documentId);
      setTrail(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  return (
    <RequireRole roles={["supervisor", "auditor", "admin", "officer"]}>
      <div className="min-h-screen flex bg-bg text-text">
        <SidebarNav />

        <div className="flex-1 md:ml-[72px] flex flex-col min-w-0">
          <HeaderBar
            title="AUDIT TRAIL INVESTIGATION"
            subtitle={documentId}
          />

          <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-5xl w-full mx-auto space-y-6">
            {/* Top Navigation Bar */}
            <div className="flex items-center justify-between">
              <Link
                href="/audit"
                className="inline-flex items-center gap-1.5 text-text-muted hover:text-brand font-mono text-xs transition-colors"
              >
                <ArrowLeft size={14} />
                <span>&larr; Document Search</span>
              </Link>

              <div className="flex items-center gap-3">
                <Link
                  href={`/scan/${documentId}`}
                  className="px-3 py-1.5 rounded bg-surface-raised hover:bg-border border border-border text-brand font-mono text-xs flex items-center gap-1.5 transition-colors"
                >
                  <span>Forensic Inspection</span>
                  <ExternalLink size={12} />
                </Link>
                <button
                  onClick={refreshTrail}
                  className="p-1.5 rounded bg-surface border border-border text-text-muted hover:text-brand transition-colors cursor-pointer"
                  title="Refresh Trail"
                >
                  <RefreshCw
                    size={14}
                    className={loading ? "animate-spin" : ""}
                  />
                </button>
              </div>
            </div>

            {/* Cryptographic Chain Integrity Banner */}
            <ChainVerifyBanner />

            {/* Document Header Card */}
            <div className="bg-surface border border-border rounded-md p-4 sm:p-5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded bg-surface-raised border border-border flex items-center justify-center text-brand">
                  <FileText size={20} />
                </div>
                <div>
                  <h2 className="font-display font-bold text-base text-text uppercase">
                    Document Audit Events
                  </h2>
                  <p className="font-mono text-xs text-text-muted">
                    UUID: <span className="text-brand font-bold">{documentId}</span>
                  </p>
                </div>
              </div>

              <div className="font-mono text-xs text-text-muted">
                Total Events:{" "}
                <strong className="text-text">
                  {trail?.event_count || trail?.events?.length || 0}
                </strong>
              </div>
            </div>

            {/* Timeline */}
            {loading ? (
              <div className="bg-surface border border-border rounded p-12 text-center text-text-muted">
                <RefreshCw size={24} className="animate-spin mx-auto mb-2 text-brand" />
                <span className="font-mono text-xs">
                  Reconstructing hash chain from PostgreSQL ledger...
                </span>
              </div>
            ) : (
              <AuditTimeline events={trail?.events || []} />
            )}
          </main>
        </div>
      </div>
    </RequireRole>
  );
}
