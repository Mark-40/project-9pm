import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.models.schemas import MLPrediction, TAResult

logger = logging.getLogger(__name__)

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    logger.warning("XGBoost not available — ML predictions disabled")

FEATURE_COLS: List[str] = [
    "rsi",
    "macd",
    "macd_hist",
    "bb_pct",
    "bb_bandwidth",
    "stoch_k",
    "stoch_d",
    "ema_cross_pct",
    "volume_ratio",
    "price_change_1",
    "price_change_3",
    "rsi_lag1",
    "macd_hist_lag1",
    "stoch_k_lag1",
    # v3 additions
    "adx",
    "adx_cross_pct",
    "ema50_200_cross_pct",
    "obv_trend",
    "vwap_dist",
]


class MLEngine:
    """XGBoost-based price direction classifier per trading symbol.

    Classes:
        0 = SELL  (price drops > threshold in next N candles)
        1 = HOLD  (price moves within ±threshold)
        2 = BUY   (price rises > threshold in next N candles)
    """

    LABEL_MAP = {0: "SELL", 1: "HOLD", 2: "BUY"}

    def __init__(self, model_dir: str, executor: ThreadPoolExecutor):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.executor = executor
        self._models: Dict[str, Any] = {}
        self._ready: Dict[str, bool] = {}

    # ── Public API ────────────────────────────────────────────────────────

    async def initialize(self, symbol: str, df: pd.DataFrame) -> bool:
        """Load saved model or train a new one for *symbol*."""
        if not HAS_XGB:
            return False

        loop = asyncio.get_event_loop()
        from app.config import settings
        model_path = self.model_dir / f"{symbol}_{settings.MODEL_VERSION}.json"

        if model_path.exists():
            model = await loop.run_in_executor(
                self.executor, self._load_model, model_path
            )
        else:
            model = await loop.run_in_executor(
                self.executor, self._train_model, symbol, df
            )

        if model is not None:
            self._models[symbol] = model
            self._ready[symbol] = True
            logger.info(f"[ML] Model ready for {symbol}")
            return True

        logger.warning(f"[ML] Model not available for {symbol}")
        return False

    async def predict(
        self,
        symbol: str,
        ta: TAResult,
        prev_ta: Optional[TAResult] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> Optional[MLPrediction]:
        if not self._ready.get(symbol):
            return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self._predict_sync, symbol, ta, prev_ta, df
        )

    async def retrain(self, symbol: str, df: pd.DataFrame) -> bool:
        """Force-retrain model for symbol with current buffer data."""
        if not HAS_XGB:
            return False
        loop = asyncio.get_event_loop()
        from app.config import settings
        # Remove stale model so _train_model always writes fresh
        model_path = self.model_dir / f"{symbol}_{settings.MODEL_VERSION}.json"
        if model_path.exists():
            try:
                model_path.unlink()
            except Exception:
                pass
        model = await loop.run_in_executor(self.executor, self._train_model, symbol, df)
        if model is not None:
            self._models[symbol] = model
            self._ready[symbol] = True
            logger.info(f"[ML] Retrained {symbol} successfully")
            return True
        logger.warning(f"[ML] Retrain failed for {symbol}")
        return False

    # ── Private: prediction ───────────────────────────────────────────────

    def _predict_sync(
        self,
        symbol: str,
        ta: TAResult,
        prev_ta: Optional[TAResult],
        df: Optional[pd.DataFrame] = None,
    ) -> Optional[MLPrediction]:
        try:
            model = self._models[symbol]
            x = self._ta_to_feature_vector(ta, prev_ta, df)
            proba = model.predict_proba([x])[0]
            pred_idx = int(np.argmax(proba))
            return MLPrediction(
                action=self.LABEL_MAP[pred_idx],
                confidence=float(proba[pred_idx]),
                probabilities={
                    self.LABEL_MAP[i]: float(p) for i, p in enumerate(proba)
                },
            )
        except Exception as e:
            logger.error(f"[ML] Prediction failed for {symbol}: {e}")
            return None

    def _ta_to_feature_vector(
        self,
        ta: TAResult,
        prev_ta: Optional[TAResult],
        df: Optional[pd.DataFrame] = None,
    ) -> List[float]:
        close = ta.close or 1.0
        ema9 = ta.ema_9 or close
        ema21 = ta.ema_21 or close
        adx_pos = ta.adx_pos or 25.0
        adx_neg = ta.adx_neg or 25.0
        ema50 = ta.ema_50 or close
        ema200 = ta.ema_200 or close
        obv = ta.obv or 0.0
        obv_sig = ta.obv_signal or 0.0
        vwap = ta.vwap or close

        # Compute real price changes and volume ratio from the buffer DataFrame
        # (fixes training-inference gap — these were previously hardcoded to 0/1)
        if df is not None and len(df) >= 5:
            close_s = df["close"].astype(float)
            vol_s = df["volume"].astype(float)
            n = len(close_s)
            price_change_1 = float(
                (close_s.iloc[-1] - close_s.iloc[-2]) / close_s.iloc[-2]
            ) if n >= 2 else 0.0
            price_change_3 = float(
                (close_s.iloc[-1] - close_s.iloc[-4]) / close_s.iloc[-4]
            ) if n >= 4 else 0.0
            vol_sma = float(vol_s.iloc[-20:].mean()) if n >= 2 else 1.0
            volume_ratio = float(vol_s.iloc[-1] / vol_sma) if vol_sma > 0 else 1.0
        else:
            price_change_1 = 0.0
            price_change_3 = 0.0
            volume_ratio = 1.0

        return [
            ta.rsi or 50.0,
            ta.macd or 0.0,
            ta.macd_hist or 0.0,
            ta.bb_pct if ta.bb_pct is not None else 0.5,
            ta.bb_bandwidth or 0.0,
            ta.stoch_k or 50.0,
            ta.stoch_d or 50.0,
            (ema9 - ema21) / close if close else 0.0,
            volume_ratio,
            price_change_1,
            price_change_3,
            (prev_ta.rsi or 50.0) if prev_ta else 50.0,
            (prev_ta.macd_hist or 0.0) if prev_ta else 0.0,
            (prev_ta.stoch_k or 50.0) if prev_ta else 50.0,
            # v3 features
            ta.adx or 20.0,
            (adx_pos - adx_neg) / 100.0,
            (ema50 - ema200) / close if close else 0.0,
            (obv - obv_sig) / (abs(obv) + 1e-10),
            (close - vwap) / close if close else 0.0,
        ]

    # ── Private: training ─────────────────────────────────────────────────

    def _train_model(self, symbol: str, df: pd.DataFrame) -> Optional[Any]:
        try:
            features_df = self._build_features(df)
            if features_df is None or len(features_df) < 200:
                n = len(features_df) if features_df is not None else 0
                logger.warning(f"[ML] Insufficient training data for {symbol}: {n}")
                return None

            X = features_df.drop("label", axis=1).fillna(0)
            y = features_df["label"]

            split = int(len(X) * 0.8)

            # Class-balanced sample weights to handle HOLD-dominance
            class_counts = y.iloc[:split].value_counts()
            n_total = split
            n_classes = len(class_counts)
            weights_map = {
                cls: n_total / (n_classes * count)
                for cls, count in class_counts.items()
            }
            sample_weights = y.iloc[:split].map(weights_map).fillna(1.0).values

            model = xgb.XGBClassifier(
                n_estimators=300,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                eval_metric="mlogloss",
                random_state=42,
                n_jobs=-1,
                verbosity=0,
            )
            model.fit(X.iloc[:split], y.iloc[:split], sample_weight=sample_weights)

            from app.config import settings
            path = self.model_dir / f"{symbol}_{settings.MODEL_VERSION}.json"
            model.save_model(str(path))
            logger.info(
                f"[ML] Trained {symbol} — {split} samples → saved to {path}"
            )
            return model
        except Exception as e:
            logger.error(f"[ML] Training failed for {symbol}: {e}")
            return None

    def _load_model(self, path: Path) -> Optional[Any]:
        try:
            model = xgb.XGBClassifier()
            model.load_model(str(path))
            logger.info(f"[ML] Loaded model from {path}")
            return model
        except Exception as e:
            logger.error(f"[ML] Failed to load model {path}: {e}")
            return None

    def _build_features(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Engineer features and forward-return labels from OHLCV DataFrame."""
        if df.empty or len(df) < 60:
            return None

        df = df.copy()
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float)

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.where(loss != 0, 1e-10)
        df["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        macd_sig = macd.ewm(span=9, adjust=False).mean()
        df["macd"] = macd
        df["macd_hist"] = macd - macd_sig

        # Bollinger Bands
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20
        bb_rng = bb_upper - bb_lower
        df["bb_pct"] = (close - bb_lower) / bb_rng.where(bb_rng != 0, 1.0)
        df["bb_bandwidth"] = bb_rng / close.where(close != 0, 1.0)

        # EMAs
        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        df["ema_cross_pct"] = (ema9 - ema21) / close.where(close != 0, 1.0)

        # Stochastic
        low14 = low.rolling(14).min()
        high14 = high.rolling(14).max()
        rng14 = high14 - low14
        df["stoch_k"] = 100 * (close - low14) / rng14.where(rng14 != 0, 1.0)
        df["stoch_d"] = df["stoch_k"].rolling(3).mean()

        # Volume ratio
        vol_sma = volume.rolling(20).mean()
        df["volume_ratio"] = volume / vol_sma.where(vol_sma != 0, 1.0)

        # Price changes
        df["price_change_1"] = close.pct_change(1)
        df["price_change_3"] = close.pct_change(3)

        # Lagged features
        df["rsi_lag1"] = df["rsi"].shift(1)
        df["macd_hist_lag1"] = df["macd_hist"].shift(1)
        df["stoch_k_lag1"] = df["stoch_k"].shift(1)

        # v3: ADX
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr_series = tr.ewm(span=27, adjust=False).mean()
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
        smoothed_plus = plus_dm.ewm(span=27, adjust=False).mean()
        smoothed_minus = minus_dm.ewm(span=27, adjust=False).mean()
        atr_nz = atr_series.where(atr_series != 0, 1e-10)
        plus_di = 100 * smoothed_plus / atr_nz
        minus_di = 100 * smoothed_minus / atr_nz
        di_sum = plus_di + minus_di
        dx = 100 * (plus_di - minus_di).abs() / di_sum.where(di_sum != 0, 1e-10)
        df["adx"] = dx.ewm(span=27, adjust=False).mean()
        df["adx_cross_pct"] = (plus_di - minus_di) / 100.0

        # v3: EMA 50/200
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()
        df["ema50_200_cross_pct"] = (ema50 - ema200) / close.where(close != 0, 1.0)

        # v3: OBV trend
        close_diff = close.diff()
        obv_dir = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
        obv_series = pd.Series((obv_dir * volume.values).cumsum(), index=close.index)
        obv_sig = obv_series.ewm(span=20, adjust=False).mean()
        df["obv_trend"] = (obv_series - obv_sig) / (
            obv_series.abs().rolling(20).mean().replace(0, 1)
        )

        # v3: VWAP distance
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).rolling(24).sum() / volume.rolling(24).sum()
        df["vwap_dist"] = (close - vwap) / close.where(close != 0, 1.0)

        # Dynamic ATR-based label threshold per symbol (replaces fixed 0.3%)
        # Calibrates to each coin's actual volatility regime
        atr_pct = atr_series / close.where(close != 0, 1.0)
        dynamic_threshold = float(atr_pct.median() * 0.5)
        dynamic_threshold = max(0.002, min(0.008, dynamic_threshold))

        # Forward-return label (next 3 candles)
        fwd = close.shift(-3) / close - 1
        df["label"] = np.where(
            fwd > dynamic_threshold, 2,
            np.where(fwd < -dynamic_threshold, 0, 1)
        )

        df = df.dropna(subset=FEATURE_COLS + ["label"])
        df = df.iloc[:-3]  # remove last 3 rows — labels are look-ahead

        if len(df) < 100:
            return None

        df["label"] = df["label"].astype(int)
        return df[FEATURE_COLS + ["label"]]
