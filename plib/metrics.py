import json
import math
from datetime import datetime

import numpy as np


def compute_metrics(ledgers, specs):
    all_metrics = {}
    for sid, trades in ledgers.items():
        metrics = _compute_strategy_metrics(sid, trades)
        all_metrics[sid] = metrics
    with open("metrics.json", "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)
    return all_metrics


def _compute_strategy_metrics(sid, trades):
    if not trades:
        return {
            "strategy_id": sid,
            "total_return": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "annualised_sharpe": 0.0,
            "sortino_ratio": 0.0,
            "avg_trade_duration": "0",
            "exposure_pct": 0.0,
            "num_trades": 0,
            "largest_losing_streak": 0,
            "equity_curve": [0] * 50,
        }

    pnls = [t["pnl"] for t in trades]

    total_return = sum(pnls)
    num_wins = sum(1 for p in pnls if p > 0)
    num_losses = sum(1 for p in pnls if p < 0)
    win_rate = num_wins / len(pnls) if pnls else 0.0

    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    equity_curve = []
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        equity_curve.append(equity)

    equity_curve_sampled = _sample_equity_curve(equity_curve, 50)

    returns_pct = [t["return_pct"] for t in trades]
    avg_return = np.mean(returns_pct) if returns_pct else 0.0
    std_return = np.std(returns_pct, ddof=1) if len(returns_pct) > 1 else 0.0
    ann_sharpe = (avg_return / std_return * math.sqrt(252)) if std_return > 0 else 0.0

    neg_returns = [r for r in returns_pct if r < 0]
    downside_std = np.std(neg_returns, ddof=1) if len(neg_returns) > 1 else 0.0
    sortino = (avg_return / downside_std * math.sqrt(252)) if downside_std > 0 else 0.0

    durations_hours = []
    for t in trades:
        try:
            et = datetime.fromisoformat(t["entry_time"])
            xt = datetime.fromisoformat(t["exit_time"])
            durations_hours.append((xt - et).total_seconds() / 3600)
        except (ValueError, TypeError):
            durations_hours.append(0)
    avg_duration = sum(durations_hours) / len(durations_hours) if durations_hours else 0
    avg_duration_str = f"{avg_duration:.1f}h"

    if durations_hours:
        earliest_entry = min(
            datetime.fromisoformat(t["entry_time"]) for t in trades
            if t.get("entry_time")
        )
        latest_exit = max(
            datetime.fromisoformat(t["exit_time"]) for t in trades
            if t.get("exit_time")
        )
        total_data_hours = max((latest_exit - earliest_entry).total_seconds() / 3600, 1)
        total_exposure_hours = sum(durations_hours)
        exposure_pct = round(min(total_exposure_hours / total_data_hours * 100, 100.0), 2)
    else:
        exposure_pct = 0.0

    losing_streak = 0
    max_losing_streak = 0
    for p in pnls:
        if p < 0:
            losing_streak += 1
            max_losing_streak = max(max_losing_streak, losing_streak)
        else:
            losing_streak = 0

    return {
        "strategy_id": sid,
        "total_return": round(total_return, 2),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "max_drawdown": round(max_dd, 2),
        "annualised_sharpe": round(ann_sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "avg_trade_duration": avg_duration_str,
        "exposure_pct": exposure_pct,
        "num_trades": len(trades),
        "largest_losing_streak": max_losing_streak,
        "equity_curve": equity_curve_sampled,
    }


def _sample_equity_curve(curve, n_points=50):
    if not curve:
        return [0] * n_points
    if len(curve) <= n_points:
        return curve + [curve[-1]] * (n_points - len(curve))
    indices = np.linspace(0, len(curve) - 1, n_points, dtype=int)
    return [float(curve[i]) for i in indices]


def reconcile_ledger(metrics, ledgers):
    errors = []
    for sid, m in metrics.items():
        trades = ledgers.get(sid, [])
        ledger_return = sum(t["pnl"] for t in trades)
        if abs(ledger_return - m["total_return"]) > 0.01:
            errors.append(
                f"Strategy {sid}: ledger total ({ledger_return}) != metrics total_return ({m['total_return']})"
            )
    return errors
