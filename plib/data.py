import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


class DataManager:
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self._data_cache = {}
        self._data_info = {}

    def fetch_all(self, strategies):
        for s in strategies:
            if s["id"] == "A":
                self._fetch_eurusd(s)
            elif s["id"] == "B":
                self._fetch_qqq(s)
            elif s["id"] == "C":
                self._generate_synthetic(s)
            else:
                raise ValueError(f"Unknown strategy ID: {s['id']}")
        self._write_manifest()
        return self._data_cache

    def _fetch_eurusd(self, strategy):
        cache_path = self.data_dir / "eurusd_hourly.csv"
        if cache_path.exists():
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            source = "cached"
        else:
            df = yf.download("EURUSD=X", period="6mo", interval="1h",
                             auto_adjust=True, progress=False)
            if df.empty:
                df = self._generate_fallback_eurusd()
                source = "fallback_generated"
            else:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = [str(c).lower() for c in df.columns]
                source = "yfinance"
            df.to_csv(cache_path)
        self._data_cache[strategy["id"]] = df
        self._data_info[strategy["id"]] = {
            "instrument": "EURUSD=X",
            "source": source,
            "timeframe": "1h",
            "rows": len(df),
            "start": str(df.index[0]) if len(df) > 0 else None,
            "end": str(df.index[-1]) if len(df) > 0 else None,
        }

    def _fetch_qqq(self, strategy):
        cache_path = self.data_dir / "qqq_15min.csv"
        if cache_path.exists():
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            source = "cached"
        else:
            df = yf.download("QQQ", period="3mo", interval="15m",
                             auto_adjust=True, progress=False)
            if df.empty:
                df = self._generate_fallback_qqq()
                source = "fallback_generated"
            else:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = [str(c).lower() for c in df.columns]
                source = "yfinance"
            df.to_csv(cache_path)
        self._data_cache[strategy["id"]] = df
        self._data_info[strategy["id"]] = {
            "instrument": "QQQ",
            "source": source,
            "timeframe": "15m",
            "rows": len(df),
            "start": str(df.index[0]) if len(df) > 0 else None,
            "end": str(df.index[-1]) if len(df) > 0 else None,
        }

    def _generate_synthetic(self, strategy):
        cache_path = self.data_dir / "vol75_1min.csv"
        if cache_path.exists():
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        else:
            df = self._gbm(
                initial_price=100.0,
                drift=0.0,
                sigma=0.75 / np.sqrt(252 * 6.5 * 60),
                n_steps=50 * 60,
                seed=123,
                freq="1min",
            )
            df.to_csv(cache_path)
        self._data_cache[strategy["id"]] = df
        self._data_info[strategy["id"]] = {
            "instrument": "Volatility 75 Index",
            "source": "synthetic_gbm",
            "timeframe": "1min",
            "rows": len(df),
            "start": str(df.index[0]) if len(df) > 0 else None,
            "end": str(df.index[-1]) if len(df) > 0 else None,
            "simulation_params": {
                "process": "geometric_brownian_motion",
                "drift": 0,
                "sigma": "0.75 / sqrt(year)",
                "seed": 123,
                "timeframe": "1 minute",
                "initial_price": 100,
            },
        }

    def _gbm(self, initial_price, drift, sigma, n_steps, seed, freq="1min"):
        rng = np.random.default_rng(seed)
        dt = 1.0
        prices = [initial_price]
        for _ in range(n_steps):
            dS = drift * prices[-1] * dt + sigma * prices[-1] * rng.normal(0, np.sqrt(dt))
            prices.append(max(prices[-1] + dS, 0.01))
        start = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        dates = [start + timedelta(minutes=i) for i in range(n_steps + 1)]
        df = pd.DataFrame({"close": prices}, index=dates)
        df.index.name = "datetime"
        df["open"] = df["close"].shift(1).fillna(initial_price)
        df["high"] = df[["open", "close"]].max(axis=1)
        df["low"] = df[["open", "close"]].min(axis=1)
        df["high"] = df["high"] * (1 + rng.uniform(0, 0.002, size=len(df)))
        df["low"] = df["low"] * (1 - rng.uniform(0, 0.002, size=len(df)))
        df["volume"] = rng.poisson(100, size=len(df))
        return df[["open", "high", "low", "close", "volume"]]

    def _generate_fallback_eurusd(self):
        rng = np.random.default_rng(42)
        n = 2000
        prices = [1.08]
        for _ in range(n):
            prices.append(prices[-1] * (1 + rng.normal(0, 0.0005)))
        start = datetime(2025, 1, 1, 8, 0, 0)
        dates = [start + timedelta(hours=i) for i in range(n + 1)]
        df = pd.DataFrame({"close": prices}, index=dates)
        df.index.name = "datetime"
        df["open"] = df["close"].shift(1).fillna(prices[0])
        df["high"] = df[["open", "close"]].max(axis=1) * (1 + rng.uniform(0, 0.001, size=len(df)))
        df["low"] = df[["open", "close"]].min(axis=1) * (1 - rng.uniform(0, 0.001, size=len(df)))
        df["volume"] = rng.poisson(200, size=len(df))
        return df[["open", "high", "low", "close", "volume"]]

    def _generate_fallback_qqq(self):
        rng = np.random.default_rng(42)
        n = 3000
        prices = [450]
        for _ in range(n):
            prices.append(prices[-1] * (1 + rng.normal(0, 0.002)))
        start = datetime(2025, 1, 1, 9, 30, 0)
        dates = [start + timedelta(minutes=15 * i) for i in range(n + 1)]
        df = pd.DataFrame({"close": prices}, index=dates)
        df.index.name = "datetime"
        df["open"] = df["close"].shift(1).fillna(prices[0])
        df["high"] = df[["open", "close"]].max(axis=1) * (1 + rng.uniform(0, 0.001, size=len(df)))
        df["low"] = df[["open", "close"]].min(axis=1) * (1 - rng.uniform(0, 0.001, size=len(df)))
        df["volume"] = rng.poisson(500, size=len(df))
        return df[["open", "high", "low", "close", "volume"]]

    def _write_manifest(self):
        manifest = {"generated_at": datetime.now().isoformat(), "datasets": self._data_info}
        with open("data_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2, default=str)

    def get_data(self, strategy_id):
        return self._data_cache.get(strategy_id)
