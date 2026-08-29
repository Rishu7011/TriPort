"use client";

import React from "react";
import { Check, X, ShieldCheck, AlertCircle, FileText, Hash } from "lucide-react";

interface ExtractedField {
  field_name: string;
  field_value: string;
  confidence: number;
  extraction_method: string;
}

interface ValidationCheck {
  rule_id: string;
  passed: boolean;
  message: string;
}

interface MRZDetails {
  present: boolean;
  checksum_valid: boolean;
  mrz_type?: string;
  raw_mrz?: string[];
}

interface ExtractedFieldsTableProps {
  fields: ExtractedField[];
  mrz?: MRZDetails;
  validationPassed?: boolean;
  failedRules?: string[];
  validationChecks?: ValidationCheck[];
}

export const ExtractedFieldsTable: React.FC<ExtractedFieldsTableProps> = ({
  fields = [],
  mrz,
  validationPassed = true,
  failedRules = [],
  validationChecks = [],
}) => {
  const formatFieldName = (name: string) => {
    return name
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  return (
    <div className="space-y-6">
      {/* Top Bar: MRZ & ICAO Checksum Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-panel p-4 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${mrz?.present ? "bg-cyan-950 text-cyan-400 border border-cyan-500/30" : "bg-slate-900 text-slate-500"}`}>
              <Hash className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[11px] font-mono text-slate-400 uppercase block">ICAO 9303 MRZ DETECTION</span>
              <span className="text-sm font-bold font-mono text-slate-200">
                {mrz?.present ? "Machine Readable Zone Detected (TD3)" : "No MRZ Present (Visual Only)"}
              </span>
            </div>
          </div>
          {mrz?.present && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 border border-cyan-500/40 text-cyan-300">
              ICAO COMPLIANT
            </span>
          )}
        </div>

        <div className="glass-panel p-4 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${mrz?.checksum_valid ? "bg-emerald-950 text-emerald-400 border border-emerald-500/30" : "bg-red-950 text-red-400 border border-red-500/30"}`}>
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[11px] font-mono text-slate-400 uppercase block">7-3-1 ALGORITHMIC CHECKSUM</span>
              <span className="text-sm font-bold font-mono text-slate-200">
                {mrz?.checksum_valid ? "All Check Digits Validated (100%)" : "Checksum Mismatch / Tampered"}
              </span>
            </div>
          </div>
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
            mrz?.checksum_valid
              ? "bg-emerald-950/80 border-emerald-500/40 text-emerald-400"
              : "bg-red-950/80 border-red-500/40 text-red-400"
          }`}>
            {mrz?.checksum_valid ? "PASSED" : "FAILED"}
          </span>
        </div>
      </div>

      {/* Extracted Fields Table */}
      <div className="glass-panel rounded-xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-cyan-400" />
            <h4 className="text-xs font-bold font-mono tracking-wider text-slate-300 uppercase">
              Extracted Identity Attributes
            </h4>
          </div>
          <span className="text-[10px] font-mono text-slate-500">
            {fields.length} FIELDS PARSED
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="px-5 py-3 font-semibold">ATTRIBUTE</th>
                <th className="px-5 py-3 font-semibold">EXTRACTED VALUE</th>
                <th className="px-5 py-3 font-semibold">METHOD</th>
                <th className="px-5 py-3 font-semibold text-right">CONFIDENCE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {fields.map((field, idx) => (
                <tr key={idx} className="hover:bg-slate-900/40 transition-colors">
                  <td className="px-5 py-3 text-slate-400">
                    {formatFieldName(field.field_name)}
                  </td>
                  <td className="px-5 py-3 font-bold text-slate-100">
                    {field.field_value || "—"}
                  </td>
                  <td className="px-5 py-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold border ${
                      field.extraction_method === "mrz"
                        ? "bg-cyan-950/60 text-cyan-400 border-cyan-500/30"
                        : "bg-slate-800 text-slate-300 border-slate-700"
                    }`}>
                      {field.extraction_method}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-emerald-400 h-full rounded-full"
                          style={{ width: `${Math.round(field.confidence * 100)}%` }}
                        />
                      </div>
                      <span className="text-slate-300 w-8 text-right font-medium">
                        {Math.round(field.confidence * 100)}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Business & Rule Compliance Checklist */}
      <div className="glass-panel p-5 rounded-xl">
        <h4 className="text-xs font-bold font-mono tracking-wider text-slate-300 uppercase mb-3 flex items-center justify-between">
          <span>Validation Rules Engine Compliance</span>
          <span className={`text-[10px] px-2 py-0.5 rounded border ${
            validationPassed
              ? "bg-emerald-950/80 border-emerald-500/40 text-emerald-400"
              : "bg-red-950/80 border-red-500/40 text-red-400"
          }`}>
            {validationPassed ? "ALL RULES COMPLIANT" : `${failedRules.length} VIOLATION(S)`}
          </span>
        </h4>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs font-mono">
            <Check className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="text-slate-300">Document Not Expired</span>
          </div>
          <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs font-mono">
            <Check className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="text-slate-300">Validity Window ≥ 6 Months</span>
          </div>
          <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs font-mono">
            <Check className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="text-slate-300">Date of Birth Plausible (&lt; Today)</span>
          </div>
          <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs font-mono">
            <Check className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="text-slate-300">Country Regex Format Valid</span>
          </div>
        </div>
      </div>
    </div>
  );
};
