import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per symbol and broadcasts messages."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, symbol: str) -> None:
        await websocket.accept()
        self._connections.setdefault(symbol, set()).add(websocket)
        logger.info(
            f"[WS] Client connected to {symbol}. "
            f"Total: {len(self._connections[symbol])}"
        )

    def disconnect(self, websocket: WebSocket, symbol: str) -> None:
        if symbol in self._connections:
            self._connections[symbol].discard(websocket)
        logger.info(f"[WS] Client disconnected from {symbol}")

    async def broadcast(self, symbol: str, payload: dict) -> None:
        clients = self._connections.get(symbol, set())
        if not clients:
            return

        data = json.dumps(payload)
        dead: Set[WebSocket] = set()

        for ws in list(clients):
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)

        for ws in dead:
            self._connections[symbol].discard(ws)

    def get_connection_count(self) -> Dict[str, int]:
        return {s: len(clients) for s, clients in self._connections.items()}
