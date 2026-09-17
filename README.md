# AI Stock Hunter V6.1.0 — Entry Trigger Engine V3

V6.1.0 changes the objective of the live system from “high score = possible entry” to a stricter evidence-gated entry state machine.

## Core Entry state machine

The production Entry flow is now:

`WAIT → WATCH → ARMED → CONFIRMED ENTRY`

with two protective terminal states:

- `TOO LATE / CHASE` — setup may still be bullish, but price is too extended for a disciplined entry.
- `INVALIDATED` — trade-plan geometry or exit-risk evidence invalidates the setup.

A high Quant/Entry score alone can no longer create `CONFIRMED ENTRY`.

## Six confirmation gates

`CONFIRMED ENTRY` requires all of the following, plus a valid trade plan and low Exit Pressure:

1. **Daily Setup** — constructive daily structure and supporting Quant evidence.
2. **Fresh Signal** — recent transition evidence rather than a stale bullish state (EMA/MACD/VWAP/volume transitions).
3. **Hourly / 15m Timing** — short-timeframe confirmation.
4. **Volume / Flow** — direction-aware bullish volume / money-flow support.
5. **No Chase** — blocks entries when price is too stretched versus VWAP/EMA/ATR or momentum is overheated.
6. **Market Regime** — blocks confirmation in a defined risk-off broad-market regime.

The Scanner and Analyze views expose confirmation %, confirmed gates, `Why now`, and missing checks.

## Entry plan

For a valid setup the engine calculates:

- Entry Zone
- Breakout Trigger
- Invalidation
- Target 1
- Target 2

The plan is suppressed when data-scale / geometry checks fail.

## Entry Validation improvements

Walk-forward Entry research now includes:

- Daily causal proxy for the Entry Trigger V3 gates.
- True **MFE** (maximum favorable excursion) from future highs.
- True **MAE** (maximum adverse excursion) from future lows.
- Forward return, target hit rate, lift, and days-to-target.
- Static vs Dynamic comparison.

Historical intraday depth is provider-limited, so the long-history Entry Validation uses a daily causal proxy; live `CONFIRMED ENTRY` still requires the actual Hourly/15m timing gate.

## Feedback / Outcome Tracker

V6.1.0 fixes target-vs-invalidation ordering:

- When Target 1 and Invalidation are both touched inside the same daily candle, the tracker checks **15m** bars first and **1h** bars second.
- If order still cannot be determined, the result stays **AMBIGUOUS** and is excluded from clean win/loss statistics.
- Feedback refresh also revisits older `AMBIGUOUS SAME DAY` rows when intraday history is still available.
- Feedback analytics are split by **market + horizon + trade stage**, with Clean Resolved, Clean Win Rate and Ambiguous counts.

## Exit Pressure recalibration

Historical weakness alone can no longer create a high live Exit signal.

`EXIT ARMED` / `EXIT TRIGGER` now require both:

- present-session bearish price direction, and
- confirmed outflow/distribution evidence.

Old weakness may remain contextual evidence, but is capped when the current session is not bearish.

## Scanner universe

The standard multi-market universe is now **151 stocks**:

- **US 51** — the existing U.S. 50 plus **ITT**. ORCL and INTC remain in the universe. ITT is classified as NYSE / Industrials.
- Hong Kong 50.
- Tel Aviv 50.

U.S. timing logic supports both NASDAQ and NYSE pre-market / regular / after-market phases.

## Discovery direction

The V6.1 architecture is ready for the next stage: a wider Discovery Scan that first filters a broad universe for the calibrated setup, then sends only qualified candidates into the heavier Daily + Hourly + 15m Entry Trigger Engine.

That future workflow is intended to be:

`Broad market → Discovery → Setup → ARMED → Hourly/15m confirmation → CONFIRMED ENTRY`

## Current-price and corporate-action safety retained

V6.1.0 retains the V6.0.8 current-quote / split safeguards:

- Current/delayed display price is separated from trade-grade freshness.
- Stale prior-session intraday bars cannot become a live price.
- Split / corporate-action price scales are normalized only when evidence is trustworthy.
- Cross-timeframe data mismatches can invalidate the trade plan and block live confirmation.

## Deployment

Replace all four files together:

- `app.py`
- `quant_engine.py`
- `requirements.txt`
- `README.md`

The app and quant engine must both show **V6.1.0** / build `V610-ENTRY-TRIGGER-V3-20260917-A`.

## Important calibration note

The V6.1 gates are deliberately conservative starting rules, not a guarantee of future performance. The purpose of Entry Validation + Feedback is to measure which combinations remain predictive out of sample, separately by market, and only then justify further threshold changes.
