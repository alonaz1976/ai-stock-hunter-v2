
## V6.1.4 Excel Timezone Hotfix (2026-09-19)
- Fixed Analyze crash: `Excel does not support datetimes with timezones`.
- 15m/1H exchange-local timestamps remain timezone-aware for calculations, but Excel exports now strip timezone metadata only at serialization time.
- The fix is global for multi-sheet workbooks and Scanner exports.
- Analyze no longer fails the entire run if a future Excel-only serialization problem occurs; results remain available and the export error is shown separately.
- Includes the V6.1.4 After-Market Aware + Trigger Anchor V2 + Chase/Extension Guard changes.

# AI Stock Hunter V6.1.4 — Model Registry + Hourly OOS Timing

V6.1.4 continues the V6.1.2 OOS architecture, but fixes the most important issue found in the latest optimizer/scanner review: **the Optimized Scanner must not use whichever optimizer run happened to finish last.** It now uses a persistent **Model Registry** and selects only models that passed the OOS promotion gate for the requested market / daily horizon / target.

## Four-tab interface

The product remains intentionally reduced to four top-level tabs:

1. **Scanner** — Production 151, Optimized 151 and Discovery.
2. **Analyze** — one-stock cockpit using the same live/optimized language.
3. **Optimizer** — daily OOS learning, hourly OOS timing, Pre-Move and matched-hour research.
4. **Feedback** — live forward outcomes, recency weighting and Production-vs-Optimized A/B tracking.

## 1. Model Registry — best eligible OOS model, not latest run

Every completed Optimizer run is stored in `entry_model_registry_v613.json` on the running Streamlit host. Each registry record preserves:

- optimization universe;
- history length;
- daily horizon;
- daily target;
- daily learned weights and threshold;
- Fold-4 OOS lift and sample size by market/scope;
- hourly target/horizons;
- hourly OOS timing model when available.

When Scanner is set to **Optimized 151** or **Discovery**, it filters the registry to the currently selected daily horizon/target and then selects separately for NASDAQ, NYSE, Hong Kong and Tel Aviv.

Selection rules:

- only `SHADOW ELIGIBLE` models are eligible;
- exact-market evidence is preferred to US / ALL fallback evidence;
- within the same specificity tier, the stronger final OOS model wins;
- a US-only optimizer run cannot leak its `ALL` scope into Hong Kong or Tel Aviv;
- a research-only model is never silently used because it was the most recent run.

If no eligible model exists for a market/horizon/target, the UI says **NO ELIGIBLE MODEL** instead of inventing weights.

## 2. Reuse the V6.1.2 Optimizer runs

The Optimizer tab now has an importer for prior V6.1.2 Optimizer `.xlsx` workbooks. This is important because the expensive optimizer runs already completed in V6.1.2 do not need to be repeated merely to populate the new registry.

Use:

`Optimizer -> Import prior V6.1.2 Optimizer workbooks into Model Registry`

Select the previously downloaded optimizer workbooks and import them together. Their daily OOS models are added to the registry immediately. V6.1.3 hourly OOS timing models require a new V6.1.3 optimizer run because the older workbook did not contain raw hourly OOS model weights.

## 3. Separate Hourly OOS Timing Optimizer

V6.1.2 showed that the strongest timing evidence was intraday — especially fresh EMA9/EMA20 crossover, RVOL and bullish directional volume. V6.1.3 therefore stops treating Hourly only as a descriptive lift table.

The Optimizer now learns a separate intraday timing model from features including:

- fresh EMA9/EMA20 bullish cross;
- hourly RVOL;
- bullish directional volume;
- hourly volume acceleration;
- fresh MACD bullish cross;
- VWAP reclaim;
- positive/strengthening MACD;
- intraday Institutional Flow proxy;
- hourly ADX.

Hourly selection uses nested OOS folds and compares selected signals against a **same-clock-hour baseline**, reducing open/close time-of-day bias. Fold 4 remains untouched until final evaluation.

An hourly timing model is marked `SHADOW ELIGIBLE` only when it has enough Fold-4 signals and retains meaningful lift outside the learning period.

## 4. Daily model + hourly timing model

Optimized live ranking now has two learned layers:

`Daily OOS setup model -> Hourly OOS timing model -> OPTIMIZED CONFIRMED`

The daily model answers whether the stock fits the historically learned setup. The hourly model answers whether the current intraday timing resembles the historically stronger timing states.

The Scanner exposes:

- `OptimizedScore`
- `OptimizedMatchPct`
- `OptimizedModelID`
- `OptimizedModelScope`
- `OptimizedModelOOSLift`
- `HourlyOptimizedScore`
- `HourlyOptimizedMatchPct`
- `HourlyOptimizedHorizon`
- `OptimizedStage`

`OPTIMIZED CONFIRMED` requires the learned daily threshold plus learned hourly confirmation when an eligible hourly model exists. If no hourly OOS model exists yet, the existing causal Hourly Entry gate remains the fallback.

## 5. No-Chase is no longer a hard Optimized veto

The latest OOS work showed that the old global No-Chase gate could erase useful edge, especially outside Hong Kong. V6.1.3 therefore stops using the old `NoChaseCheck` as a mandatory boolean veto for the Optimized model.

It remains visible as risk evidence and remains part of the learnable daily feature set, but Optimized confirmation is driven by the learned model, hourly timing, market regime and Exit Pressure rather than a single global No-Chase switch.

The Production Entry Trigger remains unchanged for continuity and comparison.

## 6. Feedback becomes a Production-vs-Optimized A/B test

New V6.1.3 snapshots persist both sides of the decision:

- Production entry state;
- Optimized stage;
- Optimized score/match;
- registry model ID/scope/OOS lift;
- optimized hourly match/horizon;
- scan mode;
- model disagreement category.

Disagreement categories are:

- `BOTH CONFIRMED`
- `OPTIMIZED ONLY`
- `PRODUCTION ONLY`
- `NEITHER`

Once 1D/2D/3D/5D outcomes mature, Feedback reports clean win rate, MFE and MAE for these groups. This creates a live forward A/B test for the exact cases where the old and new systems disagree.

The Feedback export includes a **Production vs Optimized** worksheet in addition to snapshots, outcomes, recent weighted summaries and feature lift.

## 7. Feedback remains trading-session aware

The V6.1.2 hotfixes remain included:

- 1D / 2D / 3D / 5D mean actual trading sessions, not calendar days;
- weekends and exchange holidays do not advance the outcome window;
- evaluation waits for completed provider daily bars;
- Target-vs-Invalidation event order is resolved with 15m first, then 1h when possible;
- unresolved same-bar cases stay ambiguous and are excluded from clean win/loss conclusions;
- Feedback Excel export is available even before the first outcome matures.

## 8. Institutional Flow

Institutional Flow remains an OHLCV-derived proxy, not proof that a named institution is buying. It remains available to both the daily and hourly learning layers.

## 9. Scanner modes

### Production 151
The fixed reference universe and existing Production logic.

### Optimized 151
The same 151-stock universe, ranked only with eligible registry models matching the selected horizon/target.

### Discovery
The broader 299-symbol universe in this build. Stage 1 is a lightweight daily optimized prefilter. Only top candidates with an eligible model proceed to the expensive 1h/15m analysis.

Markets with no eligible model are not allowed to consume optimized deep-analysis slots merely because Production score is high.

## 10. Deployment

Upload these four files together:

- `app.py`
- `quant_engine.py`
- `requirements.txt`
- `README.md`

App and engine must both show **V6.1.4** / build `V614-AH-AWARE-TRIGGER-AUDIT-20260919-B`.

### Recommended first use after upgrade

1. Open **Optimizer**.
2. Import the V6.1.2 optimizer workbooks already downloaded. This restores the useful daily OOS evidence into the V6.1.4 registry without rerunning it.
3. Check Scanner with the daily horizon/target you want. The registry selection table shows exactly which eligible model is being used by each market.
4. Run a fresh V6.1.4 Optimizer when convenient to learn the new Hourly OOS timing model.
5. Run Production and Optimized/Discovery scans so Feedback can start accumulating `OPTIMIZED ONLY` vs `PRODUCTION ONLY` forward outcomes.

No model is automatically promoted into the Production strategy. The registry governs the Optimized/Discovery research path; Production remains the stable reference until enough OOS + live Feedback evidence supports a deliberate promotion.


## V6.1.3 Chase / Extension Guard hotfix (2026-09-18)

This build adds an independent late-entry guard. The six classic Entry Gates remain visible, but a stock can now show 6/6 and still be blocked as **EXTENDED — DO NOT CHASE** when the move has already run too far. The guard evaluates current-session percentage move, gap, distance from VWAP/EMA9/EMA20 normalized by ATR, percentage move since the original fresh transition, progress already consumed toward Target 1, and whether intraday volume is accelerating or fading.

The Entry Zone is no longer regenerated around a late current price. When a fresh EMA/MACD/VWAP transition exists in the active lookback, the trade plan is anchored to the earliest still-fresh transition and exposes the original trigger price/timeframe plus `SinceTriggerPct`. A high extension score hard-blocks both the production `CONFIRMED ENTRY` state and the optimized confirmation layer, returning **WAIT FOR RETEST** instead.


## V6.1.4 Trigger Anchor V2 + Evidence Audit (2026-09-18)

This build fixes the main audit issue found in the COIN Analyze export. A same-day daily transition timestamped at midnight could win the original-trigger selection even when 15m/1H data contained an earlier executable intraday transition. Trigger Anchor V2 now scans the full current intraday session (40×15m / 12×1H), detects a bearish reset that starts a new setup episode, prefers the earliest transition after that reset, and uses daily data only as a low-quality fallback. The UI/export now expose anchor quality, age, and selection rationale.

The Chase / Extension Guard is now volatility-aware. It adds session move in ATR units and the stock's own recent positive-day percentile, while preserving the hard protection against already-completed large moves. It also creates an auditable retest band, pullback-needed percentage, and retest status instead of only saying WAIT FOR RETEST.

Analyze now separates **Setup Entry Score (pre-chase)** from **Live Entry Timing (after chase penalty)**, exports an **Entry Audit** sheet plus recent **Hourly Features** and **15m Features**, and fixes an evidence-order bug: the Analyze decision layer previously used neutral `SignalLift=1.0` before the Static-vs-Dynamic holdout was calculated. V6.1.4 computes the holdout first and feeds the actual Dynamic signal lift into Reliability / Opportunity. Tiny samples remain explicitly LOW evidence and are not allowed to masquerade as statistically strong proof.


## V6.1.4 After-Market Awareness hotfix (2026-09-19)

Analyze and Scanner now treat U.S. after-hours as a separate session context. Regular-session 15m/1H technicals remain frozen after 16:00 ET; the after-hours print is used only for current-price, extension/chase risk, and confirmation context. The system exports regular-session move, AH move, total move vs prior close, AH volume strength, quote timestamp/freshness, and a Session Entry State. After-hours confirmation no longer makes `ActionableNow=True`; a setup must be reconfirmed during the next regular session. EXTENDED / DO NOT CHASE remains a hard override and carries forward into the AH review.
