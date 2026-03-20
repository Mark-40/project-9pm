"use client";

import { usePaperTradingStore } from "@/store/use-paper-trading-store";
import { useMarketStore } from "@/store/use-market-store";
import { cn, formatTimestamp } from "@/lib/utils";
import { PAPER_TRADING_INITIAL_BALANCE } from "@/lib/constants";

interface Props {
  symbol: string;
  stopLoss?: number | null;
}

export default function PaperTrading({ symbol, stopLoss }: Props) {
  const price = useMarketStore((s) => s.symbols[symbol]?.price ?? 0);
  const prices = useMarketStore((s) => s.symbols);
  const { balance, positions, trades, totalPnl, buy, sell, reset } =
    usePaperTradingStore();

  const position = positions[symbol] ?? null;

  // Portfolio value = cash + sum of all open positions at current prices
  const openValue = Object.values(positions).reduce((acc, pos) => {
    const currentPrice = prices[pos.symbol]?.price ?? pos.entry;
    return acc + pos.qty * currentPrice;
  }, 0);
  const totalValue = balance + openValue;

  const unrealizedPnl = position
    ? position.qty * price - position.qty * position.entry
    : 0;

  const openCount = Object.keys(positions).length;

  return (
    <div className="rounded-xl border border-surface-border bg-surface-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Paper Trading
        </h3>
        <button
          onClick={reset}
          className="text-[10px] text-gray-600 hover:text-gray-400 transition-colors"
        >
          Reset
        </button>
      </div>

      {/* Portfolio summary */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-surface-muted rounded-lg p-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
            Portfolio Value
          </p>
          <p className="text-sm font-mono font-bold text-gray-200">
            ${totalValue.toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="bg-surface-muted rounded-lg p-3">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
            Total P&L
          </p>
          <p
            className={cn(
              "text-sm font-mono font-bold",
              totalPnl >= 0 ? "text-green-400" : "text-red-400"
            )}
          >
            {totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Cash + open positions count */}
      <div className="flex justify-between text-xs text-gray-500 bg-surface-muted rounded-lg px-3 py-2">
        <span>
          Cash:{" "}
          <span className="text-gray-300 font-mono">
            ${balance.toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </span>
        </span>
        <span>
          Open positions:{" "}
          <span className="text-gray-300 font-mono">{openCount}</span>
        </span>
      </div>

      {/* Current symbol position */}
      {position ? (
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 space-y-1">
          <p className="text-[10px] text-blue-400 uppercase tracking-wider">
            Open — {symbol.replace("USDT", "/USDT")}
          </p>
          <div className="flex justify-between text-xs">
            <span className="text-gray-400">Entry</span>
            <span className="font-mono text-gray-200">
              ${position.entry.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-400">Size</span>
            <span className="font-mono text-gray-200">
              ${position.position_size.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </span>
          </div>
          {position.stop_loss != null && (
            <div className="flex justify-between text-xs">
              <span className="text-gray-400">Stop Loss</span>
              <span className="font-mono text-red-400">
                ${position.stop_loss.toLocaleString("en-US", { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
          <div className="flex justify-between text-xs">
            <span className="text-gray-400">Unrealized P&L</span>
            <span
              className={cn(
                "font-mono font-semibold",
                unrealizedPnl >= 0 ? "text-green-400" : "text-red-400"
              )}
            >
              {unrealizedPnl >= 0 ? "+" : ""}${unrealizedPnl.toFixed(2)}
            </span>
          </div>
        </div>
      ) : (
        <div className="text-xs text-gray-600 bg-surface-muted rounded-lg px-3 py-2 space-y-0.5">
          <p>No open position for {symbol.replace("USDT", "/USDT")}</p>
          {stopLoss != null && price > stopLoss ? (
            <p className="text-gray-500">
              Risk-based sizing active — 2% risk / trade
              {" "}(SL: ${stopLoss.toLocaleString("en-US", { minimumFractionDigits: 2 })})
            </p>
          ) : (
            <p className="text-gray-500">Fixed size: 10% of balance per trade</p>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => buy(symbol, price, stopLoss)}
          disabled={!!position || price === 0 || balance <= 0}
          className="py-2 rounded-lg bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white text-xs font-semibold transition-colors"
        >
          BUY @ $
          {price > 0
            ? price.toLocaleString("en-US", { minimumFractionDigits: 2 })
            : "—"}
        </button>
        <button
          onClick={() => sell(symbol, price)}
          disabled={!position || price === 0}
          className="py-2 rounded-lg bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white text-xs font-semibold transition-colors"
        >
          SELL @ $
          {price > 0
            ? price.toLocaleString("en-US", { minimumFractionDigits: 2 })
            : "—"}
        </button>
      </div>

      {/* All open positions (other symbols) */}
      {openCount > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">
            All Open Positions
          </p>
          <div className="space-y-1">
            {Object.values(positions).map((pos) => {
              const cur = prices[pos.symbol]?.price ?? pos.entry;
              const upnl = pos.qty * cur - pos.qty * pos.entry;
              return (
                <div
                  key={pos.symbol}
                  className="flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-surface-muted"
                >
                  <span className="text-gray-400">
                    {pos.symbol.replace("USDT", "/USDT")}
                  </span>
                  <span
                    className={cn(
                      "font-mono font-semibold",
                      upnl >= 0 ? "text-green-400" : "text-red-400"
                    )}
                  >
                    {upnl >= 0 ? "+" : ""}${upnl.toFixed(2)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Trade history */}
      {trades.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">
            Trade History
          </p>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {trades.slice(0, 20).map((t) => (
              <div
                key={t.id}
                className={cn(
                  "flex items-center justify-between text-xs px-3 py-1.5 rounded-lg",
                  t.is_win ? "bg-green-500/10" : "bg-red-500/10"
                )}
              >
                <span className="text-gray-400">
                  {t.symbol.replace("USDT", "")} —{" "}
                  {formatTimestamp(t.timestamp)}
                </span>
                <span
                  className={cn(
                    "font-mono font-bold",
                    t.is_win ? "text-green-400" : "text-red-400"
                  )}
                >
                  {t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
