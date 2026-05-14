#!/usr/bin/env python3
"""Validation script — checks required artifacts and invariants."""

import json
import os
import sys
from pathlib import Path


REQUIRED_ARTIFACTS = [
    "strategies.json",
    "data_manifest.json",
    "metrics.json",
    "critiques.json",
    "report.md",
    "llm_calls.jsonl",
]

REQUIRED_DIRS = ["specs", "ledgers"]

REQUIRED_SPEC_KEYS = [
    "strategy_id", "instrument", "timeframe", "data_source",
    "entry_conditions", "exit_conditions", "position_sizing_rule",
    "session_filters", "risk_controls", "explicit_ambiguities",
]

REQUIRED_METRICS_KEYS = [
    "total_return", "win_rate", "profit_factor", "max_drawdown",
    "annualised_sharpe", "sortino_ratio", "avg_trade_duration",
    "num_trades", "largest_losing_streak",
]


def run_validation():
    errors = []

    # Check required artifacts exist
    for art in REQUIRED_ARTIFACTS:
        if not Path(art).exists():
            errors.append(f"Missing required artifact: {art}")

    for d in REQUIRED_DIRS:
        if not Path(d).is_dir():
            errors.append(f"Missing required directory: {d}")

    # Check strategies.json is valid JSON
    try:
        with open("strategies.json") as f:
            strategies = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        errors.append(f"strategies.json is not valid JSON: {e}")
        strategies = []

    # Check specs exist for every strategy
    strategy_ids = [s["id"] for s in strategies]
    for sid in strategy_ids:
        spec_path = Path(f"specs/{sid}.json")
        if not spec_path.exists():
            errors.append(f"Missing spec for strategy {sid}: {spec_path}")
            continue
        try:
            with open(spec_path) as f:
                spec = json.load(f)
        except json.JSONDecodeError:
            errors.append(f"specs/{sid}.json is not valid JSON")
            continue

        # Check spec has all required keys
        for key in REQUIRED_SPEC_KEYS:
            if key not in spec:
                errors.append(f"Strategy {sid}: missing required spec key '{key}'")

        # Check at least 3 substantive ambiguities
        amb = spec.get("explicit_ambiguities", [])
        if len(amb) < 3:
            errors.append(f"Strategy {sid}: only {len(amb)} ambiguities, minimum 3 required")

        # Check each ambiguity has all required fields
        for i, a in enumerate(amb):
            for k in ("ambiguity", "assumption_used_for_backtest", "impact_if_different"):
                if k not in a:
                    errors.append(f"Strategy {sid}: ambiguity[{i}] missing '{k}'")
                elif len(str(a.get(k, ""))) < 10:
                    errors.append(f"Strategy {sid}: ambiguity[{i}].{k} is too short (must be substantive)")

    # Check ledgers exist for every strategy
    for sid in strategy_ids:
        ledger_path = Path(f"ledgers/{sid}.csv")
        if not ledger_path.exists():
            errors.append(f"Missing ledger for strategy {sid}: {ledger_path}")

    # Check metrics.json exists and is valid JSON
    if Path("metrics.json").exists():
        try:
            with open("metrics.json") as f:
                metrics = json.load(f)
        except json.JSONDecodeError:
            errors.append("metrics.json is not valid JSON")
            metrics = {}

        # Check each strategy has metrics
        for sid in strategy_ids:
            if sid not in metrics:
                errors.append(f"Strategy {sid} missing from metrics.json")
                continue
            m = metrics[sid]
            for key in REQUIRED_METRICS_KEYS:
                if key not in m:
                    errors.append(f"Strategy {sid}: missing metric '{key}'")

        # Check ledger totals reconcile with summary metrics
        for sid in strategy_ids:
            ledger_path = Path(f"ledgers/{sid}.csv")
            if ledger_path.exists() and sid in metrics:
                try:
                    import pandas as pd
                    ledger_df = pd.read_csv(ledger_path)
                    if not ledger_df.empty:
                        ledger_total = ledger_df["pnl"].sum()
                        metric_total = metrics[sid].get("total_return", 0)
                        if abs(ledger_total - metric_total) > 0.01:
                            errors.append(
                                f"Strategy {sid}: ledger total ({ledger_total}) != "
                                f"metrics total_return ({metric_total})"
                            )
                except Exception as e:
                    errors.append(f"Strategy {sid}: ledger reconciliation failed: {e}")

    # Check Strategy C is flagged high risk
    if "C" in strategy_ids and Path("critiques.json").exists():
        try:
            with open("critiques.json") as f:
                critiques = json.load(f)
            c_critique = critiques.get("C", {})
            if not c_critique.get("high_risk_flag"):
                errors.append("Strategy C is NOT flagged as high risk (should be)")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            errors.append(f"Could not check Strategy C high risk flag: {e}")

    # Check llm_calls.jsonl has separate records for formalisation and critique
    if Path("llm_calls.jsonl").exists():
        try:
            stages_seen = set()
            with open("llm_calls.jsonl") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    stages_seen.add(record.get("stage"))
            if "formalisation" not in stages_seen:
                errors.append("llm_calls.jsonl: missing formalisation stage records")
            if "critique" not in stages_seen:
                errors.append("llm_calls.jsonl: missing critique stage records")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            errors.append(f"llm_calls.jsonl error: {e}")

    # Check data_manifest.json exists and is valid
    if Path("data_manifest.json").exists():
        try:
            with open("data_manifest.json") as f:
                manifest = json.load(f)
            if "datasets" not in manifest:
                errors.append("data_manifest.json: missing 'datasets' key")
        except (json.JSONDecodeError, FileNotFoundError):
            errors.append("data_manifest.json is not valid JSON")

    # Check report.md exists
    if not Path("report.md").exists():
        errors.append("Missing required artifact: report.md")

    return errors


def main():
    errors = run_validation()
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print("✓ All validation checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
