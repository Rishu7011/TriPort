"use client";

import React, { useEffect, useState } from "react";
import {
  FileSearch,
  CheckSquare,
  Sparkles,
  UserCheck,
  ShieldCheck,
  Check,
  Loader2,
} from "lucide-react";

interface PipelineStepperProps {
  isLoading: boolean;
}

interface StepInfo {
  id: string;
  name: string;
  sub: string;
  icon: React.ElementType;
}

const STEPS: StepInfo[] = [
  {
    id: "ocr",
    name: "OCR Extraction",
    sub: "ICAO 9303 MRZ Parsing",
    icon: FileSearch,
  },
  {
    id: "validation",
    name: "Validation Rules",
    sub: "Checksums & Expiry Check",
    icon: CheckSquare,
  },
  {
    id: "tampering",
    name: "Forensic Tampering",
    sub: "ELA & Copy-Move Analysis",
    icon: Sparkles,
  },
  {
    id: "face",
    name: "Biometric Face Match",
    sub: "ArcFace & Cluster Dedup",
    icon: UserCheck,
  },
  {
    id: "risk",
    name: "Risk Engine",
    sub: "Score & Ledger Chaining",
    icon: ShieldCheck,
  },
];

export function PipelineStepper({ isLoading }: PipelineStepperProps) {
  const [activeStepIndex, setActiveStepIndex] = useState(isLoading ? 0 : STEPS.length);
  const [elapsedMs, setElapsedMs] = useState(0);

  // Staged client-side progression while the upload request is in flight
  useEffect(() => {
    if (!isLoading) {
      const finishTimer = setTimeout(() => {
        setActiveStepIndex(STEPS.length);
      }, 0);
      return () => clearTimeout(finishTimer);
    }

    const resetTimer = setTimeout(() => {
      setActiveStepIndex(0);
      setElapsedMs(0);
    }, 0);

    const startTime = Date.now();
    const timerInterval = setInterval(() => {
      setElapsedMs(Date.now() - startTime);
    }, 50);

    // Progression cadence across ~3-4 seconds while request is in flight
    const step1 = setTimeout(() => setActiveStepIndex(1), 600);
    const step2 = setTimeout(() => setActiveStepIndex(2), 1400);
    const step3 = setTimeout(() => setActiveStepIndex(3), 2200);
    const step4 = setTimeout(() => setActiveStepIndex(4), 3000);

    return () => {
      clearTimeout(resetTimer);
      clearInterval(timerInterval);
      clearTimeout(step1);
      clearTimeout(step2);
      clearTimeout(step3);
      clearTimeout(step4);
    };
  }, [isLoading]);

  return (
    <div className="w-full bg-surface border border-border rounded-md p-6 sm:p-8">
      {/* Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 pb-4 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-brand animate-pulse" />
            <h2 className="font-display font-bold text-base sm:text-lg text-text uppercase tracking-tight">
              Sequential Screening Pipeline Execution
            </h2>
          </div>
          <p className="font-mono text-xs text-text-muted mt-1">
            Running 5 forensic AI modules concurrently & writing to SHA-256 Ledger
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="bg-surface-raised border border-border px-3 py-1.5 rounded font-mono text-xs text-brand flex items-center gap-2">
            <Loader2 size={14} className="animate-spin text-brand" />
            <span>{(elapsedMs / 1000).toFixed(2)}s elapsed</span>
          </div>
        </div>
      </div>

      {/* Stepper Graphic */}
      <div className="relative py-4">
        {/* Background Connecting Line */}
        <div className="absolute top-9 left-6 right-6 h-[2px] bg-border -translate-y-1/2 z-0">
          {isLoading && (
            <div
              className="h-full bg-brand animate-stepper-progress"
              style={{
                width: `${Math.min(
                  100,
                  ((activeStepIndex + 0.5) / STEPS.length) * 100
                )}%`,
                transition: "width 0.4s ease-out",
              }}
            />
          )}
        </div>

        {/* Steps Grid */}
        <div className="grid grid-cols-5 gap-2 relative z-10">
          {STEPS.map((step, idx) => {
            const Icon = step.icon;
            const isCompleted = idx < activeStepIndex || !isLoading;
            const isCurrent = idx === activeStepIndex && isLoading;

            return (
              <div
                key={step.id}
                className="flex flex-col items-center text-center group"
              >
                {/* Step Circle */}
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 border-2 ${
                    isCompleted
                      ? "bg-brand border-brand text-bg shadow-[0_0_10px_rgba(166,255,77,0.3)]"
                      : isCurrent
                      ? "bg-surface-raised border-brand text-brand animate-pulse shadow-[0_0_12px_rgba(166,255,77,0.4)]"
                      : "bg-surface border-border text-text-muted/60"
                  }`}
                >
                  {isCompleted ? (
                    <Check size={18} strokeWidth={2.5} />
                  ) : isCurrent ? (
                    <Loader2 size={18} className="animate-spin text-brand" />
                  ) : (
                    <Icon size={16} strokeWidth={1.5} />
                  )}
                </div>

                {/* Step Label */}
                <div className="mt-3 min-w-0 px-1">
                  <div
                    className={`font-display text-xs font-bold uppercase tracking-tight truncate ${
                      isCompleted || isCurrent ? "text-text" : "text-text-muted/60"
                    }`}
                  >
                    {step.name}
                  </div>
                  <div className="font-mono text-[10px] text-text-muted truncate hidden sm:block mt-0.5">
                    {step.sub}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Dynamic Status Log Terminal */}
      <div className="mt-8 bg-bg border border-border rounded p-3 font-mono text-[11px] text-text-muted space-y-1 overflow-hidden">
        <div className="flex items-center justify-between text-text border-b border-border pb-1 mb-1">
          <span className="uppercase text-brand font-semibold">
            {isLoading ? "Pipeline In Flight" : "Pipeline Completed"}
          </span>
          <span className="text-text-muted">Target SLA: &lt;5.00s</span>
        </div>
        <div className="text-brand">
          &gt; [0.00s] Ingesting document scan bytes...
        </div>
        {activeStepIndex >= 1 && (
          <div>&gt; [0.60s] OCR extracted document numbers & visual zone</div>
        )}
        {activeStepIndex >= 2 && (
          <div>&gt; [1.40s] Evaluated ICAO check digits & validity windows</div>
        )}
        {activeStepIndex >= 3 && (
          <div>&gt; [2.20s] ELA forensic analysis completed (ELA Heatmap computed)</div>
        )}
        {activeStepIndex >= 4 && (
          <div>&gt; [3.00s] Biometric face embeddings matched & deduplicated</div>
        )}
        {!isLoading && (
          <div className="text-brand font-bold">
            &gt; [Complete] Composite risk computed. Result persisted to Postgres.
          </div>
        )}
      </div>
    </div>
  );
}
