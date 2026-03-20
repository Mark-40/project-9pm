"use client";

import { useState, useCallback } from "react";
import { API_BASE_URL } from "@/lib/constants";
import type { BacktestResult } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  symbol: string;
}

export default function BacktestPanel({ symbol }: Props) {
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/backtest/${symbol}`);
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail ?? "Backtest failed");
        return;
      }
      setResult(await res.json());
    } catch (e) {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  return (
    <div className="rounded-xl border border-surface-border bg-surface-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Backtest — {symbol.replace("USDT", "/USDT")}
        </h3>
        <button
          onClick={run}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-medium transition-colors"
        >
          {loading ? "Running…" : "Run Backtest"}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}

      {result && (
        <div className="space-y-4">
          {/* Summary stats */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <StatBox label="Total Trades" value={String(result.total_signals)} />
            <StatBox
              label="Win Rate"
              value={`${result.win_rate.toFixed(1)}%`}
              color={result.win_rate >= 50 ? "green" : "red"}
            />
            <StatBox
              label="Avg Return"
              value={`${result.avg_return.toFixed(3)}%`}
              color={result.avg_return >= 0 ? "green" : "red"}
            />
            <StatBox
              label="Profit Factor"
              value={result.profit_factor != null ? result.profit_factor.toFixed(2) : "N/A"}
              color={
                result.profit_factor != null
                  ? result.profit_factor >= 1 ? "green" : "red"
                  : undefined
              }
            />
            <StatBox
              label="Max Drawdown"
              value={`${result.max_drawdown.toFixed(2)}%`}
              color={result.max_drawdown > 10 ? "red" : undefined}
            />
            <StatBox
              label="Total Return"
              value={`${result.total_return.toFixed(2)}%`}
              color={result.total_return >= 0 ? "green" : "red"}
            />
          </div>

          {/* Recent trades */}
          {result.trades.length > 0 && (
            <div>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">
                Recent Trades (last {result.trades.length})
              </p>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {result.trades.map((t, i) => (
                  <div
                    key={i}
                    className={cn(
                      "flex items-center justify-between text-xs px-3 py-1.5 rounded-lg",
                      t.is_win ? "bg-green-500/10" : "bg-red-500/10"
                    )}
                  >
                    <span className="font-mono text-gray-400">
                      ${t.entry.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                      {" → "}
                      ${t.exit_price.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </span>
                    <span
                      className={cn(
                        "font-mono font-bold",
                        t.is_win ? "text-green-400" : "text-red-400"
                      )}
                    >
                      {t.return_pct >= 0 ? "+" : ""}
                      {t.return_pct.toFixed(3)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!result && !loading && (
        <p className="text-xs text-gray-600 text-center py-4">
          Click "Run Backtest" to simulate trading with historical data
        </p>
      )}
    </div>
  );
}

function StatBox({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: "green" | "red";
}) {
  return (
    <div className="bg-surface-muted rounded-lg p-3">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p
        className={cn(
          "text-sm font-mono font-bold",
          color === "green"
            ? "text-green-400"
            : color === "red"
            ? "text-red-400"
            : "text-gray-200"
        )}
      >
        {value}
      </p>
    </div>
  );
}
