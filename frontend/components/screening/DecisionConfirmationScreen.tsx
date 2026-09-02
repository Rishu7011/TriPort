"use client";

import React from "react";
import type { DecisionResponse, RiskBand } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthContext";

interface DecisionConfirmationScreenProps {
  decisionData: DecisionResponse;
  travelerName: string;
  documentId: string;
  riskBand?: RiskBand | string | null;
  riskScore?: number | null;
  onReset: () => void;
}

export function DecisionConfirmationScreen({
  decisionData,
  travelerName,
  documentId,
  riskBand,
  riskScore,
  onReset,
}: DecisionConfirmationScreenProps) {
  const { user } = useAuth();
  const isApproved = decisionData.decision.toLowerCase() === "approve";
  const now = new Date();
  const utcTimeStr = `${now.getUTCHours().toString().padStart(2, "0")}:${now
    .getUTCMinutes()
    .toString()
    .padStart(2, "0")}:${now.getUTCSeconds().toString().padStart(2, "0")} UTC`;

  const checkpointLabel = user?.checkpoint_id
    ? `STATION / ${user.checkpoint_id.substring(0, 8).toUpperCase()}`
    : "STATION-04 / LHR-UK";

  const riskLabel = riskBand
    ? `${riskBand.toUpperCase()}${
        riskScore !== null && riskScore !== undefined
          ? ` (${riskScore.toFixed(1)})`
          : ""
      }`
    : "REJECTED AT STAGE 1 (DOCUMENT FORENSICS)";

  return (
    <div className="flex flex-col w-full justify-center items-center px-4 sm:px-8 py-8 relative overflow-hidden">
      {/* Glow Backdrops */}
      <div
        className={`absolute top-1/4 left-1/4 w-96 h-96 rounded-full blur-3xl pointer-events-none opacity-10 ${
          isApproved ? "bg-primary-fixed" : "bg-error"
        }`}
      />
      <div
        className={`absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full blur-3xl pointer-events-none opacity-10 ${
          isApproved ? "bg-primary-fixed" : "bg-error"
        }`}
      />

      <div className="w-full max-w-2xl bg-surface-container-low border border-outline-variant/60 p-8 shadow-2xl relative z-10 flex flex-col items-center">
        {/* Status Badge */}
        <div className="flex flex-col items-center mb-6">
          <div
            className={`w-24 h-24 rounded-full border-2 flex items-center justify-center mb-4 relative ${
              isApproved
                ? "bg-primary-fixed/10 border-primary-fixed text-primary-fixed shadow-[0_0_25px_rgba(192,245,0,0.2)]"
                : "bg-error/10 border-error text-error shadow-[0_0_25px_rgba(255,59,48,0.2)]"
            }`}
          >
            <span
              className="material-symbols-outlined text-[48px] z-10"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              {isApproved ? "check_circle" : "block"}
            </span>
            <div
              className={`absolute inset-0 rounded-full animate-ping opacity-20 ${
                isApproved ? "bg-primary-fixed" : "bg-error"
              }`}
            />
          </div>

          <h1
            className={`font-headline-lg uppercase tracking-widest text-center ${
              isApproved ? "text-primary-fixed" : "text-error"
            }`}
          >
            {isApproved ? "Entry Approved" : "Entry Rejected"}
          </h1>
          <div className="mt-1 font-label-caps text-on-surface-variant tracking-[0.2em] uppercase text-xs">
            {isApproved ? "AUTHORIZATION COMPLETE" : "ENTRY FORMALLY DENIED"}
          </div>
        </div>

        {/* Data Summary Table */}
        <div className="w-full bg-surface-container border border-outline-variant/60 p-6 mb-6 relative">
          <table className="w-full text-left border-collapse">
            <tbody>
              <tr className="border-b border-outline-variant/30">
                <th className="py-3 pr-4 font-label-caps text-on-surface-variant text-xs w-1/3">
                  DOCUMENT ID
                </th>
                <td className="py-3 font-data-mono-md text-on-surface text-xs font-semibold">
                  {documentId}
                </td>
              </tr>
              <tr className="border-b border-outline-variant/30">
                <th className="py-3 pr-4 font-label-caps text-on-surface-variant text-xs w-1/3">
                  TRAVELER NAME
                </th>
                <td className="py-3 font-data-mono-lg text-on-surface font-semibold tracking-wide">
                  {travelerName || "IDENTIFIED TRAVELER"}
                </td>
              </tr>
              <tr className="border-b border-outline-variant/30">
                <th className="py-3 pr-4 font-label-caps text-on-surface-variant text-xs w-1/3">
                  CHECKPOINT
                </th>
                <td className="py-3 font-data-mono-md text-on-surface text-xs">
                  {checkpointLabel}
                </td>
              </tr>
              <tr className="border-b border-outline-variant/30">
                <th className="py-3 pr-4 font-label-caps text-on-surface-variant text-xs w-1/3">
                  TIME OF RECORD
                </th>
                <td className="py-3 font-data-mono-md text-on-surface text-xs">
                  {utcTimeStr}
                </td>
              </tr>
              <tr>
                <th className="py-3 pr-4 font-label-caps text-on-surface-variant text-xs w-1/3">
                  FINAL RISK BAND
                </th>
                <td
                  className={`py-3 font-data-mono-md font-bold text-xs uppercase ${
                    isApproved ? "text-primary-fixed" : "text-error"
                  }`}
                >
                  {riskLabel}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Action Button: Reset to Screen 1 */}
        <button
          type="button"
          onClick={onReset}
          className="w-full bg-primary-fixed hover:bg-primary-fixed-dim text-on-primary-fixed font-headline-md py-4 px-8 transition-all duration-200 uppercase tracking-wider flex items-center justify-center gap-2 group cursor-pointer shadow-[0_0_15px_rgba(192,245,0,0.25)]"
        >
          <span>SCREEN NEXT TRAVELER</span>
          <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">
            arrow_forward
          </span>
        </button>

        {/* Audit Sequence Reference */}
        <div className="mt-4 font-data-mono-md text-[11px] text-on-surface-variant/70 flex items-center gap-1.5 uppercase">
          <span className="material-symbols-outlined text-[14px]">lock</span>
          <span>
            LOGGED SECURELY IN AUDIT LEDGER // SEQUENCE #
            {decisionData.ledger_sequence ?? "RECORDED"}
          </span>
        </div>
      </div>
    </div>
  );
}
