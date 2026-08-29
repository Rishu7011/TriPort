"use client";

import React, { useState, useRef } from "react";
import { Upload, Camera, FileText, CheckCircle2, AlertCircle, Sparkles, RefreshCw, X } from "lucide-react";

interface DocumentUploaderProps {
  onUpload: (file: File, liveFile?: File | null, presetName?: string) => Promise<void>;
  loading: boolean;
}

export const DocumentUploader: React.FC<DocumentUploaderProps> = ({ onUpload, loading }) => {
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docPreview, setDocPreview] = useState<string | null>(null);
  const [liveFile, setLiveFile] = useState<File | null>(null);
  const [livePreview, setLivePreview] = useState<string | null>(null);
  const [useCamera, setUseCamera] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Drag & drop handlers
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setDocFile(file);
      setDocPreview(URL.createObjectURL(file));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setDocFile(file);
      setDocPreview(URL.createObjectURL(file));
    }
  };

  // Webcam capture
  const startCamera = async () => {
    setUseCamera(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
    } catch (err) {
      console.warn("Webcam access denied or unavailable:", err);
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => {
        if (blob) {
          const file = new File([blob], "live_capture.jpg", { type: "image/jpeg" });
          setLiveFile(file);
          setLivePreview(canvas.toDataURL("image/jpeg"));
        }
      }, "image/jpeg", 0.95);
    }
    // Stop camera
    const stream = videoRef.current.srcObject as MediaStream;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }
    setUseCamera(false);
  };

  const handleSubmit = async () => {
    if (!docFile) return;
    await onUpload(docFile, liveFile);
  };

  // Preset sample runner
  const handlePresetSelect = async (presetType: string) => {
    await onUpload(null as any, null, presetType);
  };

  return (
    <div className="space-y-6">
      {/* Quick Demo Preset Selection Bar */}
      <div className="glass-panel p-4 rounded-xl border border-cyan-500/30">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          <h4 className="text-xs font-bold font-mono tracking-wider text-slate-200 uppercase">
            Quick-Test Evaluator Presets (1-Click Screening Scenarios)
          </h4>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
          <button
            onClick={() => handlePresetSelect("genuine")}
            disabled={loading}
            className="p-2.5 rounded-lg bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-500/40 text-emerald-300 font-mono text-[11px] font-bold text-left transition-all disabled:opacity-50"
          >
            <span className="block text-emerald-400">🟢 Genuine Passport</span>
            <span className="text-[9px] text-slate-400 font-normal">Clean MRZ + ELA clear</span>
          </button>

          <button
            onClick={() => handlePresetSelect("photoswap")}
            disabled={loading}
            className="p-2.5 rounded-lg bg-red-950/40 hover:bg-red-900/60 border border-red-500/40 text-red-300 font-mono text-[11px] font-bold text-left transition-all disabled:opacity-50"
          >
            <span className="block text-red-400">🔴 Photo-Swap Tamper</span>
            <span className="text-[9px] text-slate-400 font-normal">Splice anomaly detected</span>
          </button>

          <button
            onClick={() => handlePresetSelect("textedit")}
            disabled={loading}
            className="p-2.5 rounded-lg bg-orange-950/40 hover:bg-orange-900/60 border border-orange-500/40 text-orange-300 font-mono text-[11px] font-bold text-left transition-all disabled:opacity-50"
          >
            <span className="block text-orange-400">🟠 Text-Edit Tamper</span>
            <span className="text-[9px] text-slate-400 font-normal">Date compression spike</span>
          </button>

          <button
            onClick={() => handlePresetSelect("expired")}
            disabled={loading}
            className="p-2.5 rounded-lg bg-amber-950/40 hover:bg-amber-900/60 border border-amber-500/40 text-amber-300 font-mono text-[11px] font-bold text-left transition-all disabled:opacity-50"
          >
            <span className="block text-amber-400">🟡 Expired Passport</span>
            <span className="text-[9px] text-slate-400 font-normal">Rule engine violation</span>
          </button>

          <button
            onClick={() => handlePresetSelect("blacklist")}
            disabled={loading}
            className="p-2.5 rounded-lg bg-purple-950/40 hover:bg-purple-900/60 border border-purple-500/40 text-purple-300 font-mono text-[11px] font-bold text-left transition-all disabled:opacity-50"
          >
            <span className="block text-purple-400">🚨 Watchlist / Blacklist</span>
            <span className="text-[9px] text-slate-400 font-normal">Interpol match trigger</span>
          </button>
        </div>
      </div>

      {/* Dual Upload / Webcam Ingestion Deck */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Document Ingestion Zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`glass-panel relative rounded-xl p-6 border-2 border-dashed flex flex-col items-center justify-center min-h-[220px] cursor-pointer transition-all ${
            isDragOver ? "border-cyan-400 bg-cyan-950/20" : "border-slate-800 hover:border-slate-700 bg-slate-950/60"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />

          {loading && <div className="radar-scanner-line" />}

          {docPreview ? (
            <div className="relative w-full h-full max-h-[180px] flex items-center justify-center">
              <img
                src={docPreview}
                alt="Document Scan"
                className="max-h-[170px] rounded object-contain"
              />
              <button
                onClick={(e) => { e.stopPropagation(); setDocFile(null); setDocPreview(null); }}
                className="absolute top-0 right-0 p-1.5 rounded-full bg-slate-900/90 text-slate-300 hover:text-red-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 text-center">
              <div className="p-3 rounded-full bg-slate-900 border border-slate-800 text-cyan-400">
                <Upload className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs font-bold font-mono text-slate-200 block">
                  DROP PASSPORT SCAN OR CLICK TO BROWSE
                </span>
                <span className="text-[10px] font-mono text-slate-500">
                  Supports JPEG, PNG, TIFF, WebP (ICAO TD3 / TD1)
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Live Biometric Camera Zone */}
        <div className="glass-panel rounded-xl p-6 border border-slate-800 flex flex-col items-center justify-center min-h-[220px] bg-slate-950/60">
          {useCamera ? (
            <div className="relative w-full flex flex-col items-center">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                className="w-full max-h-[160px] object-cover rounded-lg bg-black"
              />
              <button
                onClick={capturePhoto}
                className="mt-3 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-bold flex items-center gap-2 shadow-lg"
              >
                <Camera className="w-4 h-4" />
                <span>Snap Live Photo</span>
              </button>
            </div>
          ) : livePreview ? (
            <div className="relative w-full max-h-[180px] flex items-center justify-center">
              <img
                src={livePreview}
                alt="Live Snapshot"
                className="max-h-[170px] rounded object-contain"
              />
              <button
                onClick={() => { setLiveFile(null); setLivePreview(null); }}
                className="absolute top-0 right-0 p-1.5 rounded-full bg-slate-900/90 text-slate-300 hover:text-red-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 text-center">
              <div className="p-3 rounded-full bg-slate-900 border border-slate-800 text-emerald-400">
                <Camera className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs font-bold font-mono text-slate-200 block">
                  LIVE CHECKPOINT WEBCAM (1:1 BIOMETRICS)
                </span>
                <span className="text-[10px] font-mono text-slate-500 block mb-2">
                  Captures traveler portrait for facial cosine similarity match
                </span>
                <button
                  onClick={startCamera}
                  className="px-3 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 font-mono text-xs"
                >
                  Activate Camera
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Execute Pipeline Button */}
      {docFile && (
        <div className="flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-600 to-emerald-600 hover:from-cyan-500 hover:to-emerald-500 text-white font-mono text-xs font-bold tracking-wider uppercase shadow-xl shadow-cyan-500/20 transition-all disabled:opacity-50"
          >
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>SCREENING FORENSIC PIPELINE RUNNING...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>EXECUTE FORENSIC PIPELINE</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
};
