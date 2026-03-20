import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok", "symbols": settings.SYMBOLS}


@router.get("/symbols")
async def get_symbols():
    return {"symbols": settings.SYMBOLS}


@router.get("/history/{symbol}")
async def get_history(
    symbol: str,
    interval: str = "1h",
    limit: int = 500,
):
    """Proxy Binance historical klines."""
    symbol = symbol.upper()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"{settings.BINANCE_REST_URL}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            resp.raise_for_status()
            candles = [
                {
                    "time": int(k[0]) // 1000,
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
                for k in resp.json()
            ]
            return {"symbol": symbol, "interval": interval, "candles": candles}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str):
    """24hr stats for a symbol."""
    symbol = symbol.upper()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{settings.BINANCE_REST_URL}/api/v3/ticker/24hr",
                params={"symbol": symbol},
            )
            resp.raise_for_status()
            d = resp.json()
            return {
                "symbol": symbol,
                "price": float(d["lastPrice"]),
                "change_pct": float(d["priceChangePercent"]),
                "high": float(d["highPrice"]),
                "low": float(d["lowPrice"]),
                "volume": float(d["volume"]),
                "quote_volume": float(d["quoteVolume"]),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/tickers")
async def get_all_tickers():
    """24hr stats for all configured symbols."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        results = []
        for symbol in settings.SYMBOLS:
            try:
                resp = await client.get(
                    f"{settings.BINANCE_REST_URL}/api/v3/ticker/24hr",
                    params={"symbol": symbol},
                )
                d = resp.json()
                results.append(
                    {
                        "symbol": symbol,
                        "price": float(d["lastPrice"]),
                        "change_pct": float(d["priceChangePercent"]),
                        "high": float(d["highPrice"]),
                        "low": float(d["lowPrice"]),
                        "volume": float(d["volume"]),
                        "quote_volume": float(d["quoteVolume"]),
                    }
                )
            except Exception:
                pass
        return {"tickers": results}


@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, limit: int = 20):
    """Proxy Binance order book depth."""
    symbol = symbol.upper()
    if limit > 100:
        limit = 100
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{settings.BINANCE_REST_URL}/api/v3/depth",
                params={"symbol": symbol, "limit": limit},
            )
            resp.raise_for_status()
            d = resp.json()
            return {
                "symbol": symbol,
                "bids": [[float(p), float(q)] for p, q in d["bids"]],
                "asks": [[float(p), float(q)] for p, q in d["asks"]],
                "last_update_id": d["lastUpdateId"],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/{symbol}")
async def run_backtest(request: Request, symbol: str):
    """Walk-forward backtest for a symbol using stored kline buffer."""
    symbol = symbol.upper()
    buffers = request.app.state.buffers
    if symbol not in buffers:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    buf = buffers[symbol]
    df = buf.to_dataframe()
    if df.empty or len(df) < 70:
        raise HTTPException(
            status_code=422, detail="Not enough data for backtest (need 70+ candles)"
        )

    backtest_engine = request.app.state.backtest_engine
    executor = request.app.state.executor
    loop = asyncio.get_event_loop()

    result = await loop.run_in_executor(
        executor, backtest_engine.run, df, symbol
    )
    return result.model_dump()


@router.get("/model/status")
async def model_status(request: Request):
    ml_engine = request.app.state.ml_engine
    return {
        "models": {
            symbol: {"ready": ml_engine._ready.get(symbol, False)}
            for symbol in request.app.state.buffers
        }
    }


@router.get("/signals/latest")
async def latest_signals(request: Request):
    return {"signals": request.app.state.latest_signals}


@router.get("/trade-log")
async def get_trade_log(request: Request, symbol: str = None, limit: int = 100):
    trade_logger = request.app.state.trade_logger
    entries = trade_logger.get_log(symbol=symbol.upper() if symbol else None, limit=limit)
    return {"entries": entries, "total": len(entries)}


@router.get("/trade-log/stats")
async def get_trade_log_stats(request: Request, symbol: str = None):
    trade_logger = request.app.state.trade_logger
    return trade_logger.get_stats(symbol=symbol.upper() if symbol else None)


@router.get("/ic-scores/{symbol}")
async def get_ic_scores(request: Request, symbol: str):
    symbol = symbol.upper()
    buffers = request.app.state.buffers
    if symbol not in buffers:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    df = buffers[symbol].to_dataframe()
    if df.empty or len(df) < 100:
        raise HTTPException(status_code=422, detail="Not enough data (need 100+ candles)")

    ic_engine = request.app.state.ic_engine
    executor = request.app.state.executor
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, ic_engine.compute, df, symbol)
    return result.model_dump()
