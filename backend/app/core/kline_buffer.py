from collections import deque
from typing import Deque, Optional
import threading
import pandas as pd


class KlineBuffer:
    """Thread-safe rolling buffer of closed kline candles per symbol."""

    def __init__(self, symbol: str, maxlen: int = 500):
        self.symbol = symbol
        self.maxlen = maxlen
        self._data: Deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self.last_price: float = 0.0
        self.last_open: float = 0.0
        self.last_high: float = 0.0
        self.last_low: float = 0.0

    def push_closed_candle(self, kline: dict) -> None:
        """Append a closed candle. kline dict must have Binance kline keys."""
        row = {
            "open_time": int(kline["t"]),
            "open": float(kline["o"]),
            "high": float(kline["h"]),
            "low": float(kline["l"]),
            "close": float(kline["c"]),
            "volume": float(kline["v"]),
        }
        with self._lock:
            self._data.append(row)

    def update_live_price(
        self,
        price: float,
        open_price: float = 0.0,
        high: float = 0.0,
        low: float = 0.0,
    ) -> None:
        self.last_price = price
        if open_price:
            self.last_open = open_price
        if high:
            self.last_high = high
        if low:
            self.last_low = low

    def to_dataframe(self) -> pd.DataFrame:
        with self._lock:
            if not self._data:
                return pd.DataFrame()
            return pd.DataFrame(list(self._data))

    @property
    def is_ready(self) -> bool:
        return len(self._data) >= 50

    def __len__(self) -> int:
        return len(self._data)
