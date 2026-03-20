import logging
from typing import Optional

import pandas as pd

from app.core.ta_engine import TAEngine
from app.core.signal_generator import SignalGenerator
from app.models.schemas import BacktestResult, BacktestTrade
from app.config import settings

logger = logging.getLogger(__name__)

# Round-trip fee: entry fee + exit fee (0.1% each side)
_FEE_RT_PCT = settings.BACKTEST_FEE_PCT * 2 * 100  # as percent (e.g. 0.2)


class BacktestEngine:
    """Walk-forward backtester with fee modeling, SL enforcement, and short side."""

    def __init__(self, ta_engine: TAEngine, signal_gen: SignalGenerator):
        self.ta_engine = ta_engine
        self.signal_gen = signal_gen

    def run(self, df: pd.DataFrame, symbol: str) -> BacktestResult:
        """Simulate both long and short trades with fees and stop-losses."""
        if len(df) < 70:
            return BacktestResult(
                symbol=symbol,
                total_signals=0,
                win_rate=0.0,
                avg_return=0.0,
                profit_factor=None,
                max_drawdown=0.0,
                total_return=0.0,
                trades=[],
            )

        trades: list[BacktestTrade] = []
        open_long: Optional[dict] = None
        open_short: Optional[dict] = None
        prev_ta = None

        for i in range(60, len(df)):
            window = df.iloc[: i + 1]
            ta = self.ta_engine.compute(window)
            if ta is None:
                continue

            current_close = float(df["close"].iloc[i])
            current_low = float(df["low"].iloc[i])
            current_high = float(df["high"].iloc[i])

            signal = self.signal_gen.generate(
                symbol, ta, None, current_close, prev_ta=prev_ta
            )
            prev_ta = ta

            # ── LONG position management ───────────────────────────────
            if open_long is not None:
                sl = open_long.get("sl")
                exited = False

                # Stop-loss hit check (use candle low for accuracy)
                if sl is not None and sl > 0 and current_low <= sl:
                    exit_price = sl
                    return_pct = (exit_price - open_long["entry"]) / open_long["entry"] * 100
                    return_pct -= _FEE_RT_PCT
                    trades.append(BacktestTrade(
                        timestamp=open_long["time"],
                        action="BUY",
                        entry=open_long["entry"],
                        exit_price=round(exit_price, 6),
                        return_pct=round(return_pct, 3),
                        is_win=return_pct > 0,
                        side="LONG",
                    ))
                    open_long = None
                    exited = True

                # Exit on SELL signal
                if not exited and signal.action == "SELL":
                    return_pct = (current_close - open_long["entry"]) / open_long["entry"] * 100
                    return_pct -= _FEE_RT_PCT
                    trades.append(BacktestTrade(
                        timestamp=open_long["time"],
                        action="BUY",
                        entry=open_long["entry"],
                        exit_price=current_close,
                        return_pct=round(return_pct, 3),
                        is_win=return_pct > 0,
                        side="LONG",
                    ))
                    open_long = None
                    exited = True

                # Force-exit after 10 candles
                if not exited and (i - open_long["idx"]) >= 10:
                    return_pct = (current_close - open_long["entry"]) / open_long["entry"] * 100
                    return_pct -= _FEE_RT_PCT
                    trades.append(BacktestTrade(
                        timestamp=open_long["time"],
                        action="BUY",
                        entry=open_long["entry"],
                        exit_price=current_close,
                        return_pct=round(return_pct, 3),
                        is_win=return_pct > 0,
                        side="LONG",
                    ))
                    open_long = None

            # ── SHORT position management ──────────────────────────────
            if open_short is not None:
                sl = open_short.get("sl")
                exited = False

                # Stop-loss hit check (use candle high for shorts)
                if sl is not None and sl > 0 and current_high >= sl:
                    exit_price = sl
                    return_pct = (open_short["entry"] - exit_price) / open_short["entry"] * 100
                    return_pct -= _FEE_RT_PCT
                    trades.append(BacktestTrade(
                        timestamp=open_short["time"],
                        action="SELL",
                        entry=open_short["entry"],
                        exit_price=round(exit_price, 6),
                        return_pct=round(return_pct, 3),
                        is_win=return_pct > 0,
                        side="SHORT",
                    ))
                    open_short = None
                    exited = True

                # Cover on BUY signal
                if not exited and signal.action == "BUY":
                    return_pct = (open_short["entry"] - current_close) / open_short["entry"] * 100
                    return_pct -= _FEE_RT_PCT
                    trades.append(BacktestTrade(
                        timestamp=open_short["time"],
                        action="SELL",
                        entry=open_short["entry"],
                        exit_price=current_close,
                        return_pct=round(return_pct, 3),
                        is_win=return_pct > 0,
                        side="SHORT",
                    ))
                    open_short = None
                    exited = True

                # Force-exit after 10 candles
                if not exited and (i - open_short["idx"]) >= 10:
                    return_pct = (open_short["entry"] - current_close) / open_short["entry"] * 100
                    return_pct -= _FEE_RT_PCT
                    trades.append(BacktestTrade(
                        timestamp=open_short["time"],
                        action="SELL",
                        entry=open_short["entry"],
                        exit_price=current_close,
                        return_pct=round(return_pct, 3),
                        is_win=return_pct > 0,
                        side="SHORT",
                    ))
                    open_short = None

            # ── Enter new positions ────────────────────────────────────
            if signal.action == "BUY" and open_long is None:
                open_long = {
                    "entry": current_close,
                    "time": int(df["open_time"].iloc[i]),
                    "idx": i,
                    "sl": signal.stop_loss,
                }

            if signal.action == "SELL" and open_short is None:
                open_short = {
                    "entry": current_close,
                    "time": int(df["open_time"].iloc[i]),
                    "idx": i,
                    "sl": signal.stop_loss,  # for shorts: stop_loss = entry + ATR
                }

        if not trades:
            return BacktestResult(
                symbol=symbol,
                total_signals=0,
                win_rate=0.0,
                avg_return=0.0,
                profit_factor=None,
                max_drawdown=0.0,
                total_return=0.0,
                trades=[],
            )

        # ── Stats for all trades ───────────────────────────────────────
        total = len(trades)
        wins = sum(1 for t in trades if t.is_win)
        returns = [t.return_pct for t in trades]
        gains = sum(r for r in returns if r > 0)
        losses = abs(sum(r for r in returns if r < 0))

        # Max drawdown on combined equity curve
        cum = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in returns:
            cum += r / 100
            peak = max(peak, cum)
            max_dd = max(max_dd, peak - cum)

        # Short-side stats
        short_trades = [t for t in trades if t.side == "SHORT"]
        short_wins = sum(1 for t in short_trades if t.is_win)
        short_win_rate = round(short_wins / len(short_trades) * 100, 1) if short_trades else 0.0
        short_total_return = round(sum(t.return_pct for t in short_trades), 2) if short_trades else 0.0

        return BacktestResult(
            symbol=symbol,
            total_signals=total,
            win_rate=round(wins / total * 100, 1),
            avg_return=round(sum(returns) / total, 3),
            profit_factor=round(gains / losses, 2) if losses > 0 else None,
            max_drawdown=round(max_dd * 100, 2),
            total_return=round(sum(returns), 2),
            trades=trades[-30:],
            short_win_rate=short_win_rate,
            short_total_return=short_total_return,
        )
