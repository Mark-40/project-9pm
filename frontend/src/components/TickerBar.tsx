"use client";

import { cn } from "@/lib/utils";
import { useMarketStore } from "@/store/use-market-store";
import { SYMBOLS, SYMBOL_LABELS, SYMBOL_ICONS } from "@/lib/constants";
import type { SignalAction } from "@/lib/types";

const SIGNAL_COLORS: Record<SignalAction, string> = {
  BUY: "text-green-400 bg-green-500/10 border-green-500/30",
  SELL: "text-red-400 bg-red-500/10 border-red-500/30",
  HOLD: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
};

interface Props {
  onSelectSymbol?: (symbol: string) => void;
}

export default function TickerBar({ onSelectSymbol }: Props) {
  const symbols = useMarketStore((s) => s.symbols);
  const activeSymbol = useMarketStore((s) => s.activeSymbol);
  const setActiveSymbol = useMarketStore((s) => s.setActiveSymbol);

  const handleSelect = (symbol: string) => {
    setActiveSymbol(symbol);
    onSelectSymbol?.(symbol);
  };

  return (
    <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
      {SYMBOLS.map((symbol) => {
        const state = symbols[symbol];
        const price = state?.price ?? 0;
        const prev = state?.prevPrice ?? 0;
        const isUp = price >= prev;
        const action = state?.action;
        const isActive = activeSymbol === symbol;

        return (
          <button
            key={symbol}
            onClick={() => handleSelect(symbol)}
            className={cn(
              "flex-shrink-0 rounded-xl border p-3 text-left transition-all duration-200",
              "min-w-[140px] hover:border-gray-600",
              isActive
                ? "border-blue-500/50 bg-blue-500/5"
                : "border-surface-border bg-surface-card"
            )}
          >
            {/* Symbol + live dot */}
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold text-gray-400">
                  {SYMBOL_ICONS[symbol]}
                </span>
                <span className="text-xs font-semibold text-gray-300">
                  {SYMBOL_LABELS[symbol]}
                </span>
              </div>
              <span
                className={cn(
                  "size-1.5 rounded-full",
                  state?.connected ? "bg-green-500 animate-pulse" : "bg-gray-600"
                )}
              />
            </div>

            {/* Price */}
            <div
              className={cn(
                "text-sm font-mono font-bold",
                price > 0
                  ? isUp
                    ? "text-green-400"
                    : "text-red-400"
                  : "text-gray-600"
              )}
            >
              {price > 0
                ? `$${price.toLocaleString("en-US", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: price < 1 ? 5 : 2,
                  })}`
                : "Loading…"}
            </div>

            {/* Signal badge */}
            {action && (
              <div
                className={cn(
                  "mt-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold border",
                  SIGNAL_COLORS[action]
                )}
              >
                {action}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
