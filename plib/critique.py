import json

from plib.llm import LLMClient


def critique_strategies(specs, metrics, data, ledgers, llm: LLMClient):
    critiques = {}
    assumptions = {
        "intrabar_ordering": "stop_first: if both stop-loss and take-profit are touched in same bar, stop is hit first",
        "slippage": "zero slippage assumption",
        "commission": "zero commission assumption",
        "data_quality": "OHLCV data as-is from source, no adjustments",
    }

    for sid, spec in specs.items():
        m = metrics.get(sid, {})
        trades = ledgers.get(sid, [])
        equity_curve = m.get("equity_curve", [0])
        critique = llm.critique_strategy(sid, spec, m, trades, equity_curve, assumptions)
        if isinstance(critique, str):
            critique = json.loads(critique)
        critiques[sid] = critique

    with open("critiques.json", "w") as f:
        json.dump(critiques, f, indent=2)
    return critiques
