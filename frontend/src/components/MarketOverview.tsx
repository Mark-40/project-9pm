"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL, SYMBOL_LABELS } from "@/lib/constants";
import type { TickerInfo } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function MarketOverview() {
  const [tickers, setTickers] = useState<TickerInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/tickers`);
        if (res.ok) {
          const data = await res.json();
          setTickers(data.tickers);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    };

    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border border-surface-border bg-surface-card p-5">
        <p className="text-xs text-gray-500">Loading market overview…</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-surface-border bg-surface-card overflow-hidden">
      <div className="px-5 py-3 border-b border-surface-border">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          24h Market Overview
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-border">
              <th className="text-left px-4 py-2.5 text-gray-500 font-medium">Pair</th>
              <th className="text-right px-4 py-2.5 text-gray-500 font-medium">Price</th>
              <th className="text-right px-4 py-2.5 text-gray-500 font-medium">24h %</th>
              <th className="text-right px-4 py-2.5 text-gray-500 font-medium">24h High</th>
              <th className="text-right px-4 py-2.5 text-gray-500 font-medium">24h Low</th>
              <th className="text-right px-4 py-2.5 text-gray-500 font-medium">Volume (USDT)</th>
            </tr>
          </thead>
          <tbody>
            {tickers.map((t) => (
              <tr
                key={t.symbol}
                className="border-b border-surface-border/40 hover:bg-surface-muted transition-colors"
              >
                <td className="px-4 py-2.5 font-medium text-gray-200">
                  {SYMBOL_LABELS[t.symbol] ?? t.symbol}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-200">
                  ${t.price.toLocaleString("en-US", {
                    minimumFractionDigits: t.price < 1 ? 5 : 2,
                  })}
                </td>
                <td
                  className={cn(
                    "px-4 py-2.5 text-right font-mono font-semibold",
                    t.change_pct >= 0 ? "text-green-400" : "text-red-400"
                  )}
                >
                  {t.change_pct >= 0 ? "+" : ""}
                  {t.change_pct.toFixed(2)}%
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-400">
                  ${t.high.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-400">
                  ${t.low.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-400">
                  ${t.quote_volume
                    ? (t.quote_volume / 1_000_000).toFixed(1) + "M"
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
