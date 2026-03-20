"use client";

import { TrendingUp, TrendingDown, Minus, Cpu, BarChart2 } from "lucide-react";
import { useMarketStore } from "@/store/use-market-store";
import { cn, formatTimestamp } from "@/lib/utils";
import type { SignalAction, QualityLabel, MacroTrend } from "@/lib/types";

const ACTION_CONFIG: Record<
  SignalAction,
  {
    icon: typeof TrendingUp;
    label: string;
    bgClass: string;
    textClass: string;
    borderClass: string;
    animClass: string;
  }
> = {
  BUY: {
    icon: TrendingUp,
    label: "BUY",
    bgClass: "bg-green-500/10",
    textClass: "text-green-400",
    borderClass: "border-green-500/30",
    animClass: "animate-pulse-green",
  },
  SELL: {
    icon: TrendingDown,
    label: "SELL",
    bgClass: "bg-red-500/10",
    textClass: "text-red-400",
    borderClass: "border-red-500/30",
    animClass: "animate-pulse-red",
  },
  HOLD: {
    icon: Minus,
    label: "HOLD",
    bgClass: "bg-yellow-500/10",
    textClass: "text-yellow-400",
    borderClass: "border-yellow-500/20",
    animClass: "",
  },
};

const QUALITY_COLORS: Record<QualityLabel, string> = {
  "Very Strong": "text-green-400 bg-green-500/10 border-green-500/20",
  Strong: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  Moderate: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
  Weak: "text-gray-500 bg-gray-500/10 border-gray-500/20",
};

const CONFLUENCE_LABELS: Record<string, string> = {
  aligned_bull: "15m Aligned ▲",
  aligned_bear: "15m Aligned ▼",
  mixed: "15m Mixed",
};

const MACRO_TREND_CONFIG: Record<
  MacroTrend,
  { label: string; className: string }
> = {
  uptrend: {
    label: "Uptrend ▲",
    className: "bg-green-500/10 border-green-500/20 text-green-400",
  },
  downtrend: {
    label: "Downtrend ▼",
    className: "bg-red-500/10 border-red-500/20 text-red-400",
  },
  ranging: {
    label: "Ranging ↔",
    className: "bg-yellow-500/10 border-yellow-500/20 text-yellow-400",
  },
};

interface Props {
  symbol: string;
}

export default function SignalCard({ symbol }: Props) {
  const state = useMarketStore((s) => s.symbols[symbol]);
  const action = state?.action ?? "HOLD";
  const cfg = ACTION_CONFIG[action];
  const Icon = cfg.icon;
  const strength = state?.strength ?? 0;
  const qualityScore = state?.qualityScore ?? 0;
  const qualityLabel: QualityLabel = state?.qualityLabel ?? "Weak";
  const macroTrend = state?.macroTrend ?? null;

  return (
    <div
      className={cn(
        "rounded-xl border p-5 bg-surface-card flex flex-col gap-4",
        cfg.borderClass,
        cfg.animClass
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500 uppercase tracking-wider">
          AI Signal
        </span>
        <div className="flex items-center gap-2">
          {/* Quality badge */}
          {state?.action && state.action !== "HOLD" && (
            <span
              className={cn(
                "text-[10px] font-semibold px-2 py-0.5 rounded-full border",
                QUALITY_COLORS[qualityLabel]
              )}
            >
              {qualityScore}/100
            </span>
          )}
          <span className="flex items-center gap-1 text-xs text-gray-500">
            {state?.source === "ml" ? (
              <>
                <Cpu className="size-3" /> ML Model
              </>
            ) : (
              <>
                <BarChart2 className="size-3" /> Rule-Based
              </>
            )}
          </span>
        </div>
      </div>

      {/* Main action */}
      <div className="flex items-center gap-4">
        <div className={cn("rounded-xl p-3", cfg.bgClass)}>
          <Icon className={cn("size-8", cfg.textClass)} strokeWidth={2.5} />
        </div>
        <div>
          <div
            className={cn(
              "text-4xl font-bold font-mono tracking-tight",
              cfg.textClass
            )}
          >
            {cfg.label}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">
            {state?.signalTimestamp
              ? formatTimestamp(state.signalTimestamp)
              : "Waiting for signal…"}
          </div>
        </div>
      </div>

      {/* Strength bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs text-gray-500">
          <span>Signal Strength</span>
          <span className={cn("font-mono font-bold", cfg.textClass)}>
            {(strength * 100).toFixed(0)}%
          </span>
        </div>
        <div className="h-2 bg-surface-muted rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-700",
              action === "BUY"
                ? "bg-green-500"
                : action === "SELL"
                ? "bg-red-500"
                : "bg-yellow-500"
            )}
            style={{ width: `${strength * 100}%` }}
          />
        </div>
      </div>

      {/* Quality score bar */}
      {state?.action && state.action !== "HOLD" && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-gray-500">
            <span>Quality Score</span>
            <span className={cn("font-mono font-bold", QUALITY_COLORS[qualityLabel].split(" ")[0])}>
              {qualityLabel}
            </span>
          </div>
          <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-700",
                qualityScore >= 75
                  ? "bg-green-500"
                  : qualityScore >= 50
                  ? "bg-blue-500"
                  : qualityScore >= 25
                  ? "bg-yellow-500"
                  : "bg-gray-600"
              )}
              style={{ width: `${qualityScore}%` }}
            />
          </div>
        </div>
      )}

      {/* Confluence indicator */}
      {state?.confluenceDirection && (
        <div
          className={cn(
            "flex items-center justify-between text-xs px-3 py-2 rounded-lg border",
            state.confluenceDirection === "aligned_bull"
              ? "bg-green-500/10 border-green-500/20 text-green-400"
              : state.confluenceDirection === "aligned_bear"
              ? "bg-red-500/10 border-red-500/20 text-red-400"
              : "bg-surface-muted border-surface-border text-gray-500"
          )}
        >
          <span className="font-medium">
            {CONFLUENCE_LABELS[state.confluenceDirection]}
          </span>
          {state.confluenceScore != null && (
            <span className="font-mono">
              {(state.confluenceScore * 100).toFixed(0)}%
            </span>
          )}
        </div>
      )}

      {/* Macro trend badge */}
      {macroTrend && (
        <div
          className={cn(
            "flex items-center justify-between text-xs px-3 py-2 rounded-lg border",
            MACRO_TREND_CONFIG[macroTrend].className
          )}
        >
          <span className="font-medium">Macro Trend</span>
          <span className="font-semibold">
            {MACRO_TREND_CONFIG[macroTrend].label}
          </span>
        </div>
      )}

      {/* ATR profit targets */}
      {action !== "HOLD" && state?.takeProfit != null && state?.stopLoss != null && (
        <div className="grid grid-cols-3 gap-2 pt-1 border-t border-surface-border">
          <div className="text-center">
            <div className="text-[10px] text-gray-500 mb-0.5">Target</div>
            <div className={cn("text-xs font-mono font-bold", action === "BUY" ? "text-green-400" : "text-red-400")}>
              ${state.takeProfit.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: state.takeProfit < 1 ? 5 : 2 })}
            </div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-gray-500 mb-0.5">Stop</div>
            <div className={cn("text-xs font-mono font-bold", action === "BUY" ? "text-red-400" : "text-green-400")}>
              ${state.stopLoss.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: state.stopLoss < 1 ? 5 : 2 })}
            </div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-gray-500 mb-0.5">R:R</div>
            <div className="text-xs font-mono font-bold text-blue-400">
              {state.riskReward?.toFixed(1)}x
            </div>
          </div>
        </div>
      )}

      {/* ML probabilities */}
      {state?.ml && (
        <div className="grid grid-cols-3 gap-2 pt-1 border-t border-surface-border">
          {Object.entries(state.ml.probabilities).map(([label, prob]) => (
            <div key={label} className="text-center">
              <div
                className={cn(
                  "text-xs font-bold",
                  label === "BUY"
                    ? "text-green-400"
                    : label === "SELL"
                    ? "text-red-400"
                    : "text-yellow-400"
                )}
              >
                {label}
              </div>
              <div className="text-xs font-mono text-gray-400">
                {(prob * 100).toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
