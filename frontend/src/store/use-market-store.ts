import { create } from "zustand";
import type {
  TAResult,
  MLPrediction,
  SignalAction,
  SignalSource,
  CandleBar,
  QualityLabel,
  ConfluenceDirection,
  MacroTrend,
  PivotLevels,
  VolumeBucket,
} from "@/lib/types";

import { SYMBOLS, MAX_CANDLES } from "@/lib/constants";

interface SymbolState {
  price: number;
  prevPrice: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  action: SignalAction | null;
  source: SignalSource | null;
  strength: number;
  ta: TAResult | null;
  ml: MLPrediction | null;
  candles: CandleBar[];
  connected: boolean;
  signalTimestamp: number | null;
  // Feature 2: quality score
  qualityScore: number;
  qualityLabel: QualityLabel;
  // Feature 1: multi-timeframe confluence
  confluenceScore: number | null;
  confluenceDirection: ConfluenceDirection | null;
  ta15m: TAResult | null;
  // Feature 5: pivot levels
  pivots: PivotLevels | null;
  // Feature 13: volume profile
  volumeProfile: VolumeBucket[];
  // ATR targets + macro trend
  takeProfit: number | null;
  stopLoss: number | null;
  riskReward: number | null;
  trailingStop: number | null;
  macroTrend: MacroTrend | null;
  // 4H confluence
  ta4h: TAResult | null;
  confluence4hScore: number | null;
  confluence4hDirection: ConfluenceDirection | null;
}

interface MarketStore {
  symbols: Record<string, SymbolState>;
  activeSymbol: string;
  setActiveSymbol: (symbol: string) => void;
  updateTick: (
    symbol: string,
    tick: Partial<Pick<SymbolState, "price" | "open" | "high" | "low" | "volume">>
  ) => void;
  updateSignal: (
    symbol: string,
    data: {
      action: SignalAction;
      source: SignalSource;
      strength: number;
      ta: TAResult;
      ml: MLPrediction | null;
      timestamp: number;
      price: number;
      qualityScore?: number;
      qualityLabel?: QualityLabel;
      confluenceScore?: number | null;
      confluenceDirection?: ConfluenceDirection | null;
      ta15m?: TAResult | null;
      pivots?: PivotLevels | null;
      takeProfit?: number | null;
      stopLoss?: number | null;
      riskReward?: number | null;
      trailingStop?: number | null;
      macroTrend?: MacroTrend | null;
      ta4h?: TAResult | null;
      confluence4hScore?: number | null;
      confluence4hDirection?: ConfluenceDirection | null;
    }
  ) => void;
  setCandles: (symbol: string, candles: CandleBar[]) => void;
  pushCandle: (symbol: string, candle: CandleBar) => void;
  setConnected: (symbol: string, connected: boolean) => void;
  setVolumeProfile: (symbol: string, profile: VolumeBucket[]) => void;
  setPivots: (symbol: string, pivots: PivotLevels) => void;
}

const defaultState = (): SymbolState => ({
  price: 0,
  prevPrice: 0,
  open: 0,
  high: 0,
  low: 0,
  volume: 0,
  action: null,
  source: null,
  strength: 0,
  ta: null,
  ml: null,
  candles: [],
  connected: false,
  signalTimestamp: null,
  qualityScore: 0,
  qualityLabel: "Weak",
  confluenceScore: null,
  confluenceDirection: null,
  ta15m: null,
  pivots: null,
  volumeProfile: [],
  takeProfit: null,
  stopLoss: null,
  riskReward: null,
  trailingStop: null,
  macroTrend: null,
  ta4h: null,
  confluence4hScore: null,
  confluence4hDirection: null,
});

export const useMarketStore = create<MarketStore>((set) => ({
  symbols: Object.fromEntries(SYMBOLS.map((s) => [s, defaultState()])),
  activeSymbol: "BTCUSDT",

  setActiveSymbol: (symbol) => set({ activeSymbol: symbol }),

  updateTick: (symbol, tick) =>
    set((state) => ({
      symbols: {
        ...state.symbols,
        [symbol]: {
          ...state.symbols[symbol],
          prevPrice: state.symbols[symbol]?.price ?? 0,
          ...tick,
        },
      },
    })),

  updateSignal: (symbol, data) =>
    set((state) => ({
      symbols: {
        ...state.symbols,
        [symbol]: {
          ...state.symbols[symbol],
          action: data.action,
          source: data.source,
          strength: data.strength,
          ta: data.ta,
          ml: data.ml,
          signalTimestamp: data.timestamp,
          price: data.price || state.symbols[symbol]?.price || 0,
          qualityScore: data.qualityScore ?? state.symbols[symbol]?.qualityScore ?? 0,
          qualityLabel: data.qualityLabel ?? state.symbols[symbol]?.qualityLabel ?? "Weak",
          confluenceScore: data.confluenceScore ?? null,
          confluenceDirection: data.confluenceDirection ?? null,
          ta15m: data.ta15m ?? null,
          pivots: data.pivots ?? state.symbols[symbol]?.pivots ?? null,
          takeProfit: data.takeProfit ?? null,
          stopLoss: data.stopLoss ?? null,
          riskReward: data.riskReward ?? null,
          trailingStop: data.trailingStop ?? null,
          macroTrend: data.macroTrend ?? null,
          ta4h: data.ta4h ?? null,
          confluence4hScore: data.confluence4hScore ?? null,
          confluence4hDirection: data.confluence4hDirection ?? null,
        },
      },
    })),

  setCandles: (symbol, candles) =>
    set((state) => ({
      symbols: {
        ...state.symbols,
        [symbol]: { ...state.symbols[symbol], candles },
      },
    })),

  pushCandle: (symbol, candle) =>
    set((state) => {
      const prev = state.symbols[symbol];
      const candles = [...prev.candles.slice(-(MAX_CANDLES - 1)), candle];
      return {
        symbols: { ...state.symbols, [symbol]: { ...prev, candles } },
      };
    }),

  setConnected: (symbol, connected) =>
    set((state) => ({
      symbols: {
        ...state.symbols,
        [symbol]: { ...state.symbols[symbol], connected },
      },
    })),

  setVolumeProfile: (symbol, volumeProfile) =>
    set((state) => ({
      symbols: {
        ...state.symbols,
        [symbol]: { ...state.symbols[symbol], volumeProfile },
      },
    })),

  setPivots: (symbol, pivots) =>
    set((state) => ({
      symbols: {
        ...state.symbols,
        [symbol]: { ...state.symbols[symbol], pivots },
      },
    })),
}));
