# Comparative Strategy Brief

Generated: 2026-05-15T03:08:47.837796

---

## Risk-Adjusted Ranking

1. **London Breakout EUR/USD (A)** — Risk-Adj Score: 7.50, Return: $10909.47, Sharpe: 7.50, MaxDD: $439.12

2. **Synthetic Index Martingale (volatility 75) (C)** — Risk-Adj Score: 0.11, Return: $0.05, Sharpe: 0.11, MaxDD: $0.08

3. **RSI mean reversion on US tech (B)** — Risk-Adj Score: -4.44, Return: $-0.46, Sharpe: -4.44, MaxDD: $0.51

## Strongest Strategy

**London Breakout EUR/USD (A)** — Highest risk-adjusted score.

## Weakest Strategy

**RSI mean reversion on US tech (B)** — Lowest risk-adjusted score.

## Risk-Adjusted Reasoning

- Strategies are ranked by Sharpe ratio (annualised) as the primary risk-adjusted metric.
- Sharpe ratio measures return per unit of total volatility. A higher Sharpe indicates better risk-adjusted performance.
- Sortino ratio (downside deviation only) is also reported for context.
- Max drawdown is reported as a complementary risk measure.


## Robustness Warning

- Walk-forward analysis provides the best indication of out-of-sample robustness.
- Strategies that degrade across windows may be overfitted to specific market regimes.
- Adversarial scenario tests reveal strategy fragility under stressed conditions.
- Parameter sensitivity analysis shows how performance changes with input assumptions.


## Retail-Reader Warning

- **This is automated analysis tooling, not financial advice.**
- No strategy should be traded with real capital without independent validation.
- Backtest results are hypothetical and do not account for real-world frictions.
- Past performance is not indicative of future results.
- Retail traders should be especially cautious of strategies with high win rates but tail-risk exposure (e.g., martingale).


## High-Risk Warning for Martingale Strategies

### ⚠ Strategy C: Martingale — HIGH RISK

Martingale strategies carry inherent ruin risk:
- **Exponential stake escalation**: A losing streak of N trades requires a stake of $2^(N-1).
- **Finite capital**: With a $200 drawdown limit, only 8 consecutive losses are needed to fail.
- **Path dependency**: The order of wins and losses matters more than the win rate.
- **Misleading win rate**: Many small wins can mask the impact of rare but catastrophic losses.
- **Recommendation**: Not suitable for retail traders. Avoid strategies that double down on losses.
