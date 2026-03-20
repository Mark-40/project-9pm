"use client";

import { useEffect, useState, useCallback } from "react";
import { API_BASE_URL } from "@/lib/constants";
import type { OrderBookData } from "@/lib/types";

interface Props {
  symbol: string;
}

export default function OrderBook({ symbol }: Props) {
  const [data, setData] = useState<OrderBookData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await window.fetch(`${API_BASE_URL}/api/orderbook/${symbol}?limit=15`);
      if (res.ok) setData(await res.json());
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetch();
    const id = setInterval(fetch, 5000);
    return () => clearInterval(id);
  }, [fetch]);

  if (loading && !data) {
    return (
      <div className="rounded-xl border border-surface-border bg-surface-card p-5">
        <p className="text-xs text-gray-500 text-center">Loading order book…</p>
      </div>
    );
  }

  const maxBidQty = data ? Math.max(...data.bids.map(([, q]) => q), 1) : 1;
  const maxAskQty = data ? Math.max(...data.asks.map(([, q]) => q), 1) : 1;

  return (
    <div className="rounded-xl border border-surface-border bg-surface-card p-4 space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
        Order Book — {symbol.replace("USDT", "/USDT")}
      </h3>

      {data && (
        <div className="grid grid-cols-2 gap-3">
          {/* Bids */}
          <div>
            <div className="flex justify-between text-[10px] text-gray-600 mb-1.5 px-1">
              <span>Price</span>
              <span>Qty</span>
            </div>
            {data.bids.slice(0, 10).map(([price, qty], i) => (
              <div key={i} className="relative flex justify-between text-xs py-0.5 px-1">
                <div
                  className="absolute inset-0 bg-green-500/10 rounded"
                  style={{ width: `${(qty / maxBidQty) * 100}%` }}
                />
                <span className="relative text-green-400 font-mono">
                  {price.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </span>
                <span className="relative text-gray-400 font-mono">
                  {qty.toFixed(4)}
                </span>
              </div>
            ))}
          </div>

          {/* Asks */}
          <div>
            <div className="flex justify-between text-[10px] text-gray-600 mb-1.5 px-1">
              <span>Price</span>
              <span>Qty</span>
            </div>
            {data.asks.slice(0, 10).map(([price, qty], i) => (
              <div key={i} className="relative flex justify-between text-xs py-0.5 px-1">
                <div
                  className="absolute inset-0 bg-red-500/10 rounded"
                  style={{ width: `${(qty / maxAskQty) * 100}%` }}
                />
                <span className="relative text-red-400 font-mono">
                  {price.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </span>
                <span className="relative text-gray-400 font-mono">
                  {qty.toFixed(4)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
