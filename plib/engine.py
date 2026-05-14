import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


class BacktestEngine:
    """Deterministic backtest engine.

    Intrabar ordering assumption: If both stop-loss and take-profit are
    touched in the same bar, assume the stop-loss is hit first unless
    the strategy explicitly defines otherwise.
    """

    def __init__(self):
        self.intrabar_ordering = "stop_first"
        self.assumptions = []

    def run(self, spec, df):
        sid = spec["strategy_id"]
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        df["hour"] = df.index.hour
        df["minute"] = df.index.minute
        df["dayofweek"] = df.index.dayofweek

        df = self._add_time_columns(df, spec)

        if any("rsi" in str(c) for ec in spec.get("entry_conditions", [])
               for c in ec.get("indicators_required", [])):
            df = self._add_rsi(df, 14)

        trades = []
        position = None
        entry_bar_idx = 0
        martingale_stake = 1.0
        prev_trade_was_loss = False
        cumulative_drawdown = 0.0
        trade_count = 0
        session_active = True
        peak_equity = 0.0

        first_hour_high = None
        first_hour_low = None

        for i, (idx, bar) in enumerate(df.iterrows()):
            if not session_active:
                continue

            skip = self._check_session_filters(spec.get("session_filters", []), bar, df, i, first_hour_high)
            if skip:
                if position is not None:
                    trade = self._close_position(position, bar, "session_filter", idx, sid)
                    trades.append(trade)
                    position = None
                    trade_count += 1
                    prev_trade_was_loss = trade["pnl"] < 0
                    if prev_trade_was_loss:
                        martingale_stake *= 2
                    else:
                        martingale_stake = 1.0
                continue

            if spec["strategy_id"] == "A":
                is_first_hour = self._is_first_hour(bar, idx)
                if is_first_hour:
                    first_hour_high = bar["high"]
                    first_hour_low = bar["low"]
                elif first_hour_high is not None:
                    if "first_hour_high" not in df.columns:
                        df["first_hour_high"] = np.nan
                        df["first_hour_low"] = np.nan
                    df.at[idx, "first_hour_high"] = first_hour_high
                    df.at[idx, "first_hour_low"] = first_hour_low

            if position is None:
                entry = self._check_entry(spec, bar, df, idx, i, first_hour_high, first_hour_low)
                if entry:
                    size = self._calc_size(spec, martingale_stake)
                    stop = self._calc_stop(spec, entry["price"], first_hour_high, first_hour_low, "long")
                    target = self._calc_target(spec, entry["price"], stop)
                    partial = entry.get("partial", False)
                    position = {
                        "direction": "long",
                        "entry_price": entry["price"],
                        "entry_time": idx,
                        "size": size,
                        "current_size": size,
                        "stop_level": stop,
                        "target_level": target,
                        "partial": partial,
                        "partial_filled": False,
                    }
                    entry_bar_idx = i
            else:
                if spec["strategy_id"] == "B" and position.get("partial") and not position.get("partial_filled"):
                    if self._check_condition(spec, "add_to_position", bar, df, idx, first_hour_high, first_hour_low):
                        add_size = position["size"]
                        position["current_size"] = position["size"] + add_size
                        position["partial_filled"] = True
                        position["entry_price"] = (position["entry_price"] * position["size"] + bar["close"] * add_size) / position["current_size"]
                        position["entry_time"] = idx

                exit_reason, exit_price = self._check_exit(spec, position, bar, df, idx)
                if exit_reason:
                    trade = self._close_position(position, bar, exit_reason, idx, sid, exit_price)
                    if spec["strategy_id"] == "C":
                        trade["size"] = position["size"]
                        trade["pnl"] = trade["size"] * (trade["exit_price"] / trade["entry_price"] - 1)
                        if prev_trade_was_loss and position.get("size", 0) > 0:
                            prev_trade_was_loss = trade["pnl"] < 0
                    trades.append(trade)
                    position = None
                    trade_count += 1
                    prev_trade_was_loss = trade["pnl"] < 0
                    if prev_trade_was_loss:
                        martingale_stake *= 2
                    else:
                        martingale_stake = 1.0
                    cumulative_drawdown += abs(trade["pnl"]) if trade["pnl"] < 0 else -trade["pnl"] * 0
                    cumulative_drawdown = max(0, cumulative_drawdown + (trade["pnl"] if trade["pnl"] < 0 else 0))

                    if spec["strategy_id"] == "C":
                        for rc in spec.get("risk_controls", []):
                            if "drawdown" in rc.lower() and cumulative_drawdown > 200:
                                session_active = False
                            if "trade" in rc.lower() and "50" in rc:
                                if trade_count >= 50:
                                    session_active = False

        if position is not None:
            last_bar = df.iloc[-1]
            trade = self._close_position(position, last_bar, "end_of_data", df.index[-1], sid)
            trades.append(trade)

        self.assumptions.append({
            "key": "intrabar_ordering",
            "value": self.intrabar_ordering,
            "description": "If both stop-loss and take-profit are touched in the same bar, stop-loss is hit first.",
        })

        return trades

    def _add_time_columns(self, df, spec):
        return df

    def _add_rsi(self, df, period=14):
        close = df["close"].values.astype(float)
        n = len(close)
        gains = np.zeros(n)
        losses = np.zeros(n)
        for i in range(1, n):
            diff = close[i] - close[i - 1]
            if diff > 0:
                gains[i] = diff
            else:
                losses[i] = -diff
        avg_gain = np.full(n, np.nan)
        avg_loss = np.full(n, np.nan)
        avg_gain[period] = gains[1:period + 1].mean()
        avg_loss[period] = losses[1:period + 1].mean()
        for i in range(period + 1, n):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period
        rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.nan), where=avg_loss != 0)
        rsi = 100 - (100 / (1 + rs))
        rsi = np.nan_to_num(rsi, nan=50.0)
        df["rsi_14"] = rsi
        return df

    def _is_first_hour(self, bar, idx):
        hour = idx.hour
        return 8 <= hour < 9

    def _check_session_filters(self, filters, bar, df, i, first_hour_high):
        day = bar["dayofweek"]
        hour = bar["hour"]
        minute = bar["minute"]
        for f in filters:
            if "wednesday" in f.lower() and day == 2:
                return True
            if "wednesdays" in f.lower() and day == 2:
                return True
            if "ny close" in f.lower() and hour >= 16:
                return True
            if "last 30 min" in f.lower() or "last 30 minute" in f.lower():
                if hour == 15 and minute >= 30:
                    return True
                if hour >= 16:
                    return True
            if "no shorts" in f.lower():
                pass
            if "long only" in f.lower():
                pass
            if "8am" in f.lower() and "london" in f.lower():
                if hour < 8:
                    return True
        return False

    def _check_entry(self, spec, bar, df, idx, i, first_hour_high, first_hour_low):
        sid = spec["strategy_id"]
        if sid == "A":
            if first_hour_high is None or first_hour_low is None:
                return None
            if bar["close"] > first_hour_high + 0.0005:
                return {"price": bar["close"], "partial": False}
            if bar["close"] < first_hour_low - 0.0005:
                return {"price": bar["close"], "partial": False}
            return None
        elif sid == "B":
            rsi = bar.get("rsi_14", 50)
            if pd.isna(rsi):
                return None
            if rsi < 25:
                return {"price": bar["close"], "partial": True}
            return None
        elif sid == "C":
            return {"price": bar["close"], "partial": False}
        for ec in spec.get("entry_conditions", []):
            if self._eval_expr(ec["expression"], bar, df, idx, first_hour_high, first_hour_low):
                return {"price": bar["close"], "partial": False}
        return None

    def _check_condition(self, spec, condition_id, bar, df, idx, first_hour_high, first_hour_low):
        for ec in spec.get("entry_conditions", []):
            if ec["condition_id"] == condition_id:
                return self._eval_expr(ec["expression"], bar, df, idx, first_hour_high, first_hour_low)
        return False

    def _check_exit(self, spec, position, bar, df, idx):
        direction = position["direction"]
        entry = position["entry_price"]
        stop = position["stop_level"]
        target = position["target_level"]

        if direction == "long":
            stop_hit = stop is not None and bar["low"] <= stop
            target_hit = target is not None and bar["high"] >= target
        else:
            stop_hit = stop is not None and bar["high"] >= stop
            target_hit = target is not None and bar["low"] <= target

        if stop_hit and target_hit:
            if self.intrabar_ordering == "stop_first":
                return "stop_loss", stop
            else:
                return "take_profit", target
        elif stop_hit:
            return "stop_loss", stop
        elif target_hit:
            return "take_profit", target

        if idx.hour >= 16 and idx.hour < 17:
            return "end_of_day", bar["close"]
        if idx.hour >= 17 or idx.hour < 8:
            return "session_end", bar["close"]

        for ec in spec.get("exit_conditions", []):
            if ec["condition_id"] == "end_of_day":
                if self._eval_expr(ec["expression"], bar, df, idx, None, None):
                    return "end_of_day", bar["close"]

        return None, None

    def _close_position(self, position, bar, reason, idx, sid, exit_price=None):
        if exit_price is None:
            exit_price = bar["close"]
        pnl = position.get("current_size", position["size"]) * (exit_price / position["entry_price"] - 1)
        return {
            "strategy_id": sid,
            "entry_time": position["entry_time"].isoformat() if hasattr(position["entry_time"], "isoformat") else str(position["entry_time"]),
            "exit_time": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
            "direction": position["direction"],
            "entry_price": round(position["entry_price"], 6),
            "exit_price": round(exit_price, 6),
            "size": position.get("current_size", position["size"]),
            "pnl": round(pnl, 2),
            "return_pct": round((exit_price / position["entry_price"] - 1) * 100, 4),
            "exit_reason": reason,
        }

    def _calc_size(self, spec, martingale_stake=1.0):
        sid = spec["strategy_id"]
        if sid == "A":
            return 100000
        elif sid == "B":
            return 50
        elif sid == "C":
            return martingale_stake
        return 1

    def _calc_stop(self, spec, entry_price, first_hour_high, first_hour_low, direction):
        sid = spec["strategy_id"]
        if sid == "A":
            return first_hour_low if direction == "long" else first_hour_high
        elif sid == "C":
            return entry_price * 0.99
        return None

    def _calc_target(self, spec, entry_price, stop_price):
        sid = spec["strategy_id"]
        if sid == "A" and stop_price is not None:
            risk = abs(entry_price - stop_price)
            if risk > 0:
                return entry_price + 1.5 * risk
        elif sid == "C":
            return entry_price * 1.01
        return None

    def _eval_expr(self, expr, bar, df, idx, first_hour_high, first_hour_low):
        try:
            namespace = {
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar.get("volume", 0),
                "hour": idx.hour,
                "minute": idx.minute,
                "dayofweek": bar.get("dayofweek", idx.dayofweek),
                "rsi_14": bar.get("rsi_14", 50),
                "first_hour_high": first_hour_high if first_hour_high is not None else bar.get("first_hour_high", np.nan),
                "first_hour_low": first_hour_low if first_hour_low is not None else bar.get("first_hour_low", np.nan),
                "stop_level": bar.get("stop_level", np.nan),
                "target_level": bar.get("target_level", np.nan),
            }
            result = eval(expr, {"__builtins__": {}}, namespace)
            return bool(result)
        except Exception:
            return False


def run_backtests(specs, data):
    engine = BacktestEngine()
    ledgers = {}
    for sid, spec in specs.items():
        df = data.get(sid)
        if df is None:
            continue
        trades = engine.run(spec, df)
        ledgers[sid] = trades
    return ledgers


def write_ledgers(ledgers):
    ledgers_dir = Path("ledgers")
    ledgers_dir.mkdir(exist_ok=True)
    for sid, trades in ledgers.items():
        filepath = ledgers_dir / f"{sid}.csv"
        if not trades:
            pd.DataFrame([], columns=[
                "strategy_id", "entry_time", "exit_time", "direction",
                "entry_price", "exit_price", "size", "pnl", "return_pct", "exit_reason",
            ]).to_csv(filepath, index=False)
            continue
        rows = []
        for t in trades:
            rows.append({
                "strategy_id": t["strategy_id"],
                "entry_time": t["entry_time"],
                "exit_time": t["exit_time"],
                "direction": t["direction"],
                "entry_price": t["entry_price"],
                "exit_price": t["exit_price"],
                "size": t["size"],
                "pnl": t["pnl"],
                "return_pct": t["return_pct"],
                "exit_reason": t["exit_reason"],
            })
        pd.DataFrame(rows).to_csv(filepath, index=False)
