from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, List
import time


class TAResult(BaseModel):
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_bandwidth: Optional[float] = None
    bb_pct: Optional[float] = None
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    adx: Optional[float] = None
    adx_pos: Optional[float] = None
    adx_neg: Optional[float] = None
    atr: Optional[float] = None
    obv: Optional[float] = None
    obv_signal: Optional[float] = None
    vwap: Optional[float] = None
    volume: float = 0.0
    volume_sma: Optional[float] = None  # 20-period volume SMA for confirmation
    close: float = 0.0


class MLPrediction(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    probabilities: Dict[str, float]


class PivotLevels(BaseModel):
    pivot: Optional[float] = None
    r1: Optional[float] = None
    r2: Optional[float] = None
    r3: Optional[float] = None
    s1: Optional[float] = None
    s2: Optional[float] = None
    s3: Optional[float] = None


class VolumeBucket(BaseModel):
    price_low: float
    price_high: float
    volume: float
    volume_pct: float


class SignalPayload(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    source: Literal["ml", "rule", "ensemble"]
    strength: float
    price: float
    ta: TAResult
    ml: Optional[MLPrediction] = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    # Quality score
    quality_score: int = 0
    quality_label: Literal["Weak", "Moderate", "Strong", "Very Strong"] = "Weak"
    # 15m multi-timeframe confluence
    confluence_score: Optional[float] = None
    confluence_direction: Optional[Literal["aligned_bull", "aligned_bear", "mixed"]] = None
    ta_15m: Optional[TAResult] = None
    # 4H timeframe confluence
    ta_4h: Optional[TAResult] = None
    confluence_4h_score: Optional[float] = None
    confluence_4h_direction: Optional[Literal["aligned_bull", "aligned_bear", "mixed"]] = None
    # Pivot levels
    pivots: Optional[PivotLevels] = None
    # ATR-based profit targets
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_reward: Optional[float] = None
    trailing_stop: Optional[float] = None
    # Macro trend
    macro_trend: Optional[Literal["uptrend", "downtrend", "ranging"]] = None


class KlineRow(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class BacktestTrade(BaseModel):
    timestamp: int
    action: Literal["BUY", "SELL"]
    entry: float
    exit_price: float
    return_pct: float
    is_win: bool
    side: Literal["LONG", "SHORT"] = "LONG"


class BacktestResult(BaseModel):
    symbol: str
    total_signals: int
    win_rate: float
    avg_return: float
    profit_factor: Optional[float] = None
    max_drawdown: float
    total_return: float
    trades: List[BacktestTrade]
    short_win_rate: float = 0.0
    short_total_return: float = 0.0


class TradeLogEntry(BaseModel):
    id: str
    symbol: str
    action: Literal["BUY", "SELL"]
    entry_price: float
    exit_price: Optional[float] = None
    return_pct: Optional[float] = None
    status: Literal["open", "closed"]
    signal_strength: float
    quality_score: int
    timestamp: int


class TradeLogResponse(BaseModel):
    entries: List[TradeLogEntry]
    total: int


class IndicatorIC(BaseModel):
    name: str
    ic: float
    abs_ic: float
    direction: Literal["bullish", "bearish", "neutral"]
    n_samples: int


class ICScoreResult(BaseModel):
    symbol: str
    scores: List[IndicatorIC]
    computed_at: int
