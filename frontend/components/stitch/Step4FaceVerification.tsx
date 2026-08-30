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
  // Auto-capture detection state
  const [faceDetected, setFaceDetected] = useState<boolean>(false);
  const [faceAligned, setFaceAligned] = useState<boolean>(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [autoCapSupported, setAutoCapSupported] = useState<boolean>(true);
  // Testing: capture mode toggle
  const [captureMode, setCaptureMode] = useState<"camera" | "upload">("camera");
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectionRef = useRef<{ stableFrames: number; rafId: number; active: boolean }>({
    stableFrames: 0,
    rafId: 0,
    active: false,
  });

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

  // ── Auto-capture: FaceDetector API detection loop ───────────────────────────
  const handleCaptureRef = useRef<() => void>(() => { });

  useEffect(() => {
    if (verifyState !== "idle") {
      detectionRef.current.active = false;
      return;
    }

    // FaceDetector is available in Chrome 74+
    if (!("FaceDetector" in window)) {
      setAutoCapSupported(false);
      return;
    }

    const det = detectionRef.current;
    det.active = true;
    det.stableFrames = 0;
    // Frames needed at ~8fps for 2.5s countdown
    const FRAMES_PER_TICK = 1;
    const STABLE_FOR_AUTO = 20; // ~2.5s

    let faceDetector: any;
    try {
      faceDetector = new (window as any).FaceDetector({ fastMode: true, maxDetectedFaces: 1 });
    } catch {
      setAutoCapSupported(false);
      return;
    }

    const runDetection = async () => {
      if (!det.active || verifyState !== "idle") return;
      const video = videoRef.current;
      if (!video || video.readyState < 2) {
        det.rafId = window.setTimeout(runDetection, 150) as unknown as number;
        return;
      }

      try {
        const faces = await faceDetector.detect(video);
        if (!det.active) return;

        if (faces.length > 0) {
          const face = faces[0];
          const vw = video.videoWidth || 640;
          const vh = video.videoHeight || 480;
          const bb = face.boundingBox;

          // Map oval zone: center ~50% x, ~43% y; width ~60% frame, height ~59%
          const ovalCX = vw * 0.50;
          const ovalCY = vh * 0.43;
          const ovalRX = vw * 0.30;
          const ovalRY = vh * 0.295;

          const faceCX = bb.x + bb.width / 2;
          const faceCY = bb.y + bb.height / 2;

          // Normalized ellipse distance (should be < 0.75 to be "inside")
          const dx = (faceCX - ovalCX) / ovalRX;
          const dy = (faceCY - ovalCY) / ovalRY;
          const dist = Math.sqrt(dx * dx + dy * dy);

          // Face should occupy at least 30% of frame width
          const faceSizeOk = bb.width / vw > 0.28;

          const aligned = dist < 0.80 && faceSizeOk;

          setFaceDetected(true);
          setFaceAligned(aligned);

          if (aligned) {
            det.stableFrames = Math.min(det.stableFrames + FRAMES_PER_TICK, STABLE_FOR_AUTO);
            const remaining = Math.ceil((STABLE_FOR_AUTO - det.stableFrames) / (STABLE_FOR_AUTO / 3));
            setCountdown(Math.max(1, remaining));

            if (det.stableFrames >= STABLE_FOR_AUTO) {
              det.active = false;
              setCountdown(0);
              // Small delay so user sees "0" flash, then auto-capture
              setTimeout(() => handleCaptureRef.current(), 200);
              return;
            }
          } else {
            det.stableFrames = Math.max(0, det.stableFrames - 2);
            setCountdown(null);
          }
        } else {
          setFaceDetected(false);
          setFaceAligned(false);
          setCountdown(null);
          det.stableFrames = Math.max(0, det.stableFrames - 1);
        }
      } catch {
        // Detection failed this frame — skip
      }

      det.rafId = window.setTimeout(runDetection, 120) as unknown as number;
    };

    runDetection();

    return () => {
      det.active = false;
      clearTimeout(det.rafId);
      setFaceDetected(false);
      setFaceAligned(false);
      setCountdown(null);
    };
  }, [verifyState]);

  // ── Capture + Verify ────────────────────────────────────────────────────────
  const handleCapture = async () => {
    // Stop detection loop
    detectionRef.current.active = false;
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
        await new Promise<void>((resolve) => {
          canvas.toBlob((blob) => { frameBlob = blob; resolve(); }, "image/jpeg", 0.92);
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
      setVerifyError("Face verification service unavailable. Please retry or escalate.");
    }
    setVerifyState("done");
  };

  // Keep handleCaptureRef in sync so the detection loop can call it
  handleCaptureRef.current = handleCapture;

  const handleRetake = () => {
    setVerifyState("idle");
    setCapturedFrame(null);
    setMatchResult(null);
    setVerifyError(null);
    setShowFlash(false);
    setUploadedImage(null);
  };

  // ── Upload mode: file selected ─────────────────────────────────────────
  const handleUploadFile = async (file: File) => {
    if (!file.type.startsWith("image/")) return;
    const dataUrl = URL.createObjectURL(file);
    setUploadedImage(dataUrl);
    setCapturedFrame(dataUrl);
    setVerifyError(null);
    setVerifyState("verifying");

    if (onVerifyFace) {
      try {
        const result = await onVerifyFace(file);
        if (result) { setMatchResult(result); setVerifyState("done"); return; }
      } catch (err) {
        console.error("[Step4/upload] verifyFace error:", err);
      }
    }
    const backendFace = pipelineData?.face?.one_to_one ?? null;
    if (backendFace) { setMatchResult(backendFace); }
    else { setVerifyError("Face verification service unavailable."); }
    setVerifyState("done");
  };

  // ── Mode switch: stop camera when switching to upload ─────────────────────
  const switchMode = (mode: "camera" | "upload") => {
    if (mode === "upload") {
      detectionRef.current.active = false;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    }
    setCaptureMode(mode);
    setVerifyState("idle");
    setCapturedFrame(null);
    setMatchResult(null);
    setVerifyError(null);
    setUploadedImage(null);
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

            {/* Right: Live camera / upload — with mode toggle */}
            <div className="flex flex-col items-center gap-3">

              {/* Mode toggle — shown only before capture */}
              {verifyState === "idle" && (
                <div className="flex items-center gap-2 w-full">
                  <button
                    id="mode-camera"
                    onClick={() => switchMode("camera")}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[10px] font-bold border transition-all cursor-pointer ${
                      captureMode === "camera"
                        ? "bg-[#d97757] border-[#d97757] text-white shadow-sm"
                        : "bg-white border-[#E8E2D9] text-[#655d54] hover:border-[#d97757]/50"
                    }`}
                  >
                    <span className="material-symbols-outlined !text-[14px]">videocam</span>
                    Live Camera
                  </button>
                  <button
                    id="mode-upload"
                    onClick={() => switchMode("upload")}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[10px] font-bold border transition-all cursor-pointer ${
                      captureMode === "upload"
                        ? "bg-[#B8860B] border-[#B8860B] text-white shadow-sm"
                        : "bg-white border-[#E8E2D9] text-[#655d54] hover:border-[#B8860B]/50"
                    }`}
                  >
                    <span className="material-symbols-outlined !text-[14px]">upload_file</span>
                    Upload Image
                    <span className="bg-white/20 text-[8px] px-1 py-0.5 rounded font-extrabold">TEST</span>
                  </button>
                </div>
              )}

              {/* Panel label */}
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#655d54] w-full">
                <span className="material-symbols-outlined !text-[16px]">
                  {verifyState === "done" ? "photo_camera" : captureMode === "upload" ? "upload_file" : "videocam"}
                </span>
                <span>
                  {verifyState === "done" ? "Captured Frame" : captureMode === "upload" ? "Upload Face Image" : "Live Camera Feed"}
                </span>
              </div>
              <div className="w-full aspect-[3/4] rounded-2xl overflow-hidden border-2 border-[#d97757]/50 bg-[#1c1c19] shadow-sm relative flex items-center justify-center">

                {/* Idle state: Live Camera OR Image Upload (Test Mode) */}
                {verifyState === "idle" && captureMode === "upload" && (
                  <div
                    onClick={() => uploadInputRef.current?.click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const file = e.dataTransfer.files?.[0];
                      if (file) handleUploadFile(file);
                    }}
                    className="w-full h-full flex flex-col items-center justify-center p-6 text-center cursor-pointer border-2 border-dashed border-[#B8860B]/40 hover:border-[#B8860B] hover:bg-[#B8860B]/5 transition-all group"
                  >
                    <input
                      ref={uploadInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadFile(file);
                      }}
                    />
                    <div className="w-16 h-16 rounded-2xl bg-[#B8860B]/10 flex items-center justify-center text-[#B8860B] mb-3 group-hover:scale-110 transition-transform">
                      <span className="material-symbols-outlined text-3xl">upload_file</span>
                    </div>
                    <p className="text-sm font-bold text-[#2B2622]">Upload Traveler Face Photo</p>
                    <p className="text-xs text-[#88726c] mt-1 max-w-[200px]">
                      Drag and drop image here, or click to browse (Test Mode)
                    </p>
                    <span className="mt-4 px-3 py-1 bg-[#B8860B] text-white text-[10px] font-bold rounded-full">
                      Select Image
                    </span>
                  </div>
                )}

                {/* Idle state: Live video */}
                {verifyState === "idle" && captureMode === "camera" && (
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
                      {/* Dynamic SVG — color changes based on detection state */}
                      {(() => {
                        const ovalColor = faceAligned
                          ? "rgba(47,143,91,1)"      // green — aligned
                          : faceDetected
                          ? "rgba(184,134,11,1)"     // amber — face found, not centred
                          : "rgba(217,119,87,0.9)";  // orange — no face

                        const glowColor = faceAligned
                          ? "rgba(47,143,91,0.25)"
                          : faceDetected
                          ? "rgba(184,134,11,0.20)"
                          : "rgba(217,119,87,0.20)";

                        const bracketColor = faceAligned
                          ? "#2F8F5B"
                          : faceDetected
                          ? "#B8860B"
                          : "#d97757";

                        const animDur = faceAligned ? "2s" : "8s";

                        return (
                          <svg
                            className="absolute inset-0 w-full h-full"
                            viewBox="0 0 300 400"
                            preserveAspectRatio="xMidYMid slice"
                            xmlns="http://www.w3.org/2000/svg"
                          >
                            <defs>
                              <mask id="face-oval-mask-dyn">
                                <rect width="300" height="400" fill="white" />
                                <ellipse cx="150" cy="175" rx="90" ry="118" fill="black" />
                              </mask>
                            </defs>
                            {/* Darkened surround */}
                            <rect
                              width="300" height="400"
                              fill={faceAligned ? "rgba(0,0,0,0.35)" : "rgba(0,0,0,0.55)"}
                              mask="url(#face-oval-mask-dyn)"
                            />
                            {/* Animated dashed oval */}
                            <ellipse
                              cx="150" cy="175" rx="90" ry="118"
                              fill="none"
                              stroke={ovalColor}
                              strokeWidth={faceAligned ? "3" : "2.5"}
                              strokeLinecap="round"
                              strokeDasharray={faceAligned ? "560" : "20 8"}
                              style={{ transition: "stroke 0.3s, stroke-dasharray 0.5s" }}
                            >
                              <animateTransform
                                attributeName="transform"
                                type="rotate"
                                from="0 150 175"
                                to="360 150 175"
                                dur={animDur}
                                repeatCount="indefinite"
                              />
                            </ellipse>
                            {/* Inner glow ring */}
                            <ellipse
                              cx="150" cy="175" rx="90" ry="118"
                              fill={faceAligned ? "rgba(47,143,91,0.08)" : "none"}
                              stroke={glowColor}
                              strokeWidth="7"
                              style={{ transition: "all 0.3s" }}
                            />
                            {/* Corner brackets */}
                            <path d="M 62 100 L 62 80 L 82 80" fill="none" stroke={bracketColor} strokeWidth="3" strokeLinecap="round" />
                            <path d="M 218 100 L 218 80 L 198 80" fill="none" stroke={bracketColor} strokeWidth="3" strokeLinecap="round" />
                            <path d="M 62 280 L 62 300 L 82 300" fill="none" stroke={bracketColor} strokeWidth="3" strokeLinecap="round" />
                            <path d="M 218 280 L 218 300 L 198 300" fill="none" stroke={bracketColor} strokeWidth="3" strokeLinecap="round" />
                            {/* Crosshairs */}
                            <line x1="60" y1="175" x2="88" y2="175" stroke={`${bracketColor}80`} strokeWidth="1" />
                            <line x1="212" y1="175" x2="240" y2="175" stroke={`${bracketColor}80`} strokeWidth="1" />
                            {/* Countdown number inside oval */}
                            {countdown !== null && countdown > 0 && (
                              <text
                                x="150" y="195"
                                textAnchor="middle"
                                fontSize="72"
                                fontWeight="900"
                                fill={faceAligned ? "rgba(47,143,91,0.9)" : "rgba(255,255,255,0.6)"}
                                style={{ fontFamily: "sans-serif" }}
                              >
                                {countdown}
                              </text>
                            )}
                            {countdown === 0 && (
                              <text
                                x="150" y="185"
                                textAnchor="middle"
                                fontSize="22"
                                fontWeight="900"
                                fill="rgba(47,143,91,1)"
                                style={{ fontFamily: "sans-serif" }}
                              >
                                AUTO CAPTURING
                              </text>
                            )}
                          </svg>
                        );
                      })()}

                      {/* Bottom instruction pill — updates live */}
                      <div className="absolute bottom-4 left-0 right-0 flex flex-col items-center gap-1.5">
                        <span
                          className={`backdrop-blur-sm text-white text-[10px] font-bold px-3 py-1.5 rounded-full flex items-center gap-1.5 transition-all ${
                            faceAligned
                              ? "bg-[#2F8F5B]/80"
                              : faceDetected
                              ? "bg-[#B8860B]/80"
                              : "bg-black/70"
                          }`}
                        >
                          <span className="material-symbols-outlined !text-[12px]">
                            {faceAligned ? "check_circle" : faceDetected ? "center_focus_weak" : "face_retouching_natural"}
                          </span>
                          {faceAligned && countdown !== null
                            ? `Hold still — capturing in ${countdown}...`
                            : faceDetected
                            ? "Move closer & centre your face in the oval"
                            : autoCapSupported
                            ? "Align face within oval · Look straight ahead"
                            : "Align face within oval · Click Capture when ready"}
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
                  className={`rounded-2xl p-6 flex flex-col items-center gap-3 border ${isMatch ? "bg-[#E5F3EA] border-[#2F8F5B]/30" : "bg-[#FBE3E3] border-[#C13B3B]/30"
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
                      className={`absolute inset-0 flex flex-col items-center justify-center ${isMatch ? "text-[#2F8F5B]" : "text-[#C13B3B]"
                        }`}
                    >
                      <span className="text-2xl font-extrabold leading-none">{displayScore ?? "—"}</span>
                      <span className="text-[10px] font-bold">%</span>
                    </div>
                  </div>

                  <div
                    className={`flex items-center gap-2 font-extrabold text-lg ${isMatch ? "text-[#2F8F5B]" : "text-[#C13B3B]"
                      }`}
                  >
                    <span className="material-symbols-outlined icon-fill !text-2xl">
                      {isMatch ? "verified_user" : "gpp_bad"}
                    </span>
                    {isMatch ? "Biometric Match Confirmed" : "Face Mismatch Detected"}
                  </div>

                  <p
                    className={`text-xs font-medium text-center max-w-md ${isMatch ? "text-[#2F8F5B]" : "text-[#C13B3B]"
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
              captureMode === "upload" ? (
                <button
                  onClick={() => uploadInputRef.current?.click()}
                  className="w-full bg-[#B8860B] text-white px-10 py-4 rounded-xl font-bold text-sm shadow-[0px_8px_24px_rgba(184,134,11,0.25)] hover:scale-[1.03] transition-all duration-300 flex items-center justify-center gap-2.5 cursor-pointer active:scale-95"
                >
                  <span className="material-symbols-outlined !text-xl">upload_file</span>
                  <span>Select Image to Verify (Test Mode)</span>
                </button>
              ) : (
                <button
                  onClick={handleCapture}
                  className="w-full bg-[#d97757] text-white px-10 py-4 rounded-xl font-bold text-sm shadow-[0px_8px_24px_rgba(217,119,87,0.25)] hover:scale-[1.03] transition-all duration-300 flex items-center justify-center gap-2.5 cursor-pointer active:scale-95"
                >
                  <span className="material-symbols-outlined !text-xl">photo_camera</span>
                  <span>Capture & Match</span>
                </button>
              )
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
