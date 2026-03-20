"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { cn, formatTimestamp } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/constants";
import type { TradeLogEntry } from "@/lib/types";

interface Props {
  symbol: string;
}

export default function TradeLog({ symbol }: Props) {
  const [entries, setEntries] = useState<TradeLogEntry[]>([]);
  const [stats, setStats] = useState<{ total: number; win_rate: number; avg_return: number } | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch_ = async () => {
    setLoading(true);
    try {
      const [logRes, statsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/trade-log?symbol=${symbol}&limit=100`),
        fetch(`${API_BASE_URL}/api/trade-log/stats?symbol=${symbol}`),
      ]);
      const logData = await logRes.json();
      const statsData = await statsRes.json();
      setEntries(logData.entries ?? []);
      setStats(statsData);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch_();
    const id = setInterval(fetch_, 30_000);
    return () => clearInterval(id);
  }, [symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="rounded-xl border border-surface-border bg-surface-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Actualized Trade Log — {symbol}
        </h3>
        <button
          onClick={fetch_}
          disabled={loading}
          className="p-1.5 rounded-lg hover:bg-surface-muted transition-colors"
        >
          <RefreshCw className={cn("size-3.5 text-gray-500", loading && "animate-spin")} />
        </button>
      </div>

      {/* Stats summary */}
      {stats && stats.total > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg bg-surface-muted p-3 text-center">
            <div className="text-lg font-bold font-mono text-white">{stats.total}</div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider">Closed</div>
          </div>
          <div className="rounded-lg bg-surface-muted p-3 text-center">
            <div className={cn("text-lg font-bold font-mono", stats.win_rate >= 0.5 ? "text-green-400" : "text-red-400")}>
              {(stats.win_rate * 100).toFixed(1)}%
            </div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider">Win Rate</div>
          </div>
          <div className="rounded-lg bg-surface-muted p-3 text-center">
            <div className={cn("text-lg font-bold font-mono", stats.avg_return >= 0 ? "text-green-400" : "text-red-400")}>
              {stats.avg_return >= 0 ? "+" : ""}{stats.avg_return.toFixed(2)}%
            </div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider">Avg Return</div>
          </div>
        </div>
      )}

      {/* Table */}
      {entries.length === 0 ? (
        <p className="text-xs text-gray-600 py-4 text-center">
          No trades recorded yet. Signals fire on closed 1h candles.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-surface-border text-gray-500">
                <th className="text-left py-2 pr-3">Time</th>
                <th className="text-left py-2 pr-3">Action</th>
                <th className="text-right py-2 pr-3">Entry</th>
                <th className="text-right py-2 pr-3">Exit</th>
                <th className="text-right py-2 pr-3">P&L %</th>
                <th className="text-right py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr
                  key={e.id}
                  className="border-b border-surface-border/40 hover:bg-surface-muted/30"
                >
                  <td className="py-2 pr-3 text-gray-400 font-mono whitespace-nowrap">
                    {formatTimestamp(e.timestamp)}
                  </td>
                  <td className="py-2 pr-3">
                    <span
                      className={cn(
                        "font-bold",
                        e.action === "BUY" ? "text-green-400" : "text-red-400"
                      )}
                    >
                      {e.action}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-300">
                    ${e.entry_price.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono text-gray-300">
                    {e.exit_price != null
                      ? `$${e.exit_price.toLocaleString("en-US", { minimumFractionDigits: 2 })}`
                      : "—"}
                  </td>
                  <td className="py-2 pr-3 text-right font-mono font-bold">
                    {e.return_pct != null ? (
                      <span className={e.return_pct >= 0 ? "text-green-400" : "text-red-400"}>
                        {e.return_pct >= 0 ? "+" : ""}{e.return_pct.toFixed(2)}%
                      </span>
                    ) : (
                      <span className="text-gray-500">—</span>
                    )}
                  </td>
                  <td className="py-2 text-right">
                    <span
                      className={cn(
                        "px-2 py-0.5 rounded-full text-[10px] font-semibold border",
                        e.status === "open"
                          ? "bg-blue-500/10 border-blue-500/20 text-blue-400"
                          : (e.return_pct ?? 0) >= 0
                          ? "bg-green-500/10 border-green-500/20 text-green-400"
                          : "bg-red-500/10 border-red-500/20 text-red-400"
                      )}
                    >
                      {e.status === "open" ? "Open" : (e.return_pct ?? 0) >= 0 ? "Win" : "Loss"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
