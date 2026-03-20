"use client";

import { Trash2 } from "lucide-react";
import { useSignalLogStore } from "@/store/use-signal-log-store";
import { cn, formatTimestamp } from "@/lib/utils";
import { SYMBOL_LABELS } from "@/lib/constants";
import type { SignalAction } from "@/lib/types";

const ACTION_STYLES: Record<SignalAction, string> = {
  BUY: "text-green-400 bg-green-500/10 border-green-500/30",
  SELL: "text-red-400 bg-red-500/10 border-red-500/30",
  HOLD: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
};

export default function SignalLog() {
  const entries = useSignalLogStore((s) => s.entries);
  const clear = useSignalLogStore((s) => s.clear);

  return (
    <div className="rounded-xl border border-surface-border bg-surface-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Signal Log
          </span>
          {entries.length > 0 && (
            <span className="inline-flex items-center justify-center size-4 rounded-full bg-blue-500/20 text-blue-400 text-[10px] font-bold">
              {entries.length}
            </span>
          )}
        </div>
        {entries.length > 0 && (
          <button
            onClick={clear}
            className="text-gray-600 hover:text-gray-400 transition-colors"
            title="Clear log"
          >
            <Trash2 className="size-3.5" />
          </button>
        )}
      </div>

      {/* Entries */}
      <div className="overflow-y-auto max-h-64">
        {entries.length === 0 ? (
          <div className="flex items-center justify-center h-20 text-xs text-gray-600">
            No signals yet — waiting for closed candles…
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-surface-border/50">
                <th className="text-left px-4 py-2 text-gray-600 font-normal">
                  Time
                </th>
                <th className="text-left px-4 py-2 text-gray-600 font-normal">
                  Pair
                </th>
                <th className="text-left px-4 py-2 text-gray-600 font-normal">
                  Signal
                </th>
                <th className="text-right px-4 py-2 text-gray-600 font-normal">
                  Price
                </th>
                <th className="text-right px-4 py-2 text-gray-600 font-normal">
                  Strength
                </th>
                <th className="text-right px-4 py-2 text-gray-600 font-normal">
                  Source
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr
                  key={entry.id}
                  className="border-b border-surface-border/30 hover:bg-surface-muted/30 transition-colors animate-fade-in"
                >
                  <td className="px-4 py-2 font-mono text-gray-500">
                    {formatTimestamp(entry.timestamp)}
                  </td>
                  <td className="px-4 py-2 text-gray-300 font-medium">
                    {SYMBOL_LABELS[entry.symbol] ?? entry.symbol}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={cn(
                        "inline-flex items-center px-2 py-0.5 rounded border text-[11px] font-bold",
                        ACTION_STYLES[entry.action]
                      )}
                    >
                      {entry.action}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-gray-300">
                    $
                    {entry.price.toLocaleString("en-US", {
                      minimumFractionDigits: 2,
                    })}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-gray-400">
                    {(entry.strength * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-2 text-right text-gray-600 uppercase">
                    {entry.source}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
