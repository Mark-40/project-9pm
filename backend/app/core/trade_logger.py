import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class TradeLogger:
    """Persists signal outcomes to a JSON file.

    Flow:
        record_signal()  — called when a BUY/SELL signal fires
        resolve_outcomes() — called on every closed candle; closes entries
                             that are old enough and records actual return
    """

    def __init__(self, log_path: str):
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: List[dict] = self._load()

    # ── Public API ─────────────────────────────────────────────────────

    def record_signal(
        self,
        symbol: str,
        action: str,
        entry_price: float,
        timestamp: int,
        signal_strength: float,
        quality_score: int,
    ) -> None:
        entry = {
            "id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "action": action,
            "entry_price": entry_price,
            "exit_price": None,
            "return_pct": None,
            "status": "open",
            "signal_strength": round(signal_strength, 4),
            "quality_score": quality_score,
            "timestamp": timestamp,
        }
        self._entries.append(entry)
        self._save()

    def resolve_outcomes(
        self,
        symbol: str,
        current_price: float,
        current_timestamp: int,
        n_candles_threshold: int,
    ) -> None:
        """Close open entries for *symbol* that are older than n_candles_threshold * 1h."""
        threshold_ms = n_candles_threshold * 3_600_000
        changed = False
        for entry in self._entries:
            if entry["symbol"] != symbol or entry["status"] != "open":
                continue
            age_ms = current_timestamp - entry["timestamp"]
            if age_ms < threshold_ms:
                continue
            entry["exit_price"] = current_price
            if entry["action"] == "BUY":
                entry["return_pct"] = round(
                    (current_price - entry["entry_price"]) / entry["entry_price"] * 100, 4
                )
            else:  # SELL
                entry["return_pct"] = round(
                    (entry["entry_price"] - current_price) / entry["entry_price"] * 100, 4
                )
            entry["status"] = "closed"
            changed = True
        if changed:
            self._save()

    def get_log(
        self, symbol: Optional[str] = None, limit: int = 100
    ) -> List[dict]:
        entries = self._entries
        if symbol:
            entries = [e for e in entries if e["symbol"] == symbol]
        return list(reversed(entries))[:limit]

    def get_stats(self, symbol: Optional[str] = None) -> dict:
        entries = [
            e for e in self._entries
            if e["status"] == "closed" and (symbol is None or e["symbol"] == symbol)
        ]
        if not entries:
            return {"total": 0, "win_rate": 0.0, "avg_return": 0.0}
        wins = sum(1 for e in entries if (e["return_pct"] or 0) > 0)
        avg_ret = sum(e["return_pct"] or 0 for e in entries) / len(entries)
        return {
            "total": len(entries),
            "win_rate": round(wins / len(entries), 4),
            "avg_return": round(avg_ret, 4),
        }

    # ── Private ────────────────────────────────────────────────────────

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self._entries, indent=2))
            os.replace(tmp, self._path)
        except Exception as e:
            logger.error(f"[TradeLogger] Failed to save: {e}")

    def _load(self) -> List[dict]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text())
        except Exception as e:
            logger.error(f"[TradeLogger] Failed to load: {e}")
            return []
