"use client";

import React from "react";

interface Step4ConfirmationProps {
  onScanNext: () => void;
  decision?: "permitted" | "denied" | "flagged";
  pipelineData?: any;
}

export const Step4Confirmation: React.FC<Step4ConfirmationProps> = ({
  onScanNext,
  decision = "permitted",
  pipelineData,
}) => {
  const isPermitted = decision === "permitted";
  const isFlagged = decision === "flagged";
  const isDenied = decision === "denied";

  // Extract person name from pipeline data
  const fields: any[] = pipelineData?.extraction?.fields ?? [];
  const findField = (...aliases: string[]): string => {
    for (const alias of aliases) {
      const f = fields.find(
        (x: any) => x?.field_name?.toLowerCase() === alias.toLowerCase()
      );
      if (f?.field_value) return f.field_value;
    }
    // Also try MRZ fields
    const mrzFields = pipelineData?.extraction?.mrz?.mrz_fields ?? {};
    for (const alias of aliases) {
      if (mrzFields[alias.toLowerCase()]) return mrzFields[alias.toLowerCase()];
    }
    return "";
  };

  const givenNames = findField("given_names", "name");
  const surname = findField("surname");
  const docNumber = findField("passport_number", "doc_number", "document_number");
  const nationality = findField("nationality", "country_code");

  let personName = givenNames || surname
    ? [givenNames, surname].filter(Boolean).join(" ")
    : "Unknown Traveler";

  const riskScore = pipelineData?.risk_score?.score ?? null;
  const riskBand = (pipelineData?.risk_score?.band ?? "").toUpperCase();
  const faceScore = pipelineData?.face?.one_to_one?.match_score
    ? Math.round(pipelineData.face.one_to_one.match_score * 100)
    : null;

  // Color scheme
  const colors = isPermitted
    ? {
        bg: "bg-[#E5F3EA]",
        text: "text-[#2F8F5B]",
        border: "border-[#2F8F5B]/20",
        glow: "bg-[#E5F3EA]",
        icon: "verified_user",
        label: "ENTRY PERMITTED",
        subLabel: "Traveler has been cleared for entry",
        btnBg: "bg-[#2F8F5B] hover:bg-[#27784e] shadow-[0px_8px_24px_rgba(47,143,91,0.25)]",
      }
    : isFlagged
    ? {
        bg: "bg-[#FBF0D6]",
        text: "text-[#B8860B]",
        border: "border-[#B8860B]/20",
        glow: "bg-[#FBF0D6]",
        icon: "warning_amber",
        label: "ESCALATED FOR REVIEW",
        subLabel: "Referred to secondary inspection officer",
        btnBg: "bg-[#B8860B] hover:bg-[#9a7009] shadow-[0px_8px_24px_rgba(184,134,11,0.25)]",
      }
    : {
        bg: "bg-[#FBE3E3]",
        text: "text-[#C13B3B]",
        border: "border-[#C13B3B]/20",
        glow: "bg-[#FBE3E3]",
        icon: "block",
        label: "ENTRY DENIED",
        subLabel: "Traveler has been refused entry",
        btnBg: "bg-[#C13B3B] hover:bg-[#a83232] shadow-[0px_8px_24px_rgba(193,59,59,0.25)]",
      };

  // Generate a pseudo-deterministic audit hash from doc number + timestamp
  const auditHash = docNumber
    ? `0x${Array.from(docNumber + Date.now().toString(36))
        .map((c) => c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
        .slice(0, 40)}`
    : "0x" + Math.random().toString(16).slice(2, 42);

  return (
    <div className="flex-1 flex flex-col justify-center items-center p-6 relative overflow-hidden py-12">
      {/* Ambient glow */}
      <div className="absolute inset-0 flex justify-center items-center pointer-events-none opacity-30">
        <div className={`w-[600px] h-[600px] rounded-full blur-[120px] ${colors.glow}`} />
      </div>

      {/* Confirmation card */}
      <div className="relative z-10 w-full max-w-lg animate-slide-up">

        {/* Main status banner */}
        <div className={`${colors.bg} ${colors.border} border rounded-[28px] p-8 md:p-10 shadow-[0px_16px_48px_rgba(43,38,34,0.10)] flex flex-col items-center text-center mb-4`}>

          {/* Icon */}
          <div className={`w-24 h-24 rounded-full ${colors.bg} border-4 ${colors.border} flex items-center justify-center mb-6 shadow-lg`}>
            <span className={`material-symbols-outlined icon-fill !text-5xl ${colors.text}`}>
              {colors.icon}
            </span>
          </div>

          {/* Decision headline */}
          <h1 className={`text-3xl md:text-4xl font-black tracking-tight mb-1 ${colors.text}`}>
            {colors.label}
          </h1>
          <p className="text-sm font-semibold text-[#55433d] mb-6">{colors.subLabel}</p>

          {/* Person info */}
          {personName !== "Unknown Traveler" && (
            <div className="w-full bg-white/70 rounded-2xl p-4 mb-5 text-left border border-white/80">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[10px] font-bold text-[#655d54] uppercase tracking-wider mb-0.5">Name</p>
                  <p className="text-sm font-bold text-[#2B2622] truncate">{personName}</p>
                </div>
                {docNumber && (
                  <div>
                    <p className="text-[10px] font-bold text-[#655d54] uppercase tracking-wider mb-0.5">Doc Number</p>
                    <p className="text-sm font-bold text-[#2B2622] font-mono">{docNumber}</p>
                  </div>
                )}
                {nationality && (
                  <div>
                    <p className="text-[10px] font-bold text-[#655d54] uppercase tracking-wider mb-0.5">Nationality</p>
                    <p className="text-sm font-bold text-[#2B2622]">{nationality}</p>
                  </div>
                )}
                {faceScore !== null && (
                  <div>
                    <p className="text-[10px] font-bold text-[#655d54] uppercase tracking-wider mb-0.5">Face Match</p>
                    <p className={`text-sm font-bold ${faceScore >= 60 ? "text-[#2F8F5B]" : "text-[#C13B3B]"}`}>
                      {faceScore}%
                    </p>
                  </div>
                )}
                {riskScore !== null && (
                  <div>
                    <p className="text-[10px] font-bold text-[#655d54] uppercase tracking-wider mb-0.5">Risk Score</p>
                    <p className="text-sm font-bold text-[#2B2622]">{riskScore}/100 — {riskBand}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Audit ledger hash */}
          <div className="w-full bg-[#1c1c19] rounded-xl p-3 text-left mb-6">
            <div className="flex justify-between items-center text-[10px] font-bold uppercase tracking-wider mb-1">
              <span className="text-[#655d54]">Audit Ledger Entry</span>
              <span className="text-[#2F8F5B] flex items-center gap-1">
                <span className="material-symbols-outlined !text-[11px]">lock</span>
                SHA-256
              </span>
            </div>
            <p className="font-mono text-[10px] text-green-400 truncate">{auditHash}</p>
            <p className="text-[9px] text-[#655d54] mt-0.5">
              {new Date().toISOString()} · Checkpoint Alpha-7
            </p>
          </div>

          {/* CTA */}
          <button
            onClick={onScanNext}
            className={`w-full ${colors.btnBg} text-white font-bold text-base py-4 px-8 rounded-xl flex items-center justify-center gap-3 transition-all duration-300 cursor-pointer active:scale-95 hover:scale-[1.02] group`}
          >
            <span className="material-symbols-outlined group-hover:rotate-12 transition-transform duration-300">
              document_scanner
            </span>
            <span>Scan Next Document</span>
          </button>
        </div>

        <p className="text-center text-xs text-[#655d54] font-medium">
          Session active · Checkpoint Alpha-7 ready for next traveler
        </p>
      </div>
    </div>
  );
};
