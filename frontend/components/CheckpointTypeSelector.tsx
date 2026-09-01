"use client";

import React from "react";
import type { CheckpointType } from "../lib/api/types";
import { Plane, Truck, Anchor } from "lucide-react";

interface CheckpointTypeSelectorProps {
  value: CheckpointType;
  onChange: (type: CheckpointType) => void;
}

const CHECKPOINTS: Array<{
  id: CheckpointType;
  label: string;
  icon: React.ElementType;
}> = [
  { id: "airport", label: "Airport", icon: Plane },
  { id: "land_border", label: "Land Border", icon: Truck },
  { id: "sea", label: "Sea Port", icon: Anchor },
];

export function CheckpointTypeSelector({
  value,
  onChange,
}: CheckpointTypeSelectorProps) {
  return (
    <div className="flex items-center gap-1 bg-surface-raised/80 p-1 rounded border border-border">
      {CHECKPOINTS.map((cp) => {
        const Icon = cp.icon;
        const active = value === cp.id;
        return (
          <button
            key={cp.id}
            type="button"
            onClick={() => onChange(cp.id)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-body transition-all cursor-pointer ${
              active
                ? "bg-brand text-bg font-semibold shadow-xs"
                : "text-text-muted hover:text-text hover:bg-surface"
            }`}
          >
            <Icon size={14} strokeWidth={1.5} />
            <span>{cp.label}</span>
          </button>
        );
      })}
    </div>
  );
}
