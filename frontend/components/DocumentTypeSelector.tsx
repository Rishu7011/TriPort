"use client";

import React from "react";
import type { DocumentType } from "../lib/api/types";
import { BookOpen, FileCheck, CreditCard, Car, Award, Vote } from "lucide-react";

interface DocumentTypeSelectorProps {
  value: DocumentType;
  onChange: (type: DocumentType) => void;
}

const DOC_TYPES: Array<{
  id: DocumentType;
  label: string;
  icon: React.ElementType;
}> = [
  { id: "passport", label: "Passport", icon: BookOpen },
  { id: "visa", label: "Visa", icon: FileCheck },
  { id: "national_id", label: "Aadhaar Card", icon: CreditCard },
  { id: "pan_card", label: "PAN Card", icon: CreditCard },
  { id: "voter_id", label: "Voter ID", icon: Vote },
  { id: "driving_license", label: "Driving License", icon: Car },
  { id: "permit", label: "Permit", icon: Award },
];

export function DocumentTypeSelector({
  value,
  onChange,
}: DocumentTypeSelectorProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="font-mono text-[11px] uppercase tracking-wider text-text-muted mr-1">
        Doc Type:
      </span>
      {DOC_TYPES.map((dt) => {
        const Icon = dt.icon;
        const active = value === dt.id;
        return (
          <button
            key={dt.id}
            type="button"
            onClick={() => onChange(dt.id)}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-body transition-all cursor-pointer ${
              active
                ? "bg-brand text-bg font-semibold shadow-xs"
                : "bg-surface border border-border text-text hover:border-brand/60 hover:text-brand"
            }`}
          >
            <Icon size={13} strokeWidth={1.5} />
            <span>{dt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
