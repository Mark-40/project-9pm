"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  IPriceLine,
  ColorType,
  CrosshairMode,
  LineStyle,
  type Time,
} from "lightweight-charts";
import { useTheme } from "next-themes";
import { useMarketStore } from "@/store/use-market-store";
import { API_BASE_URL } from "@/lib/constants";
import type { ChartInterval, CandleBar } from "@/lib/types";
import IntervalSelector from "./IntervalSelector";

interface Props {
  symbol: string;
}

const PIVOT_COLORS = {
  pivot: "#94a3b8",
  r1: "#f97316",
  r2: "#ef4444",
  r3: "#dc2626",
  s1: "#22d3ee",
  s2: "#22c55e",
  s3: "#16a34a",
};

function getChartColors(isDark: boolean) {
  return {
    bg: isDark ? "#0d1117" : "#ffffff",
    grid: isDark ? "#1f2937" : "#e5e7eb",
    border: isDark ? "#374151" : "#d1d5db",
    text: isDark ? "#6b7280" : "#6b7280",
  };
}

export default function TradingChart({ symbol }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const priceLineRefs = useRef<IPriceLine[]>([]);
  const [interval, setInterval] = useState<ChartInterval>("1h");

  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme !== "light";

  const candles = useMarketStore((s) => s.symbols[symbol]?.candles ?? []);
  const price = useMarketStore((s) => s.symbols[symbol]?.price ?? 0);
  const pivots = useMarketStore((s) => s.symbols[symbol]?.pivots ?? null);

  // Create chart once on mount
  useEffect(() => {
    if (!containerRef.current) return;
    const colors = getChartColors(isDark);

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: colors.bg },
        textColor: colors.text,
        fontFamily: "JetBrains Mono, Fira Code, Consolas, monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: colors.grid, style: 1 },
        horzLines: { color: colors.grid, style: 1 },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#4b5563", width: 1, style: 2 },
        horzLine: { color: "#4b5563", width: 1, style: 2 },
      },
      rightPriceScale: { borderColor: colors.border },
      timeScale: {
        borderColor: colors.border,
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight || 400,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addHistogramSeries({
      color: "#3b82f620",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleRef.current = candleSeries;
    volumeRef.current = volumeSeries;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
      priceLineRefs.current = [];
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Update theme colors when theme changes
  useEffect(() => {
    if (!chartRef.current) return;
    const colors = getChartColors(isDark);
    chartRef.current.applyOptions({
      layout: {
        background: { type: ColorType.Solid, color: colors.bg },
        textColor: colors.text,
      },
      grid: {
        vertLines: { color: colors.grid, style: 1 },
        horzLines: { color: colors.grid, style: 1 },
      },
      rightPriceScale: { borderColor: colors.border },
      timeScale: { borderColor: colors.border },
    });
  }, [isDark]);

  // Fetch candles when interval changes
  useEffect(() => {
    if (interval === "1h") return; // 1h data comes from WebSocket

    const load = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/api/history/${symbol}?interval=${interval}&limit=300`
        );
        if (!res.ok) return;
        const data = await res.json();
        const bars: CandleBar[] = data.candles;
        if (!candleRef.current || !volumeRef.current) return;

        candleRef.current.setData(
          bars.map((c) => ({
            time: c.time as Time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }))
        );
        volumeRef.current.setData(
          bars.map((c) => ({
            time: c.time as Time,
            value: c.volume,
            color:
              c.close >= c.open
                ? "rgba(34,197,94,0.25)"
                : "rgba(239,68,68,0.25)",
          }))
        );
        chartRef.current?.timeScale().scrollToRealTime();
      } catch {
        // ignore
      }
    };

    load();
  }, [interval, symbol]);

  // Update candles from store when interval is 1h
  useEffect(() => {
    if (interval !== "1h") return;
    if (!candleRef.current || !volumeRef.current || !candles.length) return;

    candleRef.current.setData(
      candles.map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );
    volumeRef.current.setData(
      candles.map((c) => ({
        time: c.time as Time,
        value: c.volume,
        color:
          c.close >= c.open
            ? "rgba(34,197,94,0.25)"
            : "rgba(239,68,68,0.25)",
      }))
    );
    chartRef.current?.timeScale().scrollToRealTime();
  }, [candles, interval]);

  // Draw S/R pivot lines
  useEffect(() => {
    if (!candleRef.current) return;

    // Remove old lines
    priceLineRefs.current.forEach((pl) => {
      try { candleRef.current?.removePriceLine(pl); } catch { /* removed already */ }
    });
    priceLineRefs.current = [];

    if (!pivots) return;

    const entries = [
      { key: "pivot", label: "P", price: pivots.pivot },
      { key: "r1", label: "R1", price: pivots.r1 },
      { key: "r2", label: "R2", price: pivots.r2 },
      { key: "r3", label: "R3", price: pivots.r3 },
      { key: "s1", label: "S1", price: pivots.s1 },
      { key: "s2", label: "S2", price: pivots.s2 },
      { key: "s3", label: "S3", price: pivots.s3 },
    ] as const;

    for (const entry of entries) {
      if (entry.price == null) continue;
      const pl = candleRef.current.createPriceLine({
        price: entry.price,
        color: PIVOT_COLORS[entry.key],
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: entry.label,
      });
      priceLineRefs.current.push(pl);
    }
  }, [pivots]);

  return (
    <div className="space-y-2">
      {/* Interval selector */}
      <div className="flex items-center justify-between px-1">
        <IntervalSelector value={interval} onChange={setInterval} />
        {pivots?.pivot != null && (
          <div className="flex items-center gap-3 text-[10px] text-gray-500">
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-px bg-orange-400" />
              R1/R2
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-px bg-cyan-400" />
              S1/S2
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-px bg-slate-400" />
              Pivot
            </span>
          </div>
        )}
      </div>

      <div className="relative w-full h-[400px] rounded-xl overflow-hidden border border-surface-border bg-surface">
        <div ref={containerRef} className="w-full h-full" />
        {price > 0 && (
          <div className="absolute top-3 left-3 bg-surface-card/80 backdrop-blur-sm px-2.5 py-1 rounded-md border border-surface-border text-xs font-mono text-gray-300">
            {symbol.replace("USDT", "")}{" "}
            <span className="text-white font-bold">
              ${price.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
