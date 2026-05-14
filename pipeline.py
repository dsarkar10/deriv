#!/usr/bin/env python3
"""Pipeline orchestrator - runs all stages in order with state transitions."""

import json
import sys
from pathlib import Path

from plib.state import Pipeline, PipelineStage
from plib.data import DataManager
from plib.llm import LLMClient
from plib.formalise import formalise_strategies, validate_specs
from plib.engine import run_backtests, write_ledgers
from plib.metrics import compute_metrics, reconcile_ledger
from plib.critique import critique_strategies
from plib.walkforward import run_walkforward
from plib.sensitivity import run_sensitivity
from plib.adversarial import run_adversarial
from plib.report import generate_report, generate_comparative_brief


def main():
    pipeline = Pipeline()
    errors = []

    # ── INIT → STRATEGIES_LOADED ──
    try:
        with open("strategies.json") as f:
            strategies = json.load(f)
        pipeline.transition(PipelineStage.STRATEGIES_LOADED)
        print(f"[{pipeline.current_stage.name}] Loaded {len(strategies)} strategies")
    except Exception as e:
        print(f"FATAL: Could not load strategies.json: {e}")
        sys.exit(1)

    # ── DATA_FETCHED_OR_SIMULATED ──
    try:
        data_manager = DataManager()
        data = data_manager.fetch_all(strategies)
        pipeline.transition(PipelineStage.DATA_FETCHED_OR_SIMULATED)
        for sid, df in data.items():
            print(f"  Data for {sid}: {len(df)} rows, {list(df.columns)}")
        print(f"[{pipeline.current_stage.name}] Data ready")
    except Exception as e:
        errors.append(f"Data fetch failed: {e}")
        print(f"ERROR: {e}")

    # ── STRATEGIES_FORMALISED ──
    try:
        llm = LLMClient()
        specs = formalise_strategies(strategies, llm)
        pipeline.transition(PipelineStage.STRATEGIES_FORMALISED)
        for sid in specs:
            num_amb = len(specs[sid].get("explicit_ambiguities", []))
            print(f"  {sid}: {num_amb} ambiguities documented")
        print(f"[{pipeline.current_stage.name}] Strategies formalised")
    except Exception as e:
        errors.append(f"Formalisation failed: {e}")
        print(f"ERROR: {e}")

    # ── SPECS_VALIDATED ──
    try:
        spec_errors = validate_specs(specs)
        if spec_errors:
            for e in spec_errors:
                print(f"  SPEC ERROR: {e}")
            errors.extend(spec_errors)
        else:
            print("  All specs valid")
        pipeline.transition(PipelineStage.SPECS_VALIDATED)
        print(f"[{pipeline.current_stage.name}] Specs validated")
    except Exception as e:
        errors.append(f"Spec validation failed: {e}")

    # ── BACKTESTS_EXECUTED ──
    try:
        ledgers = run_backtests(specs, data)
        pipeline.transition(PipelineStage.BACKTESTS_EXECUTED)
        for sid, trades in ledgers.items():
            print(f"  {sid}: {len(trades)} trades")
        print(f"[{pipeline.current_stage.name}] Backtests complete")
    except Exception as e:
        errors.append(f"Backtest failed: {e}")

    # ── LEDGERS_WRITTEN ──
    try:
        write_ledgers(ledgers)
        pipeline.transition(PipelineStage.LEDGERS_WRITTEN)
        print(f"[{pipeline.current_stage.name}] Ledgers written")
    except Exception as e:
        errors.append(f"Ledger write failed: {e}")

    # ── METRICS_COMPUTED ──
    try:
        metrics = compute_metrics(ledgers, specs)
        reconciliation = reconcile_ledger(metrics, ledgers)
        if reconciliation:
            errors.extend(reconciliation)
            for e in reconciliation:
                print(f"  RECON ERROR: {e}")
        else:
            print("  All ledgers reconcile with metrics")
        pipeline.transition(PipelineStage.METRICS_COMPUTED)
        print(f"[{pipeline.current_stage.name}] Metrics computed")
    except Exception as e:
        errors.append(f"Metrics computation failed: {e}")

    # ── STRATEGIES_CRITIQUED ──
    try:
        critiques = critique_strategies(specs, metrics, data, ledgers, llm)
        pipeline.transition(PipelineStage.STRATEGIES_CRITIQUED)
        for sid, c in critiques.items():
            risk = "HIGH RISK" if c.get("high_risk_flag") else "OK"
            print(f"  {sid}: {c.get('robustness_verdict', '?')} [{risk}]")
        print(f"[{pipeline.current_stage.name}] Critiques complete")
    except Exception as e:
        errors.append(f"Critique failed: {e}")

    # ── OPTIONAL_ROBUSTNESS_TESTS_COMPLETE ──
    try:
        print("  Walk-forward analysis...")
        wf = run_walkforward(specs, data)
        print("  Parameter sensitivity...")
        sens = run_sensitivity(specs, data, llm)
        print("  Adversarial scenarios...")
        adv = run_adversarial(specs, data, llm)
        pipeline.transition(PipelineStage.OPTIONAL_ROBUSTNESS_TESTS_COMPLETE)
        print(f"[{pipeline.current_stage.name}] Robustness tests complete")
    except Exception as e:
        errors.append(f"Robustness tests failed: {e}")
        wf = {}
        sens = {}
        adv = {}

    # ── REPORT_GENERATED ──
    try:
        strategy_names = {s["id"]: s["name"] for s in strategies}
        generate_report(specs, metrics, critiques, data, ledgers, wf, sens, adv, strategy_names=strategy_names)
        critiques_dict = critiques
        generate_comparative_brief(specs, metrics, critiques_dict, strategy_names=strategy_names)
        pipeline.transition(PipelineStage.REPORT_GENERATED)
        print(f"[{pipeline.current_stage.name}] Reports generated")
    except Exception as e:
        errors.append(f"Report generation failed: {e}")

    # ── VALIDATION_COMPLETE ──
    try:
        from validate import run_validation
        val_errors = run_validation()
        if val_errors:
            errors.extend(val_errors)
            for e in val_errors:
                print(f"  VALIDATION ERROR: {e}")
        else:
            print("  All validation checks passed")
        pipeline.transition(PipelineStage.VALIDATION_COMPLETE)
        print(f"[{pipeline.current_stage.name}] Validation complete")
    except Exception as e:
        errors.append(f"Validation failed: {e}")

    # ── RESULTS_FINALISED ──
    pipeline.transition(PipelineStage.RESULTS_FINALISED)
    print(f"[{pipeline.current_stage.name}] Pipeline finished")

    if errors:
        print(f"\n⚠ {len(errors)} issue(s) encountered:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n✓ Pipeline completed successfully")


if __name__ == "__main__":
    main()
