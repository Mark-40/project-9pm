import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Dict

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.http_router import router as http_router
from app.api.ws_router import router as ws_router
from app.config import settings
from app.core.backtest_engine import BacktestEngine
from app.core.binance_stream import BinanceStreamManager
from app.core.connection_manager import ConnectionManager
from app.core.ic_engine import ICEngine
from app.core.kline_buffer import KlineBuffer
from app.core.ml_engine import MLEngine
from app.core.signal_generator import SignalGenerator
from app.core.ta_engine import TAEngine
from app.core.trade_logger import TradeLogger

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def _seed_historical(buffers: dict, interval: str, limit: int) -> None:
    """Pre-fill each symbol buffer with historical closed candles."""
    logger.info(f"[Seed] Fetching {interval} klines from Binance REST…")
    async with httpx.AsyncClient(timeout=30.0) as client:
        for symbol, buf in buffers.items():
            try:
                resp = await client.get(
                    f"{settings.BINANCE_REST_URL}/api/v3/klines",
                    params={
                        "symbol": symbol,
                        "interval": interval,
                        "limit": limit,
                    },
                )
                resp.raise_for_status()
                klines = resp.json()

                for k in klines[:-1]:
                    buf.push_closed_candle(
                        {
                            "t": k[0], "o": k[1], "h": k[2], "l": k[3],
                            "c": k[4], "v": k[5], "T": k[6], "q": k[7],
                            "n": k[8], "x": True,
                        }
                    )

                if klines:
                    buf.update_live_price(float(klines[-1][4]))

                logger.info(
                    f"[Seed] {symbol} ({interval}): {len(klines) - 1} candles loaded"
                )
            except Exception as e:
                logger.error(f"[Seed] Failed for {symbol} ({interval}): {e}")


async def _ml_retrain_loop(
    buffers: dict,
    ml_engine: MLEngine,
) -> None:
    """Periodic ML model retraining every ML_RETRAIN_INTERVAL_HOURS hours."""
    while True:
        await asyncio.sleep(settings.ML_RETRAIN_INTERVAL_HOURS * 3600)
        logger.info("[ML] Periodic retrain starting…")
        for symbol, buf in buffers.items():
            df = buf.to_dataframe()
            if len(df) >= settings.ML_MIN_SAMPLES:
                await ml_engine.retrain(symbol, df)
        logger.info("[ML] Periodic retrain complete")


def _build_signal_payload_dict(signal) -> dict:
    return {
        "type": "signal",
        "symbol": signal.symbol,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    executor = ThreadPoolExecutor(max_workers=4)

    buffers = {
        s: KlineBuffer(s, settings.KLINE_BUFFER_SIZE) for s in settings.SYMBOLS
    }
    buffers_15m = {
        s: KlineBuffer(s, settings.KLINE_BUFFER_SIZE_SECONDARY)
        for s in settings.SYMBOLS
    }
    buffers_4h = {
        s: KlineBuffer(s, settings.KLINE_BUFFER_SIZE_4H)
        for s in settings.SYMBOLS
    }

    ta_engine = TAEngine()
    ml_engine = MLEngine(model_dir=settings.ML_ARTIFACTS_DIR, executor=executor)
    signal_gen = SignalGenerator()
    backtest_engine = BacktestEngine(ta_engine, signal_gen)
    conn_manager = ConnectionManager()
    trade_logger = TradeLogger(settings.TRADE_LOG_PATH)
    ic_engine = ICEngine()
    latest_signals: dict = {}
    ic_cache: Dict[str, Dict[str, float]] = {}

    # Intercept broadcasts to cache the latest signal per symbol
    _original_broadcast = conn_manager.broadcast

    async def _broadcast_with_cache(symbol: str, payload: dict) -> None:
        if payload.get("type") == "signal":
            latest_signals[symbol] = payload
        await _original_broadcast(symbol, payload)

    conn_manager.broadcast = _broadcast_with_cache

    # Seed historical data for all three intervals
    await _seed_historical(buffers, settings.KLINE_INTERVAL, settings.KLINE_BUFFER_SIZE)
    await _seed_historical(
        buffers_15m,
        settings.KLINE_INTERVAL_SECONDARY,
        settings.KLINE_BUFFER_SIZE_SECONDARY,
    )
    await _seed_historical(
        buffers_4h,
        settings.KLINE_INTERVAL_4H,
        settings.KLINE_BUFFER_SIZE_4H,
    )

    # Train / load ML models in parallel
    logger.info("[ML] Initializing models…")
    ml_tasks = [
        ml_engine.initialize(symbol, buf.to_dataframe())
        for symbol, buf in buffers.items()
    ]
    results = await asyncio.gather(*ml_tasks, return_exceptions=True)
    ready = sum(1 for r in results if r is True)
    logger.info(f"[ML] {ready}/{len(settings.SYMBOLS)} models ready")

    # Compute initial IC scores for signal weighting
    logger.info("[IC] Computing initial IC scores…")
    loop = asyncio.get_event_loop()
    ic_tasks = [
        loop.run_in_executor(executor, ic_engine.compute, buf.to_dataframe(), symbol)
        for symbol, buf in buffers.items()
        if len(buf) >= 100
    ]
    ic_results = await asyncio.gather(*ic_tasks, return_exceptions=True)
    for result in ic_results:
        if hasattr(result, "symbol") and hasattr(result, "scores"):
            ic_cache[result.symbol] = {s.name: s.abs_ic for s in result.scores}
    logger.info(f"[IC] Scores computed for {len(ic_cache)} symbols")

    # Compute initial signals so the frontend never shows "Waiting for signal…"
    logger.info("[Signal] Computing initial signals from seeded data…")
    for symbol, buf in buffers.items():
        if not buf.is_ready:
            continue
        df = buf.to_dataframe()
        ta = ta_engine.compute(df)
        if ta is None:
            continue
        buf_15m = buffers_15m.get(symbol)
        ta_15m = None
        if buf_15m and buf_15m.is_ready:
            ta_15m = ta_engine.compute(buf_15m.to_dataframe())
        buf_4h = buffers_4h.get(symbol)
        ta_4h = None
        if buf_4h and buf_4h.is_ready:
            ta_4h = ta_engine.compute(buf_4h.to_dataframe())
        pivots = ta_engine.compute_pivot_points(df)
        ml = await ml_engine.predict(symbol, ta, None, df=df)
        signal = signal_gen.generate(
            symbol, ta, ml, buf.last_price,
            ta_15m=ta_15m,
            ta_4h=ta_4h,
            pivots=pivots,
            ic_scores=ic_cache.get(symbol),
        )
        latest_signals[symbol] = _build_signal_payload_dict(signal)
        logger.info(
            f"[Signal] {symbol} initial → {signal.action} "
            f"(quality={signal.quality_score}, 4h={signal.confluence_4h_direction})"
        )

    # Attach to app state
    app.state.buffers = buffers
    app.state.buffers_15m = buffers_15m
    app.state.buffers_4h = buffers_4h
    app.state.conn_manager = conn_manager
    app.state.ml_engine = ml_engine
    app.state.ta_engine = ta_engine
    app.state.backtest_engine = backtest_engine
    app.state.executor = executor
    app.state.latest_signals = latest_signals
    app.state.trade_logger = trade_logger
    app.state.ic_engine = ic_engine
    app.state.ic_cache = ic_cache

    # Start live Binance stream
    stream = BinanceStreamManager(
        settings,
        buffers,
        buffers_15m,
        buffers_4h,
        ta_engine,
        ml_engine,
        signal_gen,
        conn_manager,
        ic_engine=ic_engine,
        ic_cache=ic_cache,
        executor=executor,
        trade_logger=trade_logger,
    )
    stream_task = asyncio.create_task(stream.run())
    app.state.stream_task = stream_task

    # Start periodic ML retrain background task
    retrain_task = asyncio.create_task(_ml_retrain_loop(buffers, ml_engine))
    app.state.retrain_task = retrain_task

    logger.info("Crypto Trader API is ready!")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    stream_task.cancel()
    retrain_task.cancel()
    for task in (stream_task, retrain_task):
        try:
            await task
        except asyncio.CancelledError:
            pass
    executor.shutdown(wait=False)
    logger.info("[Shutdown] Complete")


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Project 9PM - Crypto Trader",
    version="3.0.0",
    description="Real-time Binance market data + TA + XGBoost signals",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(http_router)


@app.get("/health")
async def health():
    return {"status": "ok", "symbols": settings.SYMBOLS}
