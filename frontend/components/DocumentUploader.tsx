"use client";

import React, { useRef, useState, useEffect } from "react";
import {
  UploadCloud,
  Camera,
  Trash2,
  CheckCircle2,
  Video,
  X,
  RefreshCw,
  FolderOpen,
} from "lucide-react";

interface DocumentUploaderProps {
  docFile: File | null;
  onDocFileChange: (file: File | null) => void;
  livePhoto: File | null;
  onLivePhotoChange: (file: File | null) => void;
}

export function DocumentUploader({
  docFile,
  onDocFileChange,
  livePhoto,
  onLivePhotoChange,
}: DocumentUploaderProps) {
  const docInputRef = useRef<HTMLInputElement>(null);
  const liveInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const [docDragOver, setDocDragOver] = useState(false);
  const [liveDragOver, setLiveDragOver] = useState(false);

  const [docPreview, setDocPreview] = useState<string | null>(null);
  const [livePreview, setLivePreview] = useState<string | null>(null);

  // Live Camera Streaming State
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);

  const stopCameraStream = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    setIsCameraActive(false);
  };

  useEffect(() => {
    return () => {
      // Clean up camera stream on unmount
      stopCameraStream();
    };
  }, []);

  const startCamera = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setCameraError(null);

    try {
      if (!navigator?.mediaDevices?.getUserMedia) {
        throw new Error("Camera device access not supported in this browser.");
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: "user",
        },
        audio: false,
      });

      mediaStreamRef.current = stream;
      setIsCameraActive(true);

      // Attach to video element
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => {});
        }
      }, 50);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Could not access camera. Please allow camera permissions or upload an image file.";
      setCameraError(msg);
      setIsCameraActive(false);
    }
  };

  const captureFrame = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!videoRef.current) return;

    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (blob) {
          const file = new File(
            [blob],
            `live_capture_${Date.now()}.jpg`,
            { type: "image/jpeg" }
          );
          onLivePhotoChange(file);
          const url = URL.createObjectURL(file);
          setLivePreview(url);
          stopCameraStream();
        }
      },
      "image/jpeg",
      0.92
    );
  };

  const handleDocSelect = (file: File | null) => {
    onDocFileChange(file);
    if (file) {
      const url = URL.createObjectURL(file);
      setDocPreview(url);
    } else {
      setDocPreview(null);
    }
  };

  const handleLiveSelect = (file: File | null) => {
    onLivePhotoChange(file);
    if (file) {
      const url = URL.createObjectURL(file);
      setLivePreview(url);
      stopCameraStream();
    } else {
      setLivePreview(null);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* 1. Document Dropzone (Required) */}
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
        className={`relative bg-surface border-2 border-dashed rounded-md p-6 flex flex-col items-center justify-center min-h-[280px] text-center transition-colors cursor-pointer group ${
          docDragOver
            ? "border-brand bg-surface-raised"
            : docFile
            ? "border-brand/60 bg-surface-raised/40"
            : "border-border hover:border-brand/40"
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
          <div className="relative w-full h-full flex flex-col items-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={docPreview}
              alt="Document Scan Preview"
              className="max-h-44 max-w-full object-contain rounded border border-border"
            />
            <div className="mt-3 flex items-center gap-2">
              <CheckCircle2 size={16} className="text-brand" />
              <span className="font-mono text-xs text-text font-bold truncate max-w-[200px]">
                {docFile?.name}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDocSelect(null);
                }}
                className="p-1 text-text-muted hover:text-risk-critical"
              >
                <Trash2 size={14} />
              </button>
            </div>
            <p className="font-mono text-[10px] text-text-muted mt-1">
              Click to replace document scan
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-surface-raised border border-border flex items-center justify-center text-brand mb-3 group-hover:scale-105 transition-transform">
              <UploadCloud size={24} strokeWidth={1.5} />
            </div>
            <div className="font-display font-bold text-sm uppercase text-text tracking-tight">
              Ingest Document Scan Image
            </div>
            <p className="font-mono text-xs text-text-muted mt-1">
              Drop ICAO 9303 passport, ID card, or visa scan
            </p>
            <span className="mt-4 px-3 py-1 bg-surface-raised border border-border rounded font-mono text-[10px] text-brand uppercase tracking-wider">
              JPG • PNG • WEBP (Up to 10MB)
            </span>
          </div>
        )}
      </div>

      {/* 2. Live Camera / Facial Capture Feed */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setLiveDragOver(true);
        }}
        onDragLeave={() => setLiveDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setLiveDragOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) handleLiveSelect(file);
        }}
        className={`relative bg-surface border-2 border-dashed rounded-md p-6 flex flex-col items-center justify-center min-h-[280px] text-center transition-colors ${
          liveDragOver
            ? "border-brand bg-surface-raised"
            : livePhoto || isCameraActive
            ? "border-brand/60 bg-surface-raised/40"
            : "border-border hover:border-brand/40"
        }`}
      >
        <input
          ref={liveInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => handleLiveSelect(e.target.files?.[0] || null)}
        />

        {/* Live Camera Viewfinder */}
        {isCameraActive ? (
          <div className="relative w-full h-full flex flex-col items-center">
            <div className="relative w-full h-44 bg-black rounded border border-brand/60 overflow-hidden flex items-center justify-center">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover mirror"
              />

              {/* Facial alignment reticle */}
              <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                <div className="w-28 h-36 border-2 border-dashed border-brand/70 rounded-full animate-pulse" />
              </div>

              {/* LIVE Indicator */}
              <div className="absolute top-2 left-2 flex items-center gap-1.5 px-2 py-0.5 rounded bg-black/80 border border-risk-critical text-risk-critical font-mono text-[10px] uppercase font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-risk-critical animate-ping" />
                <span>Live Feed</span>
              </div>

              {/* Close Camera Button */}
              <button
                type="button"
                onClick={stopCameraStream}
                className="absolute top-2 right-2 p-1 rounded bg-black/80 text-text-muted hover:text-white border border-border"
                title="Close Camera"
              >
                <X size={14} />
              </button>
            </div>

            {/* Shutter Capture Button */}
            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                onClick={captureFrame}
                className="px-4 py-2 bg-brand hover:bg-white text-bg font-display text-xs font-bold uppercase tracking-wider rounded transition-all flex items-center gap-2 shadow-[0_0_12px_rgba(166,255,77,0.3)] cursor-pointer"
              >
                <Camera size={15} />
                <span>Capture Snapshot</span>
              </button>

              <button
                type="button"
                onClick={stopCameraStream}
                className="px-3 py-2 bg-surface-raised hover:bg-border text-text-muted font-mono text-xs uppercase rounded transition-colors cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : livePreview ? (
          <div className="relative w-full h-full flex flex-col items-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={livePreview}
              alt="Live Portrait Capture Preview"
              className="max-h-44 max-w-full object-contain rounded border border-border"
            />
            <div className="mt-3 flex items-center gap-2">
              <CheckCircle2 size={16} className="text-brand" />
              <span className="font-mono text-xs text-text font-bold truncate max-w-[200px]">
                {livePhoto?.name}
              </span>
              <button
                type="button"
                onClick={() => handleLiveSelect(null)}
                className="p-1 text-text-muted hover:text-risk-critical"
              >
                <Trash2 size={14} />
              </button>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <button
                type="button"
                onClick={startCamera}
                className="text-[11px] font-mono text-brand hover:underline flex items-center gap-1 cursor-pointer"
              >
                <RefreshCw size={11} />
                <span>Retake with Camera</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-surface-raised border border-border flex items-center justify-center text-text-muted mb-3 group-hover:scale-105 transition-transform">
              <Video size={24} strokeWidth={1.5} className="text-brand" />
            </div>

            <div className="font-display font-bold text-sm uppercase text-text tracking-tight">
              Live Biometric Camera Capture
            </div>
            <p className="font-mono text-xs text-text-muted mt-1 max-w-xs">
              Direct webcam stream for 1:1 ArcFace biometric matching
            </p>

            {cameraError && (
              <p className="font-mono text-[11px] text-risk-critical mt-2 max-w-xs">
                {cameraError}
              </p>
            )}

            {/* Action Buttons: Live Camera vs File Upload */}
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              <button
                type="button"
                onClick={startCamera}
                className="px-4 py-2 bg-brand hover:bg-white text-bg font-display text-xs font-bold uppercase tracking-wider rounded transition-all flex items-center gap-2 shadow-[0_0_10px_rgba(166,255,77,0.25)] cursor-pointer"
              >
                <Camera size={14} />
                <span>Open Live Camera</span>
              </button>

              <button
                type="button"
                onClick={() => liveInputRef.current?.click()}
                className="px-3 py-2 bg-surface-raised hover:bg-border border border-border text-text-muted hover:text-text font-mono text-xs uppercase rounded transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <FolderOpen size={13} />
                <span>Choose File</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
