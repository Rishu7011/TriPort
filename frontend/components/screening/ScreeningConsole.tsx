"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "../../lib/auth/AuthContext";
import { api } from "../../lib/api/client";
import type {
  CheckpointType,
  DocumentType,
  UploadResponse,
  DecisionResponse,
  FaceVerificationResult,
  RiskScoreResponse,
} from "../../lib/api/types";
import { DocumentUploadScreen } from "./DocumentUploadScreen";
import { DocumentResultsScreen } from "./DocumentResultsScreen";
import { BiometricScreen } from "./BiometricScreen";
import { DecisionConfirmationScreen } from "./DecisionConfirmationScreen";

type ScreeningStep = "upload" | "results" | "biometric" | "confirmation";

export function ScreeningConsole() {
  const { user } = useAuth();

  // Wizard Step State
  const [currentStep, setCurrentStep] = useState<ScreeningStep>("upload");

  // Real Backend Data State
  const [uploadData, setUploadData] = useState<UploadResponse | null>(null);
  const [localDocPreviewUrl, setLocalDocPreviewUrl] = useState<string | null>(null);
  const [stage2Data, setStage2Data] = useState<{
    face: FaceVerificationResult;
    risk_score: RiskScoreResponse;
    live_image_url: string;
  } | null>(null);
  const [decisionData, setDecisionData] = useState<DecisionResponse | null>(null);

  // Loading & In-Flight Status
  const [isUploading, setIsUploading] = useState(false);
  const [isDeciding, setIsDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Live UTC Clock
  const [utcClock, setUtcClock] = useState("UTC --:--:--");
  useEffect(() => {
    const updateTime = () => {
      const d = new Date();
      const h = d.getUTCHours().toString().padStart(2, "0");
      const m = d.getUTCMinutes().toString().padStart(2, "0");
      const s = d.getUTCSeconds().toString().padStart(2, "0");
      setUtcClock(`UTC ${h}:${m}:${s}`);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // 1. Stage 1: Document Upload
  const handleUploadDocument = async (
    file: File,
    docType: DocumentType,
    checkpointType: CheckpointType
  ) => {
    try {
      setIsUploading(true);
      setError(null);

      // Instantly generate local preview URL so officer sees exact document image
      const localUrl = URL.createObjectURL(file);
      setLocalDocPreviewUrl(localUrl);

      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", docType);
      formData.append("checkpoint_type", checkpointType);
      if (user?.checkpoint_id) {
        formData.append("checkpoint_id", user.checkpoint_id);
      }

      // Real live call to POST /api/v1/documents/upload
      const res = await api.uploadDocument(formData);
      setUploadData(res);
      setCurrentStep("results");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Document upload failed";
      setError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  // 2. Stage 2: Biometric Verification
  const handleVerifyLiveFace = async (photoBlob: Blob) => {
    if (!uploadData?.document_id) {
      throw new Error("No active document screening record");
    }

    const formData = new FormData();
    formData.append("file", photoBlob, "live_capture.jpg");

    // Real live call to POST /api/v1/documents/{documentId}/verify-live-face
    const res = await api.verifyLiveFace(uploadData.document_id, formData);
    setStage2Data(res);
    return res;
  };

  // 3. Officer Decision Recording
  const handleRecordDecision = async (
    decision: "approve" | "reject",
    notes?: string
  ) => {
    if (!uploadData?.document_id) return;

    try {
      setIsDeciding(true);
      const effectiveOfficerId =
        user?.user_id || "00000000-0000-0000-0000-000000000001";
      const res = await api.recordDecision(uploadData.document_id, {
        officer_id: effectiveOfficerId,
        decision,
        notes: notes || `Decision recorded from Checkpoint Console: ${decision.toUpperCase()}`,
      });
      setDecisionData(res);
      setCurrentStep("confirmation");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record decision";
      setError(msg);
    } finally {
      setIsDeciding(false);
    }
  };

  // 4. Reset flow completely for next traveler
  const handleReset = () => {
    if (localDocPreviewUrl) {
      URL.revokeObjectURL(localDocPreviewUrl);
    }
    setLocalDocPreviewUrl(null);
    setUploadData(null);
    setStage2Data(null);
    setDecisionData(null);
    setError(null);
    setIsUploading(false);
    setIsDeciding(false);
    setCurrentStep("upload");
  };

  // Extract traveler name accurately
  const extractedFields = uploadData?.pipeline?.extraction?.fields || [];
  const getVal = (k: string) =>
    extractedFields.find((f) => f.field_name.toLowerCase() === k.toLowerCase())
      ?.field_value;
  const givenN = getVal("given_names") || getVal("given_name") || getVal("first_name");
  const surN = getVal("surname") || getVal("last_name");
  const fullN = getVal("full_name") || getVal("name");

  let travelerName = fullN?.trim() || "";
  if (givenN && surN) {
    if (!travelerName || travelerName.toLowerCase() === surN.toLowerCase()) {
      travelerName = `${givenN.trim()} ${surN.trim()}`;
    }
  } else if (!travelerName) {
    travelerName = givenN || surN || "IDENTIFIED TRAVELER";
  }

  const stationLabel = user?.checkpoint_id
    ? `STATION / ${user.checkpoint_id.substring(0, 8).toUpperCase()}`
    : "STATION-04 / LHR-UK";

  return (
    <div className="flex flex-col min-h-screen bg-background font-body-md text-on-surface antialiased">
      {/* Top Fixed Header matching Google Stitch Design */}
      <header className="fixed top-0 left-0 right-0 h-16 bg-surface-container-low border-b border-outline-variant/60 z-50 px-4 sm:px-6 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div className="flex flex-col">
            <span className="font-label-caps text-primary-fixed uppercase tracking-widest text-[11px]">
              TRIPORT //
            </span>
            <span className="font-data-mono-md text-[11px] text-on-surface-variant opacity-80 uppercase">
              {stationLabel}
            </span>
          </div>

          <div className="h-8 w-px bg-outline-variant/60 hidden sm:block" />

          {/* Stepper Navigation */}
          <nav className="hidden md:flex gap-4">
            <div
              className={`h-16 flex items-center px-3 font-label-caps transition-all text-xs tracking-wider border-b-2 ${
                currentStep === "upload" || currentStep === "results"
                  ? "border-primary-fixed text-primary-fixed"
                  : "border-transparent text-on-surface-variant"
              }`}
            >
              01. DOCUMENT SCREENING
            </div>
            <div
              className={`h-16 flex items-center px-3 font-label-caps transition-all text-xs tracking-wider border-b-2 ${
                currentStep === "biometric"
                  ? "border-primary-fixed text-primary-fixed"
                  : "border-transparent text-on-surface-variant"
              }`}
            >
              02. BIOMETRIC VERIFICATION
            </div>
            <div
              className={`h-16 flex items-center px-3 font-label-caps transition-all text-xs tracking-wider border-b-2 ${
                currentStep === "confirmation"
                  ? "border-primary-fixed text-primary-fixed"
                  : "border-transparent text-on-surface-variant"
              }`}
            >
              03. FINAL DECISION
            </div>
          </nav>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="font-data-mono-md text-xs text-on-surface uppercase font-medium">
              {utcClock}
            </div>
            <div className="flex items-center justify-end gap-1.5 mt-0.5">
              <span className="w-2 h-2 bg-primary-fixed rounded-full animate-pulse shadow-[0_0_6px_#c0f500]" />
              <span className="font-label-caps text-[10px] text-primary-fixed uppercase tracking-wider">
                OPERATIONAL / SECURE
              </span>
            </div>
          </div>

          <div className="w-8 h-8 rounded-full bg-surface-container-highest border border-outline-variant/60 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary-fixed text-[18px]">
              person
            </span>
          </div>
        </div>
      </header>

      {/* Left Navigation Rail matching Google Stitch Design */}
      <aside className="fixed left-0 top-16 bottom-0 w-16 bg-surface-container-lowest border-r border-outline-variant/60 flex flex-col items-center py-4 gap-6 z-40">
        <Link
          href="/command"
          title="Command Overview"
          className="text-on-surface-variant hover:text-primary-fixed transition-colors"
        >
          <span className="material-symbols-outlined">groups</span>
        </Link>
        <Link
          href="/command/admin"
          title="System Alerts & Watchlists"
          className="text-on-surface-variant hover:text-error transition-colors"
        >
          <span className="material-symbols-outlined">warning</span>
        </Link>
        <Link
          href="/audit"
          title="Cryptographic Audit Logs"
          className="text-on-surface-variant hover:text-primary-fixed transition-colors"
        >
          <span className="material-symbols-outlined">history_edu</span>
        </Link>
        <div className="mt-auto">
          <Link
            href="/command/admin"
            title="System Settings"
            className="text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <span className="material-symbols-outlined">settings</span>
          </Link>
        </div>
      </aside>

      {/* Main Screening Content Stage */}
      <main className="pt-16 pl-16 w-full min-h-screen bg-background flex flex-col">
        {currentStep === "upload" && (
          <DocumentUploadScreen
            onScanDocument={handleUploadDocument}
            isUploading={isUploading}
            error={error}
          />
        )}

        {currentStep === "results" && uploadData && (
          <DocumentResultsScreen
            uploadData={uploadData}
            localPreviewUrl={localDocPreviewUrl}
            onProceedToBiometrics={() => setCurrentStep("biometric")}
            onRejectDocument={(notes) => handleRecordDecision("reject", notes)}
            isRejecting={isDeciding}
          />
        )}

        {currentStep === "biometric" && uploadData && (
          <BiometricScreen
            documentId={uploadData.document_id}
            docPortraitUrl={uploadData.doc_face_crop_url || uploadData.doc_image_url || ""}
            onVerifyLiveFace={handleVerifyLiveFace}
            onRecordDecision={handleRecordDecision}
            isDeciding={isDeciding}
          />
        )}

        {currentStep === "confirmation" && decisionData && (
          <DecisionConfirmationScreen
            decisionData={decisionData}
            travelerName={travelerName}
            documentId={uploadData?.document_id || decisionData.document_id}
            riskBand={stage2Data?.risk_score?.band || null}
            riskScore={stage2Data?.risk_score?.score ?? null}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  );
}
