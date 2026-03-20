export type SignalAction = "BUY" | "SELL" | "HOLD";
export type SignalSource = "ml" | "rule" | "ensemble";
export type QualityLabel = "Weak" | "Moderate" | "Strong" | "Very Strong";
export type ConfluenceDirection = "aligned_bull" | "aligned_bear" | "mixed";
export type MacroTrend = "uptrend" | "downtrend" | "ranging";
export type ChartInterval = "1m" | "5m" | "15m" | "1h" | "4h" | "1d";

export interface TAResult {
  rsi: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_hist: number | null;
  bb_upper: number | null;
  bb_middle: number | null;
  bb_lower: number | null;
  bb_bandwidth: number | null;
  bb_pct: number | null;
  ema_9: number | null;
  ema_21: number | null;
  ema_50: number | null;
  ema_200: number | null;
  stoch_k: number | null;
  stoch_d: number | null;
  adx: number | null;
  adx_pos: number | null;
  adx_neg: number | null;
  atr: number | null;
  obv: number | null;
  obv_signal: number | null;
  vwap: number | null;
  volume: number;
  volume_sma: number | null;
  close: number;
}

export interface MLPrediction {
  action: SignalAction;
  confidence: number;
  probabilities: Record<SignalAction, number>;
}

export interface PivotLevels {
  pivot: number | null;
  r1: number | null;
  r2: number | null;
  r3: number | null;
  s1: number | null;
  s2: number | null;
  s3: number | null;
}

export interface VolumeBucket {
  price_low: number;
  price_high: number;
  volume: number;
  volume_pct: number;
}

export interface SignalData {
  symbol: string;
  action: SignalAction;
  source: SignalSource;
  strength: number;
  price: number;
  ta: TAResult;
  ml: MLPrediction | null;
  timestamp: number;
  quality_score?: number;
  quality_label?: QualityLabel;
  confluence_score?: number | null;
  confluence_direction?: ConfluenceDirection | null;
  ta_15m?: TAResult | null;
  ta_4h?: TAResult | null;
  confluence_4h_score?: number | null;
  confluence_4h_direction?: ConfluenceDirection | null;
  pivots?: PivotLevels | null;
  take_profit?: number | null;
  stop_loss?: number | null;
  risk_reward?: number | null;
  trailing_stop?: number | null;
  macro_trend?: MacroTrend | null;
}

export interface CandleBar {
  time: number; // Unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface WSMessage {
  type: "tick" | "signal" | "init" | "pong" | "volume_profile";
  symbol?: string;
  price?: number;
  open?: number;
  high?: number;
  low?: number;
  volume?: number;
  time?: number;
  is_closed?: boolean;
  // signal fields
  action?: SignalAction;
  source?: SignalSource;
  strength?: number;
  ta?: TAResult;
  ml?: MLPrediction | null;
  timestamp?: number;
  quality_score?: number;
  quality_label?: QualityLabel;
  confluence_score?: number | null;
  confluence_direction?: ConfluenceDirection | null;
  ta_15m?: TAResult | null;
  ta_4h?: TAResult | null;
  confluence_4h_score?: number | null;
  confluence_4h_direction?: ConfluenceDirection | null;
  pivots?: PivotLevels | null;
  take_profit?: number | null;
  stop_loss?: number | null;
  risk_reward?: number | null;
  trailing_stop?: number | null;
  macro_trend?: MacroTrend | null;
  // init fields
  candles?: CandleBar[];
  signal?: SignalData;
  volume_profile?: VolumeBucket[];
  // volume_profile message
  buckets?: VolumeBucket[];
}

export interface SignalLogEntry {
  id: string;
  symbol: string;
  action: SignalAction;
  price: number;
  strength: number;
  source: SignalSource;
  timestamp: number;
  quality_score?: number;
  quality_label?: QualityLabel;
}

export interface TickerInfo {
  symbol: string;
  price: number;
  change_pct: number;
  high: number;
  low: number;
  volume: number;
  quote_volume: number;
}

export interface OrderBookEntry {
  price: number;
  qty: number;
}

export interface OrderBookData {
  symbol: string;
  bids: [number, number][];
  asks: [number, number][];
  last_update_id: number;
}

export interface BacktestTrade {
  timestamp: number;
  action: "BUY" | "SELL";
  entry: number;
  exit_price: number;
  return_pct: number;
  is_win: boolean;
  side: "LONG" | "SHORT";
}

export interface BacktestResult {
  symbol: string;
  total_signals: number;
  win_rate: number;
  avg_return: number;
  profit_factor: number | null;
  max_drawdown: number;
  total_return: number;
  trades: BacktestTrade[];
  short_win_rate: number;
  short_total_return: number;
}

export interface PaperPosition {
  symbol: string;
  entry: number;
  qty: number;
  timestamp: number;
  stop_loss?: number | null;
  position_size: number;
}

export interface PaperTrade {
  id: string;
  symbol: string;
  entry: number;
  exit: number;
  qty: number;
  return_pct: number;
  pnl: number;
  is_win: boolean;
  timestamp: number;
}

export interface TradeLogEntry {
  id: string;
  symbol: string;
  action: SignalAction;
  entry_price: number;
  exit_price: number | null;
  return_pct: number | null;
  status: "open" | "closed";
  signal_strength: number;
  quality_score: number;
  timestamp: number;
}

export interface IndicatorIC {
  name: string;
  ic: number;
  abs_ic: number;
  direction: "bullish" | "bearish" | "neutral";
  n_samples: number;
}

export interface ICScoreResult {
  symbol: string;
  scores: IndicatorIC[];
  computed_at: number;
}
