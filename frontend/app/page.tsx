"use client";

import React, { useState, useEffect, useCallback } from "react";
import { ScreenSwitcherNav, ScreenId } from "@/components/stitch/ScreenSwitcherNav";
import { Step1Upload } from "@/components/stitch/Step1Upload";
import { Step2Scanning } from "@/components/stitch/Step2Scanning";
import { Step3ExtractionReview } from "@/components/stitch/Step3ExtractionReview";
import { Step4FaceVerification } from "@/components/stitch/Step4FaceVerification";
import { Step4Confirmation } from "@/components/stitch/Step4Confirmation";
import { AdminScanQueue } from "@/components/stitch/AdminScanQueue";

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
const getApiBases = (): string[] => {
  const envBase = process.env.NEXT_PUBLIC_API_BASE_URL;
  const list = [envBase, "http://localhost:8000", "http://localhost:8007"].filter(Boolean) as string[];
  return Array.from(new Set(list));
};

const safeApiFetch = async (path: string, options?: RequestInit): Promise<Response> => {
  const bases = getApiBases();
  let lastError: any = null;
  for (const base of bases) {
    try {
      const res = await fetch(`${base}${path}`, options);
      return res;
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("All backend endpoints unreachable");
};

const DEMO_CREDENTIALS: Record<string, { email: string; pass: string }> = {
  officer: { email: "officer@triport.gov", pass: "officer123" },
  supervisor: { email: "supervisor@triport.gov", pass: "supervisor123" },
  auditor: { email: "auditor@triport.gov", pass: "auditor123" },
  admin: { email: "admin@triport.gov", pass: "admin123" },
};

// ---------------------------------------------------------------------------
// Preset data (demo mode — no hardcoded identities, uses generic placeholders)
// ---------------------------------------------------------------------------
const PRESETS: Record<string, any> = {
  genuine: {
    extraction: {
      document_type: "passport",
      extraction_method: "mrz",
      fields: [
        { field_name: "given_names", field_value: "JANE MARIE", confidence: 0.99, extraction_method: "mrz" },
        { field_name: "surname", field_value: "MILLER", confidence: 0.99, extraction_method: "mrz" },
        { field_name: "passport_number", field_value: "A98765432", confidence: 0.98, extraction_method: "mrz" },
        { field_name: "nationality", field_value: "USA", confidence: 0.99, extraction_method: "mrz" },
        { field_name: "date_of_birth", field_value: "05/11/1982", confidence: 0.97, extraction_method: "mrz" },
        { field_name: "date_of_expiry", field_value: "04/11/2032", confidence: 0.98, extraction_method: "mrz" },
        { field_name: "gender", field_value: "F", confidence: 0.99, extraction_method: "mrz" },
      ],
      mrz: {
        mrz_present: true,
        checksum_valid: true,
        checksum_failures: [],
        mrz_fields: { name: "JANE MARIE MILLER", doc_number: "A98765432", nationality: "USA", date_of_birth: "05/11/1982", date_of_expiry: "04/11/2032", sex: "F" },
        raw_mrz: "P<USAJANE<<MARIE<<MILLER<<<<<<<<<<<<<<<<<<\nA987654321USA8211059F3211043<<<<<<<<<<<0",
      },
    },
    validation: { passed: true, failed_rules: [], rule_results: [] },
    tampering: { flagged: false, tampering_score: 0.04, checks: [] },
    face: { one_to_one: { matched: true, match_score: 0.96, cosine_similarity: 0.93, threshold: 0.60, detail: "ArcFace match within threshold" } },
    risk_score: { score: 12, band: "LOW", reasons: ["All cryptographic and biometric verifications passed standard tolerances."] },
  },
  tampered_mrz: {
    extraction: {
      document_type: "passport",
      extraction_method: "mrz",
      fields: [
        { field_name: "given_names", field_value: "JANE MARIE", confidence: 0.99, extraction_method: "mrz" },
        { field_name: "surname", field_value: "MILLER", confidence: 0.99, extraction_method: "mrz" },
        { field_name: "passport_number", field_value: "A98765432", confidence: 0.98, extraction_method: "mrz" },
        { field_name: "nationality", field_value: "USA", confidence: 0.99, extraction_method: "mrz" },
        { field_name: "date_of_birth", field_value: "05/11/1982", confidence: 0.72, extraction_method: "mrz" },
        { field_name: "date_of_expiry", field_value: "04/11/2032", confidence: 0.98, extraction_method: "mrz" },
        { field_name: "gender", field_value: "F", confidence: 0.99, extraction_method: "mrz" },
      ],
      mrz: {
        mrz_present: true,
        checksum_valid: false,
        checksum_failures: ["expiry_date"],
        mrz_fields: { doc_number: "A98765432", nationality: "USA" },
        raw_mrz: "P<USAJANE<<MARIE<<MILLER<<<<<<<<<<<<<<<<<<\nA987654321USA8211059F3211043<<<<<<<<<<<7",
      },
    },
    validation: { passed: false, failed_rules: ["mrz_checksum_valid"], rule_results: [] },
    tampering: { flagged: true, tampering_score: 0.78, checks: [{ check_type: "mrz_tampered", score: 0.78, flagged: true, detail: "Check digit mismatch detected" }] },
    face: { one_to_one: { matched: true, match_score: 0.91, cosine_similarity: 0.88, threshold: 0.60, detail: "Face match confirmed" } },
    risk_score: { score: 84, band: "HIGH", reasons: ["MRZ check digit mismatch detected in expiry date block."] },
  },
  tampered_photo: {
    extraction: {
      document_type: "passport",
      extraction_method: "ocr",
      fields: [
        { field_name: "given_names", field_value: "MARCUS", confidence: 0.95, extraction_method: "ocr" },
        { field_name: "surname", field_value: "VANCE", confidence: 0.95, extraction_method: "ocr" },
        { field_name: "passport_number", field_value: "C44910281", confidence: 0.92, extraction_method: "ocr" },
        { field_name: "nationality", field_value: "AUS", confidence: 0.96, extraction_method: "ocr" },
        { field_name: "date_of_birth", field_value: "19/04/1976", confidence: 0.94, extraction_method: "ocr" },
        { field_name: "date_of_expiry", field_value: "12/08/2029", confidence: 0.95, extraction_method: "ocr" },
        { field_name: "gender", field_value: "M", confidence: 0.97, extraction_method: "ocr" },
      ],
      mrz: {
        mrz_present: true,
        checksum_valid: false,
        checksum_failures: ["doc_number", "expiry_date"],
        mrz_fields: {},
        raw_mrz: "P<AUSVANCE<<MARCUS<<<<<<<<<<<<<<<<<<<<<<<<\nC449102814AUS7604191M2908126<<<<<<<<<<4",
      },
    },
    validation: { passed: false, failed_rules: ["mrz_checksum_valid", "photo_integrity"], rule_results: [] },
    tampering: { flagged: true, tampering_score: 0.94, checks: [{ check_type: "ela", score: 0.94, flagged: true, detail: "High-frequency ELA anomaly in photo region" }] },
    face: { one_to_one: { matched: false, match_score: 0.38, cosine_similarity: 0.31, threshold: 0.60, detail: "Face geometric distance exceeds threshold" } },
    risk_score: { score: 94, band: "CRITICAL", reasons: ["Multi-layer photo substrate tampering detected.", "Biometric face mismatch confirmed.", "MRZ checksums invalid."] },
  },
};

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------
export default function TriPortDashboard() {
  const [currentScreen, setCurrentScreen] = useState<ScreenId>("step1_upload");
  const [role, setRole] = useState<string>("officer");
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [pipelineData, setPipelineData] = useState<any>(null);
  const [pipelineReady, setPipelineReady] = useState<boolean>(false);
  const [docImagePreview, setDocImagePreview] = useState<string | null>(null);
  const [documentFile, setDocumentFile] = useState<File | null>(null); // kept for face verify step
  const [faceCropUrl, setFaceCropUrl] = useState<string | null>(null);
  const [decision, setDecision] = useState<"permitted" | "denied" | "flagged">("permitted");

  // ── Auth token fetch ───────────────────────────────────────────────────────
  const obtainToken = useCallback(async (targetRole: string = role): Promise<string | null> => {
    try {
      const creds = DEMO_CREDENTIALS[targetRole] || DEMO_CREDENTIALS.officer;
      const res = await safeApiFetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: creds.email, password: creds.pass }),
      });
      if (res.ok) {
        const data = await res.json();
        setAuthToken(data.access_token);
        return data.access_token;
      }
    } catch (err) {
      console.warn("Auth token fetch (backend may be offline):", err);
    }
    return null;
  }, [role]);

  useEffect(() => { obtainToken(role); }, [role]);

  // ── Face crop fetch ────────────────────────────────────────────────────────
  const fetchFaceCrop = useCallback(async (file: File, token: string | null) => {
    try {
      const formData = new FormData();
      formData.append("file", file);
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await safeApiFetch("/api/v1/documents/face-crop", {
        method: "POST",
        headers,
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        if (data.face_detected && data.face_crop_base64) {
          setFaceCropUrl(data.face_crop_base64);
        }
      }
    } catch (err) {
      console.warn("Face crop API unavailable (will use full passport image):", err);
    }
  }, []);

  // ── Reset helper ───────────────────────────────────────────────────────────
  const resetSession = useCallback(() => {
    setPipelineData(null);
    setPipelineReady(false);
    setDocImagePreview(null);
    setDocumentFile(null);
    setFaceCropUrl(null);
    setCurrentScreen("step1_upload");
  }, []);

  // ── Real face verification: send passport + live frame to backend ──────────
  // Returns OneToOneVerifyResponse-shaped object or null on failure
  const verifyFace = useCallback(async (
    liveFrameBlob: Blob
  ): Promise<{ matched: boolean; match_score: number; cosine_similarity: number } | null> => {
    // Prefer the stored File; fallback to re-fetching the preview URL
    let passportFile: File | Blob | null = documentFile;
    if (!passportFile && docImagePreview) {
      try {
        const res = await fetch(docImagePreview);
        passportFile = await res.blob();
      } catch {
        passportFile = null;
      }
    }

    if (!passportFile) {
      console.warn("[verifyFace] No passport file available for comparison");
      return null;
    }

    try {
      let token = authToken;
      if (!token) token = await obtainToken();

      const formData = new FormData();
      formData.append("file", passportFile, "passport.jpg");
      formData.append("live_photo", liveFrameBlob, "live_capture.jpg");
      formData.append("document_type", "passport");

      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await safeApiFetch("/api/v1/documents/upload", {
        method: "POST",
        headers,
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        const faceResult = data?.pipeline?.face?.one_to_one ?? data?.face?.one_to_one ?? null;
        if (faceResult) {
          console.info("[verifyFace] Real 1:1 match result:", faceResult);
          // Merge the fresh face result back into pipelineData so confirmation screen shows it
          setPipelineData((prev: any) => ({
            ...prev,
            face: { ...(prev?.face ?? {}), one_to_one: faceResult },
          }));
          return faceResult;
        }
      } else {
        console.warn("[verifyFace] Backend error:", res.status);
      }
    } catch (err) {
      console.error("[verifyFace] Network error:", err);
    }
    return null;
  }, [documentFile, docImagePreview, authToken, obtainToken]);

  // ── Preset scenario loader ─────────────────────────────────────────────────
  const loadPreset = useCallback((presetName: string) => {
    const preset = PRESETS[presetName] || PRESETS.genuine;
    setPipelineData(preset);
    setPipelineReady(true);
    setDocImagePreview(null);
    setFaceCropUrl(null);
  }, []);

  // ── Main scan handler ──────────────────────────────────────────────────────
  const handleStartScan = useCallback(async (
    file: File | null,
    _liveFile?: File | null,
    presetName?: string
  ) => {
    // Reset state for new scan
    setPipelineData(null);
    setPipelineReady(false);
    setFaceCropUrl(null);
    setCurrentScreen("step2_scanning");

    if (presetName) {
      setTimeout(() => loadPreset(presetName), 100);
      return;
    }

    if (!file) {
      loadPreset("genuine");
      return;
    }

    // Store original file for face verify step + set preview
    setDocumentFile(file);
    setDocImagePreview(URL.createObjectURL(file));

    // Get/refresh token
    let token = authToken;
    if (!token) token = await obtainToken();

    // Start face crop fetch in parallel (non-blocking)
    fetchFaceCrop(file, token);

    // Upload to backend pipeline
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", "passport");

      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await safeApiFetch("/api/v1/documents/upload", {
        method: "POST",
        headers,
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setPipelineData(data.pipeline || data);
        setPipelineReady(true);
        console.info("[TriPort] Pipeline complete:", data.status);
      } else {
        const errData = await res.json().catch(() => ({}));
        console.error("[TriPort] Upload error:", res.status, errData);
        // Still mark ready so scanning animation can advance
        setPipelineReady(true);
      }
    } catch (err) {
      console.error("[TriPort] Backend unreachable:", err);
      setPipelineReady(true);
    }
  }, [authToken, obtainToken, fetchFaceCrop, loadPreset]);

  // ── Decision handlers ──────────────────────────────────────────────────────
  const handlePermit = () => { setDecision("permitted"); setCurrentScreen("step4_confirm"); };
  const handleDeny = () => { setDecision("denied"); setCurrentScreen("step4_confirm"); };
  const handleFlag = () => { setDecision("flagged"); setCurrentScreen("step4_confirm"); };

  return (
    <div className="min-h-screen flex flex-col bg-[#fcf9f4] text-[#1c1c19]">
      {/* Navigation */}
      <ScreenSwitcherNav
        currentScreen={currentScreen}
        onSelectScreen={setCurrentScreen}
        role={role}
        onRoleChange={setRole}
      />

      {/* Screen content */}
      <main className="flex-1 flex flex-col">

        {/* Step 1: Upload */}
        {currentScreen === "step1_upload" && (
          <Step1Upload
            onStartScan={(file, live, preset) => handleStartScan(file, live, preset)}
            isLoading={false}
            onSelectPreset={(preset) => handleStartScan(null, null, preset)}
          />
        )}

        {/* Step 2: Scanning animation (waits for backend) */}
        {currentScreen === "step2_scanning" && (
          <Step2Scanning
            documentImage={docImagePreview}
            pipelineReady={pipelineReady}
            onComplete={() => setCurrentScreen("step3_extraction")}
          />
        )}

        {/* Step 3: Extraction + MRZ review */}
        {currentScreen === "step3_extraction" && (
          <Step3ExtractionReview
            pipelineData={pipelineData}
            documentImage={docImagePreview}
            faceCropUrl={faceCropUrl}
            onContinueToFace={() => setCurrentScreen("step4_face")}
            onFlagForReview={handleFlag}
          />
        )}

        {/* Step 4a: Face Verification */}
        {currentScreen === "step4_face" && (
          <Step4FaceVerification
            documentPhoto={docImagePreview}
            faceCropUrl={faceCropUrl}
            pipelineData={pipelineData}
            onVerifyFace={verifyFace}
            onPermit={handlePermit}
            onDeny={handleDeny}
          />
        )}

        {/* Step 4b: Decision confirmation */}
        {currentScreen === "step4_confirm" && (
          <Step4Confirmation
            decision={decision}
            pipelineData={pipelineData}
            onScanNext={resetSession}
          />
        )}

        {/* Admin Queue */}
        {currentScreen === "admin_queue" && (
          <AdminScanQueue
            onInspectRow={(rowId) => {
              const preset = rowId === "scan-001" ? "tampered_mrz" : rowId === "scan-005" ? "tampered_photo" : "genuine";
              loadPreset(preset);
              setCurrentScreen("step3_extraction");
            }}
          />
        )}
      </main>
    </div>
  );
}
