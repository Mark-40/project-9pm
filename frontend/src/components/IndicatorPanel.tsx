"use client";

import { useMarketStore } from "@/store/use-market-store";
import { cn } from "@/lib/utils";

interface GaugeProps {
  label: string;
  value: number | null;
  min: number;
  max: number;
  lowLabel?: string;
  highLabel?: string;
}

function Gauge({ label, value, min, max, lowLabel, highLabel }: GaugeProps) {
  const pct =
    value != null
      ? Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100))
      : 50;
  const isHigh = pct > 70;
  const isLow = pct < 30;
  const barColor = isHigh
    ? "bg-red-500"
    : isLow
    ? "bg-green-500"
    : "bg-blue-500";
  const labelColor = isHigh
    ? "text-red-400"
    : isLow
    ? "text-green-400"
    : "text-gray-400";

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-gray-500">{label}</span>
        <span className={cn("font-mono font-semibold", labelColor)}>
          {value != null ? value.toFixed(2) : "—"}
          {isHigh && highLabel ? (
            <span className="ml-1 text-red-400">({highLabel})</span>
          ) : isLow && lowLabel ? (
            <span className="ml-1 text-green-400">({lowLabel})</span>
          ) : null}
        </span>
      </div>
      <div className="h-1.5 w-full bg-surface-muted rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            barColor
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      {(lowLabel || highLabel) && (
        <div className="flex justify-between text-[10px] text-gray-600">
          <span>{lowLabel}</span>
          <span>{highLabel}</span>
        </div>
      )}
    </div>
  );
}

interface ValueRowProps {
  label: string;
  value: number | null;
  decimals?: number;
  colored?: boolean;
}

function ValueRow({ label, value, decimals = 4, colored = false }: ValueRowProps) {
  const isPositive = value != null && value > 0;
  const isNegative = value != null && value < 0;

  return (
    <div className="flex justify-between text-xs py-1 border-b border-surface-border/50 last:border-0">
      <span className="text-gray-500">{label}</span>
      <span
        className={cn(
          "font-mono font-semibold",
          colored
            ? isPositive
              ? "text-green-400"
              : isNegative
              ? "text-red-400"
              : "text-gray-400"
            : "text-gray-300"
        )}
      >
        {value != null ? value.toFixed(decimals) : "—"}
      </span>
    </div>
  );
}

interface Props {
  symbol: string;
}

export default function IndicatorPanel({ symbol }: Props) {
  const ta = useMarketStore((s) => s.symbols[symbol]?.ta);

  return (
    <div className="rounded-xl border border-surface-border bg-surface-card p-5 space-y-5">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
        Indicators
      </h3>

      {/* Oscillators */}
      <div className="space-y-4">
        <Gauge
          label="RSI (14)"
          value={ta?.rsi ?? null}
          min={0}
          max={100}
          lowLabel="Oversold"
          highLabel="Overbought"
        />
        <Gauge
          label="Stoch %K"
          value={ta?.stoch_k ?? null}
          min={0}
          max={100}
          lowLabel="Oversold"
          highLabel="Overbought"
        />
        <Gauge
          label="BB Position"
          value={ta?.bb_pct != null ? ta.bb_pct * 100 : null}
          min={0}
          max={100}
          lowLabel="Below Lower"
          highLabel="Above Upper"
        />
      </div>

      {/* MACD + EMA grid */}
      <div className="pt-1 border-t border-surface-border">
        <ValueRow
          label="MACD"
          value={ta?.macd ?? null}
          decimals={4}
          colored
        />
        <ValueRow
          label="MACD Signal"
          value={ta?.macd_signal ?? null}
          decimals={4}
        />
        <ValueRow
          label="MACD Hist"
          value={ta?.macd_hist ?? null}
          decimals={4}
          colored
        />
        <ValueRow label="EMA 9" value={ta?.ema_9 ?? null} decimals={2} />
        <ValueRow label="EMA 21" value={ta?.ema_21 ?? null} decimals={2} />
        <ValueRow label="Stoch %D" value={ta?.stoch_d ?? null} decimals={2} />
        <ValueRow
          label="BB Width"
          value={ta?.bb_bandwidth != null ? ta.bb_bandwidth * 100 : null}
          decimals={3}
        />
      </div>
    </div>
  );
}
