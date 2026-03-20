import time
from typing import Dict, Optional, Tuple

from app.models.schemas import TAResult, MLPrediction, SignalPayload, PivotLevels
from app.config import settings

# Minimum IC (abs Pearson correlation) for an indicator's vote to count.
# Indicators with IC below this are considered noise for a given symbol.
_IC_NOISE_THRESHOLD = 0.02


class SignalGenerator:
    """Combines rule-based TA scoring, ML ensemble blend, quality scoring,
    multi-timeframe (15m + 4H) confluence, and portfolio correlation gate."""

    def generate(
        self,
        symbol: str,
        ta: TAResult,
        ml: Optional[MLPrediction],
        price: float,
        ta_15m: Optional[TAResult] = None,
        ta_4h: Optional[TAResult] = None,
        pivots: Optional[PivotLevels] = None,
        prev_ta: Optional[TAResult] = None,
        ic_scores: Optional[Dict[str, float]] = None,
        active_buy_count: int = 0,
        active_sell_count: int = 0,
    ) -> SignalPayload:

        # Step 1: Classify macro trend first (needed for VWAP context in _rule_based)
        macro_trend = self._classify_macro_trend(ta)

        # Step 2: Rule-based scoring
        rule_action, net, max_score = self._rule_based(ta, prev_ta, ic_scores, macro_trend)
        rule_score = net / max_score if max_score > 0 else 0.0

        # Step 3: Ensemble blend — 60% TA weight + 40% ML weight
        # This replaces the old "either ML or TA" mutually exclusive logic.
        if ml is not None:
            buy_p = ml.probabilities.get("BUY", 0.0)
            sell_p = ml.probabilities.get("SELL", 0.0)
            ml_directional = buy_p - sell_p   # range: -1.0 to +1.0
            blend = 0.6 * rule_score + 0.4 * ml_directional
            ml_contrib = abs(0.4 * ml_directional)
            ta_contrib = abs(0.6 * rule_score)
            if ml_contrib > 0 and ta_contrib > 0:
                source = "ensemble"
            elif ml_contrib > ta_contrib:
                source = "ml"
            else:
                source = "rule"
        else:
            blend = rule_score
            source = "rule"

        # Convert blend score to action using configurable threshold
        threshold = settings.SIGNAL_THRESHOLD / 11.0
        if blend >= threshold:
            final_action = "BUY"
        elif blend <= -threshold:
            final_action = "SELL"
        else:
            final_action = "HOLD"

        strength = min(1.0, abs(blend))

        # Step 4: ADX gate — suppress signals in ranging/choppy markets
        if ta.adx is not None and ta.adx < 25 and final_action != "HOLD":
            final_action = "HOLD"

        # Step 5: Macro trend gate — don't fight the higher-timeframe trend
        if macro_trend == "uptrend" and final_action == "SELL":
            final_action = "HOLD"
        elif macro_trend == "downtrend" and final_action == "BUY":
            final_action = "HOLD"

        # Step 6: Portfolio correlation gate — avoid piling into correlated trades
        if final_action == "BUY" and active_buy_count >= settings.MAX_CORRELATED_SIGNALS:
            final_action = "HOLD"
        elif final_action == "SELL" and active_sell_count >= settings.MAX_CORRELATED_SIGNALS:
            final_action = "HOLD"

        # Step 7: Quality score
        quality_score, quality_label = self._compute_quality_score(ta, ml, final_action)

        # Step 8: 15m confluence (now checks 5 indicators instead of 3)
        confluence_score = None
        confluence_direction = None
        if ta_15m is not None:
            confluence_score, confluence_direction = self._compute_confluence_15m(ta_15m, final_action)
            if confluence_direction in ("aligned_bull", "aligned_bear"):
                strength = min(1.0, strength * 1.2)
                quality_score = min(100, quality_score + 10)

        # Step 9: 4H confluence — higher-timeframe confirmation
        confluence_4h_score = None
        confluence_4h_direction = None
        if ta_4h is not None:
            confluence_4h_score, confluence_4h_direction = self._compute_confluence_4h(ta_4h, final_action)
            if confluence_4h_direction in ("aligned_bull", "aligned_bear"):
                # 4H alignment gives a bigger boost (more meaningful timeframe)
                strength = min(1.0, strength * 1.1)
                quality_score = min(100, quality_score + 15)
            elif confluence_4h_direction == "mixed" and final_action != "HOLD":
                # 4H disagrees — reduce conviction
                strength = max(0.0, strength * 0.8)
                quality_score = max(0, quality_score - 10)

        # Re-label quality after confluence adjustments
        if quality_score >= 75:
            quality_label = "Very Strong"
        elif quality_score >= 50:
            quality_label = "Strong"
        elif quality_score >= 25:
            quality_label = "Moderate"
        else:
            quality_label = "Weak"

        # Step 10: ATR-based profit targets + trailing stop
        take_profit = stop_loss = risk_reward = trailing_stop = None
        if ta.atr is not None and ta.atr > 0 and final_action != "HOLD":
            tp_dist = ta.atr * settings.ATR_TP_MULTIPLIER
            sl_dist = ta.atr * settings.ATR_SL_MULTIPLIER
            if final_action == "BUY":
                take_profit = round(price + tp_dist, 6)
                stop_loss = round(price - sl_dist, 6)
                # Trailing stop activates in strong trending conditions
                if ta.adx is not None and ta.adx >= settings.TRAILING_STOP_ADX_THRESHOLD:
                    trailing_stop = round(price - ta.atr * settings.TRAILING_STOP_MULTIPLIER, 6)
            else:  # SELL
                take_profit = round(price - tp_dist, 6)
                stop_loss = round(price + sl_dist, 6)
                if ta.adx is not None and ta.adx >= settings.TRAILING_STOP_ADX_THRESHOLD:
                    trailing_stop = round(price + ta.atr * settings.TRAILING_STOP_MULTIPLIER, 6)
            risk_reward = round(settings.ATR_TP_MULTIPLIER / settings.ATR_SL_MULTIPLIER, 2)

        return SignalPayload(
            symbol=symbol,
            action=final_action,
            source=source,
            strength=min(1.0, strength),
            price=price,
            ta=ta,
            ml=ml,
            quality_score=quality_score,
            quality_label=quality_label,
            confluence_score=confluence_score,
            confluence_direction=confluence_direction,
            ta_15m=ta_15m,
            ta_4h=ta_4h,
            confluence_4h_score=confluence_4h_score,
            confluence_4h_direction=confluence_4h_direction,
            pivots=pivots,
            take_profit=take_profit,
            stop_loss=stop_loss,
            risk_reward=risk_reward,
            trailing_stop=trailing_stop,
            macro_trend=macro_trend,
            timestamp=int(time.time() * 1000),
        )

    # ── Rule-Based Scoring ─────────────────────────────────────────────

    def _rule_based(
        self,
        ta: TAResult,
        prev_ta: Optional[TAResult] = None,
        ic_scores: Optional[Dict[str, float]] = None,
        macro_trend: Optional[str] = None,
    ) -> Tuple[str, int, int]:
        buy = 0
        sell = 0
        max_score = 0

        def _ic_ok(name: str) -> bool:
            """Return False if IC scores show this indicator is noise for this symbol."""
            if ic_scores is None:
                return True
            return ic_scores.get(name, 1.0) >= _IC_NOISE_THRESHOLD

        # RSI
        if ta.rsi is not None and _ic_ok("rsi"):
            max_score += 2
            if ta.rsi < 35:
                buy += 2
            elif ta.rsi > 65:
                sell += 2

        # MACD — with histogram momentum check (growing vs fading)
        if (
            ta.macd is not None
            and ta.macd_signal is not None
            and ta.macd_hist is not None
            and _ic_ok("macd_hist")
        ):
            max_score += 2
            hist_prev = (
                prev_ta.macd_hist
                if prev_ta is not None and prev_ta.macd_hist is not None
                else ta.macd_hist
            )
            hist_growing = ta.macd_hist > hist_prev
            hist_falling = ta.macd_hist < hist_prev
            if ta.macd > ta.macd_signal and ta.macd_hist > 0 and (prev_ta is None or hist_growing):
                buy += 2
            elif ta.macd < ta.macd_signal and ta.macd_hist < 0 and (prev_ta is None or hist_falling):
                sell += 2

        # Bollinger Bands — with volume confirmation on breakouts
        if ta.bb_upper is not None and ta.bb_lower is not None and _ic_ok("bb_pct"):
            max_score += 2
            vol_confirmed = ta.volume_sma is None or ta.volume > ta.volume_sma * 1.2
            if ta.close < ta.bb_lower and vol_confirmed:
                buy += 2
            elif ta.close > ta.bb_upper and vol_confirmed:
                sell += 2

        # EMA 9/21 crossover
        if ta.ema_9 is not None and ta.ema_21 is not None and _ic_ok("ema_cross_pct"):
            max_score += 1
            if ta.ema_9 > ta.ema_21:
                buy += 1
            else:
                sell += 1

        # Stochastic
        if ta.stoch_k is not None and ta.stoch_d is not None and _ic_ok("stoch_k"):
            max_score += 1
            if ta.stoch_k < 25 and ta.stoch_k > ta.stoch_d:
                buy += 1
            elif ta.stoch_k > 75 and ta.stoch_k < ta.stoch_d:
                sell += 1

        # ADX directional (+DI vs -DI)
        if ta.adx_pos is not None and ta.adx_neg is not None and _ic_ok("adx_cross_pct"):
            max_score += 1
            if ta.adx_pos > ta.adx_neg:
                buy += 1
            else:
                sell += 1

        # OBV trend
        if ta.obv is not None and ta.obv_signal is not None and _ic_ok("obv_trend"):
            max_score += 1
            if ta.obv > ta.obv_signal:
                buy += 1
            else:
                sell += 1

        # VWAP — context-aware:
        #   Trending markets: price above VWAP = bullish (trend-following)
        #   Ranging markets:  price below VWAP = oversold BUY (mean-reversion)
        if ta.vwap is not None and ta.close > 0 and _ic_ok("vwap_dist"):
            max_score += 1
            if macro_trend in ("uptrend", "downtrend"):
                # Trend-following: above VWAP = BUY confirmation
                if ta.close > ta.vwap:
                    buy += 1
                else:
                    sell += 1
            else:
                # Ranging / unknown: mean-reversion
                if ta.close < ta.vwap:
                    buy += 1
                else:
                    sell += 1

        net = buy - sell
        if net >= settings.SIGNAL_THRESHOLD:
            return "BUY", net, max_score
        elif net <= -settings.SIGNAL_THRESHOLD:
            return "SELL", net, max_score
        return "HOLD", net, max_score

    # ── Feature 2: Quality Score ───────────────────────────────────────

    def _compute_quality_score(
        self,
        ta: TAResult,
        ml: Optional[MLPrediction],
        action: str,
    ) -> Tuple[int, str]:
        score = 0

        # RSI extremity (0–20)
        if ta.rsi is not None:
            if action == "BUY":
                if ta.rsi < 30:
                    score += 20
                elif ta.rsi < 45:
                    score += 10
            elif action == "SELL":
                if ta.rsi > 70:
                    score += 20
                elif ta.rsi > 55:
                    score += 10

        # MACD histogram direction (0–15)
        if ta.macd_hist is not None:
            if (action == "BUY" and ta.macd_hist > 0) or (
                action == "SELL" and ta.macd_hist < 0
            ):
                score += 15

        # Bollinger Band position (0–20)
        if ta.bb_pct is not None:
            if action == "BUY":
                if ta.bb_pct < 0.1:
                    score += 20
                elif ta.bb_pct < 0.3:
                    score += 10
            elif action == "SELL":
                if ta.bb_pct > 0.9:
                    score += 20
                elif ta.bb_pct > 0.7:
                    score += 10

        # EMA separation strength (0–15)
        if ta.ema_9 is not None and ta.ema_21 is not None and ta.close > 0:
            separation = abs(ta.ema_9 - ta.ema_21) / ta.close
            if separation > 0.005:
                correct_side = (action == "BUY" and ta.ema_9 > ta.ema_21) or (
                    action == "SELL" and ta.ema_9 < ta.ema_21
                )
                if correct_side:
                    score += 15

        # Stochastic extremity (0–15)
        if ta.stoch_k is not None:
            if action == "BUY" and ta.stoch_k < 20:
                score += 15
            elif action == "SELL" and ta.stoch_k > 80:
                score += 15

        # ADX trend strength bonus (0–10)
        if ta.adx is not None:
            if ta.adx > 40:
                score += 10
            elif ta.adx > 25:
                score += 5

        # VWAP confirmation — trend-following: above VWAP = bullish (0–10)
        if ta.vwap is not None and ta.close > 0:
            vwap_dist = abs(ta.close - ta.vwap) / ta.close
            if vwap_dist > 0.005:
                correct_side = (action == "BUY" and ta.close > ta.vwap) or (
                    action == "SELL" and ta.close < ta.vwap
                )
                if correct_side:
                    score += 10

        # ML confidence bonus (0–15)
        if ml is not None:
            score += int(ml.confidence * 15)

        score = max(0, min(100, score))

        if score >= 75:
            label = "Very Strong"
        elif score >= 50:
            label = "Strong"
        elif score >= 25:
            label = "Moderate"
        else:
            label = "Weak"

        return score, label

    # ── Macro Trend Classification ─────────────────────────────────────

    def _classify_macro_trend(self, ta: TAResult) -> Optional[str]:
        if ta.ema_50 is None or ta.ema_200 is None or ta.close == 0:
            return None
        sep = abs(ta.ema_50 - ta.ema_200) / ta.close
        if sep < settings.MACRO_TREND_RANGING_THRESHOLD:
            return "ranging"
        return "uptrend" if ta.ema_50 > ta.ema_200 else "downtrend"

    # ── 15m Multi-Timeframe Confluence (5 indicators) ──────────────────

    def _compute_confluence_15m(
        self,
        ta_15m: TAResult,
        action_1h: str,
    ) -> Tuple[Optional[float], Optional[str]]:
        agreements = 0
        total = 0

        if ta_15m.rsi is not None:
            total += 1
            if (action_1h == "BUY" and ta_15m.rsi < 50) or (
                action_1h == "SELL" and ta_15m.rsi > 50
            ):
                agreements += 1

        if ta_15m.macd_hist is not None:
            total += 1
            if (action_1h == "BUY" and ta_15m.macd_hist > 0) or (
                action_1h == "SELL" and ta_15m.macd_hist < 0
            ):
                agreements += 1

        if ta_15m.ema_9 is not None and ta_15m.ema_21 is not None:
            total += 1
            if (action_1h == "BUY" and ta_15m.ema_9 > ta_15m.ema_21) or (
                action_1h == "SELL" and ta_15m.ema_9 < ta_15m.ema_21
            ):
                agreements += 1

        # Added: ADX directional check on 15m
        if ta_15m.adx_pos is not None and ta_15m.adx_neg is not None:
            total += 1
            if (action_1h == "BUY" and ta_15m.adx_pos > ta_15m.adx_neg) or (
                action_1h == "SELL" and ta_15m.adx_pos < ta_15m.adx_neg
            ):
                agreements += 1

        # Added: OBV check on 15m
        if ta_15m.obv is not None and ta_15m.obv_signal is not None:
            total += 1
            if (action_1h == "BUY" and ta_15m.obv > ta_15m.obv_signal) or (
                action_1h == "SELL" and ta_15m.obv < ta_15m.obv_signal
            ):
                agreements += 1

        if total == 0:
            return None, None

        score = agreements / total
        if score >= 0.67:
            direction = "aligned_bull" if action_1h == "BUY" else "aligned_bear"
        else:
            direction = "mixed"

        return round(score, 2), direction

    # ── 4H Multi-Timeframe Confluence (5 indicators) ───────────────────

    def _compute_confluence_4h(
        self,
        ta_4h: TAResult,
        action_1h: str,
    ) -> Tuple[Optional[float], Optional[str]]:
        """4H confluence: checks if the higher timeframe confirms the 1H signal."""
        agreements = 0
        total = 0

        # 4H RSI zone
        if ta_4h.rsi is not None:
            total += 1
            if (action_1h == "BUY" and ta_4h.rsi < 60) or (
                action_1h == "SELL" and ta_4h.rsi > 40
            ):
                agreements += 1

        # 4H EMA 9/21 cross
        if ta_4h.ema_9 is not None and ta_4h.ema_21 is not None:
            total += 1
            if (action_1h == "BUY" and ta_4h.ema_9 > ta_4h.ema_21) or (
                action_1h == "SELL" and ta_4h.ema_9 < ta_4h.ema_21
            ):
                agreements += 1

        # 4H macro trend (EMA 50/200)
        if ta_4h.ema_50 is not None and ta_4h.ema_200 is not None and ta_4h.close > 0:
            total += 1
            if (action_1h == "BUY" and ta_4h.ema_50 > ta_4h.ema_200) or (
                action_1h == "SELL" and ta_4h.ema_50 < ta_4h.ema_200
            ):
                agreements += 1

        # 4H ADX directional
        if ta_4h.adx_pos is not None and ta_4h.adx_neg is not None:
            total += 1
            if (action_1h == "BUY" and ta_4h.adx_pos > ta_4h.adx_neg) or (
                action_1h == "SELL" and ta_4h.adx_pos < ta_4h.adx_neg
            ):
                agreements += 1

        # 4H MACD histogram
        if ta_4h.macd_hist is not None:
            total += 1
            if (action_1h == "BUY" and ta_4h.macd_hist > 0) or (
                action_1h == "SELL" and ta_4h.macd_hist < 0
            ):
                agreements += 1

        if total == 0:
            return None, None

        score = agreements / total
        if score >= 0.60:
            direction = "aligned_bull" if action_1h == "BUY" else "aligned_bear"
        else:
            direction = "mixed"

        return round(score, 2), direction
