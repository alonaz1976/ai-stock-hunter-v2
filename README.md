# AI Stock Hunter V6.2.2 — Matched Baseline + Evidence Audit

- **No production-entry change.** V6.2.2 does not loosen Chase/Extension, Live R:R, Evidence, Carryover, Entry Trigger or Continuation rules.
- **Setup Origin now has a matched opening-time baseline.** A 09:45-style signal is compared with the unconditional outcome of entering at the same completed 15m opening slot across all eligible sessions, using the exact same target/stop/horizon. This answers whether the research signal adds lift beyond ordinary opening volatility.
- **Signal-position weighting prevents time-of-day bias.** The weighted baseline uses the observed mix of 1st/2nd/3rd/4th opening-bar origins rather than comparing against a different clock time.
- **New evidence dashboard.** Analyze exports a `Research Evidence Summary` showing matched hit-rate lift, expectancy delta, robustness breadth and continuation evidence state. All fields are descriptive and remain research-only.
- **Continuation evidence stays conservative.** Zero clean target hits in a tiny sample is reported explicitly, but the sample is not treated as statistically conclusive and cannot alter production.
- New Analyze sheet: **Setup Origin Matched Baseline** plus **Research Evidence Summary**.

# AI Stock Hunter V6.2.1 — Post-Spike Structure + Censoring Audit

- **After-hours structure fix.** VWAP/EMA structure is now judged against the last confirmed regular-session 15m close, not an after-hours quote. AH/live price still drives retention/giveback. This prevents a few cents of AH drift from flipping a strong regular-session structure into `DISTRIBUTION RISK`.
- **Persistent distribution confirmation.** A single borderline bearish-volume reading is no longer enough. High distribution risk now requires meaningful/persistent bearish confirmation when structure is broken.
- **Continuation research coherence.** The raw continuation-base detector is preserved, but a candidate is marked ineligible when post-spike distribution risk is HIGH. New audit fields preserve the raw candidate and the invalidation reason.
- **Right-censoring fixed.** A breakout touched near the close with insufficient forward bars is now `RIGHT-CENSORED`, not `NO BREAKOUT`. Target/stop touches on the breakout bar are conservatively marked `AMBIGUOUS_BREAKOUT_BAR`.
- **Longer Analyze research window.** Analyze now requests up to 60d of 15m history (scanner remains 1mo) to improve Setup Origin / Continuation research sample size without slowing the normal universe scan.
- **No production-entry loosening.** Chase/Extension, Live R:R, evidence and carryover guards remain unchanged.

## Previous V6.2.0 notes

- **No production-entry loosening.** V6.2.0 keeps the V6.1.9 entry, Chase/Extension, Live R:R and carryover guards unchanged. The new work is evidence infrastructure.
- **Setup Origin uncertainty is now explicit.** Analyze reports target hits/stops, a 95% Wilson confidence interval, fixed-payoff gross expectancy, median time-to-outcome, and a sample-state label. A 2/4 result is therefore shown as a very wide uncertainty band instead of a precise 50% claim.
- **Fixed robustness matrix, not optimization.** The exact causal Setup Origin rule is replayed under six pre-declared target/stop/horizon scenarios. The app does not select the best row and does not feed the grid back into scoring. This is designed to reveal whether an apparent edge survives nearby assumptions instead of overfitting one COIN example.
- **Peak-safe continuation trigger.** V6.1.9 could calculate a continuation breakout a few cents *below* the actual session high because the post-peak base high was slightly lower. V6.2.0 now requires the research breakout to clear `max(base high + 0.10 ATR, session peak + 0.05 ATR)`. It also labels base compression as TIGHT / MODERATE / LOOSE using the already-computed ATR range.
- **Continuation Base validation is causal.** For each historical 15m session, the engine builds the session bar-by-bar, records the first point where the existing V6.1.9 base detector could actually know a base existed, freezes that breakout trigger, and checks future breakout/outcome. The breakout bar itself is excluded from target/stop ordering to avoid intrabar look-ahead.
- **Scanner visibility improved.** Post-Spike State, distribution risk, Continuation Base status, and the research breakout trigger are now included in scanner results/Excel. They remain research-only and do not change ranking or ActionableNow.
- New Analyze sheets: **Setup Origin Robustness**, **Continuation Validation Summary**, and **Continuation Validation**.

# AI Stock Hunter V6.1.9 — Post-Spike State + Continuation Lab

- Keeps the V6.1.8 production entry/chase thresholds unchanged. This build adds research instrumentation rather than loosening the guard based on one COIN example.
- Adds **Post-Spike State**: peak move, giveback from high, percentage of the explosive move retained, structure hold, and a HEALTHY CONSOLIDATION / CONTINUATION PRESSURE / DISTRIBUTION RISK / FAILED SPIKE classification. This is informational and cannot clear an extension veto.
- Adds a **Continuation Base Lab**. An extended stock that never revisits the old retest zone can be tracked for a time-based reset: at least four completed 15m bars after the peak, bounded consolidation, volume dry-up, and price holding above VWAP/EMA20. The breakout level is exported as research only; it is not a buy signal until OOS/live Feedback validates it.
- Adds **Setup Origin Validation** worksheets to Analyze. The exact causal 15m opening-origin rule is replayed across the available 15m history and checked for +2% target before -1.5% stop over the next 16 bars. Same-bar target+stop cases are marked AMBIGUOUS and excluded from the clean hit rate.
- Purpose: answer the next two questions without overfitting: (1) is short-term cooling near the highs healthy consolidation or actual distribution, and (2) does the early 15m Setup Origin have enough forward evidence to deserve future weight?

# AI Stock Hunter V6.1.8

## V6.1.8 — Live Entry UI + Trigger Efficiency + Carryover Audit
- Makes **Live Entry / Actionability** the primary entry metric in Scanner cards and Analyze. `EntryScore` (timing) and `SetupEntryScore` remain visible as supporting diagnostics, preventing a strong setup from looking like an actionable entry when chase/R:R guards have already degraded the trade.
- Adds a research-only **Trigger Efficiency Audit**: `OriginToTriggerPct`, `TriggerLagMinutes`, `TriggerLagATR`, `MoveConsumedBeforeTriggerPct`, `MoveConsumedBeforeSetupOriginPct`, and `TriggerEfficiencyLabel`. These quantify how much of an explosive move occurred before the causal trigger became knowable. They do not change trade decisions until OOS evidence supports them.
- Adds **NextSessionCarryoverCandidate / HardCandidate** so a +7.5% to +10% session is explicitly marked to inherit extension memory into the next regular session instead of appearing fresh when the day-change clock resets.
- Cleans carryover retention reporting: retained move is capped at 100% for display, while any price above the prior close is reported separately rather than showing confusing values such as 150% retention.
- Historical Quant Threshold Evidence now includes `Observed Hit Rate %` even for low samples, while the existing `Hit Rate %` remains intentionally blank below the evidence threshold so low-N data is descriptive rather than decision-grade.
- Retains V6.1.7 Live R:R guard, RR-aware retest band, causal bar-close trigger timing, after-market awareness, evidence guard, and chase/extension veto.


## V6.1.7 — Causal trigger time + setup-origin audit
- Trigger timestamps are now **bar-close aware**: a 09:30 1H bar is recorded as confirmed at 10:30, so the audit cannot imply look-ahead execution.
- Export includes both `TriggerAnchorBarStartTime` and `TriggerAnchorTime` (confirmation time).
- Adds a **research-only Opening Setup Origin** from the first 15m bars when price structure, time-adjusted RVOL and bullish volume confirm a strong opening impulse. It is not an actionable buy signal until OOS validation supports it.
- Adds `MoveBeforeSetupOriginPct` / `SinceSetupOriginPct` to distinguish a move that happened before the first observable intraday confirmation from the move after it.
- Adds separate **Momentum State** for 15m and 1H (STRENGTHENING / STABLE / COOLING / BEARISH / mixed aggregate) instead of treating volume participation as momentum.
- Retest audit now explicitly states the confirmation conditions required before a retest can become actionable.

# AI Stock Hunter V6.1.7

## V6.1.5 — After-hours fallback + evidence guard + trigger decomposition
- Fixes an observed Analyze case where MarketPhase was AFTER-MARKET and the live 1m quote was fresh, but Yahoo 5m pre/post returned no AH rows. The app now falls back to the fresh live quote for AH price/change context while leaving AH volume strength unavailable instead of inventing it.
- Computes the regular-session entry state separately at the official close, so an after-hours print no longer rewrites the label called “RegularSessionEntryState”.
- Adds MoveBeforeTriggerPct, GapPct, VolumeTrend15m and VolumeTrend1H to the Entry Audit / Summary. This exposes cases where most of the daily move happened before the first valid trigger.
- Recalibrates Chase Risk: a hard extension veto now has a minimum risk score of 70 so HIGH risk cannot appear with a misleadingly mid-range numeric score.
- Makes volume-trend classification rely primarily on time-adjusted RVOL. Raw closing-volume acceleration can confirm, but can no longer single-handedly label the trend ACCELERATING.
- Adds an Evidence State / Guard. Tiny OOS samples are labeled UNPROVEN and do not veto; sufficiently large persistently weak OOS lift can block ActionableNow.


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


## V6.1.7 — Live R:R + Overnight Extension Memory
- Adds Live R:R to Target 1 / Target 2 using the current price and current invalidation.
- Adds an independent R:R guard so a late entry cannot pass merely because the original setup geometry was attractive.
- Retest-zone upper edge is capped to preserve at least 1.20x reward/risk to Target 1.
- Adds one-session carryover extension memory: an explosive prior day remains blocked next morning while most of the move is still retained.
- Adds Live Actionability Score, separate from Setup Entry Score and Entry Score.
- Exports CarryoverExtension, PriorSessionMovePct/ATR, CarryoverRetentionPct, LiveRR_T1/T2 and LiveActionabilityScore.
