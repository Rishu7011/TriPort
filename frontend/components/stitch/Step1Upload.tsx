"use client";

import React, { useRef, useState } from "react";

interface Step1UploadProps {
  onStartScan: (file: File | null, liveFile?: File | null, presetName?: string) => void;
  isLoading: boolean;
  onSelectPreset: (presetName: string) => void;
}

export const Step1Upload: React.FC<Step1UploadProps> = ({
  onStartScan,
  isLoading,
  onSelectPreset,
}) => {
  const [passportFile, setPassportFile] = useState<File | null>(null);
  const [visaFile, setVisaFile] = useState<File | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<"passport" | "visa" | null>(null);
  const passportInputRef = useRef<HTMLInputElement>(null);
  const visaInputRef = useRef<HTMLInputElement>(null);

  const handlePassportChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setPassportFile(e.target.files[0]);
      setSelectedSlot("passport");
    }
  };

  const handleVisaChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setVisaFile(e.target.files[0]);
      setSelectedSlot("visa");
    }
  };

  const canStart = passportFile !== null || visaFile !== null;

  return (
    <div className="flex-grow flex flex-col items-center justify-center px-6 py-12 max-w-[1440px] mx-auto w-full">
      {/* Title */}
      <div className="w-full max-w-4xl animate-slide-up text-center mb-10">
        <h1 className="text-3xl md:text-4xl font-bold text-[#2B2622] mb-3 tracking-tight">
          Step 1: Initiate Screening
        </h1>
        <p className="text-base md:text-lg text-[#55433d] max-w-2xl mx-auto">
          Securely upload traveler credentials to begin the automated risk assessment workflow.
        </p>
      </div>

      {/* Upload Cards Grid */}
      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Hidden inputs */}
        <input
          type="file"
          ref={passportInputRef}
          onChange={handlePassportChange}
          accept="image/*,.pdf"
          className="hidden"
        />
        <input
          type="file"
          ref={visaInputRef}
          onChange={handleVisaChange}
          accept="image/*,.pdf"
          className="hidden"
        />

        {/* Passport Upload Slot */}
        <div
          onClick={() => {
            setSelectedSlot("passport");
            passportInputRef.current?.click();
          }}
          className={`animate-slide-up relative group cursor-pointer transition-all duration-300 rounded-[24px] border-2 border-dashed p-8 flex flex-col items-center justify-center min-h-[320px] shadow-[0px_4px_20px_rgba(43,38,34,0.04)] hover:shadow-[0px_12px_32px_rgba(43,38,34,0.08)] ${
            passportFile || selectedSlot === "passport"
              ? "bg-[#ffffff] border-[#d97757] ring-2 ring-[#d97757]/20"
              : "bg-[#FAF8F5] border-[#dbc1b9] hover:border-[#d97757]"
          }`}
        >
          <div
            className={`w-16 h-16 rounded-full flex items-center justify-center mb-6 group-hover:scale-105 transition-transform duration-300 ${
              passportFile
                ? "bg-[#E5F3EA] text-[#2F8F5B]"
                : "bg-[#ede0d5] text-[#6b635a]"
            }`}
          >
            <span className="material-symbols-outlined text-[34px]">
              {passportFile ? "verified" : "contact_page"}
            </span>
          </div>

          <h3 className="text-xl font-bold text-[#2B2622] mb-2">Passport</h3>
          {passportFile ? (
            <div className="text-center">
              <p className="text-sm font-semibold text-[#2F8F5B] truncate max-w-[260px]">
                ✓ {passportFile.name}
              </p>
              <span className="text-xs text-[#88726c] mt-1 block">
                {(passportFile.size / 1024).toFixed(1)} KB · Ready to scan
              </span>
            </div>
          ) : (
            <p className="text-sm text-[#55433d] text-center">
              Drag &amp; drop or click to upload
              <span className="text-xs text-[#88726c] mt-2 block font-medium">
                MRZ visible · High Resolution
              </span>
            </p>
          )}
        </div>

        {/* Visa Upload Slot */}
        <div
          onClick={() => {
            setSelectedSlot("visa");
            visaInputRef.current?.click();
          }}
          className={`animate-slide-up relative group cursor-pointer transition-all duration-300 rounded-[24px] border-2 border-dashed p-8 flex flex-col items-center justify-center min-h-[320px] shadow-[0px_4px_20px_rgba(43,38,34,0.04)] hover:shadow-[0px_12px_32px_rgba(43,38,34,0.08)] ${
            visaFile || selectedSlot === "visa"
              ? "bg-[#ffffff] border-[#d97757] ring-2 ring-[#d97757]/20"
              : "bg-[#FAF8F5] border-[#dbc1b9] hover:border-[#d97757]"
          }`}
          style={{ animationDelay: "100ms" }}
        >
          <div
            className={`w-16 h-16 rounded-full flex items-center justify-center mb-6 group-hover:scale-105 transition-transform duration-300 ${
              visaFile
                ? "bg-[#E5F3EA] text-[#2F8F5B]"
                : "bg-[#ede0d5] text-[#6b635a]"
            }`}
          >
            <span className="material-symbols-outlined text-[34px]">
              {visaFile ? "verified" : "document_scanner"}
            </span>
          </div>

          <h3 className="text-xl font-bold text-[#2B2622] mb-2">Visa / Permit</h3>
          {visaFile ? (
            <div className="text-center">
              <p className="text-sm font-semibold text-[#2F8F5B] truncate max-w-[260px]">
                ✓ {visaFile.name}
              </p>
              <span className="text-xs text-[#88726c] mt-1 block">
                {(visaFile.size / 1024).toFixed(1)} KB · Ready to scan
              </span>
            </div>
          ) : (
            <p className="text-sm text-[#55433d] text-center">
              Drag &amp; drop or click to upload
              <span className="text-xs text-[#88726c] mt-2 block font-medium">
                Optional · Valid entry docs
              </span>
            </p>
          )}
        </div>
      </div>

      {/* Preset Fast-Eval Scenarios */}
      <div className="w-full max-w-4xl bg-[#FAF8F5] border border-[#E8E2D9] rounded-2xl p-5 mb-8 text-center shadow-[0px_4px_20px_rgba(43,38,34,0.02)]">
        <span className="text-xs font-bold uppercase tracking-wider text-[#655d54] block mb-3">
          Or Quick Test with Certified Dataset Scenarios:
        </span>
        <div className="flex flex-wrap justify-center gap-3">
          <button
            onClick={() => onSelectPreset("genuine")}
            className="px-4 py-2 rounded-full text-xs font-bold bg-[#E5F3EA] text-[#2F8F5B] hover:bg-[#d5edd9] transition-all hover:scale-105"
          >
            ✓ Genuine Passport (Jane Marie)
          </button>
          <button
            onClick={() => onSelectPreset("tampered_mrz")}
            className="px-4 py-2 rounded-full text-xs font-bold bg-[#FBE7D8] text-[#C1652E] hover:bg-[#f6d7c0] transition-all hover:scale-105"
          >
            ⚠ Tampered MRZ (Checksum Mismatch)
          </button>
          <button
            onClick={() => onSelectPreset("tampered_photo")}
            className="px-4 py-2 rounded-full text-xs font-bold bg-[#FBE3E3] text-[#C13B3B] hover:bg-[#f8cfcf] transition-all hover:scale-105"
          >
            ⛔ Photo Splice &amp; Watchlist Match
          </button>
        </div>
      </div>

      {/* Action Button */}
      <div className="w-full flex justify-center">
        <button
          onClick={() => {
            if (passportFile || visaFile) {
              onStartScan(passportFile || visaFile);
            } else {
              onSelectPreset("genuine");
            }
          }}
          disabled={isLoading}
          className="bg-[#d97757] text-white font-bold text-sm px-12 py-4 rounded-full flex items-center gap-3 shadow-[0px_8px_24px_rgba(217,119,87,0.25)] transition-all duration-300 hover:scale-[1.03] hover:shadow-[0px_12px_32px_rgba(217,119,87,0.35)] active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span className="material-symbols-outlined text-xl">qr_code_scanner</span>
          <span>{isLoading ? "Starting Pipeline..." : "Start Scan"}</span>
        </button>
      </div>
    </div>
  );
};
