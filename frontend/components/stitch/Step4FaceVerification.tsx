"use client";

import React, { useState, useRef, useEffect } from "react";

interface FaceMatchResult {
  matched: boolean;
  match_score: number;
  cosine_similarity: number;
}

interface Step4FaceVerificationProps {
  onPermit: () => void;
  onDeny: () => void;
  documentPhoto?: string | null;
  faceCropUrl?: string | null;
  pipelineData?: any;
  // Called after live capture — sends passport + live frame to backend for real 1:1 comparison
  onVerifyFace?: (liveFrameBlob: Blob) => Promise<FaceMatchResult | null>;
}

type VerifyState = "idle" | "capturing" | "verifying" | "done";

export const Step4FaceVerification: React.FC<Step4FaceVerificationProps> = ({
  onPermit,
  onDeny,
  documentPhoto,
  faceCropUrl,
  pipelineData,
  onVerifyFace,
}) => {
  const [verifyState, setVerifyState] = useState<VerifyState>("idle");
  const [showFlash, setShowFlash] = useState<boolean>(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [capturedFrame, setCapturedFrame] = useState<string | null>(null);
  const [matchResult, setMatchResult] = useState<FaceMatchResult | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // ID photo: cropped face from passport > full scan
  const idPhoto = faceCropUrl || documentPhoto;

  // ── Camera setup ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (verifyState !== "idle") return;

    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch {
        setCameraError("Camera unavailable — please allow camera access.");
      }
    };

    startCamera();

    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [verifyState]);

  // ── Capture + Verify ────────────────────────────────────────────────────────
  const handleCapture = async () => {
    setVerifyState("capturing");
    setVerifyError(null);
    setShowFlash(true);

    // Grab frame from canvas
    let frameBlob: Blob | null = null;
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
        setCapturedFrame(dataUrl);
        // Convert canvas to Blob for API
        await new Promise<void>((resolve) => {
          canvas.toBlob(
            (blob) => {
              frameBlob = blob;
              resolve();
            },
            "image/jpeg",
            0.92
          );
        });
      }
    }

    // Stop camera
    streamRef.current?.getTracks().forEach((t) => t.stop());

    // Brief flash delay
    await new Promise((r) => setTimeout(r, 600));
    setShowFlash(false);
    setVerifyState("verifying");

    // ── Call backend for real 1:1 face comparison ────────────────────────────
    if (onVerifyFace && frameBlob) {
      try {
        const result = await onVerifyFace(frameBlob);
        if (result) {
          setMatchResult(result);
          setVerifyState("done");
          return;
        }
      } catch (err) {
        console.error("[Step4] verifyFace error:", err);
      }
    }

    // ── Fallback: use pipeline data from initial upload (no live_photo case) ──
    const backendFace = pipelineData?.face?.one_to_one ?? null;
    if (backendFace) {
      setMatchResult(backendFace);
    } else {
      // Both backend and onVerifyFace failed — show error
      setVerifyError("Face verification service unavailable. Please retry or escalate.");
    }
    setVerifyState("done");
  };

  const handleRetake = () => {
    setVerifyState("idle");
    setCapturedFrame(null);
    setMatchResult(null);
    setVerifyError(null);
    setShowFlash(false);
  };

  // ── Derived match values ────────────────────────────────────────────────────
  const displayScore = matchResult ? Math.round(matchResult.match_score * 100) : null;
  const isMatch = matchResult?.matched ?? false;
  const isMismatch = matchResult !== null && !matchResult.matched;

  return (
    <div className="flex-1 w-full max-w-[1440px] mx-auto px-6 py-8 flex flex-col">
      {/* Header */}
      <div className="mb-8 animate-slide-up">
        <div className="flex items-center gap-2 text-xs font-bold text-[#d97757] uppercase tracking-wider mb-1">
          <span>Step 4 of 4</span>
          <span>·</span>
          <span>Biometric Face Verification</span>
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-[#2B2622]">Face Verification</h1>
        <p className="text-sm text-[#55433d] mt-1">
          Capture the traveler's live face and compare it against the document holder photo.
          The backend AI model computes the biometric match score in real time.
        </p>
      </div>

      <div className="flex-1 flex flex-col items-center">
        <div className="w-full max-w-4xl bg-[#FAF8F5] rounded-[28px] border border-[#E8E2D9] shadow-[0px_12px_32px_rgba(43,38,34,0.06)] p-8 md:p-10 flex flex-col items-center">

          {/* Two-panel comparison */}
          <div className="w-full grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">

            {/* Left: Document ID photo */}
            <div className="flex flex-col items-center gap-3">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#655d54]">
                <span className="material-symbols-outlined !text-[16px]">contact_page</span>
                <span>Document Holder Photo</span>
              </div>
              <div className="w-full aspect-[3/4] rounded-2xl overflow-hidden border-2 border-[#E8E2D9] bg-[#f6f3ee] shadow-sm relative">
                {idPhoto ? (
                  <img
                    alt="Document ID Photo"
                    className="w-full h-full object-cover object-top"
                    src={idPhoto}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-[#88726c]">
                    <span className="material-symbols-outlined text-5xl">person</span>
                  </div>
                )}
                <div className="absolute bottom-2 left-2 bg-black/60 backdrop-blur-sm text-white text-[9px] font-bold px-2 py-0.5 rounded flex items-center gap-1">
                  <span className="material-symbols-outlined !text-[10px]">verified</span>
                  IDENTITY DOC
                </div>
              </div>
            </div>

            {/* Right: Live camera / captured frame */}
            <div className="flex flex-col items-center gap-3">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#655d54]">
                <span className="material-symbols-outlined !text-[16px]">videocam</span>
                <span>
                  {verifyState === "done" ? "Captured Frame" : "Live Camera Feed"}
                </span>
              </div>
              <div className="w-full aspect-[3/4] rounded-2xl overflow-hidden border-2 border-[#d97757]/50 bg-[#1c1c19] shadow-sm relative flex items-center justify-center">

                {/* Live video — shown before capture */}
                {verifyState === "idle" && (
                  <>
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      className="w-full h-full object-cover"
                    />

                    {cameraError && (
                      <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#1c1c19] p-4 text-center z-10">
                        <span className="material-symbols-outlined text-4xl text-[#d97757]/80 mb-2">videocam_off</span>
                        <p className="text-xs font-semibold text-[#88726c]">{cameraError}</p>
                        <p className="text-[10px] text-[#655d54] mt-1">Allow camera access and refresh</p>
                      </div>
                    )}

                    {/* ── Biometric Face Alignment Overlay ── */}
                    <div className="absolute inset-0 z-10 pointer-events-none">
                      {/* Dark vignette mask outside the oval */}
                      <svg
                        className="absolute inset-0 w-full h-full"
                        viewBox="0 0 300 400"
                        preserveAspectRatio="xMidYMid slice"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <defs>
                          <mask id="face-oval-mask">
                            <rect width="300" height="400" fill="white" />
                            <ellipse cx="150" cy="175" rx="90" ry="118" fill="black" />
                          </mask>
                        </defs>
                        {/* Darkened surround */}
                        <rect
                          width="300"
                          height="400"
                          fill="rgba(0,0,0,0.55)"
                          mask="url(#face-oval-mask)"
                        />
                        {/* Animated oval border — normal */}
                        <ellipse
                          cx="150" cy="175" rx="90" ry="118"
                          fill="none"
                          stroke="rgba(217,119,87,0.9)"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeDasharray="20 8"
                        >
                          <animateTransform
                            attributeName="transform"
                            type="rotate"
                            from="0 150 175"
                            to="360 150 175"
                            dur="8s"
                            repeatCount="indefinite"
                          />
                        </ellipse>
                        {/* Inner glow ring */}
                        <ellipse
                          cx="150" cy="175" rx="90" ry="118"
                          fill="none"
                          stroke="rgba(217,119,87,0.25)"
                          strokeWidth="6"
                        />
                        {/* Corner scan brackets — top-left */}
                        <path d="M 62 100 L 62 80 L 82 80" fill="none" stroke="#d97757" strokeWidth="3" strokeLinecap="round" />
                        {/* top-right */}
                        <path d="M 218 100 L 218 80 L 198 80" fill="none" stroke="#d97757" strokeWidth="3" strokeLinecap="round" />
                        {/* bottom-left */}
                        <path d="M 62 280 L 62 300 L 82 300" fill="none" stroke="#d97757" strokeWidth="3" strokeLinecap="round" />
                        {/* bottom-right */}
                        <path d="M 218 280 L 218 300 L 198 300" fill="none" stroke="#d97757" strokeWidth="3" strokeLinecap="round" />
                        {/* Horizontal center crosshair line */}
                        <line x1="60" y1="175" x2="88" y2="175" stroke="rgba(217,119,87,0.5)" strokeWidth="1" />
                        <line x1="212" y1="175" x2="240" y2="175" stroke="rgba(217,119,87,0.5)" strokeWidth="1" />
                      </svg>

                      {/* Instruction text at bottom */}
                      <div className="absolute bottom-4 left-0 right-0 flex flex-col items-center gap-1.5">
                        <span className="bg-black/70 backdrop-blur-sm text-white text-[10px] font-bold px-3 py-1.5 rounded-full flex items-center gap-1.5">
                          <span className="material-symbols-outlined !text-[12px] text-[#d97757]">face_retouching_natural</span>
                          Align face within oval · Look straight ahead
                        </span>
                      </div>
                    </div>

                    {/* LIVE badge */}
                    <div className="absolute top-2 left-2 bg-[#C13B3B] text-white text-[9px] font-bold px-2 py-0.5 rounded flex items-center gap-1 z-20">
                      <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                      LIVE
                    </div>
                  </>
                )}

                {/* Capturing — show flash + progress */}
                {verifyState === "capturing" && (
                  <>
                    {capturedFrame ? (
                      <img src={capturedFrame} alt="Captured" className="w-full h-full object-cover" />
                    ) : (
                      <div className="text-[#d97757]">
                        <span className="material-symbols-outlined text-5xl animate-pulse">photo_camera</span>
                      </div>
                    )}
                    {showFlash && (
                      <div className="absolute inset-0 bg-white z-30 pointer-events-none animate-flash" />
                    )}
                  </>
                )}

                {/* Verifying — show captured frame + scanning overlay */}
                {verifyState === "verifying" && (
                  <>
                    {capturedFrame ? (
                      <img src={capturedFrame} alt="Analyzing" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full bg-[#1c1c19]" />
                    )}
                    {/* Laser sweep during AI analysis */}
                    <div className="scanning-line-sweep z-20" />
                    <div className="absolute inset-0 bg-[#d97757]/10 animate-pulse z-15 pointer-events-none mix-blend-overlay" />
                    <div className="absolute bottom-3 left-0 right-0 flex justify-center z-30">
                      <span className="bg-black/70 backdrop-blur-sm text-[#d97757] text-[10px] font-bold px-3 py-1 rounded-full flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#d97757] animate-ping" />
                        AI model computing biometric match...
                      </span>
                    </div>
                  </>
                )}

                {/* Done — show captured frame */}
                {verifyState === "done" && capturedFrame && (
                  <img src={capturedFrame} alt="Live Capture" className="w-full h-full object-cover" />
                )}
                {verifyState === "done" && !capturedFrame && (
                  <div className="w-full h-full flex items-center justify-center text-[#d97757]">
                    <span className="material-symbols-outlined text-5xl">face_retouching_natural</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Hidden canvas for frame capture */}
          <canvas ref={canvasRef} className="hidden" />

          {/* ── Match result panel (shown after done) ─────────────────────── */}
          {verifyState === "done" && (
            <div className="w-full mb-8 animate-slide-up">
              {verifyError ? (
                <div className="rounded-2xl p-5 bg-[#FBF0D6] border border-[#B8860B]/30 flex items-center gap-4 text-[#B8860B]">
                  <span className="material-symbols-outlined icon-fill !text-3xl">warning</span>
                  <div>
                    <p className="font-bold text-sm">Verification Service Error</p>
                    <p className="text-xs mt-0.5">{verifyError}</p>
                  </div>
                </div>
              ) : matchResult ? (
                <div
                  className={`rounded-2xl p-6 flex flex-col items-center gap-3 border ${
                    isMatch ? "bg-[#E5F3EA] border-[#2F8F5B]/30" : "bg-[#FBE3E3] border-[#C13B3B]/30"
                  }`}
                >
                  {/* Score ring */}
                  <div className="relative w-24 h-24 flex items-center justify-center">
                    <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                      <circle cx="50" cy="50" r="42" fill="none" stroke="#E8E2D9" strokeWidth="8" />
                      <circle
                        cx="50" cy="50" r="42"
                        fill="none"
                        stroke={isMatch ? "#2F8F5B" : "#C13B3B"}
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={`${2 * Math.PI * 42}`}
                        strokeDashoffset={`${2 * Math.PI * 42 * (1 - (displayScore ?? 0) / 100)}`}
                        className="transition-all duration-1000"
                      />
                    </svg>
                    <div
                      className={`absolute inset-0 flex flex-col items-center justify-center ${
                        isMatch ? "text-[#2F8F5B]" : "text-[#C13B3B]"
                      }`}
                    >
                      <span className="text-2xl font-extrabold leading-none">{displayScore ?? "—"}</span>
                      <span className="text-[10px] font-bold">%</span>
                    </div>
                  </div>

                  <div
                    className={`flex items-center gap-2 font-extrabold text-lg ${
                      isMatch ? "text-[#2F8F5B]" : "text-[#C13B3B]"
                    }`}
                  >
                    <span className="material-symbols-outlined icon-fill !text-2xl">
                      {isMatch ? "verified_user" : "gpp_bad"}
                    </span>
                    {isMatch ? "Biometric Match Confirmed" : "Face Mismatch Detected"}
                  </div>

                  <p
                    className={`text-xs font-medium text-center max-w-md ${
                      isMatch ? "text-[#2F8F5B]" : "text-[#C13B3B]"
                    }`}
                  >
                    {isMatch
                      ? `Facial geometry matches the document holder photo. Match confidence: ${displayScore}% (threshold 60%).`
                      : `Facial geometric distance exceeds the 60% acceptance threshold. Confidence: ${displayScore}%. Secondary manual inspection required.`}
                  </p>

                  <div className="text-[10px] font-bold text-[#655d54] bg-white/60 px-3 py-1 rounded-full">
                    ArcFace/DeepFace · cosine similarity {matchResult.cosine_similarity.toFixed(3)} · threshold 0.60
                  </div>
                </div>
              ) : null}
            </div>
          )}

          {/* ── Action buttons ─────────────────────────────────────────────── */}
          <div className="flex flex-col sm:flex-row items-center gap-4 w-full max-w-lg">
            {verifyState === "idle" && (
              <button
                onClick={handleCapture}
                className="w-full bg-[#d97757] text-white px-10 py-4 rounded-xl font-bold text-sm shadow-[0px_8px_24px_rgba(217,119,87,0.25)] hover:scale-[1.03] transition-all duration-300 flex items-center justify-center gap-2.5 cursor-pointer active:scale-95"
              >
                <span className="material-symbols-outlined !text-xl">photo_camera</span>
                <span>Capture & Match</span>
              </button>
            )}

            {(verifyState === "capturing" || verifyState === "verifying") && (
              <div className="w-full flex flex-col items-center gap-3">
                <div className="flex items-center gap-2 text-sm font-bold text-[#d97757]">
                  <span className="material-symbols-outlined animate-custom-spin">sync</span>
                  <span>
                    {verifyState === "capturing" ? "Capturing frame..." : "Running biometric comparison..."}
                  </span>
                </div>
                <div className="w-full bg-[#f0ede9] rounded-full h-2 overflow-hidden">
                  <div className="bg-[#d97757] h-2 rounded-full animate-progress" />
                </div>
              </div>
            )}

            {verifyState === "done" && (
              <>
                <button
                  onClick={handleRetake}
                  className="flex-1 px-6 py-3.5 rounded-xl border border-[#E8E2D9] text-[#655d54] hover:text-[#2B2622] hover:bg-[#ede0d5]/40 font-bold text-xs transition-colors cursor-pointer"
                >
                  Retake
                </button>

                {verifyError ? (
                  <button
                    onClick={onDeny}
                    className="flex-1 bg-[#B8860B] text-white px-8 py-4 rounded-xl font-bold text-sm shadow-[0px_8px_24px_rgba(184,134,11,0.25)] hover:scale-[1.03] transition-all flex items-center justify-center gap-2.5 cursor-pointer active:scale-95"
                  >
                    <span className="material-symbols-outlined !text-xl">flag</span>
                    <span>ESCALATE FOR REVIEW</span>
                  </button>
                ) : isMatch ? (
                  <button
                    onClick={onPermit}
                    className="flex-1 bg-[#2F8F5B] text-white px-8 py-4 rounded-xl font-bold text-sm shadow-[0px_8px_24px_rgba(47,143,91,0.25)] hover:scale-[1.03] transition-all flex items-center justify-center gap-2.5 cursor-pointer active:scale-95"
                  >
                    <span className="material-symbols-outlined !text-xl">check_circle</span>
                    <span>PERMIT ENTRY</span>
                  </button>
                ) : (
                  <button
                    onClick={onDeny}
                    className="flex-1 bg-[#C13B3B] text-white px-8 py-4 rounded-xl font-bold text-sm shadow-[0px_8px_24px_rgba(193,59,59,0.25)] hover:scale-[1.03] transition-all flex items-center justify-center gap-2.5 cursor-pointer active:scale-95"
                  >
                    <span className="material-symbols-outlined !text-xl">block</span>
                    <span>DENY ENTRY</span>
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
