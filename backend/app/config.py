from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/stream"
    # Slack notifications
    SLACK_WEBHOOK_URL: Optional[str] = None
    BINANCE_REST_URL: str = "https://api.binance.com"
    SYMBOLS: List[str] = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    ]
    KLINE_INTERVAL: str = "1h"
    KLINE_INTERVAL_SECONDARY: str = "15m"
    KLINE_INTERVAL_4H: str = "4h"
    KLINE_BUFFER_SIZE: int = 1000
    KLINE_BUFFER_SIZE_SECONDARY: int = 200
    KLINE_BUFFER_SIZE_4H: int = 500
    ML_RETRAIN_INTERVAL_HOURS: int = 6
    ML_MIN_SAMPLES: int = 200
    ML_CONFIDENCE_THRESHOLD: float = 0.60
    ML_ARTIFACTS_DIR: str = "ml/artifacts"
    MODEL_VERSION: str = "v3"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    LOG_LEVEL: str = "INFO"
    FORWARD_PERIODS: int = 3
    FORWARD_THRESHOLD: float = 0.003
    # ATR profit target multipliers
    ATR_TP_MULTIPLIER: float = 2.0
    ATR_SL_MULTIPLIER: float = 1.0
    # Macro trend gate threshold (EMA50/200 separation as fraction of price)
    MACRO_TREND_RANGING_THRESHOLD: float = 0.005
    # Actualized trade log
    TRADE_LOG_PATH: str = "data/trade_log.json"
    TRADE_OUTCOME_CANDLES: int = 5
    # Signal quality improvements
    SIGNAL_THRESHOLD: int = 4           # minimum net score to fire BUY/SELL
    BACKTEST_FEE_PCT: float = 0.001     # 0.1% per side (Binance standard)
    MAX_CORRELATED_SIGNALS: int = 3     # max same-direction signals across portfolio
    TRAILING_STOP_ADX_THRESHOLD: float = 40.0  # ADX level to activate trailing stop
    TRAILING_STOP_MULTIPLIER: float = 1.5      # trailing stop = entry ± ATR × this
    PAPER_RISK_PCT: float = 0.02        # 2% of portfolio risk per trade

    class Config:
        env_file = ".env"


settings = Settings()
