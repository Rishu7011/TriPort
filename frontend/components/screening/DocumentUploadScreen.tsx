"use client";

import React, { useState, useRef } from "react";
import type { CheckpointType, DocumentType } from "../../lib/api/types";

interface DocumentUploadScreenProps {
  onScanDocument: (
    file: File,
    docType: DocumentType,
    checkpointType: CheckpointType
  ) => void;
  isUploading: boolean;
  error: string | null;
}

const DOCUMENT_TYPES: { id: DocumentType; label: string; icon: string }[] = [
  { id: "passport", label: "PASSPORT", icon: "badge" },
  { id: "visa", label: "VISA", icon: "assignment" },
  { id: "national_id", label: "NATIONAL ID", icon: "credit_card" },
  { id: "pan_card", label: "PAN CARD", icon: "contact_page" },
  { id: "voter_id", label: "VOTER ID", icon: "how_to_vote" },
  { id: "driving_license", label: "DRIVING LICENSE", icon: "drive_eta" },
  { id: "permit", label: "PERMIT", icon: "description" },
];

const CHECKPOINT_TYPES: { id: CheckpointType; label: string; icon: string }[] = [
  { id: "airport", label: "AIRPORT POST", icon: "flight" },
  { id: "land_border", label: "LAND BORDER", icon: "directions_car" },
  { id: "sea", label: "MARITIME PORT", icon: "directions_boat" },
];

export function DocumentUploadScreen({
  onScanDocument,
  isUploading,
  error,
}: DocumentUploadScreenProps) {
  const [selectedDocType, setSelectedDocType] =
    useState<DocumentType>("passport");
  const [selectedCheckpointType, setSelectedCheckpointType] =
    useState<CheckpointType>("airport");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null);
      return;
    }
    // Generate instant client-side preview URL without any network calls
    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);
    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [selectedFile]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleRemoveFile = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || isUploading) return;
    onScanDocument(selectedFile, selectedDocType, selectedCheckpointType);
  };

  return (
    <div className="flex flex-col w-full justify-center items-center px-4 sm:px-8 py-8">
      <div className="flex flex-col items-center max-w-2xl w-full gap-6">
        {/* Title Header */}
        <div className="flex flex-col items-center text-center gap-2 mb-2">
          <h1 className="font-headline-lg text-on-surface uppercase tracking-tight">
            IDENTITY INGESTION
          </h1>
          <p className="font-body-lg text-on-surface-variant max-w-md">
            Initialize primary document scan. Align MRZ data within the capture
            zone for optimal OCR extraction.
          </p>
        </div>

        {/* Tactical Config Selectors */}
        <div className="w-full flex flex-col gap-4 bg-surface-container-low border border-outline-variant/60 p-4">
          {/* Checkpoint Mode */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="font-label-caps text-on-surface-variant uppercase">
                OPERATIONAL CHECKPOINT POST
              </span>
              <span className="font-data-mono-md text-[11px] text-primary-fixed">
                STATION ID: CONSOLE-PRIMARY
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {CHECKPOINT_TYPES.map((cp) => {
                const active = selectedCheckpointType === cp.id;
                return (
                  <button
                    key={cp.id}
                    type="button"
                    onClick={() => setSelectedCheckpointType(cp.id)}
                    className={`h-10 px-2 flex items-center justify-center gap-1.5 border transition-all text-xs font-label-caps tracking-wider cursor-pointer ${
                      active
                        ? "border-primary-fixed bg-primary-fixed/15 text-primary-fixed shadow-[0_0_10px_rgba(192,245,0,0.15)]"
                        : "border-outline-variant/50 bg-surface text-on-surface-variant hover:text-on-surface hover:border-outline"
                    }`}
                  >
                    <span className="material-symbols-outlined text-[16px]">
                      {cp.icon}
                    </span>
                    <span>{cp.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Document Type */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className="font-label-caps text-on-surface-variant uppercase">
                TARGET DOCUMENT SPECIFICATION
              </span>
              <span className="font-data-mono-md text-[11px] text-on-surface-variant/70">
                ICAO 9303 / NATIONAL STD
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-2">
              {DOCUMENT_TYPES.map((dt) => {
                const active = selectedDocType === dt.id;
                return (
                  <button
                    key={dt.id}
                    type="button"
                    onClick={() => setSelectedDocType(dt.id)}
                    className={`h-10 px-2 flex items-center justify-center gap-1.5 border transition-all text-xs font-label-caps tracking-wider cursor-pointer ${
                      active
                        ? "border-primary-fixed bg-primary-fixed/15 text-primary-fixed shadow-[0_0_10px_rgba(192,245,0,0.15)]"
                        : "border-outline-variant/50 bg-surface text-on-surface-variant hover:text-on-surface hover:border-outline"
                    }`}
                  >
                    <span className="material-symbols-outlined text-[16px]">
                      {dt.icon}
                    </span>
                    <span>{dt.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Error message if upload failed */}
        {error && (
          <div className="w-full bg-error-container/20 border-l-4 border-error p-3 text-error font-data-mono-md flex items-center gap-2">
            <span className="material-symbols-outlined text-error text-[20px]">
              warning
            </span>
            <span>{error}</span>
          </div>
        )}

        {/* Upload Dropzone / Visual Preview Area */}
        <div
          onClick={() => !previewUrl && fileInputRef.current?.click()}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`w-full relative group overflow-hidden bg-surface-container-low border transition-all duration-300 min-h-[320px] flex flex-col items-center justify-center p-6 gap-4 ${
            isDragOver
              ? "border-primary-fixed bg-surface-container-high"
              : previewUrl
              ? "border-primary-fixed/60 bg-surface-container"
              : "border-dashed border-outline-variant hover:border-primary-fixed hover:bg-surface-container-high cursor-pointer"
          }`}
        >
          {/* Corner Reticles */}
          <div
            className={`absolute top-3 left-3 w-5 h-5 border-t-2 border-l-2 transition-colors z-20 ${
              previewUrl || isDragOver
                ? "border-primary-fixed"
                : "border-outline-variant group-hover:border-primary-fixed"
            }`}
          />
          <div
            className={`absolute top-3 right-3 w-5 h-5 border-t-2 border-r-2 transition-colors z-20 ${
              previewUrl || isDragOver
                ? "border-primary-fixed"
                : "border-outline-variant group-hover:border-primary-fixed"
            }`}
          />
          <div
            className={`absolute bottom-3 left-3 w-5 h-5 border-b-2 border-l-2 transition-colors z-20 ${
              previewUrl || isDragOver
                ? "border-primary-fixed"
                : "border-outline-variant group-hover:border-primary-fixed"
            }`}
          />
          <div
            className={`absolute bottom-3 right-3 w-5 h-5 border-b-2 border-r-2 transition-colors z-20 ${
              previewUrl || isDragOver
                ? "border-primary-fixed"
                : "border-outline-variant group-hover:border-primary-fixed"
            }`}
          />

          {previewUrl ? (
            /* Visual Image Preview when file is acquired */
            <div className="w-full flex flex-col items-center gap-3 z-10">
              {/* Header Bar */}
              <div className="w-full flex items-center justify-between border-b border-outline-variant/60 pb-2">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-primary-fixed animate-pulse shadow-[0_0_6px_#c0f500]" />
                  <span className="font-label-caps text-primary-fixed uppercase tracking-wider text-xs font-bold">
                    DOCUMENT ACQUIRED // PREVIEW VERIFIED
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleRemoveFile}
                  className="font-data-mono-md text-xs text-on-surface-variant hover:text-error transition-colors flex items-center gap-1 cursor-pointer bg-surface px-2.5 py-1 border border-outline-variant/60 hover:border-error"
                >
                  <span className="material-symbols-outlined text-[16px]">
                    close
                  </span>
                  <span>CHANGE DOCUMENT</span>
                </button>
              </div>

              {/* Document Image Frame */}
              <div
                onClick={() => fileInputRef.current?.click()}
                title="Click to replace image"
                className="relative max-h-[300px] w-full flex items-center justify-center bg-surface-container-lowest border border-outline-variant/50 p-2 overflow-hidden cursor-pointer group/img"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previewUrl}
                  alt="Acquired Document Preview"
                  className="max-h-[280px] w-auto object-contain rounded filter contrast-105 shadow-2xl transition-transform duration-300 group-hover/img:scale-[1.01]"
                />
                <div className="absolute inset-0 bg-background/50 opacity-0 group-hover/img:opacity-100 flex items-center justify-center transition-opacity duration-200">
                  <span className="bg-surface border border-primary-fixed text-primary-fixed font-data-mono-md text-xs px-3 py-1.5 flex items-center gap-1.5 shadow-lg">
                    <span className="material-symbols-outlined text-[16px]">
                      sync
                    </span>
                    <span>CLICK TO REPLACE FILE</span>
                  </span>
                </div>
              </div>

              {/* Tactical Meta Bar */}
              <div className="w-full flex flex-wrap items-center justify-between gap-2 bg-surface px-3 py-2 border border-outline-variant/50 font-data-mono-md text-xs">
                <div className="flex items-center gap-2 text-on-surface">
                  <span className="material-symbols-outlined text-primary-fixed text-[18px]">
                    description
                  </span>
                  <span className="font-semibold">{selectedFile?.name}</span>
                  <span className="text-on-surface-variant">
                    ({((selectedFile?.size || 0) / 1024).toFixed(1)} KB)
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="bg-primary-fixed/15 text-primary-fixed px-2 py-0.5 text-[10px] uppercase font-bold tracking-wider">
                    {selectedDocType.toUpperCase()}
                  </span>
                  <span className="text-on-surface-variant text-[11px]">
                    LOCAL BUFFER • READY FOR ANALYSIS
                  </span>
                </div>
              </div>
            </div>
          ) : (
            /* Empty Dropzone Prompt */
            <>
              <div className="w-16 h-16 rounded bg-surface-container-highest flex items-center justify-center mb-1 group-hover:scale-105 transition-transform duration-300">
                <span className="material-symbols-outlined text-primary-fixed text-[32px]">
                  document_scanner
                </span>
              </div>

              <div className="flex flex-col items-center text-center gap-1">
                <span className="font-headline-md text-on-surface">
                  DRAG & DROP SECURE DOCUMENT
                </span>
                <span className="font-data-mono-md text-on-surface-variant">
                  or click to browse local directory
                </span>
              </div>

              <div className="mt-2 bg-surface px-4 py-2 border border-outline-variant flex items-center gap-2">
                <span className="material-symbols-outlined text-outline text-[16px]">
                  info
                </span>
                <span className="font-label-caps text-on-surface-variant">
                  SUPPORTED: ICAO-9303 PASSPORTS, SECURE NATIONAL ID CARDS (JPEG,
                  PNG, PDF)
                </span>
              </div>
            </>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,application/pdf"
            onChange={handleFileChange}
            className="hidden"
          />

          {/* Scanning Progress Overlay */}
          {isUploading && (
            <div className="absolute inset-0 bg-surface-container-lowest/90 flex flex-col items-center justify-center z-10">
              <div className="w-full max-w-[240px] h-1.5 bg-surface-variant overflow-hidden rounded-full">
                <div className="h-full bg-primary-fixed w-1/3 animate-[scan_1.5s_ease-in-out_infinite]" />
              </div>
              <span className="mt-4 font-data-mono-md text-primary-fixed uppercase animate-pulse">
                Analyzing MRZ & Forensic Signatures...
              </span>
              <span className="font-label-caps text-on-surface-variant/70 mt-1">
                Executing OCR, 5-layer ELA, & Interpol SLTD validation
              </span>
            </div>
          )}
        </div>

        {/* Action Area */}
        <div className="w-full flex flex-col items-center gap-3">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!selectedFile || isUploading}
            className={`w-full max-w-md bg-primary-fixed hover:bg-primary-fixed-dim text-on-primary-fixed font-headline-sm uppercase py-4 px-6 flex items-center justify-center gap-2 transition-all duration-200 cursor-pointer ${
              !selectedFile || isUploading
                ? "opacity-40 cursor-not-allowed"
                : "shadow-[0_0_15px_rgba(192,245,0,0.25)] hover:shadow-[0_0_20px_rgba(192,245,0,0.4)]"
            }`}
          >
            <span
              className="material-symbols-outlined"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              play_arrow
            </span>
            <span>
              {isUploading ? "EXECUTING SCREENING..." : "RUN DOCUMENT SCREENING"}
            </span>
          </button>

          <div className="flex gap-4 font-label-caps text-on-surface-variant">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-fixed" />{" "}
              ENCRYPTION: AES-256
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-fixed" />{" "}
              CONNECTION: SECURE
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
