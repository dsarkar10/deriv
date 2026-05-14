import json
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from plib.engine import BacktestEngine


def run_walkforward(specs, data):
    results = {}
    for sid, spec in specs.items():
        df = data.get(sid)
        if df is None or len(df) < 100:
            results[sid] = {"status": "insufficient_data", "windows": []}
            continue
        window_metrics = _run_windows(sid, spec, df)
        verdict = _judge_stability(window_metrics)
        results[sid] = {
            "status": verdict,
            "windows": window_metrics,
        }
    with open("walk_forward.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    return results


def _run_windows(sid, spec, df):
    n = len(df)
    split1 = n // 3
    split2 = 2 * n // 3
    windows = [
        ("window_1", df.iloc[:split1]),
        ("window_2", df.iloc[split1:split2]),
        ("window_3", df.iloc[split2:]),
    ]
    engine = BacktestEngine()
    results = []
    for name, window_df in windows:
        if len(window_df) < 20:
            results.append({"window": name, "num_trades": 0, "total_return": 0.0})
            continue
        trades = engine.run(spec, window_df)
        total_return = sum(t["pnl"] for t in trades)
        results.append({
            "window": name,
            "num_trades": len(trades),
            "total_return": round(total_return, 2),
            "start": str(window_df.index[0]),
            "end": str(window_df.index[-1]),
        })
    return results


def _judge_stability(window_metrics):
    returns = [w["total_return"] for w in window_metrics]
    if len(returns) < 2:
        return "insufficient_data"
    if all(r > 0 for r in returns):
        return "stable"
    if returns[0] > 0 and returns[-1] < returns[0]:
        return "degrading"
    if returns[0] > 0 and returns[1] > 0 and returns[2] < 0:
        return "unstable"
    return "unstable"
