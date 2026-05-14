# Strategy Backtest Report

Generated: 2026-05-15T03:08:47.836569

---
## DISCLAIMER

This report is produced by automated analysis tooling for educational and research purposes only.
It does not constitute financial advice. Past performance is not indicative of future results.
No trading decisions should be based on this analysis without independent verification.

---

## Strategy A: London Breakout EUR/USD

**Instrument:** EURUSD=X
**Timeframe:** 1h

### Enter Conditions
- long_breakout: `close > first_hour_high + 0.0005`
- short_breakout: `close < first_hour_low - 0.0005`

### Exit Conditions
- stop_loss: `low <= stop_level`
- take_profit: `high >= target_level`
- end_of_day: `hour >= 16`

### Position Sizing
- Rule: fixed 1 standard lot (100k units)
- Stop Loss: long: first_hour_low; short: first_hour_high
- Take Profit: long: entry + 1.5 * (entry - stop); short: entry - 1.5 * (stop - entry)

### Ambiguities & Assumptions
- **What counts as 'first hour after 8am London' — does it use London local time, BST/GMT conversion, or UTC?**
  - Assumption: London open = 8am UTC (ignoring BST daylight saving for simplicity)
  - Impact if different: Using BST (UTC+1) would shift the breakout window by 1 hour, potentially changing which price bars define the range.
- **What is the exact interpretation of 'breaks the high by 5 pips' — does the close need to exceed the high by 5 pips, or is an intra-bar touch sufficient?**
  - Assumption: Entry triggered when the close price exceeds (high + 5 pips). Intra-bar touches do not trigger.
  - Impact if different: Using intra-bar breaks would generate more signals and earlier entries, improving win rate but potentially reducing reliability.
- **How should 'target 1.5x risk' be calculated — is risk defined as (entry - stop) or as the dollar amount at risk including position size?**
  - Assumption: Target = entry_price + 1.5 * (entry_price - stop_loss) for longs, expressed in price terms only.
  - Impact if different: If risk were defined in dollar terms accounting for position size, the take-profit level would differ, affecting the risk-reward ratio.
- **What exactly does 'close everything before NY close' mean — does it mean exit before 4pm EST, 5pm EST, or at a specific cut-off?**
  - Assumption: All positions closed at or before 16:00 UTC (approx 4pm GMT/EST).
  - Impact if different: A different cut-off time could leave positions open during low-liquidity periods or cause premature exits.

### Performance Metrics
- Total Return: $10909.47
- Win Rate: 73.8%
- Profit Factor: 3.30
- Max Drawdown: $439.12
- Annualised Sharpe: 7.50
- Sortino Ratio: 13.04
- Number of Trades: 164
- Largest Losing Streak: 3

### Trade Summary
- Total Trades: 164
- Winners: 121, Losers: 42
- Average Win: $129.34
- Average Loss: $-112.87

### Critique

**Robustness Verdict:** moderately robust

**Overfitting Risk:** Low — breakout strategies are well-known. The 5-pip threshold is standard and not optimised from data.

**Market Regime Dependence:** Moderate — breakout strategies perform best in trending markets with momentum after the London open. They suffer in choppy/range-bound markets where false breakouts are common.

**Execution Realism:** Moderate — 5-pip breakouts on EUR/USD require fast execution. Slippage in fast markets can reduce edge. The 'close before NY close' rule is realistic.

**Failure Modes:** ['False breakouts during low-volatility London sessions.', "Slippage on stop-loss execution during news events (the Wednesday filter helps but doesn't cover all events).", 'Trend exhaustion where the breakout reverses before hitting the 1.5R target.']

### Walk-Forward Analysis
- Status: stable
  - window_1: 50 trades, return=$1474.70
  - window_2: 62 trades, return=$5350.58
  - window_3: 52 trades, return=$3851.57

### Parameter Sensitivity
  - {'multiplier': 0.5, 'threshold_pips': 2.5, 'num_trades': 164, 'total_return': np.float64(10909.47), 'win_rate': 0.7378}
  - {'multiplier': 0.75, 'threshold_pips': 3.8, 'num_trades': 164, 'total_return': np.float64(10909.47), 'win_rate': 0.7378}
  - {'multiplier': 1.0, 'threshold_pips': 5.0, 'num_trades': 164, 'total_return': np.float64(10909.47), 'win_rate': 0.7378}
  - {'multiplier': 1.25, 'threshold_pips': 6.2, 'num_trades': 164, 'total_return': np.float64(10909.47), 'win_rate': 0.7378}
  - {'multiplier': 1.5, 'threshold_pips': 7.5, 'num_trades': 164, 'total_return': np.float64(10909.47), 'win_rate': 0.7378}
  - Interpretation: Parameter sensitivity varies across the sweep range. Performance changes are within expected bounds.

### Adversarial Scenario Tests
  - False Breakout Spikes: 2749.56 return, failure: high_drawdown
  - Gap Through Levels: 20768.63 return, failure: strategy_continued_functioning
  - No-Breakout Range Day: 115.24 return, failure: strategy_continued_functioning

---

## Strategy B: RSI mean reversion on US tech

**Instrument:** QQQ
**Timeframe:** 15min

### Enter Conditions
- initial_entry: `rsi_14 < 25`
- add_to_position: `rsi_14 < 20`

### Exit Conditions
- rsi_exit: `rsi_14 >= 50`
- end_of_day: `hour >= 15 and minute >= 30`

### Position Sizing
- Rule: half position (50%) on initial entry, remaining 50% added if RSI drops further below 20

### Ambiguities & Assumptions
- **What is the 'half position' size — 50% of total capital, 50% of a standard lot, or 50% of some nominal position?**
  - Assumption: Half position = 50% of the maximum position size (assumed 100 shares total). Entry 1: 50 shares, Entry 2: 50 more shares.
  - Impact if different: Different base position sizing would change the risk profile and dollar returns proportionally.
- **What is the 'last 30 min' of trading — does this refer to the regular session (3:30-4:00pm EST), or extended hours?**
  - Assumption: Regular market session ends at 4pm EST, so last 30 min means no entries after 3:30pm EST.
  - Impact if different: If extended hours are included, the restriction window would shift and could affect after-hours trading opportunities.
- **Is the RSI(14) based on close prices only, or some other calculation (e.g., typical price)? How is the first value seeded?**
  - Assumption: RSI(14) uses Wilder's smoothed method on close prices with the first 14 periods as warm-up.
  - Impact if different: Different RSI calculation methods (SMA vs Wilder's, or using HL2 instead of close) would change signal timing and potentially miss entries.
- **What happens if RSI crosses 25 but never reaches 20 — does the strategy hold a half position or exit?**
  - Assumption: If only the first condition is met, the strategy holds a half position. Exit conditions still apply (RSI >= 50 or end of day).
  - Impact if different: If the strategy were to exit partial positions separately or ignore partial fills, trade outcomes would differ.

### Performance Metrics
- Total Return: $-0.46
- Win Rate: 62.5%
- Profit Factor: 0.41
- Max Drawdown: $0.51
- Annualised Sharpe: -4.44
- Sortino Ratio: -4.32
- Number of Trades: 8
- Largest Losing Streak: 2

### Trade Summary
- Total Trades: 8
- Winners: 5, Losers: 3
- Average Win: $0.06
- Average Loss: $-0.26

### Critique

**Robustness Verdict:** moderately fragile

**Overfitting Risk:** Low — RSI(14) mean reversion at 25/20 levels is a common heuristic. No data-mining is evident.

**Market Regime Dependence:** High — mean reversion works in ranging/oscillating markets. In strong downtrends, RSI can stay below 25 for extended periods, causing sustained losses.

**Execution Realism:** Moderate — no stop loss is specified, which is risky. Partial fills on the add-to-position order may not always be available at the exact level.

**Failure Modes:** ['No stop loss means unlimited downside in a crash scenario.', 'The strategy can get stuck holding a position into a further decline (RSI can stay oversold in strong trends).', 'End-of-day forced exit may lock in losses during late-day selloffs.']

### Walk-Forward Analysis
- Status: unstable
  - window_1: 1 trades, return=$-0.27
  - window_2: 4 trades, return=$0.28
  - window_3: 3 trades, return=$-0.47

### Parameter Sensitivity
  - {'multiplier': 0.5, 'rsi_threshold': 12.5, 'num_trades': 8, 'total_return': np.float64(-0.46), 'win_rate': 0.625}
  - {'multiplier': 0.75, 'rsi_threshold': 18.8, 'num_trades': 8, 'total_return': np.float64(-0.46), 'win_rate': 0.625}
  - {'multiplier': 1.0, 'rsi_threshold': 25.0, 'num_trades': 8, 'total_return': np.float64(-0.46), 'win_rate': 0.625}
  - {'multiplier': 1.25, 'rsi_threshold': 31.2, 'num_trades': 8, 'total_return': np.float64(-0.46), 'win_rate': 0.625}
  - {'multiplier': 1.5, 'rsi_threshold': 37.5, 'num_trades': 8, 'total_return': np.float64(-0.46), 'win_rate': 0.625}
  - Interpretation: Parameter sensitivity varies across the sweep range. Performance changes are within expected bounds.

### Adversarial Scenario Tests
  - Sustained Downtrend: -21.19 return, failure: strategy_continued_functioning
  - Flash Crash: -0.08 return, failure: strategy_continued_functioning
  - RSI Never Recovers: -14.35 return, failure: strategy_continued_functioning

---

## Strategy C: Synthetic Index Martingale (volatility 75)

**Instrument:** Volatility 75 Index
**Timeframe:** 1min

### Enter Conditions
- always_entry: `True`

### Exit Conditions
- stop_loss: `low <= stop_level`
- take_profit: `high >= target_level`

### Position Sizing
- Rule: martingale: fixed $1 base stake, double after loss, reset to $1 after win
- Stop Loss: stop_loss_price = entry_price * 0.99 (1% below entry for long)
- Take Profit: take_profit_price = entry_price * 1.01 (1% above entry for long)

### Ambiguities & Assumptions
- **What does 'predict UP' mean — is it always a long bet, or is there some directional prediction method?**
  - Assumption: Always long (buy). Entry triggered at every bar since 'predict UP' is interpreted as always going long.
  - Impact if different: If 'predict UP' were based on actual directional prediction, entry timing and win rate would change significantly.
- **How is 'next tick' defined — is it the same 1-minute bar, or does the martingale step happen at the next 1-minute interval?**
  - Assumption: Each 1-minute bar is one tick. Martingale steps occur on each bar.
  - Impact if different: If the actual tick frequency is higher (sub-minute), the martingale sequence could escalate much faster, reaching the $200 limit sooner.
- **Is the $1 stake notionally $1 per unit, or is there a contract multiplier?**
  - Assumption: $1 stake = $1 per unit position size. P&L = size * (exit_price / entry_price - 1).
  - Impact if different: If there's a contract multiplier (e.g., $1 per point), the actual P&L could be much larger, causing faster ruin.
- **What happens at the $200 drawdown limit — is it hard stopped or is it a warning? Does it reset daily or per session?**
  - Assumption: Hard stop: the session terminates immediately when cumulative drawdown exceeds $200. Drawdown is tracked from the start of the session.
  - Impact if different: If drawdown resets daily, the strategy could survive longer. If it's just a warning, losses could exceed $200 significantly.

### Performance Metrics
- Total Return: $0.05
- Win Rate: 42.0%
- Profit Factor: 1.19
- Max Drawdown: $0.08
- Annualised Sharpe: 0.11
- Sortino Ratio: 0.18
- Number of Trades: 50
- Largest Losing Streak: 6

### Trade Summary
- Total Trades: 50
- Winners: 21, Losers: 29
- Average Win: $0.02
- Average Loss: $-0.01

### ⚠ HIGH RISK WARNING

MARTINGALE STRATEGY: This is a classic martingale strategy with exponential stake escalation. A losing streak of 8 trades reduces to a $256 stake requirement on the 9th trade, and the cumulative loss before a win is $255. The strategy relies on infinite capital and no trading limits. With the $200 drawdown cap, the strategy is expected to fail regularly. The high win rate from many small wins is misleading because a single losing streak wipes out all previous gains.

### Critique

**Robustness Verdict:** fragile

**Overfitting Risk:** Low — the strategy has no optimised parameters (fixed entry, fixed 1% SL/TP). The martingale sizing is rule-based, not fitted.

**Market Regime Dependence:** High — martingale depends on avoiding long losing streaks. Works in markets with trend-following or mean-reverting microstructure. Fails in trending markets against the position direction.

**Execution Realism:** Low — real tick-level martingale requires near-zero latency and fractional sizing. The 1-minute bar approximation masks intra-bar price movements that could stop the strategy out earlier or later.

**Failure Modes:** ['Ruin from a long losing streak (e.g., 8+ consecutive losses doubles stake to $256, exceeding bankroll).', 'Slippage in fast markets makes stop-loss execution worse than assumed.', 'The strategy is path-dependent: order of wins/losses matters more than win rate.']

### Walk-Forward Analysis
- Status: stable
  - window_1: 50 trades, return=$0.05
  - window_2: 50 trades, return=$0.08
  - window_3: 50 trades, return=$0.06

### Adversarial Scenario Tests
  - Long Losing Streak: -11258995408251.37 return, failure: significant_loss
  - Alternating Wins and Losses: 0.22 return, failure: strategy_continued_functioning
  - Extended Drawdown with Delayed Recovery: -1210721449.21 return, failure: significant_loss

---

## Backtest Assumptions

1. **Intrabar ordering**: If both stop-loss and take-profit are touched in the same bar, the stop-loss is assumed to be hit first.
2. **Slippage**: Zero slippage — all orders execute at the exact specified price.
3. **Commission**: Zero commission and spread costs.
4. **Liquidity**: Assumes infinite liquidity at the traded price.
5. **Data**: OHLCV data is used as-is from the source. Synthetic data uses documented GBM parameters.
6. **Time zones**: London open is assumed at 8:00 UTC (ignoring BST). NY close is assumed at 16:00 UTC.
7. **Order types**: Market orders only. No limit orders or stop-limit orders.


## Risk Warnings

- **All strategies are theoretical.** Live execution will differ due to slippage, commission, latency, and liquidity.
- **Past backtest performance does not guarantee future results.**
- **Strategy C is a martingale strategy and carries ruin risk.** Exponential stake escalation can lead to total loss.
- **Parameter sensitivity analysis is not exhaustive.** Other parameter combinations may produce different results.
- **This tool is for educational purposes only.** Not intended for live trading decisions.
