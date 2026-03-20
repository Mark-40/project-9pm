import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

import websockets

from app.config import Settings
from app.core.connection_manager import ConnectionManager
from app.core.ic_engine import ICEngine
from app.core.kline_buffer import KlineBuffer
from app.core.ml_engine import MLEngine
from app.core.signal_generator import SignalGenerator
from app.core.slack_notifier import SlackNotifier
from app.core.ta_engine import TAEngine
from app.core.trade_logger import TradeLogger
from app.models.schemas import TAResult

logger = logging.getLogger(__name__)

# Refresh IC scores every N closed 1h candles (~24h)
_IC_REFRESH_CANDLES = 24


class BinanceStreamManager:
    """Manages a multiplexed Binance WebSocket stream for all symbols
    across three intervals: 1h (primary), 15m (secondary), 4h (tertiary).

    Data flow on closed 1h candle:
        Binance WS → KlineBuffer(1h) → TAEngine → MLEngine → SignalGenerator
        → ConnectionManager.broadcast

    Data flow on closed 15m candle:
        Binance WS → KlineBuffer(15m) → TAEngine (ta_15m cached)

    Data flow on closed 4h candle:
        Binance WS → KlineBuffer(4h) → TAEngine (ta_4h cached)
    """

    RECONNECT_DELAY = 5

    def __init__(
        self,
        settings: Settings,
        buffers: Dict[str, KlineBuffer],
        buffers_15m: Dict[str, KlineBuffer],
        buffers_4h: Dict[str, KlineBuffer],
        ta_engine: TAEngine,
        ml_engine: MLEngine,
        signal_gen: SignalGenerator,
        conn_manager: ConnectionManager,
        ic_engine: ICEngine,
        ic_cache: Dict[str, Dict[str, float]],
        executor: ThreadPoolExecutor,
        trade_logger: Optional[TradeLogger] = None,
        slack_notifier: Optional[SlackNotifier] = None,
    ):
        self.settings = settings
        self.buffers = buffers
        self.buffers_15m = buffers_15m
        self.buffers_4h = buffers_4h
        self.ta_engine = ta_engine
        self.ml_engine = ml_engine
        self.signal_gen = signal_gen
        self.conn_manager = conn_manager
        self.ic_engine = ic_engine
        self.ic_cache = ic_cache
        self.executor = executor
        self.trade_logger = trade_logger
        self.slack_notifier = slack_notifier
        self._running = False

        self._prev_ta: Dict[str, Optional[TAResult]] = {s: None for s in settings.SYMBOLS}
        self._latest_ta_15m: Dict[str, Optional[TAResult]] = {s: None for s in settings.SYMBOLS}
        self._latest_ta_4h: Dict[str, Optional[TAResult]] = {s: None for s in settings.SYMBOLS}
        # Correlation tracking: symbol → latest non-HOLD action
        self._active_signals: Dict[str, str] = {}
        # IC refresh counter per symbol
        self._candle_count: Dict[str, int] = {s: 0 for s in settings.SYMBOLS}

    def _stream_url(self) -> str:
        streams_1h = [
            f"{s.lower()}@kline_{self.settings.KLINE_INTERVAL}"
            for s in self.settings.SYMBOLS
        ]
        streams_15m = [
            f"{s.lower()}@kline_{self.settings.KLINE_INTERVAL_SECONDARY}"
            for s in self.settings.SYMBOLS
        ]
        streams_4h = [
            f"{s.lower()}@kline_{self.settings.KLINE_INTERVAL_4H}"
            for s in self.settings.SYMBOLS
        ]
        streams = "/".join(streams_1h + streams_15m + streams_4h)
        return f"{self.settings.BINANCE_WS_URL}?streams={streams}"

    async def run(self) -> None:
        self._running = True
        logger.info(f"[Binance] Starting streams for {self.settings.SYMBOLS}")

        while self._running:
            try:
                url = self._stream_url()
                logger.info(f"[Binance] Connecting to {url}")
                async with websockets.connect(
                    url, ping_interval=20, ping_timeout=15
                ) as ws:
                    logger.info("[Binance] WebSocket connected")
                    async for raw in ws:
                        await self._handle_message(json.loads(raw))
            except asyncio.CancelledError:
                self._running = False
                break
            except Exception as e:
                logger.error(
                    f"[Binance] WS error: {e}. Reconnecting in {self.RECONNECT_DELAY}s…"
                )
                await asyncio.sleep(self.RECONNECT_DELAY)

    async def _handle_message(self, msg: dict) -> None:
        data = msg.get("data", {})
        if data.get("e") != "kline":
            return

        kline = data["k"]
        symbol: str = kline["s"]
        interval: str = kline["i"]

        if interval == self.settings.KLINE_INTERVAL_SECONDARY:
            # 15m candle — update buffer + cache ta_15m on close
            buf_15m = self.buffers_15m.get(symbol)
            if buf_15m is None:
                return
            if kline["x"]:
                buf_15m.push_closed_candle(kline)
                df_15m = buf_15m.to_dataframe()
                ta_15m = self.ta_engine.compute(df_15m)
                if ta_15m is not None:
                    self._latest_ta_15m[symbol] = ta_15m
            return

        if interval == self.settings.KLINE_INTERVAL_4H:
            # 4h candle — update buffer + cache ta_4h on close
            buf_4h = self.buffers_4h.get(symbol)
            if buf_4h is None:
                return
            if kline["x"]:
                buf_4h.push_closed_candle(kline)
                df_4h = buf_4h.to_dataframe()
                ta_4h = self.ta_engine.compute(df_4h)
                if ta_4h is not None:
                    self._latest_ta_4h[symbol] = ta_4h
            return

        # 1h candle
        buf = self.buffers.get(symbol)
        if buf is None:
            return

        price = float(kline["c"])
        buf.update_live_price(
            price,
            open_price=float(kline["o"]),
            high=float(kline["h"]),
            low=float(kline["l"]),
        )

        # Broadcast live tick for chart updates
        await self.conn_manager.broadcast(
            symbol,
            {
                "type": "tick",
                "symbol": symbol,
                "price": price,
                "open": float(kline["o"]),
                "high": float(kline["h"]),
                "low": float(kline["l"]),
                "volume": float(kline["v"]),
                "time": kline["t"],
                "is_closed": kline["x"],
            },
        )

        # Heavy TA + ML only on closed candles
        if kline["x"]:
            buf.push_closed_candle(kline)
            await self._process_closed_candle(symbol, buf, price)

    async def _process_closed_candle(
        self,
        symbol: str,
        buf: KlineBuffer,
        price: float,
    ) -> None:
        if not buf.is_ready:
            return

        df = buf.to_dataframe()
        ta = self.ta_engine.compute(df)
        if ta is None:
            return

        ta_15m = self._latest_ta_15m.get(symbol)
        ta_4h = self._latest_ta_4h.get(symbol)
        pivots = self.ta_engine.compute_pivot_points(df)
        prev_ta = self._prev_ta.get(symbol)

        # Correlation counts from OTHER symbols (prevents piling into correlated trades)
        active_buy_count = sum(
            1 for s, a in self._active_signals.items() if a == "BUY" and s != symbol
        )
        active_sell_count = sum(
            1 for s, a in self._active_signals.items() if a == "SELL" and s != symbol
        )

        # IC scores for this symbol (filters noise indicators)
        ic_scores = self.ic_cache.get(symbol)

        # ML prediction — now passes df so price_change and volume_ratio are real
        ml = await self.ml_engine.predict(symbol, ta, prev_ta, df=df)

        signal = self.signal_gen.generate(
            symbol, ta, ml, price,
            ta_15m=ta_15m,
            ta_4h=ta_4h,
            pivots=pivots,
            prev_ta=prev_ta,
            ic_scores=ic_scores,
            active_buy_count=active_buy_count,
            active_sell_count=active_sell_count,
        )
        self._prev_ta[symbol] = ta

        # Update correlation tracking
        if signal.action != "HOLD":
            self._active_signals[symbol] = signal.action
        else:
            self._active_signals.pop(symbol, None)

        payload = {
            "type": "signal",
            "symbol": symbol,
            "action": signal.action,
            "source": signal.source,
            "strength": signal.strength,
            "price": signal.price,
            "ta": signal.ta.model_dump(),
            "ml": signal.ml.model_dump() if signal.ml else None,
            "timestamp": signal.timestamp,
            "quality_score": signal.quality_score,
            "quality_label": signal.quality_label,
            "confluence_score": signal.confluence_score,
            "confluence_direction": signal.confluence_direction,
            "ta_15m": signal.ta_15m.model_dump() if signal.ta_15m else None,
            "ta_4h": signal.ta_4h.model_dump() if signal.ta_4h else None,
            "confluence_4h_score": signal.confluence_4h_score,
            "confluence_4h_direction": signal.confluence_4h_direction,
            "pivots": signal.pivots.model_dump() if signal.pivots else None,
            "take_profit": signal.take_profit,
            "stop_loss": signal.stop_loss,
            "risk_reward": signal.risk_reward,
            "trailing_stop": signal.trailing_stop,
            "macro_trend": signal.macro_trend,
        }

        await self.conn_manager.broadcast(symbol, payload)

        # Send Slack notification for BUY/SELL signals
        if self.slack_notifier and signal.action != "HOLD":
            await self.slack_notifier.send_signal(
                symbol=symbol,
                action=signal.action,
                price=price,
                strength=signal.strength,
                quality_score=signal.quality_score,
                quality_label=signal.quality_label,
                source=signal.source,
                take_profit=signal.take_profit,
                stop_loss=signal.stop_loss,
                risk_reward=signal.risk_reward,
                macro_trend=signal.macro_trend,
            )

        # Record signal + resolve past outcomes in trade log
        if self.trade_logger and signal.action != "HOLD":
            self.trade_logger.record_signal(
                symbol=symbol,
                action=signal.action,
                entry_price=price,
                timestamp=signal.timestamp,
                signal_strength=signal.strength,
                quality_score=signal.quality_score,
            )
        if self.trade_logger:
            self.trade_logger.resolve_outcomes(
                symbol=symbol,
                current_price=price,
                current_timestamp=signal.timestamp,
                n_candles_threshold=self.settings.TRADE_OUTCOME_CANDLES,
            )

        # Broadcast volume profile
        volume_profile = self.ta_engine.compute_volume_profile(df)
        if volume_profile:
            await self.conn_manager.broadcast(
                symbol,
                {
                    "type": "volume_profile",
                    "symbol": symbol,
                    "buckets": [b.model_dump() for b in volume_profile],
                },
            )

        # Periodically refresh IC scores for this symbol
        self._candle_count[symbol] = self._candle_count.get(symbol, 0) + 1
        if self._candle_count[symbol] % _IC_REFRESH_CANDLES == 0:
            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(
                    self.executor, self.ic_engine.compute, df, symbol
                )
                self.ic_cache[symbol] = {s.name: s.abs_ic for s in result.scores}
                logger.info(f"[IC] Refreshed scores for {symbol}")
            except Exception as e:
                logger.error(f"[IC] Refresh failed for {symbol}: {e}")

        logger.info(
            f"[Signal] {symbol} → {signal.action} "
            f"(strength={signal.strength:.2f}, src={signal.source}, "
            f"quality={signal.quality_score}, "
            f"confluence={signal.confluence_direction}, "
            f"4h={signal.confluence_4h_direction})"
        )
