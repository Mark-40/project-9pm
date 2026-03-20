import logging
import time
from typing import List, Optional

import numpy as np
import pandas as pd

from app.models.schemas import IndicatorIC, ICScoreResult

logger = logging.getLogger(__name__)

_INDICATORS = [
    "rsi",
    "macd_hist",
    "bb_pct",
    "ema_cross_pct",
    "stoch_k",
    "adx",
    "obv_trend",
    "vwap_dist",
    "adx_cross_pct",
    "ema50_200_cross_pct",
]


class ICEngine:
    """Computes per-indicator Information Coefficient (Pearson correlation
    of indicator value vs actual 3-candle forward return)."""

    def compute(self, df: pd.DataFrame, symbol: str) -> ICScoreResult:
        if df.empty or len(df) < 100:
            return ICScoreResult(symbol=symbol, scores=[], computed_at=int(time.time() * 1000))

        df = df.copy()
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float)

        # Build indicator columns
        self._add_indicators(df, close, high, low, volume)

        # Forward return (3-candle)
        fwd_return = close.shift(-3) / close - 1
        # Drop last 3 rows (look-ahead)
        valid_idx = fwd_return.dropna().index
        fwd = fwd_return.loc[valid_idx]

        scores: List[IndicatorIC] = []
        for name in _INDICATORS:
            if name not in df.columns:
                continue
            series = df[name].loc[valid_idx]
            mask = series.notna() & fwd.notna()
            x = series[mask].values
            y = fwd[mask].values
            if len(x) < 30:
                continue
            try:
                ic = float(np.corrcoef(x, y)[0, 1])
                if np.isnan(ic):
                    continue
            except Exception:
                continue
            direction: str
            if abs(ic) < 0.02:
                direction = "neutral"
            elif ic > 0:
                direction = "bullish"
            else:
                direction = "bearish"
            scores.append(
                IndicatorIC(
                    name=name,
                    ic=round(ic, 4),
                    abs_ic=round(abs(ic), 4),
                    direction=direction,
                    n_samples=int(mask.sum()),
                )
            )

        scores.sort(key=lambda s: s.abs_ic, reverse=True)
        return ICScoreResult(
            symbol=symbol,
            scores=scores,
            computed_at=int(time.time() * 1000),
        )

    def _add_indicators(
        self,
        df: pd.DataFrame,
        close: pd.Series,
        high: pd.Series,
        low: pd.Series,
        volume: pd.Series,
    ) -> None:
        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.where(loss != 0, 1e-10)
        df["rsi"] = 100 - (100 / (1 + rs))

        # MACD hist
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        df["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()

        # BB pct
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20
        bb_rng = bb_upper - bb_lower
        df["bb_pct"] = (close - bb_lower) / bb_rng.where(bb_rng != 0, 1.0)

        # EMA cross pct
        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        df["ema_cross_pct"] = (ema9 - ema21) / close.where(close != 0, 1.0)

        # Stoch K
        low14 = low.rolling(14).min()
        high14 = high.rolling(14).max()
        rng14 = high14 - low14
        df["stoch_k"] = 100 * (close - low14) / rng14.where(rng14 != 0, 1.0)

        # ADX
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = tr.ewm(span=27, adjust=False).mean()
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
        sp = plus_dm.ewm(span=27, adjust=False).mean()
        sm = minus_dm.ewm(span=27, adjust=False).mean()
        atr_nz = atr.where(atr != 0, 1e-10)
        plus_di = 100 * sp / atr_nz
        minus_di = 100 * sm / atr_nz
        di_sum = plus_di + minus_di
        dx = 100 * (plus_di - minus_di).abs() / di_sum.where(di_sum != 0, 1e-10)
        df["adx"] = dx.ewm(span=27, adjust=False).mean()
        df["adx_cross_pct"] = (plus_di - minus_di) / 100.0

        # EMA 50/200 cross pct
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()
        df["ema50_200_cross_pct"] = (ema50 - ema200) / close.where(close != 0, 1.0)

        # OBV trend
        cd = close.diff()
        obv_dir = np.where(cd > 0, 1, np.where(cd < 0, -1, 0))
        obv_series = pd.Series((obv_dir * volume.values).cumsum(), index=close.index)
        obv_sig = obv_series.ewm(span=20, adjust=False).mean()
        df["obv_trend"] = (obv_series - obv_sig) / (obv_series.abs().rolling(20).mean().replace(0, 1))

        # VWAP dist
        tp = (high + low + close) / 3
        vwap = (tp * volume).rolling(24).sum() / volume.rolling(24).sum()
        df["vwap_dist"] = (close - vwap) / close.where(close != 0, 1.0)
