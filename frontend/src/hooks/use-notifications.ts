"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SignalAction } from "@/lib/types";

export function useNotifications() {
  const [enabled, setEnabled] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>("default");

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    setPermission(Notification.permission);
    if (Notification.permission === "granted") setEnabled(true);
  }, []);

  const requestPermission = useCallback(async () => {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    const result = await Notification.requestPermission();
    setPermission(result);
    if (result === "granted") setEnabled(true);
  }, []);

  const toggle = useCallback(async () => {
    if (!enabled) {
      if (permission !== "granted") {
        await requestPermission();
      } else {
        setEnabled(true);
      }
    } else {
      setEnabled(false);
    }
  }, [enabled, permission, requestPermission]);

  const notify = useCallback(
    (symbol: string, action: SignalAction, price: number) => {
      if (!enabled || typeof window === "undefined") return;
      if (!("Notification" in window) || Notification.permission !== "granted") return;

      const emoji = action === "BUY" ? "🟢" : action === "SELL" ? "🔴" : "🟡";
      new Notification(`${emoji} ${action} Signal — ${symbol}`, {
        body: `${symbol.replace("USDT", "/USDT")} @ $${price.toLocaleString("en-US", {
          minimumFractionDigits: 2,
        })}`,
        icon: "/favicon.ico",
        tag: `${symbol}-${action}`,
      });
    },
    [enabled]
  );

  return { enabled, permission, toggle, notify };
}
