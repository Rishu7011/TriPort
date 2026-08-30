"use client";

import React, { useEffect, useRef, useState } from "react";

interface Step2ScanningProps {
  onComplete: () => void;
  documentImage?: string | null;
  pipelineReady?: boolean; // true when backend response arrived
}

export const Step2Scanning: React.FC<Step2ScanningProps> = ({
  onComplete,
  documentImage,
  pipelineReady = false,
}) => {
  const [activeStep, setActiveStep] = useState<number>(1);
  const [canAdvance, setCanAdvance] = useState<boolean>(false);
  const completedRef = useRef(false);

  // Animate through steps regardless of backend, but only advance when both
  // the minimum animation time has passed AND pipelineReady is true
  useEffect(() => {
    const t1 = setTimeout(() => setActiveStep(2), 700);
    const t2 = setTimeout(() => setActiveStep(3), 2000);
    const t3 = setTimeout(() => setActiveStep(4), 3300);
    const t4 = setTimeout(() => setCanAdvance(true), 4000); // min display time

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, []);

  // Advance when both conditions are met
  useEffect(() => {
    if (canAdvance && pipelineReady && !completedRef.current) {
      completedRef.current = true;
      onComplete();
    }
  }, [canAdvance, pipelineReady, onComplete]);

  const steps = [
    { label: "Reading document structure & layout", detail: null },
    { label: "Detecting & parsing MRZ lines with ICAO 9303 checksums", detail: activeStep === 2 },
    { label: "Physical tampering forensics & UV substrate analysis", detail: activeStep === 3 },
    { label: "Biometric face extraction & watchlist screening", detail: activeStep >= 4 },
  ];

  return (
    <div className="flex-grow flex items-center justify-center p-6 max-w-[1440px] mx-auto w-full py-12">
      <div className="w-full max-w-5xl bg-[#FAF8F5] shadow-[0px_12px_32px_rgba(43,38,34,0.08)] rounded-[28px] p-8 md:p-12 flex flex-col md:flex-row gap-10 relative overflow-hidden border border-[#E8E2D9]">

        {/* Background accent */}
        <div className="absolute top-0 right-0 w-72 h-72 bg-[#d97757]/5 rounded-bl-full pointer-events-none" />

        {/* Left: Document with scanner laser */}
        <div className="flex-1 flex flex-col items-center justify-center relative">
          <div className="relative rounded-2xl overflow-hidden shadow-[0px_4px_20px_rgba(43,38,34,0.06)] bg-[#f6f3ee] p-2.5 border border-[#E8E2D9] max-w-md w-full">
            <div className="relative rounded-xl overflow-hidden aspect-[4/3] bg-[#f0ede9] flex items-center justify-center">
              {documentImage ? (
                <img
                  alt="Scanned Document"
                  className="w-full h-full object-contain rounded-lg relative z-10"
                  src={documentImage}
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-[#88726c]">
                  <span className="material-symbols-outlined text-5xl animate-pulse">document_scanner</span>
                </div>
              )}
              {/* Scanning Laser Line */}
              <div className="scanning-line-sweep z-20" />
              {/* Soft Pulse Glow */}
              <div className="absolute inset-0 bg-[#d97757]/10 z-15 animate-pulse mix-blend-overlay pointer-events-none" />
            </div>
          </div>

          <div className="mt-4 text-center">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[#EDE0D5] text-[#6b635a]">
              <span className="w-2 h-2 rounded-full bg-[#006b5f] animate-ping" />
              eMRTD Passport · OCR + MRZ + Biometric
            </span>
          </div>
        </div>

        {/* Right: Progress checklist */}
        <div className="flex-1 flex flex-col justify-center">
          <div className="mb-6">
            <span className="text-xs font-bold uppercase tracking-wider text-[#d97757] block mb-1">
              Step 2 of 4 · AI Pipeline Running
            </span>
            <h2 className="text-2xl md:text-3xl font-bold text-[#2B2622]">
              Document Analysis Pipeline
            </h2>
            <p className="text-sm text-[#55433d] mt-1">
              {pipelineReady
                ? "Pipeline complete — loading results..."
                : "Processing document through AI modules..."}
            </p>
          </div>

          <div className="space-y-3.5">
            {steps.map((step, idx) => {
              const stepNum = idx + 1;
              const isDone = activeStep > stepNum;
              const isActive = activeStep === stepNum;
              return (
                <div key={idx} className="flex items-center gap-3">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 transition-all ${
                      isDone
                        ? "bg-[#E5F3EA] text-[#2F8F5B]"
                        : isActive
                        ? "bg-[#d97757] text-white"
                        : "bg-[#e5e2dd] text-[#655d54]"
                    }`}
                  >
                    {isDone ? (
                      <span className="material-symbols-outlined !text-[16px]">check</span>
                    ) : isActive ? (
                      <span className="material-symbols-outlined !text-[14px] animate-custom-spin">sync</span>
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-[#88726c]" />
                    )}
                  </div>

                  <div
                    className={`flex-1 rounded-xl p-3.5 border transition-all ${
                      isActive
                        ? "bg-white border-[#d97757] shadow-sm ring-1 ring-[#d97757]/20"
                        : isDone
                        ? "bg-white border-[#E8E2D9]"
                        : "bg-[#f6f3ee]/60 border-[#E8E2D9] opacity-60"
                    }`}
                  >
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium text-[#2B2622]">{step.label}</span>
                      <span className={`text-xs font-bold ${isDone ? "text-[#2F8F5B]" : isActive ? "text-[#d97757]" : "text-[#655d54]"}`}>
                        {isDone ? "Done" : isActive ? "Running..." : "Pending"}
                      </span>
                    </div>
                    {isActive && (
                      <div className="w-full bg-[#f0ede9] rounded-full h-1.5 overflow-hidden mt-2">
                        <div className="bg-[#d97757] h-1.5 rounded-full animate-progress" />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Backend status indicator */}
          <div className="mt-6 flex items-center gap-2">
            {pipelineReady ? (
              <span className="flex items-center gap-1.5 text-xs font-bold text-[#2F8F5B]">
                <span className="material-symbols-outlined !text-[15px]">check_circle</span>
                Pipeline complete
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-xs font-semibold text-[#d97757]">
                <span className="w-2 h-2 rounded-full bg-[#d97757] animate-ping" />
                Backend processing...
              </span>
            )}
          </div>

          {/* Skip button (for dev/testing) */}
          <div className="mt-4 flex justify-end">
            <button
              onClick={() => { completedRef.current = true; onComplete(); }}
              className="text-xs font-bold text-[#d97757] hover:text-[#99462a] flex items-center gap-1 transition-colors cursor-pointer"
            >
              <span>Skip to review</span>
              <span className="material-symbols-outlined !text-sm">arrow_forward</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
