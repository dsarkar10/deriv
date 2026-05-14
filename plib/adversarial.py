import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from plib.engine import BacktestEngine


def run_adversarial(specs, data, llm):
    all_scenarios = {}
    for sid, spec in specs.items():
        scenarios_def = llm.generate_adversarial(sid, spec)
        if isinstance(scenarios_def, str):
            scenarios_def = json.loads(scenarios_def)
        results = []
        for scenario in scenarios_def.get("scenarios", []):
            df = _generate_adversarial_path(scenario, spec, sid)
            engine = BacktestEngine()
            trades = engine.run(spec, df)
            total_return = sum(t["pnl"] for t in trades)
            num_trades = len(trades)
            max_dd = _calc_max_dd(trades)
            failure = scenario.get("targeted_failure", "unknown")
            results.append({
                "scenario_name": scenario.get("name", ""),
                "scenario_description": scenario.get("description", ""),
                "targeted_failure": failure,
                "num_trades": num_trades,
                "total_return": round(total_return, 2),
                "max_drawdown": round(max_dd, 2),
                "failure_observed": _determine_failure(total_return, max_dd, sid),
            })
        all_scenarios[sid] = {"scenarios": results}
    with open("adversarial_scenarios.json", "w") as f:
        json.dump(all_scenarios, f, indent=2, default=str)
    return all_scenarios


def _generate_adversarial_path(scenario, spec, sid):
    params = scenario.get("generation_params", {})
    trend = params.get("trend", 0.0)
    vol = params.get("volatility", 0.01)
    rng = np.random.default_rng(456 + hash(sid) % 1000)
    n = 200
    price = 100.0 if sid == "C" else 1.08 if sid == "A" else 450.0
    prices = [price]
    for _ in range(n):
        ret = trend + vol * rng.normal(0, 1)
        prices.append(max(prices[-1] * (1 + ret), price * 0.01))
    start = datetime(2025, 6, 1, 9, 0, 0)
    freq = "1min" if sid == "C" else "1h" if sid == "A" else "15min"
    offsets = {"1min": timedelta(minutes=1), "1h": timedelta(hours=1), "15min": timedelta(minutes=15)}
    delta = offsets.get(freq, timedelta(hours=1))
    dates = [start + i * delta for i in range(len(prices))]
    df = pd.DataFrame({"close": prices}, index=dates)
    df.index.name = "datetime"
    df["open"] = df["close"].shift(1).fillna(prices[0])
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + rng.uniform(0, 0.001, size=len(df)))
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - rng.uniform(0, 0.001, size=len(df)))
    df["volume"] = rng.poisson(100, size=len(df))
    return df[["open", "high", "low", "close", "volume"]]


def _calc_max_dd(trades):
    if not trades:
        return 0.0
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        equity += t["pnl"]
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _determine_failure(total_return, max_dd, sid):
    if total_return < -100:
        return "significant_loss"
    if max_dd > 200 and sid == "C":
        return "drawdown_limit_exceeded"
    if max_dd > 50:
        return "high_drawdown"
    return "strategy_continued_functioning"
