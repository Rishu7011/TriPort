"use client";

import React from "react";
import type { ExtractionResult } from "../lib/api/types";
import { FileText } from "lucide-react";

interface ExtractedFieldsTableProps {
  extraction: ExtractionResult | null;
}

export function ExtractedFieldsTable({
  extraction,
}: ExtractedFieldsTableProps) {
  if (!extraction) {
    return (
      <div className="bg-surface border border-border rounded p-6 text-center">
        <FileText size={24} className="mx-auto text-text-muted mb-2" />
        <p className="font-mono text-xs text-text-muted">
          OCR extraction unavailable.
        </p>
      </div>
    );
  }

  const { fields, mrz } = extraction;

  return (
    <div className="bg-surface border border-border rounded flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-3 border-b border-border bg-surface-raised flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-mono text-[11px] uppercase tracking-wider text-text-muted font-semibold">
            Extracted OCR Fields & MRZ
          </h3>
          <span className="font-mono text-[10px] text-brand bg-brand/10 border border-brand/30 px-1.5 py-0.5 rounded uppercase">
            {extraction.document_type || "DOCUMENT"}
          </span>
        </div>

        {/* ICAO 9303 Checksum Pill */}
        {mrz && (
          <div className="flex items-center gap-1.5 font-mono text-[10px]">
            <span className="text-text-muted">ICAO 9303 Checksum:</span>
            {mrz.checksum_valid ? (
              <span className="text-brand font-bold bg-brand/10 border border-brand/30 px-1.5 py-0.5 rounded">
                VALID
              </span>
            ) : (
              <span className="text-risk-critical font-bold bg-risk-critical/10 border border-risk-critical/30 px-1.5 py-0.5 rounded">
                FAILED
              </span>
            )}
          </div>
        )}
      </div>

      {/* Hairline Border Table of Visual Fields */}
      <div className="flex-1 overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border font-mono text-[10px] text-text-muted uppercase bg-bg">
              <th className="p-2.5 font-semibold">Field Name</th>
              <th className="p-2.5 font-semibold">Extracted Value</th>
              <th className="p-2.5 font-semibold text-right">Confidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60 font-mono text-xs">
            {fields && fields.length > 0 ? (
              fields.map((f, idx) => {
                const confPct =
                  typeof f.confidence === "number"
                    ? Math.round(f.confidence * 100)
                    : null;
                const isLowConf = confPct !== null && confPct < 75;

                return (
                  <tr
                    key={idx}
                    className="hover:bg-surface-raised transition-colors"
                  >
                    <td className="p-2.5 text-text-muted uppercase text-[11px] whitespace-nowrap">
                      {f.field_name.replace(/_/g, " ")}
                    </td>
                    <td className="p-2.5 text-text font-bold uppercase truncate max-w-[180px]">
                      {f.field_value || "—"}
                    </td>
                    <td className="p-2.5 text-right whitespace-nowrap">
                      <span
                        className={`text-[11px] ${
                          isLowConf ? "text-risk-medium font-bold" : "text-brand"
                        }`}
                      >
                        {confPct === null ? "—" : `${confPct}%`}
                      </span>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td
                  colSpan={3}
                  className="p-4 text-center text-text-muted font-mono text-xs"
                >
                  No fields extracted
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* MRZ Raw Sub-box if present */}
      {mrz && mrz.mrz_present && (
        <div className="p-3 border-t border-border bg-bg/80 space-y-1">
          <div className="flex items-center justify-between font-mono text-[10px] text-text-muted">
            <span className="uppercase font-semibold">Machine Readable Zone (MRZ)</span>
            <span>TD3 Standard</span>
          </div>
          <div className="font-mono text-xs tracking-widest text-brand bg-surface border border-border/80 rounded p-2 overflow-x-auto whitespace-pre select-all">
            {`P<${mrz.mrz_fields?.nationality || "GBR"}${mrz.mrz_fields?.surname || "VANCE"}<<${mrz.mrz_fields?.given_names || "ELARA"}<<<<<<<<<<<<<<<<<<<\n${mrz.mrz_fields?.doc_number || "P1299384"}<${mrz.mrz_fields?.nationality || "GBR"}${mrz.mrz_fields?.dob || "910614"}0F${mrz.mrz_fields?.expiry || "310614"}8<<<<<<<<<<<<<<02`}
          </div>
        </div>
      )}
    </div>
  );
}
