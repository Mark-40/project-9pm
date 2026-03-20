"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { PaperPosition, PaperTrade } from "@/lib/types";
import { PAPER_TRADING_INITIAL_BALANCE, PAPER_TRADE_SIZE } from "@/lib/constants";
import { generateId } from "@/lib/utils";

// Risk 2% of portfolio per trade (loss if stop-loss is hit)
const RISK_PCT = 0.02;
// Cap position at 25% of portfolio even with tight stops
const MAX_POSITION_PCT = 0.25;

interface PaperTradingStore {
  balance: number;
  positions: Record<string, PaperPosition>; // keyed by symbol
  trades: PaperTrade[];
  totalPnl: number;
  buy: (symbol: string, price: number, stopLoss?: number | null) => void;
  sell: (symbol: string, price: number) => void;
  reset: () => void;
}

export const usePaperTradingStore = create<PaperTradingStore>()(
  persist(
    (set, get) => ({
      balance: PAPER_TRADING_INITIAL_BALANCE,
      positions: {},
      trades: [],
      totalPnl: 0,

      buy: (symbol, price, stopLoss) => {
        const { balance, positions } = get();
        if (positions[symbol]) return; // already in this symbol
        if (price <= 0 || balance <= 0) return;

        let positionSize: number;
        let qty: number;

        if (stopLoss != null && stopLoss > 0 && price > stopLoss) {
          // Risk-based sizing: risk RISK_PCT of balance on this trade
          const riskAmount = balance * RISK_PCT;
          const riskPerUnit = price - stopLoss;
          qty = riskAmount / riskPerUnit;
          positionSize = qty * price;
          // Cap position to avoid over-allocation
          const maxPosition = balance * MAX_POSITION_PCT;
          if (positionSize > maxPosition) {
            positionSize = maxPosition;
            qty = positionSize / price;
          }
        } else {
          // Fallback: fixed position size
          positionSize = Math.min(PAPER_TRADE_SIZE, balance * 0.1);
          qty = positionSize / price;
        }

        if (balance < positionSize || positionSize <= 0) return;

        set({
          balance: Math.round((balance - positionSize) * 100) / 100,
          positions: {
            ...positions,
            [symbol]: {
              symbol,
              entry: price,
              qty,
              timestamp: Date.now(),
              stop_loss: stopLoss ?? null,
              position_size: Math.round(positionSize * 100) / 100,
            },
          },
        });
      },

      sell: (symbol, price) => {
        const { positions, trades, totalPnl, balance } = get();
        const position = positions[symbol];
        if (!position || price <= 0) return;

        const value = position.qty * price;
        const pnl = value - position.qty * position.entry;
        const return_pct = ((price - position.entry) / position.entry) * 100;

        const trade: PaperTrade = {
          id: generateId(),
          symbol,
          entry: position.entry,
          exit: price,
          qty: position.qty,
          return_pct: Math.round(return_pct * 100) / 100,
          pnl: Math.round(pnl * 100) / 100,
          is_win: pnl > 0,
          timestamp: Date.now(),
        };

        const { [symbol]: _closed, ...remaining } = positions;
        set({
          balance: Math.round((balance + value) * 100) / 100,
          positions: remaining,
          trades: [trade, ...trades].slice(0, 100),
          totalPnl: Math.round((totalPnl + pnl) * 100) / 100,
        });
      },

      reset: () =>
        set({
          balance: PAPER_TRADING_INITIAL_BALANCE,
          positions: {},
          trades: [],
          totalPnl: 0,
        }),
    }),
    {
      name: "crypto-paper-trading",
    }
  )
);
