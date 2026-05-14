import json
import copy

import numpy as np

from plib.engine import BacktestEngine


def run_sensitivity(specs, data, llm):
    results = {}
    for sid, spec in specs.items():
        df = data.get(sid)
        if df is None:
            continue
        if sid == "A":
            sweeps = _sweep_breakout(spec, df)
        elif sid == "B":
            sweeps = _sweep_rsi(spec, df)
        else:
            continue
        interpretation = llm.critique_sensitivity(sid, sweeps)
        results[sid] = {
            "parameter_sweeps": sweeps,
            "interpretation": interpretation,
        }
    with open("parameter_sensitivity.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    return results


def _sweep_breakout(spec, df):
    base_threshold = 0.0005
    results = []
    for mult in [0.5, 0.75, 1.0, 1.25, 1.5]:
        threshold = base_threshold * mult
        test_spec = copy.deepcopy(spec)
        engine = BacktestEngine()
        trades = engine.run(test_spec, df)
        total_return = sum(t["pnl"] for t in trades)
        num_trades = len(trades)
        win_rate = sum(1 for t in trades if t["pnl"] > 0) / max(num_trades, 1)
        results.append({
            "multiplier": mult,
            "threshold_pips": round(threshold / 0.0001, 1),
            "num_trades": num_trades,
            "total_return": round(total_return, 2),
            "win_rate": round(win_rate, 4),
        })
    return results


def _sweep_rsi(spec, df):
    base_threshold = 25
    results = []
    for mult in [0.5, 0.75, 1.0, 1.25, 1.5]:
        threshold = base_threshold * mult
        test_spec = copy.deepcopy(spec)
        engine = BacktestEngine()
        trades = engine.run(test_spec, df)
        total_return = sum(t["pnl"] for t in trades)
        num_trades = len(trades)
        win_rate = sum(1 for t in trades if t["pnl"] > 0) / max(num_trades, 1)
        results.append({
            "multiplier": mult,
            "rsi_threshold": round(threshold, 1),
            "num_trades": num_trades,
            "total_return": round(total_return, 2),
            "win_rate": round(win_rate, 4),
        })
    return results
