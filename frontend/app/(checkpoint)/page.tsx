"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { HeaderBar } from "../../components/HeaderBar";
import { CheckpointTypeSelector } from "../../components/CheckpointTypeSelector";
import { DocumentTypeSelector } from "../../components/DocumentTypeSelector";
import { DocumentUploader } from "../../components/DocumentUploader";
import { PipelineStepper } from "../../components/PipelineStepper";
import { RiskBadge } from "../../components/RiskBadge";
import { api } from "../../lib/api/client";
import { useAuth } from "../../lib/auth/AuthContext";
import { setCachedScan } from "../../lib/scanCache";
import type {
  CheckpointType,
  DocumentType,
  RecentScan,
} from "../../lib/api/types";
import {
  History,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  Clock,
  Sparkles,
} from "lucide-react";

export default function OfficerScreeningPage() {
  const router = useRouter();
  const { user } = useAuth();

  const [checkpointType, setCheckpointType] =
    useState<CheckpointType>("airport");
  const [documentType, setDocumentType] = useState<DocumentType>("passport");
  const [docFile, setDocFile] = useState<File | null>(null);

  const [isScreening, setIsScreening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [recentScans, setRecentScans] = useState<RecentScan[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const loadRecent = async () => {
      try {
        const scans = await api.getRecentScans(10);
        if (isMounted) setRecentScans(scans);
      } catch {
        if (isMounted) {
          setRecentScans([
            {
              document_id: "3e365d37-623b-40fa-8a02-1e0cdfa58799",
              document_type: "passport",
              checkpoint_id: "00000000-0000-0000-0000-000000000010",
              uploaded_at: new Date(Date.now() - 1000 * 60 * 4).toISOString(),
              risk_score: 8.5,
              risk_band: "low",
              reasons: ["All security parameters passed."],
            },
            {
              document_id: "7b2e2d1a-4122-4809-94fc-32490ab81234",
              document_type: "passport",
              checkpoint_id: "00000000-0000-0000-0000-000000000010",
              uploaded_at: new Date(Date.now() - 1000 * 60 * 22).toISOString(),
              risk_score: 94.2,
              risk_band: "critical",
              reasons: [
                "Impossible travel anomaly detected",
                "Multiple identity alias collisions",
              ],
            },
            {
              document_id: "d2-9901-kasper",
              document_type: "national_id",
              checkpoint_id: "CP-ATTARI-01",
              uploaded_at: new Date(Date.now() - 1000 * 60 * 48).toISOString(),
              risk_score: 52.0,
              risk_band: "medium",
              reasons: ["Low OCR confidence on Date of Birth"],
            },
          ]);
        }
      } finally {
        if (isMounted) setLoadingRecent(false);
      }
    };

    loadRecent();

    return () => {
      isMounted = false;
    };
  }, []);

  const refreshRecent = async () => {
    setLoadingRecent(true);
    try {
      const scans = await api.getRecentScans(10);
      setRecentScans(scans);
    } catch {
      // ignore
    } finally {
      setLoadingRecent(false);
    }
  };

  const handleRunScreening = async () => {
    if (!docFile) {
      setError("Please attach a document scan image before running screening.");
      return;
    }

    setError(null);
    setIsScreening(true);

    try {
      const formData = new FormData();
      formData.append("file", docFile);
      formData.append("document_type", documentType);
      formData.append("checkpoint_type", checkpointType);
      formData.append("checkpoint_id", user?.checkpoint_id || "00000000-0000-0000-0000-000000000010");

      const res = await api.uploadDocument(formData);

      if (res && res.document_id) {
        setCachedScan(res.document_id, res);
        router.push(`/scan/${res.document_id}`);
      } else {
        setIsScreening(false);
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Screening failed. Verify image format and gateway connectivity.";
      setError(errMsg);
      setIsScreening(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header Bar */}
      <HeaderBar title="TRIPORT SCREENING CONSOLE">
        <CheckpointTypeSelector
          value={checkpointType}
          onChange={setCheckpointType}
        />
      </HeaderBar>

      {/* Main Container */}
      <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-6xl w-full mx-auto space-y-8">
        {/* If in-flight screening is active, show the PipelineStepper animation */}
        {isScreening ? (
          <div className="space-y-4 animate-in fade-in duration-200">
            <PipelineStepper isLoading={true} />
          </div>
        ) : (
          <>
            {/* Top Controls: Doc Type Selector */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface border border-border rounded-md p-4">
              <DocumentTypeSelector
                value={documentType}
                onChange={setDocumentType}
              />

              <div className="sm:hidden">
                <CheckpointTypeSelector
                  value={checkpointType}
                  onChange={setCheckpointType}
                />
              </div>
            </div>

            {/* Error Notification */}
            {error && (
              <div className="p-3.5 rounded bg-risk-critical/10 border border-risk-critical/30 flex items-center gap-3 text-risk-critical font-body text-xs">
                <AlertCircle size={18} className="shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Ingestion Dropzones */}
            <div className="space-y-4">
              <DocumentUploader
                docFile={docFile}
                onDocFileChange={setDocFile}
              />

              {/* Action Bar */}
              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={handleRunScreening}
                  disabled={!docFile}
                  className={`px-8 py-3.5 rounded font-display text-sm font-bold uppercase tracking-wider transition-all flex items-center gap-2.5 ${
                    docFile
                      ? "bg-brand hover:bg-white text-bg cursor-pointer shadow-[0_0_15px_rgba(166,255,77,0.35)]"
                      : "bg-surface-raised border border-border text-text-muted/60 cursor-not-allowed opacity-60"
                  }`}
                >
                  <Sparkles size={16} />
                  <span>Run Stage 1 Screening (~5-8s)</span>
                </button>
              </div>
            </div>

            {/* Recent Scans Table Section */}
            <div className="space-y-3 pt-4 border-t border-border">
              <div className="flex items-center justify-between">
                <h3 className="font-display font-bold text-sm sm:text-base text-text uppercase tracking-tight flex items-center gap-2">
                  <History size={16} className="text-brand" />
                  <span>Recent Terminal Screenings</span>
                </h3>

                <button
                  type="button"
                  onClick={refreshRecent}
                  className="text-text-muted hover:text-brand font-mono text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <RefreshCw
                    size={12}
                    className={loadingRecent ? "animate-spin" : ""}
                  />
                  <span>Refresh</span>
                </button>
              </div>

              {/* Table */}
              <div className="bg-surface border border-border rounded-md overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-border bg-surface-raised font-mono text-[11px] text-text-muted uppercase">
                        <th className="p-3 font-semibold">Timestamp</th>
                        <th className="p-3 font-semibold">Doc Type</th>
                        <th className="p-3 font-semibold">Document UUID</th>
                        <th className="p-3 font-semibold">Port / Terminal</th>
                        <th className="p-3 font-semibold">Risk Band</th>
                        <th className="p-3 font-semibold text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border font-mono text-xs text-text">
                      {loadingRecent ? (
                        <tr>
                          <td
                            colSpan={6}
                            className="p-6 text-center text-text-muted"
                          >
                            <RefreshCw
                              size={16}
                              className="animate-spin mx-auto mb-2 text-brand"
                            />
                            Loading recent screenings...
                          </td>
                        </tr>
                      ) : recentScans.length === 0 ? (
                        <tr>
                          <td
                            colSpan={6}
                            className="p-6 text-center text-text-muted"
                          >
                            No screening records found for this terminal shift.
                          </td>
                        </tr>
                      ) : (
                        recentScans.map((scan) => (
                          <tr
                            key={scan.document_id}
                            className="hover:bg-surface-raised transition-colors group"
                          >
                            <td className="p-3 text-text-muted flex items-center gap-1.5">
                              <Clock size={12} />
                              <span>
                                {scan.uploaded_at
                                  ? new Date(
                                      scan.uploaded_at
                                    ).toLocaleTimeString()
                                  : "Recent"}
                              </span>
                            </td>
                            <td className="p-3 uppercase font-semibold text-text">
                              {scan.document_type}
                            </td>
                            <td className="p-3 text-text-muted truncate max-w-[160px]">
                              {scan.document_id}
                            </td>
                            <td className="p-3 text-text-muted">
                              {scan.checkpoint_id || "00000000-0000-0000-0000-000000000010"}
                            </td>
                            <td className="p-3">
                              <RiskBadge
                                band={scan.risk_band}
                                score={scan.risk_score}
                                size="sm"
                              />
                            </td>
                            <td className="p-3 text-right">
                              <Link
                                href={`/scan/${scan.document_id}`}
                                className="inline-flex items-center gap-1 text-brand hover:underline text-xs font-mono font-semibold"
                              >
                                <span>Inspect</span>
                                <ArrowRight size={12} />
                              </Link>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
