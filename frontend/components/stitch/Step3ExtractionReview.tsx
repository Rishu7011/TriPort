"use client";

import React, { useState, useEffect } from "react";

interface Step3ExtractionReviewProps {
  onContinueToFace: () => void;
  onFlagForReview: () => void;
  pipelineData?: any;
  documentImage?: string | null;
  faceCropUrl?: string | null;
}

interface DisplayField {
  key: string;
  label: string;
  value: string;
  confidence: number | null;
  method?: string;
  isLowConfidence?: boolean;
}

const FIELD_LABEL_MAP: Record<string, string> = {
  name: "Full Name",
  given_names: "Given Name(s)",
  surname: "Surname",
  passport_number: "Passport / Doc No.",
  doc_number: "Passport / Doc No.",
  document_number: "Passport / Doc No.",
  nationality: "Nationality",
  country_code: "Nationality",
  date_of_birth: "Date of Birth",
  date_of_expiry: "Date of Expiry",
  gender: "Sex",
  sex: "Sex",
  place_of_birth: "Place of Birth",
  issuing_country: "Issuing Country",
  date_of_issue: "Date of Issue",
};

const PRIORITY_FIELDS = [
  ["name", "given_names"],
  ["surname"],
  ["passport_number", "doc_number", "document_number"],
  ["nationality", "country_code", "issuing_country"],
  ["date_of_birth"],
  ["date_of_expiry"],
  ["gender", "sex"],
  ["place_of_birth"],
  ["date_of_issue"],
];

export const Step3ExtractionReview: React.FC<Step3ExtractionReviewProps> = ({
  onContinueToFace,
  onFlagForReview,
  pipelineData,
  documentImage,
  faceCropUrl,
}) => {
  const [fields, setFields] = useState<DisplayField[]>([]);
  const [mrzLine1, setMrzLine1] = useState<string>("");
  const [mrzLine2, setMrzLine2] = useState<string>("");
  const [mrzChecksumValid, setMrzChecksumValid] = useState<boolean | null>(null);
  const [checksumFailures, setChecksumFailures] = useState<string[]>([]);
  const [mrzPresent, setMrzPresent] = useState<boolean>(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);

  useEffect(() => {
    if (!pipelineData) {
      setFields([]);
      setMrzLine1("");
      setMrzLine2("");
      setMrzChecksumValid(null);
      setMrzPresent(false);
      return;
    }

    // ── 1. Build field map from backend ExtractionResponse.fields ──────────
    const rawFieldsList: any[] =
      pipelineData?.extraction?.fields ||
      pipelineData?.fields ||
      [];

    const fieldMap: Record<string, { value: string; confidence: number | null; method?: string }> = {};

    if (Array.isArray(rawFieldsList)) {
      rawFieldsList.forEach((f: any) => {
        if (f?.field_name && f?.field_value) {
          const conf =
            f.confidence !== undefined && f.confidence !== null
              ? f.confidence <= 1
                ? Math.round(f.confidence * 100)
                : Math.round(f.confidence)
              : null;
          fieldMap[f.field_name.toLowerCase()] = {
            value: f.field_value,
            confidence: conf,
            method: f.extraction_method || "ocr",
          };
        }
      });
    }

    // ── 2. Also overlay MRZ fields (higher trust when checksum valid) ───────
    const mrzFields = pipelineData?.extraction?.mrz?.mrz_fields || {};
    const mrzChecksumOk = pipelineData?.extraction?.mrz?.checksum_valid ?? null;
    Object.entries(mrzFields).forEach(([k, v]) => {
      if (v && typeof v === "string" && !fieldMap[k.toLowerCase()]) {
        fieldMap[k.toLowerCase()] = {
          value: v,
          confidence: mrzChecksumOk ? 100 : 70,
          method: "mrz",
        };
      }
    });

    // ── 3. Build prioritized display list ───────────────────────────────────
    const seen = new Set<string>();
    const displayFields: DisplayField[] = [];

    for (const aliases of PRIORITY_FIELDS) {
      for (const alias of aliases) {
        const entry = fieldMap[alias.toLowerCase()];
        if (entry?.value && !seen.has(aliases[0])) {
          seen.add(aliases[0]);
          const conf = entry.confidence;
          displayFields.push({
            key: aliases[0],
            label: FIELD_LABEL_MAP[aliases[0]] || alias.replace(/_/g, " ").toUpperCase(),
            value: entry.value,
            confidence: conf,
            method: entry.method,
            isLowConfidence: conf !== null && conf < 75,
          });
          break;
        }
      }
    }

    // Add any remaining fields not in priority list
    const priorityKeySet = new Set(PRIORITY_FIELDS.flat());
    Object.entries(fieldMap).forEach(([k, v]) => {
      if (!priorityKeySet.has(k) && v.value && k !== "raw_mrz") {
        displayFields.push({
          key: k,
          label: (FIELD_LABEL_MAP[k] || k.replace(/_/g, " ")).toUpperCase(),
          value: v.value,
          confidence: v.confidence,
          method: v.method,
          isLowConfidence: v.confidence !== null && v.confidence < 75,
        });
      }
    });

    setFields(displayFields);

    // ── 4. MRZ Lines ─────────────────────────────────────────────────────────
    const mrz = pipelineData?.extraction?.mrz;
    const rawMrzString =
      mrz?.raw_mrz ||
      (mrz?.mrz_fields?.line1 && mrz?.mrz_fields?.line2
        ? `${mrz.mrz_fields.line1}\n${mrz.mrz_fields.line2}`
        : "");

    if (rawMrzString) {
      const lines = rawMrzString.split("\n").filter(Boolean);
      setMrzLine1(lines[0] || "");
      setMrzLine2(lines[1] || "");
    } else {
      setMrzLine1("");
      setMrzLine2("");
    }

    setMrzPresent(mrz?.mrz_present ?? false);
    setMrzChecksumValid(mrz?.checksum_valid ?? null);
    setChecksumFailures(mrz?.checksum_failures ?? []);
  }, [pipelineData]);

  const handleFieldChange = (key: string, newValue: string) => {
    setFields((prev) => prev.map((f) => (f.key === key ? { ...f, value: newValue } : f)));
  };

  // ── Derived risk signals ───────────────────────────────────────────────────
  const riskScore = pipelineData?.risk_score?.score ?? null;
  const riskBand = (pipelineData?.risk_score?.band ?? "").toUpperCase();
  const tamperingFlagged = pipelineData?.tampering?.flagged ?? false;
  const validationPassed = pipelineData?.validation?.passed ?? true;
  const mrzFailed = mrzChecksumValid === false;

  // OCR+MRZ passed = we can proceed to face verification
  const canProceedToFace = mrzPresent && !mrzFailed && !tamperingFlagged;

  const overallClear = !tamperingFlagged && !mrzFailed && validationPassed;

  const riskBandColor =
    riskBand === "CRITICAL" || riskBand === "HIGH"
      ? { bg: "bg-[#FBE7D8]", text: "text-[#C1652E]", border: "border-[#C1652E]/30", dot: "bg-[#C1652E]" }
      : riskBand === "MEDIUM"
      ? { bg: "bg-[#FBF0D6]", text: "text-[#B8860B]", border: "border-[#B8860B]/30", dot: "bg-[#B8860B]" }
      : { bg: "bg-[#E5F3EA]", text: "text-[#2F8F5B]", border: "border-[#2F8F5B]/30", dot: "bg-[#2F8F5B]" };

  return (
    <div className="flex-1 w-full max-w-[1440px] mx-auto px-6 py-8 flex flex-col gap-6">
      {/* Header */}
      <div className="animate-slide-up">
        <div className="flex items-center gap-2 text-xs font-bold text-[#d97757] uppercase tracking-wider mb-1">
          <span>Step 3 of 4</span>
          <span>·</span>
          <span>OCR, MRZ & Document Intelligence</span>
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-[#2B2622]">Extraction Review</h1>
        <p className="text-sm text-[#55433d] mt-1">
          AI-extracted identity fields and Machine Readable Zone integrity report.
        </p>
      </div>

      {/* Main 3-column bento grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 flex-1">

        {/* ── LEFT COLUMN: Passport scan + cropped ID photo ─────────────────── */}
        <div className="lg:col-span-3 flex flex-col gap-4">
          {/* Full passport scan */}
          <div className="bg-[#FAF8F5] rounded-2xl p-4 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)] flex flex-col gap-3">
            <h2 className="text-sm font-bold text-[#2B2622] flex items-center gap-2">
              <span className="material-symbols-outlined text-[#655d54] text-base">document_scanner</span>
              <span>Document Scan</span>
            </h2>
            <div className="rounded-xl overflow-hidden border border-[#E8E2D9] aspect-[4/3] bg-[#f6f3ee] flex items-center justify-center">
              {documentImage ? (
                <img
                  alt="Scanned Passport"
                  className="w-full h-full object-contain"
                  src={documentImage}
                />
              ) : (
                <div className="text-center text-[#88726c] p-4">
                  <span className="material-symbols-outlined text-3xl">image</span>
                  <p className="text-xs mt-1">No scan loaded</p>
                </div>
              )}
            </div>
          </div>

          {/* Cropped ID photo from passport */}
          <div className="bg-[#FAF8F5] rounded-2xl p-4 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)] flex flex-col gap-3">
            <h2 className="text-sm font-bold text-[#2B2622] flex items-center gap-2">
              <span className="material-symbols-outlined text-[#655d54] text-base">face</span>
              <span>Holder Photo</span>
              <span className="ml-auto text-[10px] font-bold bg-[#ede0d5] text-[#655d54] px-2 py-0.5 rounded-full">
                {faceCropUrl ? "AI Extracted" : "From Scan"}
              </span>
            </h2>
            <div className="rounded-xl overflow-hidden border-2 border-[#d97757]/30 bg-[#f6f3ee] flex items-center justify-center" style={{ minHeight: "180px" }}>
              {faceCropUrl || documentImage ? (
                <img
                  alt="Passport Holder Photo"
                  className="w-full h-full object-cover"
                  style={{ maxHeight: "220px", objectPosition: "top center" }}
                  src={faceCropUrl || documentImage!}
                />
              ) : (
                <div className="text-center text-[#88726c] p-4">
                  <span className="material-symbols-outlined text-3xl animate-pulse">person_search</span>
                  <p className="text-xs mt-1">Extracting face...</p>
                </div>
              )}
            </div>
            {faceCropUrl && (
              <div className="flex items-center gap-1.5 text-[10px] font-bold text-[#2F8F5B]">
                <span className="material-symbols-outlined !text-[13px]">check_circle</span>
                <span>MTCNN / RetinaFace detected</span>
              </div>
            )}
          </div>
        </div>

        {/* ── CENTER COLUMN: Extracted fields ───────────────────────────────── */}
        <div className="lg:col-span-5 flex flex-col">
          <div className="bg-[#FAF8F5] rounded-2xl p-5 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)] h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-base font-bold text-[#2B2622] flex items-center gap-2">
                <span className="material-symbols-outlined text-[#655d54] text-lg">data_object</span>
                <span>Extracted Identity Fields</span>
              </h2>
              <span className="text-[11px] font-bold text-[#655d54] bg-[#ede0d5] px-2.5 py-1 rounded-full">
                {fields.length} fields
              </span>
            </div>

            {fields.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-[#88726c] bg-[#f6f3ee] rounded-xl border border-dashed border-[#E8E2D9] p-8 text-center">
                <span className="material-symbols-outlined text-4xl mb-2">document_scanner</span>
                <p className="text-sm font-semibold">No fields extracted yet</p>
                <p className="text-xs mt-1">Upload a document to begin extraction.</p>
              </div>
            ) : (
              <div className="space-y-2.5 overflow-y-auto flex-1 pr-1">
                {fields.map((f) => (
                  <div
                    key={f.key}
                    className={`p-3 rounded-xl border relative overflow-hidden transition-all ${
                      f.isLowConfidence
                        ? "bg-[#FBF0D6]/50 border-[#B8860B]/40"
                        : "bg-white border-[#E8E2D9] hover:border-[#d97757]/40"
                    }`}
                  >
                    {f.isLowConfidence && (
                      <div className="absolute left-0 top-0 h-full w-1 bg-[#B8860B]" />
                    )}

                    <div className="flex justify-between items-center mb-0.5 pl-0.5">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 ${
                          f.isLowConfidence ? "text-[#B8860B]" : "text-[#655d54]"
                        }`}
                      >
                        {f.isLowConfidence && (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#B8860B] inline-block animate-pulse" />
                        )}
                        {f.label}
                        {f.method === "mrz" && (
                          <span className="ml-1 px-1.5 py-0.5 bg-[#d97757]/10 text-[#d97757] rounded text-[9px] font-bold">MRZ</span>
                        )}
                        {f.method === "llm_fallback" && (
                          <span className="ml-1 px-1.5 py-0.5 bg-purple-100 text-purple-600 rounded text-[9px] font-bold">AI</span>
                        )}
                      </span>
                      {f.confidence !== null && (
                        <span
                          className={`text-[10px] font-bold ${
                            f.isLowConfidence ? "text-[#B8860B]" : "text-[#2F8F5B]"
                          }`}
                        >
                          {f.confidence}%
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 pl-0.5">
                      {editingKey === f.key ? (
                        <input
                          type="text"
                          value={f.value}
                          onChange={(e) => handleFieldChange(f.key, e.target.value)}
                          onBlur={() => setEditingKey(null)}
                          autoFocus
                          className="flex-1 px-2 py-1 bg-white border border-[#d97757] rounded-lg text-sm font-semibold outline-none"
                        />
                      ) : (
                        <span className="flex-1 text-sm font-bold text-[#2B2622] tracking-wide">
                          {f.value || "—"}
                        </span>
                      )}
                      <button
                        onClick={() => setEditingKey(editingKey === f.key ? null : f.key)}
                        className="p-0.5 hover:bg-[#f6f3ee] rounded text-[#88726c] hover:text-[#2B2622] transition-colors cursor-pointer"
                        title="Edit"
                      >
                        <span className="material-symbols-outlined !text-[13px]">edit</span>
                      </button>
                    </div>

                    {f.confidence !== null && (
                      <div className="w-full h-1 bg-[#f0ede9] rounded-full mt-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            f.isLowConfidence ? "bg-[#B8860B]" : "bg-[#2F8F5B]"
                          }`}
                          style={{ width: `${Math.min(f.confidence, 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT COLUMN: MRZ Report + Verification Gates + Risk ──────────── */}
        <div className="lg:col-span-4 flex flex-col gap-4">

          {/* MRZ Raw Lines */}
          <div className="bg-[#FAF8F5] rounded-2xl p-5 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)]">
            <h2 className="text-sm font-bold text-[#2B2622] mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-[#655d54] text-base">code</span>
              <span>Machine Readable Zone</span>
            </h2>

            {mrzPresent ? (
              <>
                <div className="bg-[#1c1c19] rounded-xl p-3 font-mono text-[9.5px] text-green-400 leading-relaxed overflow-x-auto mb-3">
                  {mrzLine1 && <p className="break-all mb-0.5">{mrzLine1}</p>}
                  {mrzLine2 && <p className="break-all">{mrzLine2}</p>}
                  {!mrzLine1 && !mrzLine2 && (
                    <p className="text-gray-500 italic">MRZ detected — parsing...</p>
                  )}
                </div>

                {/* Checksum fields */}
                <div className="space-y-1.5">
                  {(["doc_number", "date_of_birth", "expiry_date"] as string[]).map((field) => {
                    const failed = checksumFailures.includes(field);
                    const label =
                      field === "doc_number" ? "Doc Number" :
                      field === "date_of_birth" ? "Date of Birth" :
                      "Expiry Date";
                    return (
                      <div
                        key={field}
                        className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-bold ${
                          failed
                            ? "bg-[#FBE7D8] text-[#C1652E]"
                            : mrzChecksumValid === null
                            ? "bg-[#f6f3ee] text-[#655d54]"
                            : "bg-[#E5F3EA] text-[#2F8F5B]"
                        }`}
                      >
                        <span className="flex items-center gap-1.5">
                          <span className="material-symbols-outlined !text-[14px]">
                            {failed ? "error" : mrzChecksumValid === null ? "help" : "check_circle"}
                          </span>
                          {label}
                        </span>
                        <span>{failed ? "FAIL" : mrzChecksumValid === null ? "—" : "OK"}</span>
                      </div>
                    );
                  })}
                </div>

                {/* Overall MRZ verdict */}
                <div
                  className={`mt-3 rounded-xl p-3 flex items-center gap-3 border text-xs font-bold ${
                    mrzChecksumValid === true
                      ? "bg-[#E5F3EA] border-[#2F8F5B]/30 text-[#2F8F5B]"
                      : mrzChecksumValid === false
                      ? "bg-[#FBE7D8] border-[#C1652E]/30 text-[#C1652E]"
                      : "bg-[#f6f3ee] border-[#E8E2D9] text-[#655d54]"
                  }`}
                >
                  <span className="material-symbols-outlined icon-fill !text-[20px]">
                    {mrzChecksumValid === true ? "verified_user" : mrzChecksumValid === false ? "gpp_bad" : "pending"}
                  </span>
                  <div>
                    <span className="block">
                      {mrzChecksumValid === true
                        ? "ICAO 9303 Checksums Verified"
                        : mrzChecksumValid === false
                        ? "Checksum Integrity Failure"
                        : "Awaiting MRZ validation"}
                    </span>
                    {mrzChecksumValid === false && checksumFailures.length > 0 && (
                      <span className="block text-[10px] opacity-80 mt-0.5">
                        Failed fields: {checksumFailures.join(", ")}
                      </span>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-6 text-[#88726c]">
                <span className="material-symbols-outlined text-3xl">crop_free</span>
                <p className="text-xs mt-1 font-semibold">
                  {pipelineData ? "No MRZ zone detected in document" : "Upload a document to scan MRZ"}
                </p>
              </div>
            )}
          </div>

          {/* Verification Gates */}
          <div className="bg-[#FAF8F5] rounded-2xl p-5 border border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)]">
            <h2 className="text-sm font-bold text-[#2B2622] mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-[#655d54] text-base">shield</span>
              <span>Security Gates</span>
            </h2>
            <div className="space-y-2">
              {[
                {
                  label: "OCR Extraction",
                  pass: fields.length > 0,
                  detail: fields.length > 0 ? `${fields.length} fields extracted` : "Pending",
                },
                {
                  label: "MRZ Integrity",
                  pass: mrzPresent && mrzChecksumValid === true,
                  detail: !mrzPresent ? "No MRZ detected" : mrzChecksumValid === true ? "Checksums valid" : "Checksum failure",
                },
                {
                  label: "Tampering Check",
                  pass: !tamperingFlagged,
                  detail: tamperingFlagged ? "Anomalies detected" : "Substrate intact",
                },
                {
                  label: "Business Rules",
                  pass: validationPassed,
                  detail: validationPassed ? "All rules passed" : "Rule violations found",
                },
              ].map((gate) => (
                <div
                  key={gate.label}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs ${
                    gate.pass
                      ? "bg-[#E5F3EA]/60 border-[#2F8F5B]/20 text-[#2F8F5B]"
                      : pipelineData
                      ? "bg-[#FBE7D8]/60 border-[#C1652E]/20 text-[#C1652E]"
                      : "bg-[#f6f3ee] border-[#E8E2D9] text-[#88726c]"
                  }`}
                >
                  <div className="flex items-center gap-2 font-bold">
                    <span className="material-symbols-outlined !text-[15px]">
                      {gate.pass ? "check_circle" : pipelineData ? "error" : "pending"}
                    </span>
                    {gate.label}
                  </div>
                  <span className="font-semibold text-[10px]">{gate.detail}</span>
                </div>
              ))}
            </div>

            {/* Risk score summary */}
            {riskScore !== null && (
              <div
                className={`mt-3 flex items-center gap-3 px-3 py-3 rounded-xl border text-xs font-bold ${riskBandColor.bg} ${riskBandColor.text} ${riskBandColor.border}`}
              >
                <span className={`w-3 h-3 rounded-full flex-shrink-0 ${riskBandColor.dot}`} />
                <div>
                  <span className="block">Risk Score: {riskScore}/100 — {riskBand || "COMPUTING"}</span>
                  {pipelineData?.risk_score?.reasons?.[0] && (
                    <span className="block text-[10px] opacity-80 mt-0.5 font-medium">
                      {pipelineData.risk_score.reasons[0]}
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Bottom Action Bar ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap justify-between items-center pt-5 border-t border-[#E8E2D9] gap-4">
        <button
          onClick={onFlagForReview}
          className="px-5 py-3 rounded-xl border border-[#E8E2D9] text-[#55433d] hover:bg-[#FBE7D8]/50 hover:border-[#C1652E]/30 hover:text-[#C1652E] font-bold text-xs flex items-center gap-2 transition-all cursor-pointer"
        >
          <span className="material-symbols-outlined text-base">flag</span>
          <span>Flag for Secondary Review</span>
        </button>

        <button
          onClick={onContinueToFace}
          disabled={!pipelineData}
          className={`font-bold text-sm px-8 py-4 rounded-xl flex items-center gap-3 transition-all duration-300 cursor-pointer active:scale-95 ${
            canProceedToFace || !pipelineData
              ? "bg-[#d97757] text-white shadow-[0px_8px_24px_rgba(217,119,87,0.25)] hover:scale-[1.03]"
              : "bg-[#B8860B] text-white shadow-[0px_8px_24px_rgba(184,134,11,0.20)] hover:scale-[1.02]"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <span className="material-symbols-outlined !text-xl">
            {canProceedToFace ? "face_retouching_natural" : "warning"}
          </span>
          <span>
            {!pipelineData
              ? "Awaiting scan..."
              : canProceedToFace
              ? "Proceed to Face Verification"
              : "Proceed (Flagged — Review Required)"}
          </span>
          <span className="material-symbols-outlined !text-xl">arrow_forward</span>
        </button>
      </div>
    </div>
  );
};
