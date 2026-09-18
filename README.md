# AI Stock Hunter V6.1.2 — OOS Optimizer + Optimized Discovery

V6.1.2 reorganizes the product around one goal: **learn a stable entry model from history, verify it out-of-sample, then use that learned model to discover live candidates across a wider universe while Feedback keeps measuring the current regime.**

## 1. Four-tab interface

The top-level interface is reduced from eight tabs to four:

1. **Scanner** — live production, optimized and broad-discovery scans.
2. **Analyze** — one-stock cockpit using the same entry/status language as Scanner.
3. **Optimizer** — OOS weight learning, Pre-Move and Hourly matched-lift research.
4. **Feedback** — live outcome tracking with recency weighting.

Legacy Backtest / Validate / Entry / Explosive / Research top-level tabs are removed. Their useful learning concepts are consolidated into Optimizer or Feedback.

## 2. Nested out-of-sample Entry Optimizer

The old optimizer could look excellent on its learning folds and then fail on the unseen final fold. V6.1.2 changes the selection process:

- candidate weights are evaluated with **rolling validation inside folds 1–3**;
- fold 2 is validated using only earlier history;
- fold 3 is validated using only earlier history;
- candidate selection is based on median/worst OOS lift, stability, sample size and MFE/MAE;
- highly correlated features receive a **correlation penalty** to reduce double-counting;
- **Fold 4 remains untouched** until the final report.

A model is marked **SHADOW ELIGIBLE** only if both the inner OOS evidence and final Fold-4 evidence pass minimum stability/sample rules. Production is never changed automatically.

## 3. Learned feature set

The optimizer can learn weights across:

- Daily Setup
- Fresh Signal / transition evidence
- Directional Volume / Flow
- No-Chase
- Entry Score
- Dynamic Quant Score
- Exit Safety
- **Institutional Flow proxy**
- RVOL
- ADX
- Volume Acceleration
- Fresh Transition Count

The intent is to let history determine the mix instead of hard-coding a preferred indicator.

## 4. Institutional Flow Score

V6.1.2 adds an OHLCV-derived **Institutional Flow Score (0–100)**. It is explicitly a proxy, not proof that a named institution is buying.

It combines causal evidence from:

- directional relative volume;
- CMF / OBV / Accumulation-Distribution;
- price acceptance around VWAP and candle close-location;
- turnover and volume acceleration;
- high-volume absorption-like behavior;
- persistence across multiple money-flow measures.

The score is exposed to Analyze/Scanner and is also available to the Optimizer as a learnable feature.

## 5. Optimized Scanner and broad Discovery

Scanner now has three modes:

### Production 151
The existing fixed reference universe: US 51 + Hong Kong 50 + Tel Aviv 50.

### Optimized 151
The same 151 stocks, but the daily prefilter and final ranking can use the latest learned shadow model.

### Discovery
A broader **299-symbol universe in this build**. The first pass is daily and optimized. Only the strongest candidates continue to expensive 1h / 15m analysis.

The current discovery set is built from the existing Broad-200 list plus Hong Kong 50 and Tel Aviv 50, with duplicates removed. This is intentionally broader than the fixed 151 while remaining practical for the current Yahoo/yfinance data path.

The learned model is stored locally as `entry_shadow_model_v612.json` after an Optimizer run. If no learned model exists, Optimized/Discovery modes are blocked rather than silently inventing weights.

## 6. Daily and hourly horizons

Optimizer controls now include:

- Daily horizon: **1D / 2D / 3D / 5D**
- Daily target: 3% / 5% / 10% / 15%
- Hourly target: 1% / 2% / 3%
- Hourly horizon: **1h / 2h / 4h**

Hourly lift is compared with a **same-clock-hour baseline**, reducing time-of-day bias.

Pre-Move research still checks what appears 1D / 2D / 3D before the selected daily target/horizon.

## 7. Feedback remains the current-regime learning layer

Feedback continues to store live entry-gate evidence and evaluate outcomes. Recency half-life can be viewed at 30 / 60 / 90 days.

Recent evidence can support or reject a shadow model, but small samples never auto-promote production weights.

Intended learning loop:

`Long history → rolling OOS selection → untouched Fold 4 → Shadow model → Optimized live scan → Feedback / recency confirmation → production review`

## 8. Safeguards retained

V6.1.2 retains:

- WAIT → WATCH → ARMED → CONFIRMED ENTRY state machine;
- TOO LATE / CHASE and INVALIDATED states;
- current-price / stale-quote protection;
- corporate-action / split normalization;
- target-before-invalidation ordering using intraday data when available;
- Exit Pressure requiring current bearish direction plus outflow for stronger exit states;
- market-separated analytics;
- MFE / MAE measurement;
- no automatic production promotion.

## Deployment

Replace all four files together:

- `app.py`
- `quant_engine.py`
- `requirements.txt`
- `README.md`

App and engine must both show **V6.1.2** / build `V612-OOS-OPTIMIZED-DISCOVERY-20260918-A`.

## Recommended first run

1. Open **Optimizer**.
2. Run `ALL 151`, history `2y`, daily horizon `2D` or `3D`, target `3%`, hourly target `3%`, hourly horizons `1h / 2h / 4h`.
3. Review inner OOS lift, worst OOS lift and final Fold-4 OOS lift.
4. If a shadow model is produced, run **Scanner → Optimized 151** and compare it with Production 151.
5. Then run **Discovery** to look for candidates outside the fixed 151.
6. Continue refreshing **Feedback** so the most recent market period can confirm or challenge the historical model.

This is research software. Historical and out-of-sample performance does not guarantee future returns.


## V6.1.2 market-status hotfix (2026-09-18)
- Scanner now shows persistent US / Hong Kong / Tel Aviv session badges at the top: OPEN, CLOSED, PRE-MARKET/PRE-OPEN, or AFTER-MARKET.
- Analyze now shows the ticker, exchange and live session phase together above the decision cockpit.
- TASE session logic is updated for the 2026 Monday-Friday week and the shortened Friday session (09:59-13:50 local; pre-open from 09:25).
- 2026 U.S. and Hong Kong exchange holiday calendars plus relevant early-close sessions are included for the market-status badges.
- Current known TASE 2026 special closures used by this build are displayed as CLOSED with a reason instead of a false clock-based OPEN.
- Market phase and model entry stage remain separate: CLOSED/AFTER-MARKET never masquerades as a live regular-session entry.
