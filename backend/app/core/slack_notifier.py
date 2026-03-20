import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Sends trading signal notifications to Slack via Incoming Webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send_signal(
        self,
        symbol: str,
        action: str,
        price: float,
        strength: float,
        quality_score: int,
        quality_label: str,
        source: str,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        risk_reward: Optional[float] = None,
        macro_trend: Optional[str] = None,
    ) -> bool:
        """Send a BUY/SELL signal notification to Slack."""
        if not self.webhook_url:
            logger.debug("[Slack] No webhook URL configured, skipping notification")
            return False

        if action == "HOLD":
            return False

        emoji = ":chart_with_upwards_trend:" if action == "BUY" else ":chart_with_downwards_trend:"
        color = "#00C853" if action == "BUY" else "#FF1744"
        action_emoji = ":green_circle:" if action == "BUY" else ":red_circle:"

        # Format price based on magnitude
        if price >= 1000:
            price_str = f"${price:,.2f}"
        elif price >= 1:
            price_str = f"${price:.4f}"
        else:
            price_str = f"${price:.6f}"

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Build fields
        fields = [
            {"title": "Price", "value": price_str, "short": True},
            {"title": "Strength", "value": f"{strength:.0%}", "short": True},
            {"title": "Quality", "value": f"{quality_label} ({quality_score})", "short": True},
            {"title": "Source", "value": source.upper(), "short": True},
        ]

        if macro_trend:
            fields.append({"title": "Trend", "value": macro_trend.capitalize(), "short": True})

        if take_profit:
            tp_str = f"${take_profit:,.2f}" if take_profit >= 1000 else f"${take_profit:.4f}"
            fields.append({"title": "Take Profit", "value": tp_str, "short": True})

        if stop_loss:
            sl_str = f"${stop_loss:,.2f}" if stop_loss >= 1000 else f"${stop_loss:.4f}"
            fields.append({"title": "Stop Loss", "value": sl_str, "short": True})

        if risk_reward:
            fields.append({"title": "Risk/Reward", "value": f"{risk_reward:.2f}", "short": True})

        # Format symbol for display (e.g., BTCUSDT -> BTC/USDT)
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        display_symbol = f"{base}/USDT"

        payload = {
            "attachments": [
                {
                    "fallback": f"{action} Signal - {display_symbol} @ {price_str}",
                    "color": color,
                    "pretext": f"{action_emoji} *{action} Signal* - *{display_symbol}*",
                    "fields": fields,
                    "footer": f"{emoji} Crypto Trader AI",
                    "footer_icon": "https://api.binance.com/favicon.ico",
                    "ts": int(datetime.utcnow().timestamp()),
                }
            ]
        }

        try:
            client = await self._get_client()
            response = await client.post(self.webhook_url, json=payload)
            if response.status_code == 200:
                logger.info(f"[Slack] Sent {action} notification for {symbol}")
                return True
            else:
                logger.error(f"[Slack] Failed to send: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"[Slack] Error sending notification: {e}")
            return False
