import json
import os
from pathlib import Path

from plib.llm import LLMClient


def formalise_strategies(strategies, llm: LLMClient):
    specs_dir = Path("specs")
    specs_dir.mkdir(exist_ok=True)
    specs = {}
    for s in strategies:
        spec = llm.formalise_strategy(s)
        if isinstance(spec, str):
            spec = json.loads(spec)
        filepath = specs_dir / f"{s['id']}.json"
        with open(filepath, "w") as f:
            json.dump(spec, f, indent=2)
        specs[s["id"]] = spec
    return specs


def validate_specs(specs):
    required_keys = [
        "strategy_id", "instrument", "timeframe", "data_source",
        "entry_conditions", "exit_conditions", "position_sizing_rule",
        "session_filters", "risk_controls", "explicit_ambiguities",
    ]
    errors = []
    for sid, spec in specs.items():
        for key in required_keys:
            if key not in spec:
                errors.append(f"Strategy {sid}: missing required key '{key}'")
        if "explicit_ambiguities" in spec:
            if len(spec["explicit_ambiguities"]) < 3:
                errors.append(f"Strategy {sid}: only {len(spec['explicit_ambiguities'])} ambiguities, minimum 3 required")
            for i, amb in enumerate(spec["explicit_ambiguities"]):
                for k in ("ambiguity", "assumption_used_for_backtest", "impact_if_different"):
                    if k not in amb:
                        errors.append(f"Strategy {sid}: ambiguity[{i}] missing key '{k}'")
        for i, ec in enumerate(spec.get("entry_conditions", [])):
            for k in ("condition_id", "expression", "indicators_required"):
                if k not in ec:
                    errors.append(f"Strategy {sid}: entry_conditions[{i}] missing key '{k}'")
        for i, ec in enumerate(spec.get("exit_conditions", [])):
            for k in ("condition_id", "expression"):
                if k not in ec:
                    errors.append(f"Strategy {sid}: exit_conditions[{i}] missing key '{k}'")
    return errors
