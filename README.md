# AI Stock Hunter — V6.3.1 High Confidence Model

- **Scanner snapshots are immediate; outcomes are not.** Every completed full Scanner run writes one live snapshot per returned stock immediately. A new scan therefore increases the Feedback snapshot count at once, but the new scan cannot have a real 1D/2D/3D/5D success result until those future trading sessions actually occur. Older snapshots that have already matured can be evaluated immediately by `Refresh due outcomes`.
- **Portable persistent Feedback database.** The complete SQLite Feedback database can now be downloaded and restored from the Feedback tab. The backup includes live snapshots, evaluated outcomes, Historical Replay runs and replay events. This is the safe fallback even when the Streamlit host is replaced.
- **Optional automatic GitHub persistence.** When Streamlit secrets contain a `[feedback_persistence]` GitHub token/repository/path, V6.3.1 automatically restores the database on a fresh host and syncs it after completed Scanner runs, newly evaluated outcome windows and Historical Replay runs. The token is never shown or exported.
- **Causal Historical Replay.** Feedback can now replay 25/50/100/200/350 stocks over 6mo/1y/2y/3y. For each historical signal date the daily technical features are computed causally, the future target/invalidation path is evaluated only afterward, and the result is stored in separate replay tables.
- **Replay is deliberately separate from Live Feedback.** Old 15m/1h live confirmations cannot be reconstructed reliably for long historical periods, so replay never inflates the headline live `אחוז הצלחה`. It produces its own success %, indicator scorecard and stock scorecard.
- **Replay target/stop geometry is explicit.** Target is the selected +3%/+5%/+8%; replay invalidation is 1.2 ATR, clipped to 2%-6%. Same-daily-bar target+stop cases are `AMBIGUOUS`, not counted as clean wins/losses.
- **Replay candidate rule is research-only.** V6.3.1 replaces the score-only replay candidate with a causal DAILY V2 gate using independent families, Freshness, Already-Moved/ATR-extension and Distribution guards. The old V6.3.0 score-only rule remains visible only as an audit benchmark.
- **Feedback Excel includes replay summaries.** The normal Feedback export now includes replay run history, replay success, replay indicators and replay stock summaries in addition to the live scorecards.
- **No Production trading thresholds changed.** Entry Trigger, Chase/Extension Guard, Live R:R, Exit Pressure, Pre-Move OOS rules and live Scanner ranking remain unchanged.

## V6.3.0 durable storage setup (optional but recommended)

Portable DB backup/restore works without any extra setup. For automatic persistence across Streamlit redeploys, add this to Streamlit Secrets and use a GitHub token that can write to the selected repository:

```toml
[feedback_persistence]
github_token = "YOUR_GITHUB_TOKEN"
repo = "alonaz1976/ai-stock-hunter-v2"
branch = "main"
path = "data/feedback_v630.sqlite3.gz"
```

Do **not** put the token inside `app.py`, `README.md`, GitHub source files or an exported Excel workbook. If automatic persistence is not configured, download the Feedback DB backup after important scan/feedback sessions and restore it after a fresh deployment if needed.

# AI Stock Hunter V6.2.9 — Large Universe + Feedback Success Scorecards

- **Expanded scan universes.** Scanner now offers NASDAQ 50 / 100 / 200, Hong Kong 50 / 100, Tel Aviv 50, Core 151, combined 350, US 201 (NASDAQ 200 + ITT), combined 351 + ITT, and Custom. Production mode can deep-analyze the full selected universe so Feedback can accumulate substantially more live evidence. Optimized/Discovery keep a larger two-stage prefilter for speed.
- **Research/Optimizer scaling.** Cross-Stock Validator and Pre-Move OOS Discovery can now test up to 200 NASDAQ names, 100 Hong Kong names and the combined 350 universe. Entry Optimizer also offers ALL 351 / US 201 / Hong Kong 100.
- **Simple Feedback “אחוז הצלחה”.** Feedback now shows one clear overall success percentage: Target 1 reached before Invalidation among clean resolved outcomes at each scan's primary feedback horizon. Wins, losses, unresolved/ambiguous cases and resolution coverage are displayed next to it so the headline percentage cannot hide missing outcomes.
- **Green/red indicator scorecard.** Live gates, Pre-Move independent families and recurring Pre-Move signal combinations are compared against the Feedback baseline. `WORKED` rows are green, `FAILED` rows red, `MIXED` amber, and low-sample evidence stays neutral.
- **Green/red stock scorecard.** Every ticker that has been snapshotted appears in a simple stock summary. With at least 3 clean resolved outcomes, >=55% becomes `SUCCESS` (green), <=45% becomes `FAILURE` (red), and the middle band is `MIXED`. Smaller samples remain `LOW SAMPLE / WAITING` rather than being overinterpreted.
- **More learning capacity.** The Feedback evaluation queue now reads up to 5,000 recent snapshots, manual refresh can process 80 / 250 / 500 windows, and completed scans persist Pre-Move stage, score, families and strongest features so the system can learn which early indicators actually worked in live follow-up.
- **Colored Feedback Excel.** The Feedback workbook adds `Success Summary`, `Indicator Summary`, `Stock Summary`, and `Primary Outcomes`; worked/success rows are green and failed/failure rows red.
- **No Production threshold loosening.** Larger universes and richer Feedback analytics do not change Entry Trigger, Chase/Extension Guard, Live R:R, Exit Pressure or OOS promotion rules.

# AI Stock Hunter V6.2.8 — Pre-Move Radar + Scanner Two-Layer Integration

- **Pre-Move is now explicitly a research radar, not a trade trigger.** Research stages are renamed to `WATCH`, `BUILDING`, `PRE-MOVE CANDIDATE`, `STRONG PRE-MOVE CANDIDATE`, and `LATE / ALREADY MOVED`. The old ARMED/TRIGGERED wording is no longer used for Pre-Move research.
- **Scanner now shows two separate layers side by side:** `Research radar` from the latest completed Pre-Move OOS run and the existing `Live entry` / Production timing state. A strong Pre-Move candidate can therefore still show WAIT / INVALIDATED / EXTENDED live without contradiction.
- **New Scanner filters:** `STRONG PRE-MOVE CANDIDATE` and `PRE-MOVE CANDIDATE`. They filter the research radar only and do not imply an actionable trade.
- **Scanner table + Excel now include Pre-Move evidence:** score, empirical OOS hit rate, freshness, consumed move %, independent families, best OOS lift, strongest features, research target/horizon and run timestamp.
- **Latest Pre-Move run is attached dynamically.** Normal Streamlit reruns and tab switches keep the research layer; a small best-effort local cache is also written. The Scanner always displays the research run timestamp/age so stale evidence is visible.
- **No Production rule changed.** Entry Trigger, Live Actionability, Chase/Extension Guard, Live R:R, Exit Pressure, optimized model selection and Scanner trade ranking remain unchanged.

# AI Stock Hunter V6.2.7 — Independent Signal Families + Pre-Move Freshness Guard

- **Correlated-signal de-duplication.** Current Pre-Move candidates no longer count every MACD/volume variant as an independent vote. Active signals are mapped into independent families (Momentum, Volume, Flow, Relative Strength, Trend, Structure, Transition Breadth), then collapsed by family signature and duplicate OOS evidence signature.
- **Independent-family staging.** `TRIGGERED` now requires at least 3 independent families, at least 3 positive-OOS families, a Momentum + Volume/Flow core confirmation, best OOS lift >= 1.30x, and a freshness-adjusted score >= 72. `ARMED` also requires multi-family positive OOS confirmation.
- **Pre-Move Freshness Guard.** The larger of the latest 1D/2D move is compared with the selected future-move target. Candidates that already consumed 60%+ of the target are labeled `LATE`; 100%+ is `ALREADY MOVED`. Both are prevented from becoming ARMED/TRIGGERED.
- **Auditability.** Current Candidates now exports raw vs representative signal counts, number of correlated duplicates removed, independent/positive family counts, Momentum+Volume confirmation, current/2D move, consumed %, freshness state, raw score and freshness-adjusted Early Signal Score. New Excel sheet: **Candidate Family Audit**.
- **Explicit NASDAQ scope.** Pre-Move now offers `NASDAQ` directly (separate from broader `US`, which includes ITT/NYSE), removing the scope ambiguity from V6.2.6.
- **No Production change.** Historical OOS discovery labels, Production Entry, Chase/Extension Guard, Live R:R, carryover, Scanner ranking and trade triggers are unchanged. V6.2.7 changes the research candidate ranking/presentation only.

# AI Stock Hunter V6.2.6 — Pre-Move Runtime Hotfix

- Fixes the V6.2.5 `KeyError` that occurred when Optimizer rendered the new `pre_move` background job before that job name had been registered in the unified Lab runtime.
- Registers `pre_move` explicitly and also makes the Lab runtime future-safe by lazily creating any newly added job name instead of crashing the whole Streamlit page.
- Changes **no Pre-Move research logic, OOS thresholds, Production Entry, Chase/Extension Guard, Live R:R, carryover, ranking, or scoring rules**. This is a runtime/UI hotfix only.
- Keeps the V6.2.5 Pre-Move OOS Discovery workflow and top-of-page Excel download behavior unchanged.

# AI Stock Hunter V6.2.5 — Pre-Move OOS Discovery

- Adds a dedicated **Pre-Move OOS Discovery** lab in Optimizer to search for indicators that appear before a future +3% / +5% / +8% move over 1D / 2D / 3D / 5D.
- Uses a strict chronological **70% discovery / 30% untouched validation** split for every stock.
- Tests a fixed causal catalog of fresh EMA/MACD/VWAP transitions, RVOL, directional volume, CMF/OBV/A-D, relative strength, ROC acceleration, squeeze release, near-breakout structure and related states.
- Automatically discovers **indicator pairs** on the discovery sample; OOS metrics are then reported only on the later validation sample.
- Adds a **Current pre-move candidates** table with Early Signal Score, Early Stage (WATCH / BUILDING / ARMED / TRIGGERED), empirical OOS Pre-Move Probability, active validated signals, best OOS lift and strongest active features. These are research labels, not production entry signals.
- Adds a third top-of-page Optimizer Excel button for the Pre-Move workbook.
- Fixes the V6.2.4 per-stock matched-lift inconsistency: Stock Evidence now derives hit rate, matched baseline, lift and expectancy delta from the same leave-one-session-out pair population.
- Production Entry, Chase/Extension Guard, Live R:R, carryover and ranking rules are unchanged.

# AI Stock Hunter V6.2.4 — Cross-Stock Bootstrap + Top Excel

- **Excel download moved to the top of every main tab.** Scanner, Analyze, Optimizer and Feedback now reserve the top area for the most recent available `.xlsx` download. The old bottom download buttons were removed. Optimizer can show both the regular Optimizer workbook and the Cross-Stock Research workbook side by side.
- **Cross-Stock Research Validator.** A new research-only block in Optimizer runs the unchanged 15m Setup-Origin rule across a deterministic multi-stock universe using up to 60d of intraday history.
- **Leave-one-session-out matched baseline.** Every signal is compared with the same ticker and same completed opening-bar slot, excluding that signal session from its own baseline. This reduces self-leakage and opening-volatility bias.
- **Calendar-session cluster bootstrap.** Cross-stock confidence resamples whole trading dates, keeping same-day market co-movement together instead of pretending every stock signal is independent. It reports matched hit-rate edge, 95% bootstrap CI, p-value and expectancy-edge CI by market and ALL.
- **Continuation stays conservative.** The validator aggregates continuation clean outcomes/targets but does not promote the continuation path or change live ranking.
- **No production-entry change.** Chase/Extension, Live R:R, Evidence Guard, carryover, Entry Trigger, Optimized models and Scanner ranking are unchanged. V6.2.4 is evidence infrastructure + UI placement only.

# AI Stock Hunter V6.2.3 — Session Anchor + Matched Edge Confidence

- **Closed-market/session-rollover fix.** Analyze now anchors day-change and post-spike math to the last actual trading session rather than the new calendar date. A Friday +11% move therefore remains +11% on Saturday/overnight instead of resetting to 0%.
- **Explicit session audit.** Exports now include `AnalysisSessionDate`, `PreviousSessionDate`, and `SessionContext`, so CLOSED / PRE-MARKET / OPEN / AFTER-MARKET calculations can be audited.
- **Carryover memory is phase-aware.** PRE-MARKET correctly carries the immediately prior completed session even when no new Daily bar exists yet. CLOSED weekend/overnight reviews expose the pending carryover candidate without pretending a new session is already active.
- **Post-spike classification no longer breaks at midnight.** `PreviousOfficialClose` stays tied to the session being audited, preserving peak-move/retention/giveback semantics after the exchange date rolls.
- **Matched-edge uncertainty added.** The 1.06x Setup-Origin lift is now accompanied by an approximate hit-rate-difference confidence interval and p-value. This prevents a tiny sample from looking stronger than it is.
- **No production-entry loosening.** Chase/Extension, Live R:R, Evidence Guard, Entry Trigger, and research-only continuation rules remain unchanged.

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


## V6.3.1 — High Confidence Model

V6.3.1 upgrades Historical Replay from the V6.3.0 score-only candidate rule to a causal DAILY V2 research gate. It de-duplicates correlated indicators into independent families (Momentum, Volume, Flow, Relative Strength, Trend, Structure and Transition Breadth), adds Freshness / Already-Moved / ATR-extension and distribution guards, and preserves the old V6.3.0 candidate rule only as an audit benchmark.

A new causal Meta Probability is calculated with strict-date rolling empirical-Bayes evidence: a row on date D can use only resolved replay rows from dates strictly before D. Same-day outcomes are not used. HIGH CONFIDENCE requires the V2 gate, at least four independent families, a fresh setup, low move-consumption, no distribution, at least 50 prior matching observations and Meta Probability >= 65%. It is intentionally allowed to return zero signals rather than manufacture a 70% hit rate.

Replay output now compares All-row Baseline vs Legacy V6.3.0 vs V2 Candidate vs HIGH CONFIDENCE, reports Lift, delta in percentage points and expectancy in R. It also exports Meta-Probability calibration buckets. The Replay Indicators parsing bug is fixed, and Replay Indicators / Replay Stocks use the same green/red Excel scorecard semantics as Live Feedback.

This remains research-only. Daily Historical Replay cannot honestly reconstruct historical live 15m/1h confirmation, so no replay statistic is promoted automatically to Production Entry. Production Scanner, Entry/Chase/R:R and Live Feedback rules are unchanged in V6.3.1.
