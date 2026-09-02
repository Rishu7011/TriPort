"use client";

import React, { useRef, useState } from "react";
import {
  UploadCloud,
  Trash2,
  CheckCircle2,
  FileText,
  ShieldCheck,
  Camera,
  ArrowRight,
} from "lucide-react";

interface DocumentUploaderProps {
  docFile: File | null;
  onDocFileChange: (file: File | null) => void;
  livePhoto?: File | null;
  onLivePhotoChange?: (file: File | null) => void;
}

export function DocumentUploader({
  docFile,
  onDocFileChange,
}: DocumentUploaderProps) {
  const docInputRef = useRef<HTMLInputElement>(null);
  const [docDragOver, setDocDragOver] = useState(false);
  const [docPreview, setDocPreview] = useState<string | null>(null);

  const handleDocSelect = (file: File | null) => {
    onDocFileChange(file);
    if (file) {
      const url = URL.createObjectURL(file);
      setDocPreview(url);
    } else {
      setDocPreview(null);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
      {/* 1. Primary Document Dropzone (2 Columns) */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDocDragOver(true);
        }}
        onDragLeave={() => setDocDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDocDragOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) handleDocSelect(file);
        }}
        className={`md:col-span-2 relative bg-surface border-2 border-dashed rounded-md p-8 flex flex-col items-center justify-center min-h-[320px] text-center transition-all cursor-pointer group ${
          docDragOver
            ? "border-brand bg-surface-raised/80 shadow-[0_0_20px_rgba(166,255,77,0.15)]"
            : docFile
            ? "border-brand/60 bg-surface-raised/40"
            : "border-border hover:border-brand/50 hover:bg-surface-raised/30"
        }`}
        onClick={() => docInputRef.current?.click()}
      >
        <input
          ref={docInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,application/pdf"
          className="hidden"
          onChange={(e) => handleDocSelect(e.target.files?.[0] || null)}
        />

        {docPreview ? (
          <div className="relative w-full h-full flex flex-col items-center animate-in fade-in duration-200">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={docPreview}
              alt="Document Scan Preview"
              className="max-h-56 max-w-full object-contain rounded border border-border shadow-md"
            />
            <div className="mt-4 flex items-center gap-2 bg-surface-raised/90 border border-border px-3 py-1.5 rounded-full">
              <CheckCircle2 size={16} className="text-brand" />
              <span className="font-mono text-xs text-text font-bold truncate max-w-[240px]">
                {docFile?.name}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDocSelect(null);
                }}
                className="p-1 text-text-muted hover:text-risk-critical ml-1 transition-colors"
                title="Remove image"
              >
                <Trash2 size={14} />
              </button>
            </div>
            <p className="font-mono text-[11px] text-text-muted mt-2">
              Click or drop to replace document scan
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center p-4">
            <div className="w-16 h-16 rounded-full bg-surface-raised border border-border flex items-center justify-center text-brand mb-4 group-hover:scale-105 transition-transform shadow-xs">
              <UploadCloud size={30} strokeWidth={1.5} />
            </div>
            <div className="font-display font-bold text-base uppercase text-text tracking-tight">
              Ingest Document Scan Image
            </div>
            <p className="font-mono text-xs text-text-muted mt-1.5 max-w-md">
              Drag & drop passport, national ID card, visa, or driving license scan
            </p>
            <div className="mt-5 flex items-center gap-2">
              <span className="px-3.5 py-1.5 bg-surface-raised border border-border rounded font-mono text-[10px] text-brand uppercase tracking-wider font-semibold">
                JPG • PNG • WEBP • PDF (Max 10MB)
              </span>
            </div>
          </div>
        )}
      </div>

      {/* 2. Inspection Workflow Overview Card (1 Column) */}
      <div className="md:col-span-1 bg-surface border border-border rounded-md p-6 flex flex-col justify-between space-y-4">
        <div>
          <div className="flex items-center gap-2 text-brand font-mono text-[11px] uppercase tracking-wider font-bold mb-3">
            <ShieldCheck size={16} />
            <span>Two-Stage Screening Protocol</span>
          </div>

          <div className="space-y-4 mt-2">
            {/* Stage 1 step */}
            <div className="p-3 rounded bg-surface-raised border border-border/80 space-y-1">
              <div className="flex items-center justify-between text-xs font-mono font-bold">
                <span className="text-text flex items-center gap-1.5">
                  <FileText size={14} className="text-brand" />
                  <span>Stage 1: Document Screening</span>
                </span>
                <span className="text-[10px] text-brand bg-brand/10 border border-brand/20 px-1.5 py-0.5 rounded">
                  Immediate
                </span>
              </div>
              <p className="text-[11px] font-mono text-text-muted leading-relaxed">
                OCR text extraction, MRZ checksum validation, 5-layer tampering forensics, and watchlist cross-checks (~5-8s).
              </p>
            </div>

            {/* Stage 2 step */}
            <div className="p-3 rounded bg-surface-raised/40 border border-border/40 space-y-1">
              <div className="flex items-center justify-between text-xs font-mono font-bold">
                <span className="text-text-muted flex items-center gap-1.5">
                  <Camera size={14} className="text-text-muted" />
                  <span>Stage 2: Biometrics & Decision</span>
                </span>
                <span className="text-[10px] text-text-muted bg-surface border border-border px-1.5 py-0.5 rounded">
                  Officer-Gated
                </span>
              </div>
              <p className="text-[11px] font-mono text-text-muted/80 leading-relaxed">
                Live webcam capture against document portrait, AWS Rekognition facial comparison, person clustering, and final verdict clearance.
              </p>
            </div>
          </div>
        </div>

        <div className="pt-2 border-t border-border flex items-center gap-2 text-[11px] font-mono text-text-muted">
          <ArrowRight size={13} className="text-brand shrink-0" />
          <span>Biometric live camera opens after Stage 1 review</span>
        </div>
      </div>
    </div>
  );
}

