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
  Clock,
  ArrowRight,
} from "lucide-react";

interface PipelineStepperProps {
  isLoading: boolean;
  stage?: 1 | 2;
  stage1Complete?: boolean;
  stage2Complete?: boolean;
}

interface StepInfo {
  id: string;
  stage: 1 | 2;
  name: string;
  sub: string;
  icon: React.ElementType;
}

const STAGE1_STEPS: StepInfo[] = [
  {
    id: "ocr",
    stage: 1,
    name: "OCR & MRZ Extraction",
    sub: "EasyOCR & Checksum Validation",
    icon: FileSearch,
  },
  {
    id: "tampering",
    stage: 1,
    name: "Forensic Tampering",
    sub: "5-Layer ELA & Splicing Detection",
    icon: Sparkles,
  },
  {
    id: "validation",
    stage: 1,
    name: "Integrity & Watchlists",
    sub: "YAML Rules & Interpol Checks",
    icon: CheckSquare,
  },
];

const STAGE2_STEPS: StepInfo[] = [
  {
    id: "face",
    stage: 2,
    name: "Biometric Facial Match",
    sub: "AWS Rekognition / ArcFace 1:1",
    icon: UserCheck,
  },
  {
    id: "risk",
    stage: 2,
    name: "Risk Scoring & Ledger",
    sub: "SHA-256 Chained Event Commit",
    icon: ShieldCheck,
  },
];

export function PipelineStepper({
  isLoading,
  stage = 1,
  stage1Complete = false,
  stage2Complete = false,
}: PipelineStepperProps) {
  const [activeStepIndex, setActiveStepIndex] = useState(isLoading ? 0 : 3);
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!isLoading) {
      const finishTimer = setTimeout(() => {
        setActiveStepIndex(3);
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

    const step1 = setTimeout(() => setActiveStepIndex(1), 600);
    const step2 = setTimeout(() => setActiveStepIndex(2), 1600);
    const step3 = setTimeout(() => setActiveStepIndex(3), 2800);

    return () => {
      clearTimeout(resetTimer);
      clearInterval(timerInterval);
      clearTimeout(step1);
      clearTimeout(step2);
      clearTimeout(step3);
    };
  }, [isLoading]);

  return (
    <div className="w-full bg-surface border border-border rounded-md p-6 sm:p-8 space-y-6">
      {/* Header Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isLoading ? "bg-brand animate-pulse" : "bg-brand"
              }`}
            />
            <h2 className="font-display font-bold text-base sm:text-lg text-text uppercase tracking-tight">
              {stage === 1 && isLoading
                ? "Stage 1: Document Screening In Flight"
                : stage === 2 && isLoading
                ? "Stage 2: Biometric Verification In Flight"
                : "TriPort Two-Stage Verification Pipeline"}
            </h2>
          </div>
          <p className="font-mono text-xs text-text-muted mt-1">
            Separated execution: Fast document forensics (~5-8s) ➔ Gated biometric matching
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isLoading ? (
            <div className="bg-surface-raised border border-border px-3 py-1.5 rounded font-mono text-xs text-brand flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-brand" />
              <span>{(elapsedMs / 1000).toFixed(2)}s elapsed</span>
            </div>
          ) : (
            <div className="bg-surface-raised border border-border px-3 py-1.5 rounded font-mono text-xs text-text-muted flex items-center gap-1.5">
              <Clock size={13} className="text-brand" />
              <span>Stage 1 SLA: ~5-8s</span>
            </div>
          )}
        </div>
      </div>

      {/* Two-Stage Blocks Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Stage 1 Container */}
        <div
          className={`p-4 rounded-md border transition-all ${
            stage === 1 && isLoading
              ? "bg-surface-raised border-brand/60 shadow-[0_0_15px_rgba(166,255,77,0.1)]"
              : stage1Complete || (!isLoading && stage === 1)
              ? "bg-surface border-brand/40"
              : "bg-surface border-border"
          }`}
        >
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-border/80">
            <span className="font-mono text-xs uppercase font-bold text-brand flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-brand" />
              <span>Stage 1: Document Screening</span>
            </span>
            <span className="font-mono text-[10px] text-text-muted">
              {isLoading && stage === 1 ? (
                <span className="text-brand animate-pulse font-bold">● PROCESSING</span>
              ) : (
                <span className="text-brand font-semibold">READY / COMPLETED</span>
              )}
            </span>
          </div>

          <div className="space-y-3">
            {STAGE1_STEPS.map((step, idx) => {
              const Icon = step.icon;
              const isDone = (!isLoading && stage === 1) || stage1Complete || (isLoading && idx < activeStepIndex);
              const isRunning = isLoading && stage === 1 && idx === activeStepIndex;

              return (
                <div
                  key={step.id}
                  className="flex items-center gap-3 p-2 rounded bg-surface-raised/60 border border-border/60"
                >
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 border ${
                      isDone
                        ? "bg-brand border-brand text-bg"
                        : isRunning
                        ? "bg-brand/20 border-brand text-brand animate-pulse"
                        : "bg-surface border-border text-text-muted/60"
                    }`}
                  >
                    {isDone ? (
                      <Check size={14} strokeWidth={2.5} />
                    ) : isRunning ? (
                      <Loader2 size={14} className="animate-spin text-brand" />
                    ) : (
                      <Icon size={13} />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-display text-xs font-bold uppercase text-text truncate">
                      {step.name}
                    </div>
                    <div className="font-mono text-[10px] text-text-muted truncate">
                      {step.sub}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Stage 2 Container */}
        <div
          className={`p-4 rounded-md border transition-all ${
            stage === 2 && isLoading
              ? "bg-surface-raised border-brand/60 shadow-[0_0_15px_rgba(166,255,77,0.1)]"
              : stage2Complete
              ? "bg-surface border-brand/40"
              : "bg-surface/50 border-border/60 opacity-80"
          }`}
        >
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-border/80">
            <span className="font-mono text-xs uppercase font-bold text-text-muted flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  stage2Complete ? "bg-brand" : "bg-text-muted/50"
                }`}
              />
              <span>Stage 2: Biometrics & Decision</span>
            </span>
            <span className="font-mono text-[10px] text-text-muted">
              {isLoading && stage === 2 ? (
                <span className="text-brand animate-pulse font-bold">● MATCHING</span>
              ) : stage2Complete ? (
                <span className="text-brand font-semibold">VERIFIED</span>
              ) : (
                <span>PENDING OFFICER ACTION</span>
              )}
            </span>
          </div>

          <div className="space-y-3">
            {STAGE2_STEPS.map((step) => {
              const Icon = step.icon;
              const isDone = stage2Complete;
              const isRunning = isLoading && stage === 2;

              return (
                <div
                  key={step.id}
                  className="flex items-center gap-3 p-2 rounded bg-surface-raised/40 border border-border/40"
                >
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 border ${
                      isDone
                        ? "bg-brand border-brand text-bg"
                        : isRunning
                        ? "bg-brand/20 border-brand text-brand animate-pulse"
                        : "bg-surface border-border text-text-muted/40"
                    }`}
                  >
                    {isDone ? (
                      <Check size={14} strokeWidth={2.5} />
                    ) : isRunning ? (
                      <Loader2 size={14} className="animate-spin text-brand" />
                    ) : (
                      <Icon size={13} />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-display text-xs font-bold uppercase text-text/90 truncate">
                      {step.name}
                    </div>
                    <div className="font-mono text-[10px] text-text-muted truncate">
                      {step.sub}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Dynamic Status Log Terminal */}
      <div className="bg-bg border border-border rounded p-3 font-mono text-[11px] text-text-muted space-y-1 overflow-hidden">
        <div className="flex items-center justify-between text-text border-b border-border pb-1 mb-1">
          <span className="uppercase text-brand font-semibold">
            {isLoading ? "Stage 1 Forensics In Flight" : "Screening Ready"}
          </span>
          <span className="text-text-muted">Target SLA: ~5-8s</span>
        </div>
        <div className="text-brand">
          &gt; [0.00s] Ingesting document scan image...
        </div>
        {activeStepIndex >= 1 && (
          <div>&gt; [0.60s] EasyOCR & MRZ checksum validation active</div>
        )}
        {activeStepIndex >= 2 && (
          <div>&gt; [1.60s] 5-Layer Forensic ELA & Splicing Detection executing</div>
        )}
        {activeStepIndex >= 3 && (
          <div>&gt; [2.80s] YAML rules verified • Face crop extracted for Stage 2 review</div>
        )}
        {!isLoading && (
          <div className="text-brand font-bold flex items-center gap-1">
            <ArrowRight size={13} />
            <span>Stage 1 complete. Proceed to Biometric Verification to capture live traveler photo.</span>
          </div>
        )}
      </div>
    </div>
  );
}

