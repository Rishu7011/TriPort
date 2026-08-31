"use client";

import React from "react";

export type ScreenId =
  | "step1_upload"
  | "step2_scanning"
  | "step3_extraction"
  | "step4_face"
  | "step4_confirm"
  | "admin_queue";

interface ScreenSwitcherNavProps {
  currentScreen: ScreenId;
  onSelectScreen: (screen: ScreenId) => void;
  role: string;
  onRoleChange: (role: string) => void;
}

const SCREENS: { id: ScreenId; label: string; icon: string; stepBadge?: string }[] = [
  { id: "step1_upload", label: "Upload", icon: "upload_file", stepBadge: "1" },
  { id: "step2_scanning", label: "Scanning", icon: "sync", stepBadge: "2" },
  { id: "step3_extraction", label: "Extraction & MRZ", icon: "crop_free", stepBadge: "3" },
  { id: "step4_face", label: "Face Verify", icon: "face", stepBadge: "4" },
  { id: "step4_confirm", label: "Decision", icon: "task_alt", stepBadge: "✓" },
  { id: "admin_queue", label: "Admin Queue", icon: "list_alt" },
];

export const ScreenSwitcherNav: React.FC<ScreenSwitcherNavProps> = ({
  currentScreen,
  onSelectScreen,
  role,
  onRoleChange,
}) => {
  return (
    <header className="sticky top-0 left-0 w-full z-50 bg-[#FAF8F5]/90 backdrop-blur-md border-b border-[#E8E2D9] shadow-[0px_4px_20px_rgba(43,38,34,0.04)]">
      <div className="max-w-[1440px] mx-auto px-6 py-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Left: Brand + Officer status */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => onSelectScreen("step1_upload")}
            className="text-left font-bold text-2xl tracking-tight text-[#99462a] hover:opacity-90 transition-opacity flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-[#d97757] !text-2xl">
              security
            </span>
            <span>TriPort</span>
          </button>

          <span className="hidden lg:inline-block w-px h-5 bg-[#E8E2D9]" />

          <div className="hidden lg:flex items-center gap-2 text-xs font-semibold text-[#655d54] tracking-wide">
            <span className="inline-block w-2 h-2 rounded-full bg-[#2F8F5B] animate-pulse" />
            <span>Checkpoint: Alpha-7 · Officer: J. Miller</span>
          </div>
        </div>

        {/* Center: Step Switcher Bar */}
        <nav className="flex items-center gap-1.5 overflow-x-auto py-1 scrollbar-none">
          {SCREENS.map((s) => {
            const isActive = currentScreen === s.id;
            return (
              <button
                key={s.id}
                onClick={() => onSelectScreen(s.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 whitespace-nowrap cursor-pointer ${
                  isActive
                    ? "bg-[#d97757] text-white shadow-[0px_4px_12px_rgba(217,119,87,0.3)] scale-[1.03]"
                    : "bg-[#FAF8F5] text-[#655d54] hover:bg-[#ede0d5]/60 hover:text-[#2B2622] border border-[#E8E2D9]"
                }`}
              >
                <span
                  className={`material-symbols-outlined !text-[16px] ${
                    isActive ? "icon-fill" : ""
                  }`}
                >
                  {s.icon}
                </span>
                <span>{s.label}</span>
                {s.stepBadge && (
                  <span
                    className={`ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                      isActive
                        ? "bg-white/20 text-white"
                        : "bg-[#ede0d5] text-[#655d54]"
                    }`}
                  >
                    {s.stepBadge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Right: Role selection & Avatar */}
        <div className="flex items-center gap-3 self-end md:self-auto">
          <select
            value={role}
            onChange={(e) => onRoleChange(e.target.value)}
            className="text-xs font-semibold bg-[#FAF8F5] border border-[#E8E2D9] text-[#2B2622] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#d97757] cursor-pointer"
          >
            <option value="officer">Officer (Field)</option>
            <option value="supervisor">Supervisor (Escalations)</option>
            <option value="auditor">Auditor (Compliance)</option>
            <option value="admin">System Admin</option>
          </select>

          <div className="w-8 h-8 rounded-full bg-[#d97757] flex items-center justify-center flex-shrink-0 border border-[#E8E2D9] shadow-sm">
            <span className="material-symbols-outlined !text-[18px] text-white">person</span>
          </div>
        </div>
      </div>
    </header>
  );
};
