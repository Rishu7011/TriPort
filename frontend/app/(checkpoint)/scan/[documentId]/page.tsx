"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { HeaderBar } from "../../../../components/HeaderBar";
import { ExtractedFieldsTable } from "../../../../components/ExtractedFieldsTable";
import { TamperingHeatmap } from "../../../../components/TamperingHeatmap";
import { FaceMatchPanel } from "../../../../components/FaceMatchPanel";
import { ReasonsPanel } from "../../../../components/ReasonsPanel";
import { DecisionActions } from "../../../../components/DecisionActions";
import { DecisionConfirmModal } from "../../../../components/DecisionConfirmModal";
import { RiskBadge } from "../../../../components/RiskBadge";
import { PipelineStepper } from "../../../../components/PipelineStepper";
import { api } from "../../../../lib/api/client";
import { useAuth } from "../../../../lib/auth/AuthContext";
import type {
  DecisionVerdict,
  ExtractionResult,
  ValidationResult,
  TamperingResult,
  FaceVerificationResult,
  RiskScoreResponse,
} from "../../../../lib/api/types";
import {
  ArrowLeft,
  FileText,
  CheckCircle2,
  History,
  AlertCircle,
} from "lucide-react";

export default function ScanResultPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const resolvedParams = use(params);
  const documentId = resolvedParams.documentId;
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Core forensic result states
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [tampering, setTampering] = useState<TamperingResult | null>(null);
  const [face, setFace] = useState<FaceVerificationResult | null>(null);
  const [risk, setRisk] = useState<RiskScoreResponse | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<string | null>(null);
  const [serviceIssues, setServiceIssues] = useState<string[]>([]);

  // Cached image URLs from upload session
  const [docPhotoUrl, setDocPhotoUrl] = useState<string | undefined>(undefined);
  const [livePhotoUrl, setLivePhotoUrl] = useState<string | undefined>(
    undefined
  );

  // Decision Modal State
  const [modalVerdict, setModalVerdict] = useState<DecisionVerdict>("reject");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [decisionSuccess, setDecisionSuccess] = useState<string | null>(null);
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const initializeData = async () => {
      try {
        const pipelineRes = await api.getPipelineResult(documentId);
        if (!isMounted) return;

        const pipeline = pipelineRes.pipeline;
        setPipelineStatus(pipelineRes.status);
        setExtraction(pipeline.extraction);
        setValidation(pipeline.validation);
        setTampering(pipeline.tampering);
        setFace(pipeline.face);
        setRisk(pipeline.risk_score);

        const issues: string[] = [];
        const statuses = pipeline.service_statuses || {};
        for (const [serviceName, status] of Object.entries(statuses)) {
          const svc = status as { available?: boolean; error?: string | null };
          if (svc.available === false) {
            issues.push(
              `${serviceName}: ${svc.error || "service unavailable"}`
            );
          }
        }
        if (pipeline.degraded) {
          issues.unshift(
            "One or more screening modules ran in degraded mode. Results below may be partial."
          );
        }
        setServiceIssues(issues);

        const [extData, faceData] = await Promise.allSettled([
          api.getExtraction(documentId),
          api.getFaceVerification(documentId),
        ]);

        if (extData.status === "fulfilled" && extData.value.image_url) {
          setDocPhotoUrl(extData.value.image_url);
        }
        if (faceData.status === "fulfilled") {
          const facePayload = faceData.value as {
            doc_image_url?: string;
            live_image_url?: string;
          };
          if (facePayload.doc_image_url) {
            setDocPhotoUrl(facePayload.doc_image_url);
          }
          if (facePayload.live_image_url) {
            setLivePhotoUrl(facePayload.live_image_url);
          }
        }
      } catch (err) {
        if (isMounted) {
          setLoadError(
            err instanceof Error
              ? err.message
              : "Unable to retrieve this screening result from the gateway."
          );
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    initializeData();

    return () => {
      isMounted = false;
    };
  }, [documentId]);

  // Traveler info helpers
  const holderSurname =
    extraction?.fields?.find((f) => f.field_name === "surname")?.field_value ||
    extraction?.mrz?.mrz_fields?.surname ||
    "";
  const holderGiven =
    extraction?.fields?.find((f) => f.field_name === "given_names")
      ?.field_value ||
    extraction?.mrz?.mrz_fields?.given_names ||
    "";
  const travelerName =
    holderSurname || holderGiven
      ? `${holderGiven} ${holderSurname}`.trim()
      : "TRAVELER IDENTIFIED";

  const docNumber =
    extraction?.fields?.find((f) => f.field_name === "passport_number")
      ?.field_value ||
    extraction?.mrz?.mrz_fields?.doc_number ||
    "UNAVAILABLE";

  const nationality =
    extraction?.fields?.find((f) => f.field_name === "nationality")
      ?.field_value ||
    extraction?.mrz?.mrz_fields?.nationality ||
    "N/A";

  // Decision Handlers
  const handleApprove = async () => {
    setIsSubmittingDecision(true);
    try {
      await api.recordDecision(documentId, {
        decision: "approve",
        notes: `Entry approved by Officer ${user?.name || user?.email} at ${
          user?.checkpoint_id || "Checkpoint"
        }. Genuine document and facial verification confirmed.`,
        officer_id: user?.user_id,
      });
      setDecisionSuccess(
        "Entry verdict 'APPROVE' successfully written to immutable SHA-256 ledger."
      );
    } catch (err) {
      setDecisionSuccess(
        `Unable to record approval: ${err instanceof Error ? err.message : "gateway request failed"}.`
      );
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  const handleEscalateClick = () => {
    setModalVerdict("flag");
    setIsModalOpen(true);
  };

  const handleDetainClick = () => {
    setModalVerdict("reject");
    setIsModalOpen(true);
  };

  const handleConfirmModalSubmit = async (notes: string) => {
    await api.recordDecision(documentId, {
      decision: modalVerdict,
      notes: notes,
      officer_id: user?.user_id,
    });
    setDecisionSuccess(
      `Verdict '${modalVerdict.toUpperCase()}' committed to SHA-256 ledger.`
    );
  };

  if (loading) {
    return (
      <div className="flex flex-col min-h-screen">
        <HeaderBar title="TRIPORT SCREENING CONSOLE" subtitle={documentId} />
        <main className="flex-1 p-6 max-w-6xl w-full mx-auto flex items-center justify-center">
          <PipelineStepper isLoading={true} />
        </main>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Header Bar */}
      <HeaderBar title="TRIPORT SCREENING CONSOLE" subtitle="FORENSIC INSPECTION">
        <div className="flex items-center gap-3 font-mono text-xs text-text-muted">
          <span>
            Doc: <strong className="text-brand">{docNumber}</strong>
          </span>
          <span>•</span>
          <span>
            Traveler: <strong className="text-text">{travelerName}</strong>
          </span>
        </div>
      </HeaderBar>

      <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
        {/* Navigation & Success Alert Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-text-muted hover:text-brand font-mono text-xs transition-colors"
          >
            <ArrowLeft size={14} />
            <span>&larr; Back to Screening Console</span>
          </Link>

          {decisionSuccess && (
            <div className="p-2.5 rounded bg-brand/10 border border-brand/30 flex items-center gap-2 text-brand font-mono text-xs animate-in fade-in">
              <CheckCircle2 size={16} />
              <span>{decisionSuccess}</span>
              <Link
                href={`/audit/${documentId}`}
                className="underline ml-2 font-bold hover:text-white"
              >
                View in Audit Ledger &rarr;
              </Link>
            </div>
          )}
        </div>

        {loadError && (
          <div className="p-3 rounded bg-risk-medium/10 border border-risk-medium/30 flex items-center gap-2 text-risk-medium font-mono text-xs">
            <AlertCircle size={16} />
            <span>{loadError}</span>
          </div>
        )}

        {serviceIssues.length > 0 && (
          <div className="p-3 rounded bg-risk-medium/10 border border-risk-medium/30 text-risk-medium font-mono text-xs space-y-1">
            <div className="flex items-center gap-2 font-semibold">
              <AlertCircle size={16} />
              <span>
                Screening status: {pipelineStatus || "unknown"}
              </span>
            </div>
            <ul className="list-disc pl-5 space-y-0.5">
              {serviceIssues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        )}

        {/* 1. Header Metadata Strip (Stitch Screen 4) */}
        <div className="bg-surface border border-border rounded-md p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded bg-surface-raised border border-border flex items-center justify-center text-brand shrink-0">
              <FileText size={24} strokeWidth={1.5} />
            </div>

            <div>
              <div className="flex items-center gap-2 font-mono text-[11px] text-text-muted uppercase">
                <span>{extraction?.document_type || "PASSPORT"}</span>
                <span>/</span>
                <span className="text-brand font-bold">{docNumber}</span>
              </div>
              <h2 className="font-display font-bold text-lg sm:text-xl text-text tracking-tight uppercase mt-0.5">
                {travelerName}
              </h2>
              <div className="font-mono text-xs text-text-muted">
                Nationality:{" "}
                <span className="text-text font-bold">{nationality}</span> •
                Document UUID:{" "}
                <span className="text-text-muted/80">{documentId}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href={`/audit/${documentId}`}
              className="px-3 py-2 rounded bg-surface-raised hover:bg-border border border-border text-text font-mono text-xs flex items-center gap-1.5 transition-colors"
            >
              <History size={14} />
              <span>Audit Chain</span>
            </Link>

            <RiskBadge band={risk?.band} score={risk?.score} />
          </div>
        </div>

        {/* 2. Main Multi-Panel Forensic Stage & Decision Column */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Left / Center Forensic Modules Stage (~67%) */}
          <div className="xl:col-span-2 space-y-6">
            {/* Top Grid: OCR Extracted Fields + Forensic Tampering ELA */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-[380px]">
              <ExtractedFieldsTable extraction={extraction} />
              <TamperingHeatmap
                tampering={tampering}
                rawImageUrl={docPhotoUrl}
              />
            </div>

            {/* Bottom: Biometric Facial Verification ArcFace Panel */}
            <div className="min-h-[280px]">
              <FaceMatchPanel
                face={face}
                docPhotoUrl={docPhotoUrl}
                livePhotoUrl={livePhotoUrl}
              />
            </div>
          </div>

          {/* Right Decision & Reasons Column (~33%) */}
          <div className="xl:col-span-1 flex flex-col gap-6">
            {/* Risk Factors & Reasons Panel */}
            <div className="flex-1 min-h-[380px]">
              <ReasonsPanel riskScore={risk} validation={validation} />
            </div>

            {/* Officer Verdict Action Buttons */}
            <div className="bg-surface border border-border rounded-md p-4 space-y-3">
              <div className="flex items-center justify-between font-mono text-xs text-text-muted">
                <span className="uppercase font-semibold text-text">
                  Officer Verdict Protocol:
                </span>
                <span className="text-[11px]">Kiosk Hotkeys Active</span>
              </div>

              <DecisionActions
                onApprove={handleApprove}
                onEscalate={handleEscalateClick}
                onDetain={handleDetainClick}
                isSubmitting={isSubmittingDecision}
              />
            </div>
          </div>
        </div>
      </main>

      {/* Detain / Escalate Confirmation Modal (Stitch Screen 5) */}
      <DecisionConfirmModal
        isOpen={isModalOpen}
        verdict={modalVerdict}
        documentId={documentId}
        travelerName={travelerName}
        riskScore={risk?.score ?? 0}
        onClose={() => setIsModalOpen(false)}
        onConfirm={handleConfirmModalSubmit}
      />
    </div>
  );
}
