import json
from datetime import datetime


def generate_report(specs, metrics, critiques, data, ledgers, walk_forward=None,
                    sensitivity=None, adversarial=None, strategy_names=None):
    lines = []

    lines.append("# Strategy Backtest Report")
    lines.append(f"\nGenerated: {datetime.now().isoformat()}")
    lines.append("\n---")
    lines.append("## DISCLAIMER")
    lines.append("\nThis report is produced by automated analysis tooling for educational and research purposes only.")
    lines.append("It does not constitute financial advice. Past performance is not indicative of future results.")
    lines.append("No trading decisions should be based on this analysis without independent verification.")
    lines.append("\n---")

    for sid in sorted(specs.keys()):
        spec = specs[sid]
        m = metrics.get(sid, {})
        critique = critiques.get(sid, {})
        trades = ledgers.get(sid, [])

        sname = (strategy_names or {}).get(sid, spec.get('instrument', sid))
        lines.append(f"\n## Strategy {sid}: {sname}")
        lines.append(f"\n**Instrument:** {spec.get('instrument', 'N/A')}")
        lines.append(f"**Timeframe:** {spec.get('timeframe', 'N/A')}")

        lines.append("\n### Enter Conditions")
        for ec in spec.get("entry_conditions", []):
            lines.append(f"- {ec.get('condition_id', '?')}: `{ec.get('expression', '?')}`")

        lines.append("\n### Exit Conditions")
        for ec in spec.get("exit_conditions", []):
            lines.append(f"- {ec.get('condition_id', '?')}: `{ec.get('expression', '?')}`")

        lines.append(f"\n### Position Sizing")
        lines.append(f"- Rule: {spec.get('position_sizing_rule', 'N/A')}")
        if spec.get("stop_loss_rule"):
            lines.append(f"- Stop Loss: {spec['stop_loss_rule']}")
        if spec.get("take_profit_rule"):
            lines.append(f"- Take Profit: {spec['take_profit_rule']}")

        lines.append("\n### Ambiguities & Assumptions")
        for amb in spec.get("explicit_ambiguities", []):
            lines.append(f"- **{amb.get('ambiguity', '?')}**")
            lines.append(f"  - Assumption: {amb.get('assumption_used_for_backtest', '?')}")
            lines.append(f"  - Impact if different: {amb.get('impact_if_different', '?')}")

        lines.append("\n### Performance Metrics")
        lines.append(f"- Total Return: ${m.get('total_return', 0):.2f}")
        lines.append(f"- Win Rate: {m.get('win_rate', 0)*100:.1f}%")
        lines.append(f"- Profit Factor: {m.get('profit_factor', 0):.2f}")
        lines.append(f"- Max Drawdown: ${m.get('max_drawdown', 0):.2f}")
        lines.append(f"- Annualised Sharpe: {m.get('annualised_sharpe', 0):.2f}")
        lines.append(f"- Sortino Ratio: {m.get('sortino_ratio', 0):.2f}")
        lines.append(f"- Number of Trades: {m.get('num_trades', 0)}")
        lines.append(f"- Largest Losing Streak: {m.get('largest_losing_streak', 0)}")

        lines.append("\n### Trade Summary")
        if trades:
            winners = [t for t in trades if t["pnl"] > 0]
            losers = [t for t in trades if t["pnl"] < 0]
            lines.append(f"- Total Trades: {len(trades)}")
            lines.append(f"- Winners: {len(winners)}, Losers: {len(losers)}")
            if winners:
                avg_win = sum(t["pnl"] for t in winners) / len(winners)
                lines.append(f"- Average Win: ${avg_win:.2f}")
            if losers:
                avg_loss = sum(t["pnl"] for t in losers) / len(losers)
                lines.append(f"- Average Loss: ${avg_loss:.2f}")
        else:
            lines.append("- No trades were generated.")

        high_risk = critique.get("high_risk_flag", False)
        if high_risk:
            lines.append("\n### ⚠ HIGH RISK WARNING")
            lines.append(f"\n{critique.get('high_risk_reasoning', 'This strategy is classified as high risk.')}")

        lines.append("\n### Critique")
        lines.append(f"\n**Robustness Verdict:** {critique.get('robustness_verdict', 'N/A')}")
        lines.append(f"\n**Overfitting Risk:** {critique.get('overfitting_risk', 'N/A')}")
        lines.append(f"\n**Market Regime Dependence:** {critique.get('market_regime_dependence', 'N/A')}")
        lines.append(f"\n**Execution Realism:** {critique.get('execution_realism', 'N/A')}")
        lines.append(f"\n**Failure Modes:** {critique.get('failure_modes', 'N/A')}")

        if walk_forward and sid in walk_forward:
            wf = walk_forward[sid]
            lines.append(f"\n### Walk-Forward Analysis")
            lines.append(f"- Status: {wf.get('status', 'N/A')}")
            for w in wf.get("windows", []):
                lines.append(f"  - {w.get('window', '?')}: {w.get('num_trades', 0)} trades, return=${w.get('total_return', 0):.2f}")

        if sensitivity and sid in sensitivity:
            sens = sensitivity[sid]
            lines.append(f"\n### Parameter Sensitivity")
            for sweep in sens.get("parameter_sweeps", []):
                lines.append(f"  - {sweep}")
            if "interpretation" in sens:
                interp = sens["interpretation"]
                lines.append(f"  - Interpretation: {interp.get('interpretation', 'N/A')}")

        if adversarial and sid in adversarial:
            adv = adversarial[sid]
            lines.append(f"\n### Adversarial Scenario Tests")
            for sc in adv.get("scenarios", []):
                lines.append(f"  - {sc.get('scenario_name', '?')}: {sc.get('total_return', 0):.2f} return, failure: {sc.get('failure_observed', '?')}")

        lines.append("\n---")

    lines.append("\n## Backtest Assumptions")
    lines.append("""
1. **Intrabar ordering**: If both stop-loss and take-profit are touched in the same bar, the stop-loss is assumed to be hit first.
2. **Slippage**: Zero slippage — all orders execute at the exact specified price.
3. **Commission**: Zero commission and spread costs.
4. **Liquidity**: Assumes infinite liquidity at the traded price.
5. **Data**: OHLCV data is used as-is from the source. Synthetic data uses documented GBM parameters.
6. **Time zones**: London open is assumed at 8:00 UTC (ignoring BST). NY close is assumed at 16:00 UTC.
7. **Order types**: Market orders only. No limit orders or stop-limit orders.
""")

    lines.append("\n## Risk Warnings")
    lines.append("""
- **All strategies are theoretical.** Live execution will differ due to slippage, commission, latency, and liquidity.
- **Past backtest performance does not guarantee future results.**
- **Strategy C is a martingale strategy and carries ruin risk.** Exponential stake escalation can lead to total loss.
- **Parameter sensitivity analysis is not exhaustive.** Other parameter combinations may produce different results.
- **This tool is for educational purposes only.** Not intended for live trading decisions.
""")

    with open("report.md", "w") as f:
        f.write("\n".join(lines))

    return "\n".join(lines)


def generate_comparative_brief(specs, metrics, critiques, strategy_names=None):
    lines = []
    lines.append("# Comparative Strategy Brief")
    lines.append(f"\nGenerated: {datetime.now().isoformat()}")
    strategy_names = strategy_names or {}
    lines.append("\n---")

    rankings = []
    for sid, m in metrics.items():
        sharpe = m.get("annualised_sharpe", 0)
        total_ret = m.get("total_return", 0)
        max_dd = m.get("max_drawdown", 1)
        risk_adjusted = sharpe if sharpe != 0 else total_ret / max(max_dd, 1)
        rankings.append((sid, risk_adjusted, total_ret, sharpe, max_dd))

    rankings.sort(key=lambda x: x[1], reverse=True)

    lines.append("\n## Risk-Adjusted Ranking")
    for rank, (sid, ra, ret, sharpe, dd) in enumerate(rankings, 1):
        sname = strategy_names.get(sid, sid)
        lines.append(f"\n{rank}. **{sname} ({sid})** — Risk-Adj Score: {ra:.2f}, Return: ${ret:.2f}, Sharpe: {sharpe:.2f}, MaxDD: ${dd:.2f}")

    if rankings:
        best = rankings[0][0]
        worst = rankings[-1][0]
        lines.append(f"\n## Strongest Strategy")
        lines.append(f"\n**{strategy_names.get(best, best)} ({best})** — Highest risk-adjusted score.")

        lines.append(f"\n## Weakest Strategy")
        lines.append(f"\n**{strategy_names.get(worst, worst)} ({worst})** — Lowest risk-adjusted score.")

    lines.append("\n## Risk-Adjusted Reasoning")
    lines.append("""
- Strategies are ranked by Sharpe ratio (annualised) as the primary risk-adjusted metric.
- Sharpe ratio measures return per unit of total volatility. A higher Sharpe indicates better risk-adjusted performance.
- Sortino ratio (downside deviation only) is also reported for context.
- Max drawdown is reported as a complementary risk measure.
""")

    lines.append("\n## Robustness Warning")
    lines.append("""
- Walk-forward analysis provides the best indication of out-of-sample robustness.
- Strategies that degrade across windows may be overfitted to specific market regimes.
- Adversarial scenario tests reveal strategy fragility under stressed conditions.
- Parameter sensitivity analysis shows how performance changes with input assumptions.
""")

    lines.append("\n## Retail-Reader Warning")
    lines.append("""
- **This is automated analysis tooling, not financial advice.**
- No strategy should be traded with real capital without independent validation.
- Backtest results are hypothetical and do not account for real-world frictions.
- Past performance is not indicative of future results.
- Retail traders should be especially cautious of strategies with high win rates but tail-risk exposure (e.g., martingale).
""")

    lines.append("\n## High-Risk Warning for Martingale Strategies")
    lines.append("""
### ⚠ Strategy C: Martingale — HIGH RISK

Martingale strategies carry inherent ruin risk:
- **Exponential stake escalation**: A losing streak of N trades requires a stake of $2^(N-1).
- **Finite capital**: With a $200 drawdown limit, only 8 consecutive losses are needed to fail.
- **Path dependency**: The order of wins and losses matters more than the win rate.
- **Misleading win rate**: Many small wins can mask the impact of rare but catastrophic losses.
- **Recommendation**: Not suitable for retail traders. Avoid strategies that double down on losses.
""")

    with open("comparative_brief.md", "w") as f:
        f.write("\n".join(lines))
    return "\n".join(lines)
