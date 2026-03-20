import logging
from typing import Optional, List

import numpy as np
import pandas as pd

from app.models.schemas import TAResult, PivotLevels, VolumeBucket

logger = logging.getLogger(__name__)

try:
    import ta as _ta
    HAS_TA = True
except ImportError:
    HAS_TA = False
    logger.warning("ta library not available — using manual TA fallback")


class TAEngine:
    """Computes technical indicators, pivot points, and volume profile."""

    # ── Main TA ────────────────────────────────────────────────────────

    def compute(self, df: pd.DataFrame) -> Optional[TAResult]:
        if df.empty or len(df) < 50:
            return None
        try:
            if HAS_TA:
                return self._compute_ta_lib(df)
            return self._compute_manual(df)
        except Exception as e:
            logger.error(f"TA computation error: {e}", exc_info=True)
            return None

    def _compute_ta_lib(self, df: pd.DataFrame) -> Optional[TAResult]:
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        vol = df["volume"].astype(float)

        rsi = _ta.momentum.RSIIndicator(close, window=14).rsi()
        macd_ind = _ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
        macd = macd_ind.macd()
        macd_sig = macd_ind.macd_signal()
        macd_hist = macd_ind.macd_diff()
        bb = _ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_upper = bb.bollinger_hband()
        bb_lower = bb.bollinger_lband()
        bb_pct = bb.bollinger_pband()
        bb_bw = bb.bollinger_wband()
        ema9 = _ta.trend.EMAIndicator(close, window=9).ema_indicator()
        ema21 = _ta.trend.EMAIndicator(close, window=21).ema_indicator()
        ema50 = _ta.trend.EMAIndicator(close, window=50).ema_indicator()
        ema200 = _ta.trend.EMAIndicator(close, window=200).ema_indicator()
        stoch = _ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
        stoch_k = stoch.stoch()
        stoch_d = stoch.stoch_signal()
        adx_ind = _ta.trend.ADXIndicator(high, low, close, window=14)
        adx = adx_ind.adx()
        adx_pos = adx_ind.adx_pos()
        adx_neg = adx_ind.adx_neg()
        atr = _ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
        obv_series = _ta.volume.OnBalanceVolumeIndicator(close, vol).on_balance_volume()
        obv_signal_series = obv_series.ewm(span=20, adjust=False).mean()

        # Session-reset VWAP (resets at UTC midnight)
        typical_price = (high + low + close) / 3
        vwap_series = self._compute_session_vwap(df, typical_price, vol)

        # 20-period volume SMA for breakout confirmation
        vol_sma = vol.rolling(20).mean()

        def s(series: pd.Series) -> Optional[float]:
            val = series.iloc[-1]
            return None if pd.isna(val) else float(val)

        close_val = float(close.iloc[-1])
        bu = s(bb_upper)
        bl = s(bb_lower)

        return TAResult(
            rsi=s(rsi),
            macd=s(macd),
            macd_signal=s(macd_sig),
            macd_hist=s(macd_hist),
            bb_upper=bu,
            bb_middle=s(bb.bollinger_mavg()),
            bb_lower=bl,
            bb_bandwidth=s(bb_bw),
            bb_pct=s(bb_pct),
            ema_9=s(ema9),
            ema_21=s(ema21),
            ema_50=s(ema50),
            ema_200=s(ema200),
            stoch_k=s(stoch_k),
            stoch_d=s(stoch_d),
            adx=s(adx),
            adx_pos=s(adx_pos),
            adx_neg=s(adx_neg),
            atr=s(atr),
            obv=s(obv_series),
            obv_signal=s(obv_signal_series),
            vwap=s(vwap_series),
            volume=float(vol.iloc[-1]),
            volume_sma=s(vol_sma),
            close=close_val,
        )

    def _compute_manual(self, df: pd.DataFrame) -> Optional[TAResult]:
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        vol = df["volume"].astype(float)

        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.where(loss != 0, 1e-10)
        rsi = 100 - (100 / (1 + rs))

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        macd_sig = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_sig

        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20
        bb_rng = bb_upper - bb_lower

        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()

        low14 = low.rolling(14).min()
        high14 = high.rolling(14).max()
        rng14 = high14 - low14
        stoch_k = 100 * (close - low14) / rng14.where(rng14 != 0, 1.0)
        stoch_d = stoch_k.rolling(3).mean()

        # ADX (Wilder smoothing approximation: span = 2*period - 1)
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
        smoothed_plus = plus_dm.ewm(span=27, adjust=False).mean()
        smoothed_minus = minus_dm.ewm(span=27, adjust=False).mean()
        atr_nonzero = atr.where(atr != 0, 1e-10)
        plus_di = 100 * smoothed_plus / atr_nonzero
        minus_di = 100 * smoothed_minus / atr_nonzero
        di_sum = plus_di + minus_di
        dx = 100 * (plus_di - minus_di).abs() / di_sum.where(di_sum != 0, 1e-10)
        adx = dx.ewm(span=27, adjust=False).mean()

        # OBV
        close_diff = close.diff()
        obv_direction = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
        obv_series = pd.Series((obv_direction * vol.values).cumsum(), index=close.index)
        obv_signal_series = obv_series.ewm(span=20, adjust=False).mean()

        # Session-reset VWAP (resets at UTC midnight)
        typical_price = (high + low + close) / 3
        vwap_series = self._compute_session_vwap(df, typical_price, vol)

        # 20-period volume SMA
        vol_sma = vol.rolling(20).mean()

        def s(series: pd.Series) -> Optional[float]:
            val = series.iloc[-1]
            return None if pd.isna(val) else float(val)

        close_val = float(close.iloc[-1])
        bu = s(bb_upper)
        bl = s(bb_lower)
        bb_pct_val: Optional[float] = None
        bb_bw_val: Optional[float] = None
        if bu is not None and bl is not None:
            if bu != bl:
                bb_pct_val = (close_val - bl) / (bu - bl)
            if close_val:
                bb_bw_val = (bu - bl) / close_val

        return TAResult(
            rsi=s(rsi),
            macd=s(macd),
            macd_signal=s(macd_sig),
            macd_hist=s(macd_hist),
            bb_upper=bu,
            bb_middle=s(sma20),
            bb_lower=bl,
            bb_bandwidth=bb_bw_val,
            bb_pct=bb_pct_val,
            ema_9=s(ema9),
            ema_21=s(ema21),
            ema_50=s(ema50),
            ema_200=s(ema200),
            stoch_k=s(stoch_k),
            stoch_d=s(stoch_d),
            adx=s(adx),
            adx_pos=s(plus_di),
            adx_neg=s(minus_di),
            atr=s(atr),
            obv=s(obv_series),
            obv_signal=s(obv_signal_series),
            vwap=s(vwap_series),
            volume=float(vol.iloc[-1]),
            volume_sma=s(vol_sma),
            close=close_val,
        )

    # ── Session-reset VWAP ─────────────────────────────────────────────

    def _compute_session_vwap(
        self,
        df: pd.DataFrame,
        typical_price: pd.Series,
        vol: pd.Series,
    ) -> pd.Series:
        """Session-reset VWAP: resets at UTC midnight each day.
        Falls back to 24-period rolling VWAP if open_time is unavailable."""
        if "open_time" in df.columns:
            try:
                dt = pd.to_datetime(df["open_time"], unit="ms", utc=True)
                daily_dates = dt.dt.date
                cum_tp_vol = (typical_price * vol).groupby(daily_dates).cumsum()
                cum_vol = vol.groupby(daily_dates).cumsum()
                return cum_tp_vol / cum_vol.replace(0, np.nan)
            except Exception:
                pass
        # Fallback: 24-period rolling
        return (typical_price * vol).rolling(24).sum() / vol.rolling(24).sum()

    # ── Feature 5: Pivot Points (daily session H/L/C) ─────────────────

    def compute_pivot_points(self, df: pd.DataFrame) -> PivotLevels:
        """Classic floor pivots from previous UTC day's H/L/C."""
        if len(df) < 24:
            return PivotLevels()

        prev_day = self._get_previous_day(df)

        H = float(prev_day["high"].max())
        L = float(prev_day["low"].min())
        C = float(prev_day["close"].iloc[-1])
        P = (H + L + C) / 3
        return PivotLevels(
            pivot=round(P, 6),
            r1=round(2 * P - L, 6),
            r2=round(P + (H - L), 6),
            r3=round(H + 2 * (P - L), 6),
            s1=round(2 * P - H, 6),
            s2=round(P - (H - L), 6),
            s3=round(L - 2 * (H - P), 6),
        )

    def _get_previous_day(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract the previous UTC calendar day's candles from the buffer."""
        if "open_time" in df.columns:
            try:
                dt = pd.to_datetime(df["open_time"], unit="ms", utc=True)
                today_start = dt.iloc[-1].normalize()
                yesterday_start = today_start - pd.Timedelta(days=1)
                mask = (dt >= yesterday_start) & (dt < today_start)
                prev_day = df[mask]
                if len(prev_day) > 0:
                    return prev_day
            except Exception:
                pass
        # Fallback: last 24 candles
        return df.tail(24)

    # ── Feature 13: Volume Profile ─────────────────────────────────────

    def compute_volume_profile(
        self, df: pd.DataFrame, num_buckets: int = 24
    ) -> List[VolumeBucket]:
        """Divide price range into buckets, assign cumulative volume per bucket."""
        if len(df) < 20:
            return []
        close = df["close"].astype(float)
        volume = df["volume"].astype(float)
        price_min = float(close.min())
        price_max = float(close.max())
        if price_max <= price_min:
            return []

        bucket_size = (price_max - price_min) / num_buckets
        raw: list[dict] = []
        for i in range(num_buckets):
            low = price_min + i * bucket_size
            high = low + bucket_size
            mask = (close >= low) & (close < high)
            raw.append(
                {
                    "price_low": low,
                    "price_high": high,
                    "volume": float(volume[mask].sum()),
                }
            )

        max_vol = max(b["volume"] for b in raw) or 1.0
        return [
            VolumeBucket(
                price_low=round(b["price_low"], 6),
                price_high=round(b["price_high"], 6),
                volume=round(b["volume"], 2),
                volume_pct=round(b["volume"] / max_vol, 4),
            )
            for b in raw
        ]
