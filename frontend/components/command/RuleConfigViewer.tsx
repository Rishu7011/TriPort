"use client";

import React, { useState } from "react";
import { MOCK_VALIDATION_RULES } from "../../lib/api/mocks";
import type { ValidationRuleItem } from "../../lib/api/types";
import {
  FileCode,
  Search,
  Calendar,
  Code,
  GitCompare,
  Hash,
} from "lucide-react";

export function RuleConfigViewer() {
  const [selectedDocType, setSelectedDocType] = useState<string>("all");
  const [search, setSearch] = useState("");
  const rules: ValidationRuleItem[] = MOCK_VALIDATION_RULES;

  const docTypes = [
    { id: "all", label: "All Rules" },
    { id: "passport", label: "Passport" },
    { id: "visa", label: "Visa" },
    { id: "national_id", label: "National ID" },
    { id: "voter_id", label: "Voter ID" },
    { id: "driving_license", label: "Driving License" },
  ];

  const filteredRules = rules.filter((r) => {
    const matchType =
      selectedDocType === "all" || r.document_type === selectedDocType;
    const matchSearch =
      search === "" ||
      r.rule_name.toLowerCase().includes(search.toLowerCase()) ||
      r.field.toLowerCase().includes(search.toLowerCase()) ||
      r.description.toLowerCase().includes(search.toLowerCase()) ||
      (r.condition &&
        r.condition.toLowerCase().includes(search.toLowerCase())) ||
      (r.pattern && r.pattern.toLowerCase().includes(search.toLowerCase()));

    return matchType && matchSearch;
  });

  const getRuleTypeBadge = (type: string) => {
    switch (type) {
      case "date_check":
        return (
          <span className="inline-flex items-center gap-1 text-brand bg-brand/10 border border-brand/30 px-2 py-0.5 rounded text-[10px] font-mono uppercase">
            <Calendar size={11} /> Date Check
          </span>
        );
      case "regex_format":
        return (
          <span className="inline-flex items-center gap-1 text-risk-medium bg-risk-medium/10 border border-risk-medium/30 px-2 py-0.5 rounded text-[10px] font-mono uppercase">
            <Code size={11} /> Regex Format
          </span>
        );
      case "cross_field":
        return (
          <span className="inline-flex items-center gap-1 text-risk-high bg-risk-high/10 border border-risk-high/30 px-2 py-0.5 rounded text-[10px] font-mono uppercase">
            <GitCompare size={11} /> Cross Field
          </span>
        );
      case "checksum":
        return (
          <span className="inline-flex items-center gap-1 text-cyan-400 bg-cyan-400/10 border border-cyan-400/30 px-2 py-0.5 rounded text-[10px] font-mono uppercase">
            <Hash size={11} /> Checksum
          </span>
        );
      default:
        return (
          <span className="text-text-muted font-mono text-[10px] uppercase">
            {type}
          </span>
        );
    }
  };

  return (
    <div className="bg-surface border border-border rounded-md overflow-hidden flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border bg-surface-raised flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="font-display font-bold text-sm text-text uppercase tracking-tight flex items-center gap-2">
            <FileCode size={16} className="text-brand" />
            <span>Validation Service Business Rules Engine</span>
          </h3>
          <p className="font-mono text-xs text-text-muted mt-0.5">
            Data-driven YAML rule definitions executing across Module 2
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs text-text-muted">
          <span className="w-2 h-2 rounded-full bg-brand" />
          <span>Rules Loaded from backend/validation_service/rules/</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3 border-b border-border bg-bg flex flex-col sm:flex-row items-center justify-between gap-3">
        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search rule name, field, pattern..."
            className="w-full h-8 pl-8 pr-3 bg-surface border border-border rounded text-text font-mono text-xs placeholder:text-text-muted/60 focus:border-brand focus:ring-1 focus:ring-brand outline-none"
          />
        </div>

        {/* Doc Type Selector */}
        <div className="flex items-center gap-1 font-mono text-xs w-full sm:w-auto overflow-x-auto">
          <span className="text-text-muted mr-1 hidden sm:inline">Scope:</span>
          {docTypes.map((dt) => (
            <button
              key={dt.id}
              type="button"
              onClick={() => setSelectedDocType(dt.id)}
              className={`px-2.5 py-1 rounded uppercase text-[11px] transition-colors cursor-pointer ${
                selectedDocType === dt.id
                  ? "bg-surface-raised border border-border text-brand font-bold"
                  : "text-text-muted hover:text-text"
              }`}
            >
              {dt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Rules Card Grid */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 overflow-y-auto max-h-[600px]">
        {filteredRules.map((rule, idx) => (
          <div
            key={idx}
            className="bg-bg border border-border rounded p-3.5 hover:border-brand/40 transition-colors flex flex-col justify-between"
          >
            <div>
              {/* Header */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="min-w-0">
                  <div className="font-mono text-xs font-bold text-text truncate">
                    {rule.rule_name}
                  </div>
                  <div className="font-mono text-[10px] text-text-muted uppercase">
                    Target: <span className="text-brand">{rule.field}</span>
                  </div>
                </div>
                {getRuleTypeBadge(rule.rule_type)}
              </div>

              {/* Description */}
              <p className="font-body text-xs text-text-muted mb-3 leading-snug">
                {rule.description}
              </p>
            </div>

            {/* Pattern / Condition Definition Box */}
            <div className="space-y-1.5 pt-2 border-t border-border/80 font-mono text-[11px]">
              {rule.pattern && (
                <div className="p-1.5 rounded bg-surface-raised border border-border">
                  <span className="text-text-muted text-[10px] block">Pattern (Regex):</span>
                  <code className="text-brand font-bold truncate block select-all">
                    {rule.pattern}
                  </code>
                </div>
              )}

              {rule.condition && (
                <div className="p-1.5 rounded bg-surface-raised border border-border">
                  <span className="text-text-muted text-[10px] block">Condition:</span>
                  <code className="text-brand font-bold truncate block select-all">
                    {rule.condition}
                  </code>
                </div>
              )}

              <div className="text-[10px] text-risk-critical truncate pt-0.5">
                Error: {rule.error_message}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
