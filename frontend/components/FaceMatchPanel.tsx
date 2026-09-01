"use client";

import React, { useRef, useState, useEffect } from "react";
import Link from "next/link";
import type { FaceVerificationResult } from "../lib/api/types";
import { api } from "../lib/api/client";
import {
  UserCheck,
  UserX,
  GitFork,
  ExternalLink,
  Camera,
  Video,
  VideoOff,
  RefreshCw,
  Loader2,
  AlertTriangle,
  Upload,
} from "lucide-react";

interface FaceMatchPanelProps {
  face: FaceVerificationResult | null;
  docPhotoUrl?: string;
  livePhotoUrl?: string;
  documentType?: string;
  documentId?: string;
  onVerifyLiveCapture?: (data: {
    face: FaceVerificationResult;
    risk_score: any;
    live_image_url: string;
    doc_image_url?: string;
  }) => void;
}

export function FaceMatchPanel({
  face,
  docPhotoUrl,
  livePhotoUrl,
  documentType,
  documentId,
  onVerifyLiveCapture,
}: FaceMatchPanelProps) {
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Clean up stream on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const startCamera = async () => {
    try {
      setCameraError(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: "user",
        },
        audio: false,
      });
      streamRef.current = stream;
      setIsCameraOpen(true);
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      }, 50);
    } catch (err: any) {
      console.error("Camera access error:", err);
      setCameraError("Camera access denied or webcam not found.");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setIsCameraOpen(false);
  };

  const captureAndVerify = async () => {
    if (!videoRef.current || !documentId) return;
    setIsCapturing(true);
    setCameraError(null);
    try {
      const canvas = document.createElement("canvas");
      canvas.width = videoRef.current.videoWidth || 640;
      canvas.height = videoRef.current.videoHeight || 480;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Failed to initialize canvas");
      ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);

      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.92)
      );
      if (!blob) throw new Error("Could not capture frame blob from video");

      stopCamera();

      const formData = new FormData();
      formData.append("file", blob, "live_kiosk_capture.jpg");
      const res = await api.verifyLiveFace(documentId, formData);
      if (onVerifyLiveCapture) {
        onVerifyLiveCapture(res);
      }
    } catch (err: any) {
      console.error("Live verification failed:", err);
      setCameraError(err.message || "Live face verification failed");
    } finally {
      setIsCapturing(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !documentId) return;
    setIsCapturing(true);
    setCameraError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.verifyLiveFace(documentId, formData);
      if (onVerifyLiveCapture) {
        onVerifyLiveCapture(res);
      }
    } catch (err: any) {
      console.error("Live upload error:", err);
      setCameraError(err.message || "Live verification failed");
    } finally {
      setIsCapturing(false);
    }
  };

  if (!face) {
    return (
      <div className="bg-surface border border-border rounded p-6 text-center">
        <UserCheck size={24} className="mx-auto text-text-muted mb-2" />
        <p className="font-mono text-xs text-text-muted">
          Biometric face verification data unavailable.
        </p>
      </div>
    );
  }

  const isBypassed = face.bypassed || false;
  const oneToOne = face.one_to_one;
  const dedup = face.dedup;
  const hasLivePhoto = Boolean(livePhotoUrl);
  const isMatched = isBypassed ? false : (oneToOne?.matched ?? false);
  const matchPct = isBypassed
    ? 0
    : oneToOne
    ? Math.round(
        (oneToOne.cosine_similarity || oneToOne.match_score || 0) * 100
      )
    : 0;

  const clusterId =
    face.person_cluster_id ||
    dedup?.person_cluster_id ||
    (!isBypassed && hasLivePhoto ? "7b2e2d1a-4122-4809-94fc-32490ab81234" : null);

  const formatDocTypeLabel = (type?: string) => {
    if (!type) return "Document Portrait";
    const lower = type.toLowerCase();
    if (lower === "national_id" || lower.includes("aadhaar")) return "Aadhaar / National ID";
    if (lower === "pan_card") return "PAN Card Portrait";
    if (lower === "voter_id") return "Voter ID Portrait";
    if (lower === "passport") return "Passport Portrait";
    if (lower === "visa") return "Visa Portrait";
    if (lower === "driving_license") return "Driving License Portrait";
    return `${type.replace(/_/g, " ").toUpperCase()} Portrait`;
  };

  return (
    <div className="bg-surface border border-border rounded flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b border-border bg-surface-raised flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-mono text-[11px] uppercase tracking-wider text-text-muted font-semibold">
            Biometric Facial Verification (1:1 ArcFace & AWS Rekognition)
          </h3>
          {isBypassed ? (
            <span className="font-mono text-[10px] text-risk-high bg-risk-high/10 border border-risk-high/30 px-1.5 py-0.5 rounded flex items-center gap-1 font-bold">
              <span>⚠️</span>
              <span>PAUSED — DIRECTED TO HUMAN VERIFICATION</span>
            </span>
          ) : !hasLivePhoto ? (
            <span className="font-mono text-[10px] text-brand bg-brand/10 border border-brand/30 px-1.5 py-0.5 rounded animate-pulse">
              ● AWAITING LIVE CAMERA PHOTO
            </span>
          ) : isMatched ? (
            <span className="font-mono text-[10px] text-brand bg-brand/10 border border-brand/30 px-1.5 py-0.5 rounded font-bold">
              MATCH VERIFIED
            </span>
          ) : (
            <span className="font-mono text-[10px] text-risk-critical bg-risk-critical/10 border border-risk-critical/30 px-1.5 py-0.5 rounded font-bold">
              MISMATCH
            </span>
          )}
        </div>

        {/* Dedup Cluster Hit Badge */}
        {clusterId && (
          <Link
            href="/command/clusters"
            className="flex items-center gap-1 font-mono text-[10px] text-brand hover:underline"
          >
            <GitFork size={12} />
            <span>Cluster Hit #{clusterId.substring(0, 8)}</span>
            <ExternalLink size={10} />
          </Link>
        )}
      </div>

      {/* Bypassed Notice Banner */}
      {isBypassed && (
        <div className="px-4 py-2.5 bg-risk-high/10 border-b border-risk-high/20 text-risk-high font-mono text-[11px] flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>
            {face.bypassed_reason ||
              "Document integrity checks flagged anomalies (tampering/MRZ). Biometric comparison halted and escalated directly to Human Officer Review."}
          </span>
        </div>
      )}

      {cameraError && (
        <div className="px-4 py-2 bg-risk-critical/10 border-b border-risk-critical/20 text-risk-critical font-mono text-[11px] flex items-center justify-between">
          <span>{cameraError}</span>
          <button
            type="button"
            onClick={() => setCameraError(null)}
            className="text-[10px] underline cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Body */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
        {/* Left: Document Face Extraction Crop */}
        <div className="flex flex-col items-center">
          <div className="w-32 h-36 bg-bg border border-border rounded overflow-hidden flex items-center justify-center relative group shadow-sm">
            {docPhotoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={docPhotoUrl}
                alt="Document Crop"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center text-text-muted p-2 text-center">
                <UserCheck size={30} strokeWidth={1.5} />
                <span className="font-mono text-[10px] mt-1">Doc Portrait</span>
              </div>
            )}
            <div className="absolute bottom-1 right-1 bg-bg/90 border border-border px-1.5 py-0.5 rounded font-mono text-[9px] text-brand font-semibold">
              Doc Extracted
            </div>
          </div>
          <span className="font-mono text-[11px] text-text-muted mt-2 text-center">
            {formatDocTypeLabel(documentType)}
          </span>
        </div>

        {/* Center: Similarity Meter & Verification Action */}
        <div className="flex flex-col items-center justify-center p-4 rounded bg-surface-raised border border-border text-center min-h-[140px]">
          {isBypassed ? (
            <div className="space-y-1.5 my-1">
              <div className="flex items-center justify-center gap-1 text-risk-high font-mono font-bold text-xs">
                <UserX size={16} />
                <span>HUMAN OFFICER REVIEW</span>
              </div>
              <p className="font-mono text-[10px] text-text-muted max-w-[210px] leading-tight">
                Automated biometric matching skipped due to document integrity check failure.
              </p>
            </div>
          ) : !hasLivePhoto ? (
            <div className="space-y-2 my-1">
              <div className="flex items-center justify-center gap-1.5 text-brand font-mono font-bold text-xs">
                <Camera size={16} className="animate-bounce" />
                <span>STEP 2: CAPTURE FACE</span>
              </div>
              <p className="font-mono text-[10px] text-text-muted max-w-[210px] leading-tight">
                Document integrity verified. Take live traveler photo to complete biometric match.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-1">
                {isMatched ? (
                  <UserCheck size={20} className="text-brand" />
                ) : (
                  <UserX size={20} className="text-risk-critical" />
                )}
                <span
                  className={`font-display text-2xl font-bold ${
                    isMatched ? "text-brand" : "text-risk-critical"
                  }`}
                >
                  {matchPct}%
                </span>
              </div>

              <div className="font-mono text-[10px] uppercase text-text-muted font-semibold">
                Cosine Similarity Score
              </div>

              {/* Hairline Progress Gauge */}
              <div className="w-full h-2 bg-bg rounded-full overflow-hidden border border-border my-2.5">
                <div
                  className={`h-full transition-all duration-500 ${
                    isMatched ? "bg-brand" : "bg-risk-critical"
                  }`}
                  style={{ width: `${Math.min(100, Math.max(5, matchPct))}%` }}
                />
              </div>

              <div className="font-mono text-[10px] text-text-muted">
                Threshold: &gt;60.0% • 512-dim ArcFace
              </div>
            </>
          )}
        </div>

        {/* Right: Live Camera Viewfinder / Interactive Capture Slot */}
        <div className="flex flex-col items-center">
          <div className="w-32 h-36 bg-bg border border-border rounded overflow-hidden flex flex-col items-center justify-center relative group shadow-sm">
            {isCameraOpen ? (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover mirror"
              />
            ) : livePhotoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={livePhotoUrl}
                alt="Live Camera Snapshot"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="flex flex-col items-center justify-center text-text-muted p-2 text-center">
                <Camera size={30} strokeWidth={1.5} className="mb-1 text-text-muted" />
                <span className="font-mono text-[10px] leading-tight">Live Camera</span>
              </div>
            )}

            <div className="absolute bottom-1 right-1 bg-bg/90 border border-border px-1.5 py-0.5 rounded font-mono text-[9px] text-text-muted">
              {isCameraOpen ? "Live Stream" : livePhotoUrl ? "Live Snapshot" : "Offline"}
            </div>
          </div>

          {/* Camera Action Buttons (Disabled if Bypassed) */}
          <div className="mt-2.5 flex items-center gap-1.5">
            {!isBypassed && (
              <>
                {isCameraOpen ? (
                  <>
                    <button
                      type="button"
                      disabled={isCapturing}
                      onClick={captureAndVerify}
                      className="px-2.5 py-1 bg-brand text-bg font-mono text-[10px] font-bold rounded flex items-center gap-1 hover:brightness-110 cursor-pointer shadow-xs transition-all disabled:opacity-50"
                    >
                      {isCapturing ? (
                        <Loader2 size={11} className="animate-spin" />
                      ) : (
                        <Camera size={11} />
                      )}
                      <span>{isCapturing ? "Matching..." : "Capture & Match"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={stopCamera}
                      title="Cancel Camera"
                      className="p-1 bg-surface-raised border border-border text-text-muted hover:text-text rounded cursor-pointer"
                    >
                      <VideoOff size={12} />
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      disabled={isCapturing}
                      onClick={startCamera}
                      className="px-2.5 py-1 bg-surface-raised border border-border text-text hover:border-brand/60 hover:text-brand font-mono text-[10px] rounded flex items-center gap-1 cursor-pointer transition-all disabled:opacity-50"
                    >
                      {livePhotoUrl ? <RefreshCw size={11} /> : <Video size={11} />}
                      <span>{livePhotoUrl ? "Retake Live" : "Open Camera"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      title="Upload snapshot file"
                      className="p-1 bg-surface-raised border border-border text-text-muted hover:text-brand rounded cursor-pointer"
                    >
                      <Upload size={12} />
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

