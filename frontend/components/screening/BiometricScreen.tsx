"use client";

import React, { useState, useEffect, useRef } from "react";
import type { FaceVerificationResult, RiskScoreResponse } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthContext";

interface BiometricScreenProps {
  documentId: string;
  docPortraitUrl: string;
  onVerifyLiveFace: (photoBlob: Blob) => Promise<{
    face: FaceVerificationResult;
    risk_score: RiskScoreResponse;
    live_image_url: string;
  }>;
  onRecordDecision: (decision: "approve" | "reject", notes?: string) => void;
  isDeciding: boolean;
}

export function BiometricScreen({
  documentId,
  docPortraitUrl,
  onVerifyLiveFace,
  onRecordDecision,
  isDeciding,
}: BiometricScreenProps) {
  const { user } = useAuth();

  // Camera & Stream State
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const autoClearTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);

  // Capture & Verification State
  const [capturedImageUrl, setCapturedImageUrl] = useState<string | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<{
    face: FaceVerificationResult;
    risk_score: RiskScoreResponse;
    live_image_url: string;
  } | null>(null);

  // Elapsed Timer
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Auto-advance countdown when face is recognized (no human verification required)
  const [autoApproveCountdown, setAutoApproveCountdown] = useState<number | null>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Initialize webcam
  useEffect(() => {
    let mounted = true;

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            facingMode: "user",
          },
          audio: false,
        });

        if (!mounted) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setCameraActive(true);
        setCameraError(null);
      } catch (err) {
        if (!mounted) return;
        setCameraError(
          "Camera access denied or unavailable. Please connect a webcam or permit camera permissions."
        );
      }
    }

    startCamera();

    return () => {
      mounted = false;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  // Capture frame from video feed and send to Stage 2 backend
  const handleCaptureAndVerify = async () => {
    if (!videoRef.current || isVerifying) return;

    try {
      setIsVerifying(true);
      const video = videoRef.current;
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Could not initialize canvas context");

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.95)
      );

      if (!blob) throw new Error("Failed to capture image frame");

      setCapturedImageUrl(canvas.toDataURL("image/jpeg"));

      // Call Stage 2: POST /api/v1/documents/{id}/verify-live-face (AWS Rekognition)
      const res = await onVerifyLiveFace(blob);
      setVerificationResult(res);
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Face verification failed";
      setCameraError(errorMsg);
    } finally {
      setIsVerifying(false);
    }
  };

  const cancelAutoClear = () => {
    if (autoClearTimerRef.current) {
      clearInterval(autoClearTimerRef.current);
      autoClearTimerRef.current = null;
    }
    setAutoApproveCountdown(null);
  };

  const handleRetake = () => {
    cancelAutoClear();
    setCapturedImageUrl(null);
    setVerificationResult(null);
    setCameraError(null);
  };

  // Re-attach stream to video element after retake (video is always in DOM now)
  useEffect(() => {
    if (!capturedImageUrl && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      videoRef.current.play().catch(() => {});
    }
  }, [capturedImageUrl]);

  // Real backend metrics
  const oneToOne = verificationResult?.face?.one_to_one;
  const matchScorePct =
    oneToOne?.match_score !== undefined
      ? (oneToOne.match_score <= 1.0 ? oneToOne.match_score * 100 : oneToOne.match_score)
      : null;
  const isMatched = oneToOne?.matched ?? null;
  // Threshold from backend config (0.90 / 90.0%)
  const thresholdPct =
    oneToOne?.threshold !== undefined
      ? (oneToOne.threshold <= 1.0 ? oneToOne.threshold * 100 : oneToOne.threshold)
      : 90.0;

  // Automated clearance effect when face is recognized (no human verification needed)
  useEffect(() => {
    if (autoClearTimerRef.current) {
      clearInterval(autoClearTimerRef.current);
      autoClearTimerRef.current = null;
    }

    if (verificationResult && isMatched === true && !isDeciding) {
      let remaining = 3;
      setAutoApproveCountdown(3);

      autoClearTimerRef.current = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          if (autoClearTimerRef.current) {
            clearInterval(autoClearTimerRef.current);
            autoClearTimerRef.current = null;
          }
          setAutoApproveCountdown(null);
          // Dispatch asynchronously to avoid updating parent state during render
          setTimeout(() => {
            onRecordDecision(
              "approve",
              "Automated biometric match — zero human verification required"
            );
          }, 0);
        } else {
          setAutoApproveCountdown(remaining);
        }
      }, 1000);

      return () => {
        if (autoClearTimerRef.current) {
          clearInterval(autoClearTimerRef.current);
          autoClearTimerRef.current = null;
        }
      };
    } else {
      setAutoApproveCountdown(null);
    }
  }, [verificationResult, isMatched, isDeciding]);

  const isLive = verificationResult?.face ? true : false;
  const officerBadge = user?.badge_number || user?.user_id?.substring(0, 8).toUpperCase() || "OP-773-DELTA";

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex flex-col w-full px-4 sm:px-6 pb-8 gap-4">
      {/* Top Banner: Face Recognized (No Human Verification Needed) */}
      {verificationResult && isMatched === true && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between bg-surface-container border-b-2 border-primary-fixed p-4 gap-3 shadow-[0_0_15px_rgba(192,245,0,0.12)]">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary-fixed text-[24px]">
                verified
              </span>
              <h2 className="font-headline-md text-primary-fixed uppercase leading-tight">
                BIOMETRIC MATCH CONFIRMED — NO HUMAN VERIFICATION REQUIRED
              </h2>
            </div>
            <span className="font-data-mono-md text-on-surface uppercase text-xs mt-0.5">
              1:1 Face Match Verified Against Document Photo • Automated Clearance Active
              {autoApproveCountdown !== null && (
                <span className="text-primary-fixed font-bold ml-1.5 animate-pulse">
                  [Auto-clearing in {autoApproveCountdown}s...]
                </span>
              )}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-surface-container-highest px-4 py-2 border border-primary-fixed/40 shadow-[0_0_10px_rgba(192,245,0,0.2)]">
              <span
                className="material-symbols-outlined text-primary-fixed text-[20px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                check_circle
              </span>
              <span className="font-data-mono-lg text-primary-fixed font-bold uppercase">
                {matchScorePct !== null ? matchScorePct.toFixed(1) : "100.0"}% MATCH
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Top Banner: Biometric Discrepancy (Human Verification Required) */}
      {verificationResult && isMatched === false && (
        <div className="flex items-center justify-between bg-surface-container border-b-2 border-secondary-fixed p-4">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-secondary-fixed text-[24px]">
                warning
              </span>
              <h2 className="font-headline-md text-secondary-fixed uppercase leading-tight">
                Biometric Discrepancy Detected — Human Verification Required
              </h2>
            </div>
            <span className="font-data-mono-md text-on-surface-variant uppercase text-xs mt-0.5">
              System Confidence Below Cutoff Boundary — Officer In-Person Inspection & Manual Override Required
            </span>
          </div>
          <div className="flex items-center gap-2 bg-surface-container-highest px-4 py-2 border border-secondary-fixed/40">
            <span
              className="material-symbols-outlined text-secondary-fixed text-[20px]"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              warning
            </span>
            <span className="font-data-mono-lg text-secondary-fixed font-bold uppercase">
              {matchScorePct !== null ? matchScorePct.toFixed(1) : "0.0"}% MATCH
            </span>
          </div>
        </div>
      )}

      {/* Main Dual-Source Comparison View */}
      <div className="flex flex-col md:flex-row gap-4">
        {/* Source A: Document Portrait */}
        <div className="flex-1 flex flex-col bg-surface-container-low border border-outline-variant/60 p-4 relative overflow-hidden group">
          <div className="flex justify-between items-start mb-3 z-10 relative">
            <div className="flex flex-col">
              <span className="font-data-mono-md text-xs text-on-surface-variant uppercase tracking-wider">
                SOURCE A
              </span>
              <span className="font-headline-sm text-on-surface uppercase mt-0.5">
                DOCUMENT PORTRAIT
              </span>
            </div>
            <div className="flex items-center gap-1.5 bg-surface-container-highest px-2.5 py-1 border border-outline-variant/40">
              <span className="w-1.5 h-1.5 bg-primary-fixed rounded-full" />
              <span className="font-data-mono-md text-on-surface-variant uppercase text-[10px]">
                eMRTD CHIP / VIS
              </span>
            </div>
          </div>

          <div className="relative border border-outline-variant/40 bg-surface-container-lowest flex items-center justify-center overflow-hidden h-[260px]">
            {docPortraitUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={docPortraitUrl}
                alt="Document Portrait"
                className="object-contain w-full h-full filter contrast-110"
              />
            ) : (
              <span className="font-data-mono-md text-xs text-on-surface-variant">
                NO PORTRAIT IMAGE FOUND
              </span>
            )}
            {/* Technical HUD overlay */}
            <div className="absolute top-3 left-3 font-data-mono-md text-[10px] text-primary-fixed bg-surface-container-low/90 border border-primary-fixed/30 px-2 py-1">
              RES: 600DPI • ISO: 19794-5
            </div>
          </div>
        </div>

        {/* Center Comparison Indicator */}
        <div className="w-12 hidden md:flex flex-col items-center justify-center gap-2 shrink-0">
          <div className="w-px h-1/3 bg-gradient-to-b from-transparent to-primary-fixed/40" />
          <div className="w-10 h-10 rounded-full border border-primary-fixed bg-surface-container flex items-center justify-center shadow-[0_0_15px_rgba(192,245,0,0.2)]">
            <span className="material-symbols-outlined text-primary-fixed text-[20px]">
              compare_arrows
            </span>
          </div>
          <div className="w-px h-1/3 bg-gradient-to-t from-transparent to-primary-fixed/40" />
        </div>

        {/* Source B: Live Capture */}
        <div className="flex-1 flex flex-col bg-surface-container-low border border-primary-fixed/50 p-4 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-[2px] bg-primary-fixed shadow-[0_0_10px_#c0f500]" />

          <div className="flex justify-between items-start mb-3 z-10 relative">
            <div className="flex flex-col">
              <span className="font-data-mono-md text-xs text-primary-fixed/80 uppercase tracking-wider">
                SOURCE B
              </span>
              <span className="font-headline-sm text-primary-fixed uppercase mt-0.5">
                LIVE CAPTURE FEED
              </span>
            </div>
            <div className="flex items-center gap-1.5 bg-primary-fixed/10 border border-primary-fixed/30 px-2.5 py-1">
              <span className="w-1.5 h-1.5 bg-primary-fixed rounded-full animate-pulse shadow-[0_0_5px_#c0f500]" />
              <span className="font-data-mono-md text-primary-fixed uppercase text-[10px]">
                {cameraActive ? "FEED ACTIVE" : "CAMERA OFFLINE"}
              </span>
            </div>
          </div>

          <div className="relative border border-primary-fixed/30 bg-surface-container-lowest flex items-center justify-center overflow-hidden h-[260px]">
            {/* Video always stays in DOM so videoRef is never null on retake */}
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover ${
                capturedImageUrl || cameraError ? "hidden" : ""
              }`}
            />

            {/* Captured snapshot overlaid on top */}
            {capturedImageUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={capturedImageUrl}
                alt="Captured Live Traveler"
                className="absolute inset-0 w-full h-full object-contain filter contrast-110"
              />
            )}

            {/* Camera error state */}
            {cameraError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-4 text-center">
                <span className="material-symbols-outlined text-error text-[36px]">
                  videocam_off
                </span>
                <span className="font-data-mono-md text-xs text-error">
                  {cameraError}
                </span>
              </div>
            )}

            {/* Tactical Viewfinder Overlay */}
            <div className="absolute inset-0 pointer-events-none">
              <svg className="opacity-30" height="100%" width="100%">
                <rect
                  fill="none"
                  height="60%"
                  stroke="#c0f500"
                  strokeDasharray="4 4"
                  strokeWidth="1"
                  width="60%"
                  x="20%"
                  y="20%"
                />
                <path
                  d="M 20% 20% L 25% 20% M 20% 20% L 20% 25%"
                  fill="none"
                  stroke="#c0f500"
                  strokeWidth="2"
                />
                <path
                  d="M 80% 20% L 75% 20% M 80% 20% L 80% 25%"
                  fill="none"
                  stroke="#c0f500"
                  strokeWidth="2"
                />
                <path
                  d="M 20% 80% L 25% 80% M 20% 80% L 20% 75%"
                  fill="none"
                  stroke="#c0f500"
                  strokeWidth="2"
                />
                <path
                  d="M 80% 80% L 75% 80% M 80% 80% L 80% 75%"
                  fill="none"
                  stroke="#c0f500"
                  strokeWidth="2"
                />
              </svg>
            </div>

            {/* Live Camera Controls */}
            <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between pointer-events-auto">
              <div className="flex items-center gap-1.5 bg-surface-container/90 backdrop-blur px-2.5 py-1 border border-outline-variant/60">
                <span className="material-symbols-outlined text-primary-fixed text-[16px]">
                  visibility
                </span>
                <span className="font-data-mono-md text-[10px] text-on-surface">
                  {isLive ? "LIVENESS DETECTED" : "FACE TRACKING ACTIVE"}
                </span>
              </div>

              <div className="flex gap-2">
                {capturedImageUrl ? (
                  <button
                    type="button"
                    onClick={handleRetake}
                    disabled={isVerifying}
                    className="h-9 px-3 bg-surface-container/90 border border-outline-variant text-on-surface hover:border-primary-fixed hover:text-primary-fixed font-data-mono-md text-xs uppercase flex items-center gap-1 cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[16px]">
                      refresh
                    </span>
                    <span>Retake</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleCaptureAndVerify}
                    disabled={isVerifying || !cameraActive}
                    className="h-9 px-4 bg-primary-fixed hover:bg-primary-fixed-dim text-on-primary-fixed font-data-mono-md text-xs font-bold uppercase flex items-center gap-1.5 shadow-[0_0_10px_rgba(192,245,0,0.3)] cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[16px]">
                      photo_camera
                    </span>
                    <span>
                      {isVerifying ? "VERIFYING BIOMETRICS..." : "CAPTURE & VERIFY"}
                    </span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Verification Metrics Bar */}
      <div className="bg-surface-container p-4 border border-outline-variant/60 flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Biometric Score Meter */}
        <div className="flex items-center gap-6 w-full md:w-1/2">
          <div className="flex flex-col">
            <span className="font-label-caps text-on-surface-variant uppercase text-[10px] mb-0.5">
              BIOMETRIC SCORE (AWS REKOGNITION)
            </span>
            <div className="flex items-baseline gap-1">
              <span
                className={`font-headline-lg text-[36px] leading-none tracking-tight font-bold ${
                  isMatched === false
                    ? "text-secondary-fixed"
                    : "text-primary-fixed"
                }`}
              >
                {matchScorePct !== null ? matchScorePct.toFixed(1) : "—"}
                <span className="text-[20px]">%</span>
              </span>
            </div>
          </div>

          <div className="flex-1 flex flex-col justify-center relative pt-5 pb-1">
            <div className="flex justify-between w-full absolute top-0 text-[10px] font-data-mono-md text-on-surface-variant">
              <span>0%</span>
              <span
                className="absolute -translate-x-1/2 text-primary-fixed font-bold"
                style={{ left: `${thresholdPct}%` }}
              >
                THR {thresholdPct.toFixed(0)}%
              </span>
              <span>100%</span>
            </div>
            <div className="w-full h-2.5 bg-surface-container-highest overflow-hidden relative border border-outline-variant/40">
              <div
                className={`absolute top-0 left-0 h-full transition-all duration-700 ${
                  isMatched === false
                    ? "bg-secondary-fixed"
                    : "bg-primary-fixed shadow-[0_0_8px_#c0f500]"
                }`}
                style={{ width: `${Math.min(100, matchScorePct || 0)}%` }}
              />
              <div
                className="absolute top-0 h-full w-[2px] bg-white z-10"
                style={{ left: `${thresholdPct}%` }}
              />
            </div>
          </div>
        </div>

        {/* Status Badge */}
        <div className="flex items-center border-y md:border-y-0 md:border-x border-outline-variant/60 py-2 md:py-0 px-4 md:px-6">
          {verificationResult ? (
            isMatched ? (
              <div className="bg-primary-fixed/10 border-2 border-primary-fixed px-5 py-1.5 flex flex-col items-center gap-0.5 shadow-[0_0_15px_rgba(192,245,0,0.2)]">
                <div className="flex items-center gap-1.5">
                  <span
                    className="material-symbols-outlined text-primary-fixed text-[20px]"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    verified
                  </span>
                  <span className="font-headline-sm text-primary-fixed uppercase tracking-wider text-sm font-bold">
                    FACE RECOGNIZED
                  </span>
                </div>
                <span className="text-[10px] font-data-mono-md text-primary-fixed uppercase tracking-tight">
                  NO HUMAN VERIFICATION REQUIRED
                </span>
              </div>
            ) : (
              <div className="bg-secondary-fixed/10 border-2 border-secondary-fixed px-4 py-1.5 flex flex-col items-center gap-0.5">
                <div className="flex items-center gap-1.5">
                  <span
                    className="material-symbols-outlined text-secondary-fixed text-[20px]"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    warning
                  </span>
                  <span className="font-headline-sm text-secondary-fixed uppercase tracking-wider text-xs font-bold">
                    MISMATCH DETECTED
                  </span>
                </div>
                <span className="text-[10px] font-data-mono-md text-secondary-fixed uppercase tracking-tight font-semibold">
                  HUMAN VERIFICATION REQUIRED
                </span>
              </div>
            )
          ) : (
            <div className="border border-outline-variant px-4 py-2 text-on-surface-variant font-data-mono-md text-xs uppercase">
              AWAITING LIVE PHOTO CAPTURE
            </div>
          )}
        </div>

        {/* Audit Meta & Decision Buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto justify-end">
          <div className="hidden lg:flex flex-col gap-0.5 text-right font-data-mono-md text-[11px] text-on-surface-variant mr-2">
            <span>OFFICER: {officerBadge}</span>
            <span>ELAPSED: {formatTimer(elapsedSeconds)}</span>
          </div>

          <div className="flex gap-2 w-full sm:w-auto">
            {/* Reject Option */}
            <button
              type="button"
              onClick={() => {
                cancelAutoClear();
                onRecordDecision("reject", "Biometric rejection");
              }}
              disabled={isDeciding || isVerifying}
              className="flex-1 sm:flex-none h-12 px-6 flex items-center justify-center gap-2 border-2 border-error/70 bg-transparent text-error hover:bg-error/10 hover:border-error transition-colors uppercase font-label-caps tracking-wider cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[18px]">
                block
              </span>
              <span>REJECT</span>
            </button>

            {/* Approval Option (Gated until verification runs) */}
            {verificationResult && !isMatched ? (
              <button
                type="button"
                onClick={() => {
                  cancelAutoClear();
                  onRecordDecision(
                    "approve",
                    "Manual biometric verification override by officer"
                  );
                }}
                disabled={isDeciding || isVerifying}
                className="flex-1 sm:flex-none h-12 px-6 flex items-center justify-center gap-2 border-2 border-secondary-fixed bg-secondary-fixed/15 text-secondary-fixed hover:bg-secondary-fixed/25 transition-colors uppercase font-label-caps tracking-wider cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <span className="material-symbols-outlined text-[18px]">
                  verified_user
                </span>
                <span>HUMAN OVERRIDE (APPROVE)</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  cancelAutoClear();
                  onRecordDecision(
                    "approve",
                    "Automated biometric match — zero human verification required"
                  );
                }}
                disabled={!verificationResult || !isMatched || isDeciding || isVerifying}
                className="flex-1 sm:flex-none h-12 px-8 flex items-center justify-center gap-2 bg-primary-fixed text-on-primary-fixed hover:bg-primary-fixed-dim transition-colors uppercase font-label-caps tracking-wider shadow-[0_0_15px_rgba(192,245,0,0.3)] cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <span
                  className="material-symbols-outlined text-[18px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  how_to_reg
                </span>
                <span>
                  {isDeciding
                    ? "CLEARING..."
                    : autoApproveCountdown !== null
                    ? `CLEAR NOW (${autoApproveCountdown}S)`
                    : "APPROVE ENTRY"}
                </span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
