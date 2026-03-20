"use client";

import { useCallback, useEffect, useRef } from "react";
import { useMarketStore } from "@/store/use-market-store";
import { useSignalLogStore } from "@/store/use-signal-log-store";
import { WS_BASE_URL } from "@/lib/constants";
import type { WSMessage } from "@/lib/types";

const RECONNECT_DELAY_MS = 3_000;
const MAX_RECONNECT = 20;
const PING_INTERVAL_MS = 15_000;

export function useTradingWS(symbol: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const pingTimer = useRef<ReturnType<typeof setInterval>>();

  const updateTick = useMarketStore((s) => s.updateTick);
  const updateSignal = useMarketStore((s) => s.updateSignal);
  const setCandles = useMarketStore((s) => s.setCandles);
  const setConnected = useMarketStore((s) => s.setConnected);
  const setVolumeProfile = useMarketStore((s) => s.setVolumeProfile);
  const setPivots = useMarketStore((s) => s.setPivots);
  const addSignal = useSignalLogStore((s) => s.add);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_BASE_URL}/${symbol}`);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectCount.current = 0;
      setConnected(symbol, true);

      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, PING_INTERVAL_MS);
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        handleMessage(msg);
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setConnected(symbol, false);
      clearInterval(pingTimer.current);
      if (reconnectCount.current < MAX_RECONNECT) {
        reconnectCount.current++;
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };

    ws.onerror = () => ws.close();
  }, [symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleMessage(msg: WSMessage) {
    switch (msg.type) {
      case "tick":
        updateTick(symbol, {
          price: msg.price ?? 0,
          open: msg.open ?? 0,
          high: msg.high ?? 0,
          low: msg.low ?? 0,
          volume: msg.volume ?? 0,
        });
        break;

      case "signal":
        if (!msg.ta) break;
        updateSignal(symbol, {
          action: msg.action ?? "HOLD",
          source: msg.source ?? "rule",
          strength: msg.strength ?? 0,
          ta: msg.ta,
          ml: msg.ml ?? null,
          timestamp: msg.timestamp ?? Date.now(),
          price: msg.price ?? 0,
          qualityScore: msg.quality_score,
          qualityLabel: msg.quality_label,
          confluenceScore: msg.confluence_score,
          confluenceDirection: msg.confluence_direction,
          ta15m: msg.ta_15m,
          pivots: msg.pivots,
          takeProfit: msg.take_profit,
          stopLoss: msg.stop_loss,
          riskReward: msg.risk_reward,
          trailingStop: msg.trailing_stop,
          macroTrend: msg.macro_trend,
          ta4h: msg.ta_4h,
          confluence4hScore: msg.confluence_4h_score,
          confluence4hDirection: msg.confluence_4h_direction,
        });
        if (msg.action && msg.action !== "HOLD") {
          addSignal({
            symbol,
            action: msg.action,
            price: msg.price ?? 0,
            strength: msg.strength ?? 0,
            source: msg.source ?? "rule",
            timestamp: msg.timestamp ?? Date.now(),
            quality_score: msg.quality_score,
            quality_label: msg.quality_label,
          });
        }
        break;

      case "init": {
        if (msg.price) updateTick(symbol, { price: msg.price });
        if (msg.candles?.length) setCandles(symbol, msg.candles);
        if (msg.volume_profile?.length) setVolumeProfile(symbol, msg.volume_profile);
        if (msg.pivots?.pivot != null) setPivots(symbol, msg.pivots);
        if (msg.signal) {
          const s = msg.signal;
          updateSignal(symbol, {
            action: s.action,
            source: s.source,
            strength: s.strength,
            ta: s.ta,
            ml: s.ml,
            timestamp: s.timestamp,
            price: s.price,
            qualityScore: s.quality_score,
            qualityLabel: s.quality_label,
            confluenceScore: s.confluence_score,
            confluenceDirection: s.confluence_direction,
            ta15m: s.ta_15m,
            pivots: s.pivots,
            takeProfit: s.take_profit,
            stopLoss: s.stop_loss,
            riskReward: s.risk_reward,
            trailingStop: s.trailing_stop,
            macroTrend: s.macro_trend,
            ta4h: s.ta_4h,
            confluence4hScore: s.confluence_4h_score,
            confluence4hDirection: s.confluence_4h_direction,
          });
        }
        break;
      }

      case "volume_profile":
        if (msg.buckets?.length) setVolumeProfile(symbol, msg.buckets);
        break;
    }
  }

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      clearInterval(pingTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
