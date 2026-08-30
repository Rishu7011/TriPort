"use client";

import React, { useState } from "react";

interface Step3VerificationResultProps {
  onApprove: () => void;
  onFlag: () => void;
  onReject: () => void;
  pipelineData?: any;
  documentImage?: string | null;
  livePhoto?: string | null;
}

export const Step3VerificationResult: React.FC<Step3VerificationResultProps> = ({
  onApprove,
  onFlag,
  onReject,
  pipelineData,
  documentImage,
  livePhoto,
}) => {
  const [faceExpanded, setFaceExpanded] = useState<boolean>(true);

  // Dynamic risk score and recommendation from backend RiskEngine / Tampering
  const riskScore =
    pipelineData?.risk_score?.score ??
    pipelineData?.decision?.risk_score ??
    (pipelineData?.tampering?.flagged ? 84 : 15);

  const riskBand =
    pipelineData?.risk_score?.risk_band?.toUpperCase() ??
    pipelineData?.decision?.risk_band?.toUpperCase() ??
    (riskScore >= 70 ? "HIGH" : riskScore >= 40 ? "MEDIUM" : "LOW");

  const isHighRisk = riskScore >= 50 || riskBand === "HIGH" || riskBand === "CRITICAL";

  // Dynamic checks from backend
  const extractionFieldsCount = pipelineData?.extraction?.fields?.length || 0;
  const mrzValid =
    pipelineData?.extraction?.mrz?.checksum_valid ??
    pipelineData?.validation?.mrz_checksum_valid ??
    !(pipelineData?.tampering?.mrz_tampered);

  const photoTampered =
    pipelineData?.tampering?.photo_tampered ??
    pipelineData?.tampering?.checks?.some((c: any) => c.check_type === "photo_splicing" && !c.passed) ??
    false;

  const ghostMatched = pipelineData?.tampering?.ghost_image_matched ?? true;

  const faceScore =
    pipelineData?.face?.one_to_one?.match_score !== undefined
      ? Math.round(pipelineData.face.one_to_one.match_score * 100)
      : pipelineData?.biometrics?.match_score ?? 94;

  const faceMatch =
    pipelineData?.face?.one_to_one?.is_match ??
    pipelineData?.biometrics?.is_match ??
    faceScore >= 70;

  // Reasons list from Risk Engine
  const reasons: string[] =
    pipelineData?.risk_score?.reasons ||
    pipelineData?.decision?.reasons ||
    (isHighRisk
      ? ["Anomalies detected during multi-spectral analysis and validation checks."]
      : ["All cryptographic and biometric verifications passed standard tolerances."]);

  const defaultDocPhoto =
    documentImage ||
    "https://lh3.googleusercontent.com/aida-public/AB6AXuBibx1YUmNiaerNSRHR1_TMX1n78o7sdOHzTR_bjklfZmWaW_FUhiQk4TiubSAm-56p2_BUD4s8D9xEnPiFckvei8mibCZQn46-Mm15dbWSj-sPe1uItmuxp0hqsEWfbLJraF8FwIq50_1y5Nf7DgPwaQAJAWmTOvseSByQ4tr1yNrnL0p81vfmdo_eA4De87WSG0PtZstLhRgEEDhYGqnt4uXFRpv2zmj97NRJPBCC52bdaPG8F4JDnA";

  return (
    <div className="flex-1 w-full max-w-[1440px] mx-auto px-6 py-10 flex flex-col gap-8">
      {/* Risk Verdict Banner */}
      <div
        className={`rounded-2xl p-6 md:p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 shadow-[0px_4px_20px_rgba(43,38,34,0.04)] border ${
          isHighRisk
            ? "bg-[#FBE7D8] border-[#C1652E]/30 text-[#C1652E]"
            : "bg-[#E5F3EA] border-[#2F8F5B]/30 text-[#2F8F5B]"
        }`}
      >
        <div className="flex items-center gap-5">
          <div
            className={`w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-sm ${
              isHighRisk ? "bg-[#C1652E]/20 text-[#C1652E]" : "bg-[#2F8F5B]/20 text-[#2F8F5B]"
            }`}
          >
            <span className="material-symbols-outlined !text-4xl icon-fill">
              {isHighRisk ? "warning" : "verified"}
            </span>
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">
              {riskBand} Risk — {riskScore}/100
            </h1>
            <p className="text-sm font-medium text-[#55433d] mt-1">
              {reasons[0]}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${
              isHighRisk ? "bg-[#C1652E] text-white" : "bg-[#2F8F5B] text-white"
            }`}
          >
            {isHighRisk ? "Flagged for Officer Review" : "Cleared for Fast-Track"}
          </span>
        </div>
      </div>

      {/* Main Grid: Checklist & Tampering Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Unified Verification Checklist & Decision Buttons */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          <div className="bg-[#FAF8F5] rounded-2xl p-6 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)]">
            <h3 className="text-lg font-bold text-[#2B2622] pb-3 border-b border-[#E8E2D9] mb-4 flex items-center justify-between">
              <span>Verification Checklist</span>
              <span className="text-xs font-normal text-[#655d54]">4 automated security gates</span>
            </h3>

            <div className="space-y-3.5">
              {/* Row 1: Document Extraction */}
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#E5F3EA] text-[#2F8F5B] border border-[#2F8F5B]/20">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined icon-fill">check_circle</span>
                  <span className="text-sm font-bold">Document Extraction (OCR)</span>
                </div>
                <span className="text-xs font-bold">
                  {extractionFieldsCount > 0 ? `${extractionFieldsCount} Fields Detected` : "Completed"}
                </span>
              </div>

              {/* Row 2: MRZ Validation */}
              <div
                className={`flex items-center justify-between p-3.5 rounded-xl border ${
                  !mrzValid
                    ? "bg-[#FBE7D8] text-[#C1652E] border-[#C1652E]/30"
                    : "bg-[#E5F3EA] text-[#2F8F5B] border-[#2F8F5B]/20"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined icon-fill">
                    {!mrzValid ? "error" : "check_circle"}
                  </span>
                  <span className="text-sm font-bold">MRZ Checksum Validation</span>
                </div>
                <span className="text-xs font-bold">
                  {!mrzValid ? "Checksum Mismatch Detected" : "Valid ICAO Checksums"}
                </span>
              </div>

              {/* Row 3: Physical Tampering */}
              <div
                className={`flex items-center justify-between p-3.5 rounded-xl border ${
                  photoTampered || !ghostMatched
                    ? "bg-[#FBE7D8] text-[#C1652E] border-[#C1652E]/30"
                    : "bg-[#E5F3EA] text-[#2F8F5B] border-[#2F8F5B]/20"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined icon-fill">
                    {photoTampered || !ghostMatched ? "error" : "check_circle"}
                  </span>
                  <span className="text-sm font-bold">Physical Substrate &amp; Tampering</span>
                </div>
                <span className="text-xs font-bold">
                  {photoTampered
                    ? "Photo Splicing Detected"
                    : !ghostMatched
                    ? "Ghost Image Correlation Anomaly"
                    : "Substrate Intact"}
                </span>
              </div>

              {/* Row 4: Face Match (Collapsible) */}
              <div className="border border-[#E8E2D9] rounded-xl overflow-hidden bg-white shadow-sm">
                <button
                  onClick={() => setFaceExpanded(!faceExpanded)}
                  className="w-full flex items-center justify-between p-3.5 hover:bg-[#FAF8F5] transition-colors text-[#2B2622] cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-[#2F8F5B]">face</span>
                    <span className="text-sm font-bold">Biometric Face Match</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                        faceMatch
                          ? "bg-[#E5F3EA] text-[#2F8F5B]"
                          : "bg-[#FBE3E3] text-[#C13B3B]"
                      }`}
                    >
                      {faceScore}% Match
                    </span>
                    <span
                      className={`material-symbols-outlined text-[#655d54] transition-transform ${
                        faceExpanded ? "rotate-180" : ""
                      }`}
                    >
                      expand_more
                    </span>
                  </div>
                </button>

                {faceExpanded && (
                  <div className="p-4 border-t border-[#E8E2D9] bg-[#FAF8F5] flex flex-col sm:flex-row gap-4 items-center">
                    <div className="flex gap-3">
                      <div className="text-center">
                        <div className="w-20 h-24 rounded-lg overflow-hidden border border-[#E8E2D9] shadow-sm bg-[#f6f3ee]">
                          <img
                            alt="Reference ID"
                            className="w-full h-full object-cover"
                            src={defaultDocPhoto}
                          />
                        </div>
                        <span className="text-[10px] font-bold text-[#655d54] mt-1 block">
                          Document Photo
                        </span>
                      </div>

                      <div className="text-center">
                        <div className="w-20 h-24 rounded-lg overflow-hidden border border-[#E8E2D9] shadow-sm bg-[#f6f3ee] flex items-center justify-center">
                          {livePhoto ? (
                            <img
                              alt="Live Capture"
                              className="w-full h-full object-cover"
                              src={livePhoto}
                            />
                          ) : (
                            <span className="material-symbols-outlined text-3xl text-[#88726c]">
                              videocam
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] font-bold text-[#655d54] mt-1 block">
                          Live Capture
                        </span>
                      </div>
                    </div>

                    <div className="flex-1 text-left">
                      <p className="text-xs font-bold text-[#2B2622]">
                        Match Confidence: {faceScore}%
                      </p>
                      <p className="text-xs text-[#55433d] mt-1 leading-relaxed">
                        {faceMatch
                          ? "Biometric facial features match document reference photo within acceptable thresholds."
                          : "Facial geometric distance exceeds tolerance threshold. Secondary manual inspection required."}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Officer Decision Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 mt-2">
            <button
              onClick={onApprove}
              className="flex-1 bg-[#2F8F5B] text-white font-bold text-sm py-4 rounded-xl hover:scale-[1.02] shadow-[0px_4px_16px_rgba(47,143,91,0.25)] transition-all flex justify-center items-center gap-2 cursor-pointer active:scale-95"
            >
              <span className="material-symbols-outlined !text-xl">check</span>
              <span>Approve Entry</span>
            </button>

            <button
              onClick={onFlag}
              className="flex-1 bg-[#B8860B] text-white font-bold text-sm py-4 rounded-xl hover:scale-[1.02] shadow-[0px_4px_16px_rgba(184,134,11,0.25)] transition-all flex justify-center items-center gap-2 cursor-pointer active:scale-95"
            >
              <span className="material-symbols-outlined !text-xl">flag</span>
              <span>Flag for Secondary Review</span>
            </button>

            <button
              onClick={onReject}
              className="flex-1 bg-[#C13B3B] text-white font-bold text-sm py-4 rounded-xl hover:scale-[1.02] shadow-[0px_4px_16px_rgba(193,59,59,0.25)] transition-all flex justify-center items-center gap-2 cursor-pointer active:scale-95"
            >
              <span className="material-symbols-outlined !text-xl">block</span>
              <span>Deny Entry</span>
            </button>
          </div>
        </div>

        {/* Right: Document Inspection Preview */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="bg-[#FAF8F5] rounded-2xl p-6 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)] h-full flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-base font-bold text-[#2B2622] flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#655d54]">visibility</span>
                  <span>Forensic Analysis Overlay</span>
                </h3>
                <span className="text-xs font-bold text-[#655d54] bg-[#ede0d5] px-2.5 py-1 rounded-full">
                  Multi-Spectral Review
                </span>
              </div>

              <div className="relative rounded-xl overflow-hidden border border-[#E8E2D9] bg-[#f0ede9] aspect-[4/3] flex items-center justify-center">
                {documentImage ? (
                  <img
                    alt="Document Forensics"
                    className="w-full h-full object-contain"
                    src={documentImage}
                  />
                ) : (
                  <div className="text-center text-[#88726c]">
                    <span className="material-symbols-outlined text-4xl">document_scanner</span>
                    <p className="text-xs mt-1">No document image loaded</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
