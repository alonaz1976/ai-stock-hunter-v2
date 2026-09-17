# AI Stock Hunter V6.1.1 — Adaptive Entry Learning

V6.1.1 moves the project from a fixed Entry gate toward a **history-learned and continuously monitored entry trigger**. Production still remains conservative: research can propose new weights, but only out-of-sample and live-feedback evidence can justify promotion.

## 1. Entry Optimizer — learned shadow weights

Entry Validation now includes a constrained optimizer for the Dynamic entry layer.

The optimizer uses these causal inputs:

- Daily Setup
- Fresh Signal
- Volume / Flow
- No-Chase
- Entry Score
- Quant Score
- Exit Safety

To reduce overfitting, it **learns candidate weights on Walk-Forward folds 1–3** and then reports performance on **unseen Fold 4**. Results include train hit-rate, baseline, median fold lift, positive-fold rate, shadow threshold, Fold-4 signals, Fold-4 hit-rate and Fold-4 lift.

Candidate weights are labelled **shadow only**. They do not change the live production trigger automatically.

## 2. Pre-Move Indicator Lift

Entry Validation now measures which indicators tend to appear **1, 2 or 3 trading days before** a future move.

Research includes signals such as:

- EMA9/20 bullish cross
- MACD bullish cross
- MACD histogram turn positive
- VWAP reclaim
- MACD strengthening
- Volume acceleration
- Directional bullish volume
- RVOL >= 1.20
- ADX >= 25
- RSI 50–70
- CMF > 0
- Price above EMA20 / VWAP
- EMA9 above EMA20
- Positive MACD histogram

For each signal the engine reports Signals, Hit Rate, matching Baseline, Lift, MFE and MAE. Aggregate lift is **signal-count weighted**, not a simple average of ticker percentages.

## 3. Hourly Lift vs same-hour baseline

V6.1.1 adds historical hourly research using available provider intraday history.

Hourly signals are evaluated over 1h / 2h / 4h / 8h forward windows and targets of +1% / +2% / +3%.

The baseline is matched to the **same clock hour** as the signal observations. This reduces the risk of mistaking normal open/close time-of-day behavior for genuine indicator lift.

The hourly table reports:

- Signals
- Hit Rate
- Matched Baseline
- Lift
- MFE
- MAE

Historical intraday coverage remains limited by the market-data provider, so hourly research is supporting timing evidence rather than a replacement for multi-year daily Walk-Forward.

## 4. Recent Feedback becomes a learning layer

The Feedback database now stores the live Entry confirmations for new snapshots:

- Entry state
- Confirmation %
- Daily Setup
- Fresh Signal
- Hourly / 15m confirmation
- Volume / Flow
- No-Chase
- Market Regime

Feedback analytics apply a **60-day half-life** to resolved outcomes. Newer observations therefore matter more than older observations while still preserving sample-size discipline.

The Feedback tab now shows:

- Raw win rate
- Recency-weighted win rate
- Effective recent sample size
- Recent Lift for each confirmation gate
- Evidence status (OK / LOW SAMPLE)

Small recent samples can never auto-retrain production.

## 5. Shadow-first continuous learning

The intended learning loop is now:

`Long history → Walk-Forward → learned candidate weights → unseen Fold 4 → live Feedback shadow → production review`

This keeps the system adaptive without allowing a handful of recent trades to rewrite the model.

## 6. Existing V6.1 safeguards retained

V6.1.1 retains:

- WAIT → WATCH → ARMED → CONFIRMED ENTRY state machine
- TOO LATE / CHASE and INVALIDATED protection
- Six live confirmation gates
- True MFE / MAE Entry Validation
- Target-before-Invalidation ordering using 15m then 1h when available
- Market-separated feedback analytics
- Exit Pressure requiring current bearish direction + outflow/distribution
- US 51 / Hong Kong 50 / Tel Aviv 50 universe (151 total)
- ITT as NYSE while ORCL and INTC remain in the U.S. universe
- Current-price, stale-quote and corporate-action safeguards

## Deployment

Replace all four files together:

- `app.py`
- `quant_engine.py`
- `requirements.txt`
- `README.md`

The app and engine must both show **V6.1.1** / build `V611-ADAPTIVE-ENTRY-LEARNING-20260917-A`.

## First recommended run

Run **Entry Validation → ALL 151** with a 2-year history, then inspect:

1. Entry Optimizer Fold-4 OOS Lift.
2. Pre-Move Lift at -1D / -2D / -3D.
3. Hourly Lift vs same-hour baseline.
4. Differences between NASDAQ/NYSE, Hong Kong and Tel Aviv.

Then continue collecting Feedback snapshots so the recent-market layer can accumulate enough resolved observations to judge whether the historical candidate weights still fit the present regime.

This is research software, not a guarantee of future returns or a substitute for risk controls.
