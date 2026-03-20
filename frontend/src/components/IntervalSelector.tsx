"use client";

import { INTERVALS } from "@/lib/constants";
import type { ChartInterval } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  value: ChartInterval;
  onChange: (interval: ChartInterval) => void;
}

export default function IntervalSelector({ value, onChange }: Props) {
  return (
    <div className="flex items-center gap-1 bg-surface-muted rounded-lg p-1">
      {INTERVALS.map((iv) => (
        <button
          key={iv.value}
          onClick={() => onChange(iv.value as ChartInterval)}
          className={cn(
            "px-2.5 py-1 rounded-md text-xs font-mono transition-colors",
            value === iv.value
              ? "bg-blue-600 text-white"
              : "text-gray-400 hover:text-gray-200 hover:bg-surface-card"
          )}
        >
          {iv.label}
        </button>
      ))}
    </div>
  );
}
