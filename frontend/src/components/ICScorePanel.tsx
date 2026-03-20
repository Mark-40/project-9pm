"use client";

import { useState } from "react";
import { BarChart2, Loader2 } from "lucide-react";
import { cn, formatTimestamp } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/constants";
import type { ICScoreResult, IndicatorIC } from "@/lib/types";

interface Props {
  symbol: string;
}

const INDICATOR_LABELS: Record<string, string> = {
  rsi: "RSI (14)",
  macd_hist: "MACD Histogram",
  bb_pct: "BB Position %",
  ema_cross_pct: "EMA 9/21 Cross",
  stoch_k: "Stochastic %K",
  adx: "ADX (14)",
  obv_trend: "OBV Trend",
  vwap_dist: "VWAP Distance",
  adx_cross_pct: "ADX +DI/-DI Cross",
  ema50_200_cross_pct: "EMA 50/200 Cross",
};

export default function ICScorePanel({ symbol }: Props) {
  const [result, setResult] = useState<ICScoreResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/ic-scores/${symbol}`);
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail ?? "Failed to compute IC scores");
      }
      setResult(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-surface-border bg-surface-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Indicator IC Analysis — {symbol}
          </h3>
          <p className="text-[11px] text-gray-600 mt-0.5">
            Pearson correlation of each indicator vs 3-candle forward return
          </p>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium hover:bg-blue-500/20 transition-colors disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <BarChart2 className="size-3.5" />
          )}
          {loading ? "Computing…" : "Run Analysis"}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {result && (
        <>
          <p className="text-[10px] text-gray-600">
            Computed {formatTimestamp(result.computed_at)} · {result.scores[0]?.n_samples ?? 0} samples
          </p>

          <div className="space-y-2">
            {result.scores.map((score, idx) => (
              <ICRow key={score.name} rank={idx + 1} score={score} />
            ))}
            {result.scores.length === 0 && (
              <p className="text-xs text-gray-600 text-center py-4">
                Not enough data to compute IC scores.
              </p>
            )}
          </div>
        </>
      )}

      {!result && !loading && (
        <p className="text-xs text-gray-600 text-center py-6">
          Click "Run Analysis" to rank indicator effectiveness using historical data.
        </p>
      )}
    </div>
  );
}

function ICRow({ rank, score }: { rank: number; score: IndicatorIC }) {
  const label = INDICATOR_LABELS[score.name] ?? score.name;
  const isPositive = score.ic > 0;
  const isNeutral = score.direction === "neutral";

  return (
    <div className="flex items-center gap-3 py-1.5 border-b border-surface-border/40 last:border-0">
      <span className="text-[10px] text-gray-600 w-4 text-right flex-shrink-0">
        {rank}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-300 truncate">{label}</span>
          <div className="flex items-center gap-2 flex-shrink-0 ml-2">
            <span
              className={cn(
                "text-[10px] px-1.5 py-0.5 rounded-full font-semibold border",
                score.direction === "bullish"
                  ? "bg-green-500/10 border-green-500/20 text-green-400"
                  : score.direction === "bearish"
                  ? "bg-red-500/10 border-red-500/20 text-red-400"
                  : "bg-gray-500/10 border-gray-500/20 text-gray-500"
              )}
            >
              {score.direction}
            </span>
            <span
              className={cn(
                "text-xs font-mono font-bold w-14 text-right",
                isNeutral ? "text-gray-500" : isPositive ? "text-green-400" : "text-red-400"
              )}
            >
              {score.ic >= 0 ? "+" : ""}{score.ic.toFixed(3)}
            </span>
          </div>
        </div>
        {/* IC magnitude bar */}
        <div className="h-1 bg-surface-muted rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              isNeutral ? "bg-gray-600" : isPositive ? "bg-green-500" : "bg-red-500"
            )}
            style={{ width: `${Math.min(score.abs_ic * 500, 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
