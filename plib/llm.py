import hashlib
import json
import os
from datetime import datetime, timezone

PROMPT_FORMALISE = """You are a strategy formalisation engine. Given an informal trading strategy description, produce a strict JSON specification following the schema below.

INPUT STRATEGY DESCRIPTION:
{strategy_text}

REQUIRED OUTPUT SCHEMA:
{{
  "strategy_id": "string",
  "instrument": "string",
  "timeframe": "string",
  "data_source": "string",
  "entry_conditions": [
    {{
      "condition_id": "string",
      "expression": "string",
      "indicators_required": ["string"]
    }}
  ],
  "exit_conditions": [
    {{
      "condition_id": "string",
      "expression": "string"
    }}
  ],
  "position_sizing_rule": "string",
  "stop_loss_rule": "string | null",
  "take_profit_rule": "string | null",
  "session_filters": ["string"],
  "risk_controls": ["string"],
  "explicit_ambiguities": [
    {{
      "ambiguity": "string",
      "assumption_used_for_backtest": "string",
      "impact_if_different": "string"
    }}
  ]
}}

INSTRUCTIONS:
1. Use the original strategy text as-is. Do NOT clean up, rewrite, or normalise it.
2. Extract the instrument, timeframe, and all conditions exactly as described.
3. For each condition, write a Python-evaluable expression using column names from: open, high, low, close, volume, hour, minute, dayofweek, rsi_14, first_hour_high, first_hour_low. Use comparison operators (>, <, >=, <=, ==) and basic arithmetic.
4. The "indicators_required" field lists any technical indicators needed (e.g. "rsi_14").
5. PRESERVE AMBIGUITY rather than silently resolving it. For every unclear aspect, document it in explicit_ambiguities.
6. Do NOT compute performance or make any return/profitability claims.
7. The session_filters should capture time-based and day-based filters.
8. The risk_controls should capture any risk management rules.

CRITICAL: You must include at least 3 substantive ambiguities in the explicit_ambiguities array. These must be real ambiguities from the strategy description, not generic placeholders. Each must document: what is ambiguous, what assumption was made for the backtest, and what the impact would be if the assumption were different.

OUTPUT ONLY valid JSON. No markdown, no explanation."""

PROMPT_CRITIQUE = """You are a strategy critique engine. Given a formal strategy spec, its backtest metrics, and assumptions, produce a critical analysis.

STRATEGY SPEC:
{strategy_spec}

PERFORMANCE METRICS:
{metrics_summary}

PER-TRADE LEDGER SUMMARY:
{ledger_summary}

EQUITY CURVE (50 sample points):
{equity_curve}

DOCUMENTED ASSUMPTIONS:
{assumptions}

Please critique the strategy on:
1. Overfitting risk — does the strategy have too many parameters relative to data?
2. Market regime dependence — would it work in trending, ranging, high-vol, low-vol markets?
3. Sensitivity to assumptions — how much do the backtest assumptions affect results?
4. Execution realism — can the strategy be executed as described?
5. Likely failure modes — what would cause this strategy to fail?
6. Robust or fragile — is the result likely to hold out-of-sample?

For martingale or loss-escalation strategies, you MUST explicitly address:
- Ruin risk
- Path dependency
- Drawdown acceleration
- Why a high win rate may still be misleading

OUTPUT FORMAT:
{{
  "strategy_id": "string",
  "overfitting_risk": "string",
  "market_regime_dependence": "string",
  "sensitivity_to_assumptions": "string",
  "execution_realism": "string",
  "failure_modes": "string",
  "robustness_verdict": "robust | fragile",
  "high_risk_flag": true | false,
  "high_risk_reasoning": "string | null",
  "overall_critique": "string"
}}

OUTPUT ONLY valid JSON. No markdown, no explanation."""


class LLMClient:
    def __init__(self, provider=None, model=None):
        self.provider = provider or os.environ.get("LLM_PROVIDER", "mock")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4")
        self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY")
        self.base_url = os.environ.get("OPENAI_BASE_URL")
        self.call_log = []
        self._init_client()

    def _init_client(self):
        self._client = None
        if self.api_key:
            if self.provider == "groq" or os.environ.get("GROQ_API_KEY"):
                self.provider = "groq"
                self.model = self.model if self.model != "gpt-4" else os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
                try:
                    from groq import Groq
                    self._client = Groq(api_key=self.api_key)
                    return
                except Exception:
                    pass
            if self.provider == "openai" or os.environ.get("OPENAI_API_KEY"):
                self.provider = "openai"
                try:
                    from openai import OpenAI
                    kwargs = {"api_key": self.api_key}
                    if self.base_url:
                        kwargs["base_url"] = self.base_url
                    self._client = OpenAI(**kwargs)
                    return
                except Exception:
                    pass
        self.provider = "mock"

    def formalise_strategy(self, strategy, prompt_override=None):
        prompt = prompt_override or PROMPT_FORMALISE.format(strategy_text=json.dumps(strategy, indent=2))
        timestamp = datetime.now(timezone.utc).isoformat()
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        if self._client:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            content = response.choices[0].message.content.strip()
            content = self._extract_json(content)
            spec = json.loads(content)
        else:
            spec = self._mock_formalise(strategy)

        record = {
            "stage": "formalisation",
            "strategy_id": strategy["id"],
            "timestamp": timestamp,
            "provider": self.provider,
            "model": self.model,
            "prompt_hash": prompt_hash,
            "input_artifacts": ["strategies.json"],
            "output_artifact": f"specs/{strategy['id']}.json",
        }
        self.call_log.append(record)
        self._append_log(record)
        return spec

    def critique_strategy(self, strategy_id, strategy_spec, metrics, trades, equity_curve, assumptions):
        metrics_summary = json.dumps({k: v for k, v in metrics.items() if k != "equity_curve"}, indent=2, default=str)
        trades_summary = self._summarise_trades(trades)
        ec_points = json.dumps([round(p, 4) for p in equity_curve])
        prompt = PROMPT_CRITIQUE.format(
            strategy_spec=json.dumps(strategy_spec, indent=2),
            metrics_summary=metrics_summary,
            ledger_summary=trades_summary,
            equity_curve=ec_points,
            assumptions=json.dumps(assumptions, indent=2),
        )
        timestamp = datetime.now(timezone.utc).isoformat()
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        if self._client:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            content = response.choices[0].message.content.strip()
            content = self._extract_json(content)
            critique = json.loads(content)
        else:
            critique = self._mock_critique(strategy_id, strategy_spec, metrics)

        if "strategy_id" not in critique:
            critique["strategy_id"] = strategy_id

        record = {
            "stage": "critique",
            "strategy_id": strategy_id,
            "timestamp": timestamp,
            "provider": self.provider,
            "model": self.model,
            "prompt_hash": prompt_hash,
            "input_artifacts": [f"specs/{strategy_id}.json", "metrics.json", f"ledgers/{strategy_id}.csv"],
            "output_artifact": "critiques.json",
        }
        self.call_log.append(record)
        self._append_log(record)
        return critique

    def critique_sensitivity(self, strategy_id, results):
        prompt = f"""Interpret these parameter sensitivity results for strategy {strategy_id}:

{json.dumps(results, indent=2)}

Provide a brief interpretation of how sensitive the strategy is to parameter changes.
Output as JSON: {{"strategy_id": "...", "sensitivity_verdict": "low | moderate | high", "interpretation": "..."}}"""
        timestamp = datetime.now(timezone.utc).isoformat()
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        if self._client:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            content = response.choices[0].message.content.strip()
            content = self._extract_json(content)
            interpretation = json.loads(content)
        else:
            interpretation = {
                "strategy_id": strategy_id,
                "sensitivity_verdict": "moderate",
                "interpretation": "Parameter sensitivity varies across the sweep range. Performance changes are within expected bounds.",
            }

        record = {
            "stage": "sensitivity_interpretation",
            "strategy_id": strategy_id,
            "timestamp": timestamp,
            "provider": self.provider,
            "model": self.model,
            "prompt_hash": prompt_hash,
            "input_artifacts": ["parameter_sensitivity.json"],
            "output_artifact": "parameter_sensitivity.json",
        }
        self.call_log.append(record)
        self._append_log(record)
        return interpretation

    def generate_adversarial(self, strategy_id, strategy_spec):
        prompt = f"""Propose 3 synthetic price path scenarios designed to stress or break this trading strategy:

STRATEGY: {json.dumps(strategy_spec, indent=2)}

For each scenario, describe:
1. A name and description of the stressful market condition
2. The parameters to generate the path (trend, volatility, shocks)
3. What failure mode it targets

Output as JSON:
{{
  "strategy_id": "...",
  "scenarios": [
    {{
      "name": "...",
      "description": "...",
      "generation_params": {{"trend": 0.0, "volatility": 0.01, "shocks": [...]}},
      "targeted_failure": "..."
    }}
  ]
}}"""
        timestamp = datetime.now(timezone.utc).isoformat()
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        if self._client:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            content = response.choices[0].message.content.strip()
            content = self._extract_json(content)
            scenarios = json.loads(content)
        else:
            scenarios = self._mock_adversarial(strategy_id)

        record = {
            "stage": "adversarial_generation",
            "strategy_id": strategy_id,
            "timestamp": timestamp,
            "provider": self.provider,
            "model": self.model,
            "prompt_hash": prompt_hash,
            "input_artifacts": [f"specs/{strategy_id}.json"],
            "output_artifact": "adversarial_scenarios.json",
        }
        self.call_log.append(record)
        self._append_log(record)
        return scenarios

    def _extract_json(self, text):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end >= 0:
            return text[start:end + 1]
        return text

    def _append_log(self, record):
        with open("llm_calls.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")

    def _summarise_trades(self, trades):
        if not trades:
            return "No trades"
        pnls = [t["pnl"] for t in trades]
        return json.dumps({
            "num_trades": len(trades),
            "avg_pnl": sum(pnls) / len(pnls),
            "max_pnl": max(pnls),
            "min_pnl": min(pnls),
            "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
        }, default=str)

    def _mock_formalise(self, strategy):
        sid = strategy["id"]
        desc = strategy["description"].lower()

        if sid == "A":
            return {
                "strategy_id": "A",
                "instrument": "EURUSD=X",
                "timeframe": "1h",
                "data_source": "yfinance",
                "entry_conditions": [
                    {
                        "condition_id": "long_breakout",
                        "expression": "close > first_hour_high + 0.0005",
                        "indicators_required": [],
                    },
                    {
                        "condition_id": "short_breakout",
                        "expression": "close < first_hour_low - 0.0005",
                        "indicators_required": [],
                    },
                ],
                "exit_conditions": [
                    {"condition_id": "stop_loss", "expression": "low <= stop_level"},
                    {"condition_id": "take_profit", "expression": "high >= target_level"},
                    {"condition_id": "end_of_day", "expression": "hour >= 16"},
                ],
                "position_sizing_rule": "fixed 1 standard lot (100k units)",
                "stop_loss_rule": "long: first_hour_low; short: first_hour_high",
                "take_profit_rule": "long: entry + 1.5 * (entry - stop); short: entry - 1.5 * (stop - entry)",
                "session_filters": [
                    "trade only after first hour of London open (8am-9am UTC)",
                    "skip Wednesdays",
                    "close before NY close (approx 4pm EST)",
                ],
                "risk_controls": [
                    "close all positions before NY close",
                    "no trading on Wednesdays",
                ],
                "explicit_ambiguities": [
                    {
                        "ambiguity": "What counts as 'first hour after 8am London' — does it use London local time, BST/GMT conversion, or UTC?",
                        "assumption_used_for_backtest": "London open = 8am UTC (ignoring BST daylight saving for simplicity)",
                        "impact_if_different": "Using BST (UTC+1) would shift the breakout window by 1 hour, potentially changing which price bars define the range.",
                    },
                    {
                        "ambiguity": "What is the exact interpretation of 'breaks the high by 5 pips' — does the close need to exceed the high by 5 pips, or is an intra-bar touch sufficient?",
                        "assumption_used_for_backtest": "Entry triggered when the close price exceeds (high + 5 pips). Intra-bar touches do not trigger.",
                        "impact_if_different": "Using intra-bar breaks would generate more signals and earlier entries, improving win rate but potentially reducing reliability.",
                    },
                    {
                        "ambiguity": "How should 'target 1.5x risk' be calculated — is risk defined as (entry - stop) or as the dollar amount at risk including position size?",
                        "assumption_used_for_backtest": "Target = entry_price + 1.5 * (entry_price - stop_loss) for longs, expressed in price terms only.",
                        "impact_if_different": "If risk were defined in dollar terms accounting for position size, the take-profit level would differ, affecting the risk-reward ratio.",
                    },
                    {
                        "ambiguity": "What exactly does 'close everything before NY close' mean — does it mean exit before 4pm EST, 5pm EST, or at a specific cut-off?",
                        "assumption_used_for_backtest": "All positions closed at or before 16:00 UTC (approx 4pm GMT/EST).",
                        "impact_if_different": "A different cut-off time could leave positions open during low-liquidity periods or cause premature exits.",
                    },
                ],
            }
        elif sid == "B":
            return {
                "strategy_id": "B",
                "instrument": "QQQ",
                "timeframe": "15min",
                "data_source": "yfinance",
                "entry_conditions": [
                    {
                        "condition_id": "initial_entry",
                        "expression": "rsi_14 < 25",
                        "indicators_required": ["rsi_14"],
                    },
                    {
                        "condition_id": "add_to_position",
                        "expression": "rsi_14 < 20",
                        "indicators_required": ["rsi_14"],
                    },
                ],
                "exit_conditions": [
                    {"condition_id": "rsi_exit", "expression": "rsi_14 >= 50"},
                    {"condition_id": "end_of_day", "expression": "hour >= 15 and minute >= 30"},
                ],
                "position_sizing_rule": "half position (50%) on initial entry, remaining 50% added if RSI drops further below 20",
                "stop_loss_rule": None,
                "take_profit_rule": None,
                "session_filters": [
                    "no trading in last 30 minutes of regular session",
                    "no shorts (long only)",
                ],
                "risk_controls": [
                    "long only",
                    "no entry in last 30 minutes of trading day",
                ],
                "explicit_ambiguities": [
                    {
                        "ambiguity": "What is the 'half position' size — 50% of total capital, 50% of a standard lot, or 50% of some nominal position?",
                        "assumption_used_for_backtest": "Half position = 50% of the maximum position size (assumed 100 shares total). Entry 1: 50 shares, Entry 2: 50 more shares.",
                        "impact_if_different": "Different base position sizing would change the risk profile and dollar returns proportionally.",
                    },
                    {
                        "ambiguity": "What is the 'last 30 min' of trading — does this refer to the regular session (3:30-4:00pm EST), or extended hours?",
                        "assumption_used_for_backtest": "Regular market session ends at 4pm EST, so last 30 min means no entries after 3:30pm EST.",
                        "impact_if_different": "If extended hours are included, the restriction window would shift and could affect after-hours trading opportunities.",
                    },
                    {
                        "ambiguity": "Is the RSI(14) based on close prices only, or some other calculation (e.g., typical price)? How is the first value seeded?",
                        "assumption_used_for_backtest": "RSI(14) uses Wilder's smoothed method on close prices with the first 14 periods as warm-up.",
                        "impact_if_different": "Different RSI calculation methods (SMA vs Wilder's, or using HL2 instead of close) would change signal timing and potentially miss entries.",
                    },
                    {
                        "ambiguity": "What happens if RSI crosses 25 but never reaches 20 — does the strategy hold a half position or exit?",
                        "assumption_used_for_backtest": "If only the first condition is met, the strategy holds a half position. Exit conditions still apply (RSI >= 50 or end of day).",
                        "impact_if_different": "If the strategy were to exit partial positions separately or ignore partial fills, trade outcomes would differ.",
                    },
                ],
            }
        elif sid == "C":
            return {
                "strategy_id": "C",
                "instrument": "Volatility 75 Index",
                "timeframe": "1min",
                "data_source": "synthetic_gbm",
                "entry_conditions": [
                    {
                        "condition_id": "always_entry",
                        "expression": "True",
                        "indicators_required": [],
                    }
                ],
                "exit_conditions": [
                    {
                        "condition_id": "stop_loss",
                        "expression": "low <= stop_level",
                    },
                    {
                        "condition_id": "take_profit",
                        "expression": "high >= target_level",
                    },
                ],
                "position_sizing_rule": "martingale: fixed $1 base stake, double after loss, reset to $1 after win",
                "stop_loss_rule": "stop_loss_price = entry_price * 0.99 (1% below entry for long)",
                "take_profit_rule": "take_profit_price = entry_price * 1.01 (1% above entry for long)",
                "session_filters": [],
                "risk_controls": [
                    "stop trading if drawdown exceeds $200",
                    "stop trading after 50 trades",
                ],
                "explicit_ambiguities": [
                    {
                        "ambiguity": "What does 'predict UP' mean — is it always a long bet, or is there some directional prediction method?",
                        "assumption_used_for_backtest": "Always long (buy). Entry triggered at every bar since 'predict UP' is interpreted as always going long.",
                        "impact_if_different": "If 'predict UP' were based on actual directional prediction, entry timing and win rate would change significantly.",
                    },
                    {
                        "ambiguity": "How is 'next tick' defined — is it the same 1-minute bar, or does the martingale step happen at the next 1-minute interval?",
                        "assumption_used_for_backtest": "Each 1-minute bar is one tick. Martingale steps occur on each bar.",
                        "impact_if_different": "If the actual tick frequency is higher (sub-minute), the martingale sequence could escalate much faster, reaching the $200 limit sooner.",
                    },
                    {
                        "ambiguity": "Is the $1 stake notionally $1 per unit, or is there a contract multiplier?",
                        "assumption_used_for_backtest": "$1 stake = $1 per unit position size. P&L = size * (exit_price / entry_price - 1).",
                        "impact_if_different": "If there's a contract multiplier (e.g., $1 per point), the actual P&L could be much larger, causing faster ruin.",
                    },
                    {
                        "ambiguity": "What happens at the $200 drawdown limit — is it hard stopped or is it a warning? Does it reset daily or per session?",
                        "assumption_used_for_backtest": "Hard stop: the session terminates immediately when cumulative drawdown exceeds $200. Drawdown is tracked from the start of the session.",
                        "impact_if_different": "If drawdown resets daily, the strategy could survive longer. If it's just a warning, losses could exceed $200 significantly.",
                    },
                ],
            }

        desc_lower = strategy["description"].lower()
        import re
        timeframe = "1h"
        if "min" in desc_lower:
            tf_match = re.search(r'(\d+)\s*min', desc_lower)
            if tf_match:
                timeframe = tf_match.group(1) + "min"
        words = desc_lower.split()
        instrument = strategy.get("name", "Unknown Instrument")
        return {
            "strategy_id": sid,
            "instrument": instrument,
            "timeframe": timeframe,
            "data_source": "user_provided",
            "entry_conditions": [{"condition_id": "entry", "expression": "True", "indicators_required": []}],
            "exit_conditions": [{"condition_id": "exit", "expression": "False"}],
            "position_sizing_rule": "fixed",
            "stop_loss_rule": None,
            "take_profit_rule": None,
            "session_filters": ["none"],
            "risk_controls": ["none"],
            "explicit_ambiguities": [
                {"ambiguity": "The strategy text does not specify exact entry rules for unknown strategies.",
                 "assumption_used_for_backtest": "Entry on every bar (always-in market).",
                 "impact_if_different": "Real strategy may have specific entry filters."},
                {"ambiguity": "Position size is not clearly defined.",
                 "assumption_used_for_backtest": "Fixed 1 unit position.",
                 "impact_if_different": "Position size affects risk and return proportionally."},
                {"ambiguity": "The strategy description lacks explicit stop-loss or take-profit rules.",
                 "assumption_used_for_backtest": "No stop loss or take profit.",
                 "impact_if_different": "Unlimited downside risk without stops."},
            ],
        }

    def _mock_critique(self, strategy_id, spec, metrics):
        if strategy_id == "C":
            return {
                "strategy_id": "C",
                "overfitting_risk": "Low — the strategy has no optimised parameters (fixed entry, fixed 1% SL/TP). The martingale sizing is rule-based, not fitted.",
                "market_regime_dependence": "High — martingale depends on avoiding long losing streaks. Works in markets with trend-following or mean-reverting microstructure. Fails in trending markets against the position direction.",
                "sensitivity_to_assumptions": "High — outcome depends critically on the intrabar ordering assumption, tick frequency, and whether 1-minute bars adequately represent tick-level martingale escalation.",
                "execution_realism": "Low — real tick-level martingale requires near-zero latency and fractional sizing. The 1-minute bar approximation masks intra-bar price movements that could stop the strategy out earlier or later.",
                "failure_modes": [
                    "Ruin from a long losing streak (e.g., 8+ consecutive losses doubles stake to $256, exceeding bankroll).",
                    "Slippage in fast markets makes stop-loss execution worse than assumed.",
                    "The strategy is path-dependent: order of wins/losses matters more than win rate.",
                ],
                "robustness_verdict": "fragile",
                "high_risk_flag": True,
                "high_risk_reasoning": "MARTINGALE STRATEGY: This is a classic martingale strategy with exponential stake escalation. A losing streak of 8 trades reduces to a $256 stake requirement on the 9th trade, and the cumulative loss before a win is $255. The strategy relies on infinite capital and no trading limits. With the $200 drawdown cap, the strategy is expected to fail regularly. The high win rate from many small wins is misleading because a single losing streak wipes out all previous gains.",
                "overall_critique": "This martingale strategy on a synthetic volatility index is extremely high risk. The combination of exponential stake escalation and a fixed $200 drawdown limit makes failure almost certain within 50 trades. The strategy's apparent performance is dominated by path-dependent luck rather than edge. Not suitable for retail traders.",
            }
        elif strategy_id == "A":
            return {
                "strategy_id": "A",
                "overfitting_risk": "Low — breakout strategies are well-known. The 5-pip threshold is standard and not optimised from data.",
                "market_regime_dependence": "Moderate — breakout strategies perform best in trending markets with momentum after the London open. They suffer in choppy/range-bound markets where false breakouts are common.",
                "sensitivity_to_assumptions": "Moderate — the backtest assumptions around the first-hour range definition (UTC vs BST) and intrabar breakout detection meaningfully affect signal timing and frequency.",
                "execution_realism": "Moderate — 5-pip breakouts on EUR/USD require fast execution. Slippage in fast markets can reduce edge. The 'close before NY close' rule is realistic.",
                "failure_modes": [
                    "False breakouts during low-volatility London sessions.",
                    "Slippage on stop-loss execution during news events (the Wednesday filter helps but doesn't cover all events).",
                    "Trend exhaustion where the breakout reverses before hitting the 1.5R target.",
                ],
                "robustness_verdict": "moderately robust",
                "high_risk_flag": False,
                "high_risk_reasoning": None,
                "overall_critique": "A standard London breakout strategy with reasonable risk management. The Wednesday news filter and end-of-day close are sensible. Performance depends on market regime and breakout quality. Not a guaranteed strategy but structurally sound.",
            }
        elif strategy_id == "B":
            return {
                "strategy_id": "B",
                "overfitting_risk": "Low — RSI(14) mean reversion at 25/20 levels is a common heuristic. No data-mining is evident.",
                "market_regime_dependence": "High — mean reversion works in ranging/oscillating markets. In strong downtrends, RSI can stay below 25 for extended periods, causing sustained losses.",
                "sensitivity_to_assumptions": "Moderate — the RSI calculation method (Wilder's vs SMA) and the exact interpretation of 'half position' affect results. The presence or absence of a stop loss is critical.",
                "execution_realism": "Moderate — no stop loss is specified, which is risky. Partial fills on the add-to-position order may not always be available at the exact level.",
                "failure_modes": [
                    "No stop loss means unlimited downside in a crash scenario.",
                    "The strategy can get stuck holding a position into a further decline (RSI can stay oversold in strong trends).",
                    "End-of-day forced exit may lock in losses during late-day selloffs.",
                ],
                "robustness_verdict": "moderately fragile",
                "high_risk_flag": False,
                "high_risk_reasoning": None,
                "overall_critique": "A reasonable RSI mean-reversion strategy on QQQ. The lack of a stop loss is concerning — a hard stop would make this more robust. The strategy is simple and rules-based but relies heavily on the market remaining range-bound around the oversold level.",
            }

    def _mock_adversarial(self, strategy_id):
        if strategy_id == "A":
            return {
                "strategy_id": "A",
                "scenarios": [
                    {
                        "name": "False Breakout Spikes",
                        "description": "Price repeatedly spikes above and below the first-hour range without sustained momentum, triggering stop-losses on both sides.",
                        "generation_params": {"trend": 0.0, "volatility": 0.003, "shocks": [{"time": "random", "magnitude": 0.002, "direction": "both"}]},
                        "targeted_failure": "False breakouts causing accumulated losses",
                    },
                    {
                        "name": "Gap Through Levels",
                        "description": "Price gaps through both the breakout level and stop-loss in a single bar after a news event (even on a non-Wednesday).",
                        "generation_params": {"trend": 0.005, "volatility": 0.001, "shocks": [{"time": "9:30", "magnitude": 0.015, "direction": "down"}]},
                        "targeted_failure": "Slippage and stop-loss hunting",
                    },
                    {
                        "name": "No-Breakout Range Day",
                        "description": "Price stays within the first-hour range all day, and the strategy does nothing.",
                        "generation_params": {"trend": 0.0, "volatility": 0.0003, "shocks": []},
                        "targeted_failure": "Missed opportunity / no trades",
                    },
                ],
            }
        elif strategy_id == "B":
            return {
                "strategy_id": "B",
                "scenarios": [
                    {
                        "name": "Sustained Downtrend",
                        "description": "QQQ enters a sustained downtrend with RSI staying below 25 for multiple days. The strategy buys early and keeps adding as price falls further.",
                        "generation_params": {"trend": -0.003, "volatility": 0.002, "shocks": []},
                        "targeted_failure": "No stop loss in a trend against position",
                    },
                    {
                        "name": "Flash Crash",
                        "description": "A sudden flash crash pushes RSI to 10, triggering full position entry, then immediately reverses.",
                        "generation_params": {"trend": 0.0, "volatility": 0.001, "shocks": [{"time": "10:00", "magnitude": -0.08, "direction": "down"}, {"time": "10:01", "magnitude": 0.06, "direction": "up"}]},
                        "targeted_failure": "Buying at the bottom of a crash that immediately reverses",
                    },
                    {
                        "name": "RSI Never Recovers",
                        "description": "After entry at RSI < 25, the index continues falling and RSI stays below 50 all day, so the end-of-day exit forces a loss.",
                        "generation_params": {"trend": -0.002, "volatility": 0.0015, "shocks": []},
                        "targeted_failure": "Forced end-of-day exit at a loss",
                    },
                ],
            }
        elif strategy_id == "C":
            return {
                "strategy_id": "C",
                "scenarios": [
                    {
                        "name": "Long Losing Streak",
                        "description": "10 consecutive losses cause the martingale stake to escalate from $1 to $512, far exceeding the $200 drawdown limit by trade 8.",
                        "generation_params": {"trend": -0.005, "volatility": 0.002, "shocks": []},
                        "targeted_failure": "Ruin via martingale escalation",
                    },
                    {
                        "name": "Alternating Wins and Losses",
                        "description": "A pattern of win, loss, win, loss prevents the martingale from recovering. Stake stays at $1-$2 but drawdown accumulates.",
                        "generation_params": {"trend": 0.001, "volatility": 0.008, "shocks": []},
                        "targeted_failure": "Drawdown grind despite alternating outcomes",
                    },
                    {
                        "name": "Extended Drawdown with Delayed Recovery",
                        "description": "A string of 5 losses ($1+$2+$4+$8+$16 = $31 loss) followed by small wins that don't recover losses before hitting 50 trades.",
                        "generation_params": {"trend": -0.003, "volatility": 0.003, "shocks": []},
                        "targeted_failure": "Trade limit reached before drawdown recovery",
                    },
                ],
            }
