import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str) -> None:
    symbol = symbol.upper()
    conn_manager = websocket.app.state.conn_manager
    buffers = websocket.app.state.buffers
    ta_engine = websocket.app.state.ta_engine
    latest_signals = websocket.app.state.latest_signals

    if symbol not in buffers:
        await websocket.close(code=4004, reason=f"Symbol {symbol} not supported")
        return

    await conn_manager.connect(websocket, symbol)

    try:
        buf = buffers[symbol]

        # Build init payload with historical candles and current price
        init_payload: dict = {
            "type": "init",
            "symbol": symbol,
            "price": buf.last_price,
        }

        df = buf.to_dataframe()
        if not df.empty:
            candles = [
                {
                    "time": int(row["open_time"]) // 1000,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
                for _, row in df.iterrows()
            ]
            init_payload["candles"] = candles

            # Include volume profile in init payload
            volume_profile = ta_engine.compute_volume_profile(df)
            if volume_profile:
                init_payload["volume_profile"] = [b.model_dump() for b in volume_profile]

            # Include pivot levels
            pivots = ta_engine.compute_pivot_points(df)
            if pivots.pivot is not None:
                init_payload["pivots"] = pivots.model_dump()

        latest = latest_signals.get(symbol)
        if latest:
            init_payload["signal"] = latest

        await websocket.send_text(json.dumps(init_payload))

        # Keep alive — handle ping/client messages
        while True:
            try:
                raw = await websocket.receive_text()
                data = json.loads(raw)
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                break

    except WebSocketDisconnect:
        pass
    finally:
        conn_manager.disconnect(websocket, symbol)
