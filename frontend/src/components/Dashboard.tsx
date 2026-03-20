"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { Activity, Wifi, WifiOff } from "lucide-react";
import { useMarketStore } from "@/store/use-market-store";
import { useTradingWS } from "@/hooks/use-trading-ws";
import { useNotifications } from "@/hooks/use-notifications";
import { SYMBOLS, SYMBOL_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import SignalCard from "./SignalCard";
import IndicatorPanel from "./IndicatorPanel";
import TickerBar from "./TickerBar";
import SignalLog from "./SignalLog";
import ThemeToggle from "./ThemeToggle";
import NotificationToggle from "./NotificationToggle";
import OrderBook from "./OrderBook";
import MarketOverview from "./MarketOverview";
import BacktestPanel from "./BacktestPanel";
import PaperTrading from "./PaperTrading";
import TradeLog from "./TradeLog";
import ICScorePanel from "./ICScorePanel";

// Chart must be client-only (uses DOM APIs)
const TradingChart = dynamic(() => import("./TradingChart"), { ssr: false });

type Tab = "chart" | "orderbook" | "backtest" | "paper" | "market" | "tradelog" | "ic";

const TABS: { id: Tab; label: string }[] = [
  { id: "chart", label: "Chart" },
  { id: "orderbook", label: "Order Book" },
  { id: "backtest", label: "Backtest" },
  { id: "paper", label: "Paper Trading" },
  { id: "market", label: "Market Overview" },
  { id: "tradelog", label: "Trade Log" },
  { id: "ic", label: "IC Analysis" },
];

// Mount a WS watcher for each symbol so all data stays fresh in the background
function SymbolWatcher({ symbol }: { symbol: string }) {
  const { notify } = useNotifications();
  const action = useMarketStore((s) => s.symbols[symbol]?.action);
  const price = useMarketStore((s) => s.symbols[symbol]?.price ?? 0);

  useTradingWS(symbol);

  // Notify on actionable signals
  if (action && action !== "HOLD" && price > 0) {
    // (intentionally not calling here — notifications are triggered in ws hook)
  }

  return null;
}

export default function Dashboard() {
  const activeSymbol = useMarketStore((s) => s.activeSymbol);
  const state = useMarketStore((s) => s.symbols[activeSymbol]);
  const [activeTab, setActiveTab] = useState<Tab>("chart");

  return (
    <div className="min-h-screen bg-surface text-gray-100">
      {/* Mount WebSocket connections for ALL symbols */}
      {SYMBOLS.map((s) => (
        <SymbolWatcher key={s} symbol={s} />
      ))}

      {/* ── Nav bar ─────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-10 border-b border-surface-border bg-surface/80 backdrop-blur-sm">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Activity className="size-5 text-blue-500" />
            <span className="font-bold text-white text-sm tracking-wide">
              CRYPTO SIGNALS
            </span>
            <span className="text-[10px] text-gray-600 uppercase tracking-widest ml-1">
              LIVE · BINANCE
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs">
            {state?.connected ? (
              <span className="flex items-center gap-1.5 text-green-400">
                <Wifi className="size-3" />
                Live
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-gray-500">
                <WifiOff className="size-3" />
                Connecting…
              </span>
            )}
            <NotificationToggle />
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* ── Main layout ─────────────────────────────────────────────── */}
      <main className="max-w-[1600px] mx-auto px-4 py-6 space-y-6">
        {/* Ticker row */}
        <TickerBar />

        {/* Active pair price */}
        <div className="flex items-baseline gap-3">
          <h1 className="text-3xl font-bold font-mono text-white">
            {state?.price
              ? `$${state.price.toLocaleString("en-US", {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: state.price < 1 ? 5 : 2,
                })}`
              : "—"}
          </h1>
          <span className="text-gray-500 text-sm font-medium">
            {SYMBOL_LABELS[activeSymbol]}
          </span>
          {state?.price && state.prevPrice ? (
            <span
              className={
                state.price >= state.prevPrice
                  ? "text-green-400 text-sm"
                  : "text-red-400 text-sm"
              }
            >
              {state.price >= state.prevPrice ? "▲" : "▼"}
            </span>
          ) : null}
        </div>

        {/* Tab navigation */}
        <div className="flex items-center gap-1 border-b border-surface-border overflow-x-auto scrollbar-hide">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "px-4 py-2.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors",
                activeTab === tab.id
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-500 hover:text-gray-300"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "chart" && (
          <>
            <TradingChart symbol={activeSymbol} />

            {/* Signal + Indicators */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              <SignalCard symbol={activeSymbol} />
              <IndicatorPanel symbol={activeSymbol} />

              {/* Market context mini-card */}
              <div className="rounded-xl border border-surface-border bg-surface-card p-5 space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Market Context
                </h3>
                {state?.ta ? (
                  <>
                    <InfoRow
                      label="Current Price"
                      value={`$${state.price.toLocaleString("en-US", {
                        minimumFractionDigits: 2,
                      })}`}
                    />
                    <InfoRow
                      label="BB Upper"
                      value={
                        state.ta.bb_upper
                          ? `$${state.ta.bb_upper.toLocaleString("en-US", {
                              minimumFractionDigits: 2,
                            })}`
                          : "—"
                      }
                    />
                    <InfoRow
                      label="BB Lower"
                      value={
                        state.ta.bb_lower
                          ? `$${state.ta.bb_lower.toLocaleString("en-US", {
                              minimumFractionDigits: 2,
                            })}`
                          : "—"
                      }
                    />
                    <InfoRow
                      label="EMA 9 vs EMA 21"
                      value={
                        state.ta.ema_9 && state.ta.ema_21
                          ? state.ta.ema_9 > state.ta.ema_21
                            ? "Bullish ▲"
                            : "Bearish ▼"
                          : "—"
                      }
                      colored={
                        state.ta.ema_9 && state.ta.ema_21
                          ? state.ta.ema_9 > state.ta.ema_21
                            ? "green"
                            : "red"
                          : undefined
                      }
                    />
                    <InfoRow
                      label="RSI Zone"
                      value={
                        state.ta.rsi != null
                          ? state.ta.rsi < 30
                            ? "Oversold"
                            : state.ta.rsi > 70
                            ? "Overbought"
                            : "Neutral"
                          : "—"
                      }
                      colored={
                        state.ta.rsi != null
                          ? state.ta.rsi < 30
                            ? "green"
                            : state.ta.rsi > 70
                            ? "red"
                            : undefined
                          : undefined
                      }
                    />
                    <InfoRow
                      label="MACD Trend"
                      value={
                        state.ta.macd_hist != null
                          ? state.ta.macd_hist > 0
                            ? "Bullish"
                            : "Bearish"
                          : "—"
                      }
                      colored={
                        state.ta.macd_hist != null
                          ? state.ta.macd_hist > 0
                            ? "green"
                            : "red"
                          : undefined
                      }
                    />
                    <InfoRow
                      label="ADX Strength"
                      value={
                        state.ta.adx != null
                          ? state.ta.adx > 40
                            ? `${state.ta.adx.toFixed(1)} — Strong`
                            : state.ta.adx > 25
                            ? `${state.ta.adx.toFixed(1)} — Trending`
                            : `${state.ta.adx.toFixed(1)} — Ranging`
                          : "—"
                      }
                      colored={
                        state.ta.adx != null
                          ? state.ta.adx > 25
                            ? "green"
                            : undefined
                          : undefined
                      }
                    />
                    <InfoRow
                      label="Macro Trend"
                      value={
                        state.macroTrend
                          ? state.macroTrend === "uptrend"
                            ? "Uptrend ▲"
                            : state.macroTrend === "downtrend"
                            ? "Downtrend ▼"
                            : "Ranging ↔"
                          : "—"
                      }
                      colored={
                        state.macroTrend === "uptrend"
                          ? "green"
                          : state.macroTrend === "downtrend"
                          ? "red"
                          : undefined
                      }
                    />
                    <InfoRow
                      label="VWAP"
                      value={
                        state.ta.vwap != null
                          ? `$${state.ta.vwap.toLocaleString("en-US", { minimumFractionDigits: 2 })}`
                          : "—"
                      }
                      colored={
                        state.ta.vwap != null && state.price > 0
                          ? state.price > state.ta.vwap
                            ? "green"  // above VWAP = bullish (trend-following)
                            : "red"
                          : undefined
                      }
                    />
                    <InfoRow
                      label="OBV Trend"
                      value={
                        state.ta.obv != null && state.ta.obv_signal != null
                          ? state.ta.obv > state.ta.obv_signal
                            ? "Bullish"
                            : "Bearish"
                          : "—"
                      }
                      colored={
                        state.ta.obv != null && state.ta.obv_signal != null
                          ? state.ta.obv > state.ta.obv_signal
                            ? "green"
                            : "red"
                          : undefined
                      }
                    />
                    {/* Pivot levels */}
                    {state.pivots?.pivot != null && (
                      <>
                        <div className="pt-1 border-t border-surface-border/40">
                          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-1.5">
                            Pivot Levels
                          </p>
                          <InfoRow
                            label="Pivot"
                            value={`$${state.pivots.pivot.toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
                          />
                          {state.pivots.r1 != null && (
                            <InfoRow
                              label="R1"
                              value={`$${state.pivots.r1.toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
                              colored="red"
                            />
                          )}
                          {state.pivots.s1 != null && (
                            <InfoRow
                              label="S1"
                              value={`$${state.pivots.s1.toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
                              colored="green"
                            />
                          )}
                        </div>
                      </>
                    )}
                  </>
                ) : (
                  <p className="text-xs text-gray-600">
                    Waiting for closed candle…
                  </p>
                )}
              </div>
            </div>

            {/* Signal log */}
            <SignalLog />
          </>
        )}

        {activeTab === "orderbook" && (
          <div className="max-w-2xl">
            <OrderBook symbol={activeSymbol} />
          </div>
        )}

        {activeTab === "backtest" && (
          <div className="max-w-2xl">
            <BacktestPanel symbol={activeSymbol} />
          </div>
        )}

        {activeTab === "paper" && (
          <div className="max-w-md">
            <PaperTrading symbol={activeSymbol} stopLoss={state?.stopLoss} />
          </div>
        )}

        {activeTab === "market" && <MarketOverview />}

        {activeTab === "tradelog" && (
          <div className="max-w-4xl">
            <TradeLog symbol={activeSymbol} />
          </div>
        )}

        {activeTab === "ic" && (
          <div className="max-w-2xl">
            <ICScorePanel symbol={activeSymbol} />
          </div>
        )}
      </main>
    </div>
  );
}

function InfoRow({
  label,
  value,
  colored,
}: {
  label: string;
  value: string;
  colored?: "green" | "red" | undefined;
}) {
  return (
    <div className="flex justify-between text-xs py-1 border-b border-surface-border/40 last:border-0">
      <span className="text-gray-500">{label}</span>
      <span
        className={
          colored === "green"
            ? "text-green-400 font-semibold"
            : colored === "red"
            ? "text-red-400 font-semibold"
            : "text-gray-300 font-mono"
        }
      >
        {value}
      </span>
    </div>
  );
}
