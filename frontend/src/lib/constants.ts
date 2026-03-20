export const SYMBOLS = [
  "BTCUSDT",
  "ETHUSDT",
  "SOLUSDT",
  "BNBUSDT",
  "XRPUSDT",
  "DOGEUSDT",
  "ADAUSDT",
  "AVAXUSDT",
  "LINKUSDT",
] as const;

export type SymbolType = (typeof SYMBOLS)[number];

export const SYMBOL_LABELS: Record<string, string> = {
  BTCUSDT: "BTC/USDT",
  ETHUSDT: "ETH/USDT",
  SOLUSDT: "SOL/USDT",
  BNBUSDT: "BNB/USDT",
  XRPUSDT: "XRP/USDT",
  DOGEUSDT: "DOGE/USDT",
  ADAUSDT: "ADA/USDT",
  AVAXUSDT: "AVAX/USDT",
  LINKUSDT: "LINK/USDT",
};

export const SYMBOL_ICONS: Record<string, string> = {
  BTCUSDT: "₿",
  ETHUSDT: "Ξ",
  SOLUSDT: "◎",
  BNBUSDT: "B",
  XRPUSDT: "✕",
  DOGEUSDT: "Ð",
  ADAUSDT: "₳",
  AVAXUSDT: "A",
  LINKUSDT: "⬡",
};

export const INTERVALS = [
  { label: "1m", value: "1m" },
  { label: "5m", value: "5m" },
  { label: "15m", value: "15m" },
  { label: "1h", value: "1h" },
  { label: "4h", value: "4h" },
  { label: "1d", value: "1d" },
] as const;

export const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const MAX_SIGNAL_LOG = 50;
export const MAX_CANDLES = 500;

export const PAPER_TRADING_INITIAL_BALANCE = 10_000;
export const PAPER_TRADE_SIZE = 1_000; // fallback fixed size when no stop-loss
export const PAPER_RISK_PCT = 0.02;    // 2% portfolio risk per trade (risk-based sizing)
