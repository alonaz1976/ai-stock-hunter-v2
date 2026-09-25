# AI Stock Hunter — V6.3.9.35 Timing / No-Chase Consistency Fix

## V6.3.9.35 — explicit No-Chase reasons + freshness-first Emerging rank
- Added `RawNoChaseCheck`, `NoChaseCheck`, `NoChaseConsistencyOverride`, and `NoChaseReason` so every No-Chase failure is auditable instead of appearing as an unexplained boolean.
- Removed the old binary-cliff contradiction around the legacy distance thresholds. A legacy distance-only failure can receive a narrow consistency override only when the independent extension engine is **LOW**, has no veto, and move-consumed timing is below 70% (or unavailable). RSI > 76 and 3-day momentum > 16% remain hard No-Chase failures.
- `TimingQualification` now explicitly reports **NO-CHASE BLOCK** when No-Chase remains false, so it cannot simultaneously say `FRESH / QUALIFIED` while TradeStage is blocked for chase.
- Emerging E# is now freshness-first: **FRESH + ARMED/CONFIRMED → FRESH WAIT/WATCH → AGING → RETEST**, with Emerging Score used only as the tie-breaker inside the freshness tier.
- Added `EmergingFreshnessTier` for audit. No Decision-score weights, Q/E numeric thresholds, Evidence rules, 80% timing hard gate, trade-plan geometry, or valuation rules were changed.
- Decision diagnostics: `V3.8`; Trade Priority: `V3.8-FRESHNESS-FIRST-NOCHASE-CONSISTENCY`.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.35**.

---

# AI Stock Hunter — V6.3.9.34 Feedback Integrity + Rank Unification

## V6.3.9.34 — independent events, movement/trade split, one current rank
- Added deterministic `EventID` de-duplication. The first snapshot of an event is `ORIGIN`; later scans are `TRACKING` and do not inflate statistical N.
- `SetupOriginTime` is used when available to preserve a setup across sessions; otherwise the exchange session date is the conservative event boundary. `TriggerAnchorTime` remains audit-only so a small timing refresh cannot manufacture a new event.
- Legacy snapshots are de-duplicated non-destructively at read time, so historical same-session repeat scans stop inflating Feedback without deleting the DB.
- Added trade-plan geometry audit. Invalid long plans (`Target1 <= snapshot price`, `Invalidation >= snapshot price`, reversed entry/target geometry) remain visible but are excluded from Trade Outcome learning.
- Split outcome truth into **Movement Outcome** (`MFE +3% / +5%`) and **Trade Outcome** (`Target1 before Invalidation`).
- Feedback now reports Raw Snapshots, Independent Events, Tracking Snapshots, invalid-plan exclusions, and Trade-learning eligible events. Excel export adds `Feedback Integrity` and `Movement Outcomes`.
- User-facing `GlobalRank` is unified with current-first `TradePriorityRank`. Raw Decision-score order is retained separately as `DecisionScoreRank (research)`.
- Market and Sector rank now follow the same current-first priority order, preventing safety-blocked names from looking top-ranked locally.
- Decision diagnostics: `V3.7`; Trade Priority: `V3.7-CURRENT-FIRST-UNIFIED`. No Decision score weights or Q/E thresholds were changed.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.34**.

---

# AI Stock Hunter — V6.3.9.33 Ranking Semantics Fix

## V6.3.9.33 — EV stays historical; current Trade Priority stays current
- **Q# = Qualified NOW:** current setup passed the live qualification gates.
- **E# = Emerging NOW:** strong current technical setup with low-sample/unproven historical Evidence; research only.
- **EV# = Historical Evidence Rank:** ranks OOS/Feedback Evidence only. EV# no longer receives a special promotion in the live `TradePriorityRank`.
- **Current-first Trade Priority:** Q names come first, then E names, then safe CURRENT WATCH / RESEARCH names by Decision Score, while `INVALIDATED`, `TOO LATE / RETEST ONLY`, stale/data-blocked, no-chase/extension-blocked and `EVIDENCE VALIDATED / BLOCKED` names are pushed to **BLOCKED / HISTORICAL ONLY**.
- Added audit fields: `TradePriorityClass`, `TradePriorityCurrentEligible`, `TradePriorityBucket`, `TradePriorityVersion`.
- The Decision Score formula/weights, EvidenceRank calculation, Q/E eligibility thresholds, Entry gates, Timing hard gate, valuation, HK freshness and trade-plan geometry are unchanged.
- Ranking engine label is **V3.6** to identify the new priority semantics; the underlying score weights remain the prior de-duplicated model.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.33**.

---

# AI Stock Hunter — V6.3.9.32 Decision Wording Consistency Fix

## V6.3.9.32 — clean blocked wording + explicit timing label
- **Duplicate wording removed:** non-armed blocked rows now show **NOT QUALIFIED FOR ENTRY** only once; armed-but-blocked rows show **SETUP ARMED — NOT QUALIFIED FOR ENTRY**.
- **EntryTimingScore is named correctly:** current-opportunity failure reasons now say **Timing X.X<55** instead of **Entry X.X<55**, avoiding confusion with the separate visible `EntryScore`.
- No thresholds, ranking weights, Evidence rules, Timing gates, valuation logic, market freshness logic, or trade-plan geometry were changed.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.32**.

---

# AI Stock Hunter — V6.3.9.31 Decision Consistency + HK Freshness Fallback

## V6.3.9.31 — action/lane consistency and Hong Kong completed-session repair
- **Decision/Action Consistency Guard:** the Entry engine's original text is retained as `RawRecommendedAction`, while visible `RecommendedAction` is synchronized after Decision Intelligence. A row can no longer show a positive `ARMED / CONFIRMED` recommendation when `CurrentOpportunityQualified=False` or `DecisionLane=RESEARCH / BLOCKED`.
- **Clear blocked wording:** an armed setup that fails Setup / Entry / Decision Rank qualification is shown as **SETUP ARMED — NOT QUALIFIED FOR ENTRY** with the missing conditions. Emerging low-sample cases are labelled **RESEARCH ONLY / LOW-SAMPLE EVIDENCE**. Timing/data/invalidated guards take precedence.
- **Hong Kong Daily freshness fallback:** when HK Daily data is exactly one completed session stale, the app now tries confirmed intraday reconstruction before declaring `STALE_SESSION`. It tries lightweight Yahoo **1H**, then **15m**, plus an alternate `Ticker.history` route when `yf.download` lags.
- **Close-coverage validation:** reconstruction checks the **end of the final confirmed bar** against the official close, so a confirmed 15:00–16:00 HK 1H bar can safely represent the 16:00 session close. Larger gaps or incomplete intraday data remain blocked.
- Reconstruction remains temporary analysis data only; provider history is never overwritten.
- Scanner export adds `RawRecommendedAction` and `RecommendedActionReason` for audit.
- `app.py` / package build updated to **V6.3.9.31**.

---

# AI Stock Hunter — V6.3.9.30 Consistency & Safety Fix

## V6.3.9.30 — timing, evidence, valuation, split/data and session consistency
- **Move-consumed hard timing gate:** when `MoveConsumedBeforeTriggerPct >= 80%`, the Entry engine can no longer return `ARMED` or `CONFIRMED ENTRY`. 80–99.9% becomes **RETEST ONLY / LATE**; 100%+ becomes **TOO LATE / CHASE**. The recommendation explicitly says not to chase and shows a retest zone when one exists.
- **Evidence warning vs veto:** low sample, missing lift and low Reliability are now warnings rather than automatic live-entry vetoes. A hard Evidence veto is reserved for **12+ OOS signals with lift below 0.90x**. `EvidenceTradeGrade` remains stricter, so low-sample setups are not mislabeled as validated.
- **Valuation price-scale guard:** if Scanner price and fundamentals `InfoPrice` differ by more than **35%**, peer valuation is suppressed with **PRICE/FUNDAMENTALS MISMATCH** rather than producing a false discount/premium. The mismatch and percentage are exported for audit.
- **Fair Value geometry fixed:** every valid valuation now guarantees `FairValueLow <= FairValueMid <= FairValueHigh`.
- **Better valuation peers:** comparables now prefer **Market + Industry**, then **Market + Fundamental Sector**, then app sector, before broadening to Market / Scan Universe.
- **Open-session freshness fixed:** during an **OPEN** market, `ExpectedSessionDate` is the current exchange session date. A Daily series that is still on the prior session is now marked stale instead of appearing current. Completed-session reconstruction remains conservative and separate.
- Scanner/Analyze exports include the hard timing audit flag `TimingConsumedHardBlock`.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.30**.

---

# AI Stock Hunter — V6.3.9.29 Visible Intraday RVOL

## V6.3.9.29 — cumulative time-of-day RVOL on Scanner + Analyze cards
- Added a visible **Intraday RVOL** tile to both **Scanner** and **Analyze** decision cards.
- While the regular market is **OPEN**, the tile shows **cumulative session volume up to the current time divided by the median cumulative volume at the same intraday point across up to 20 prior sessions**. Example: `1.55× • HIGH • LIVE • TIME-ADJUSTED`.
- After the regular session closes, the same tile switches to **final full-session RVOL versus the prior 20-session average full-day volume** and is labelled `FINAL • CLOSED`.
- RVOL bands are direction-neutral: **LOW <0.75×**, **NORMAL 0.75–1.24×**, **HIGH 1.25–1.99×**, **VERY HIGH ≥2.00×**. High RVOL alone is not treated as bullish; direction still comes from Inflow/Outflow/Money Flow.
- Added `IntradayCumulativeRVOL` and `FullSessionRVOL` to scan/analyze data and exports. Existing model-facing `time_adjusted_rvol` is unchanged, so this display upgrade does **not** alter Ranking V3.5, Entry, Evidence, Emerging eligibility, Inflow/Outflow ranking logic or trade-plan logic.
- Per the user's preference for **Level 2 only**, the V6.3.9.27 **L1 Order Book tile is removed/disabled**. No order-book score is shown until a genuine Level-2 feed is connected.
- V6.3.9.28 immediate 1D/2D/3D/5D Feedback tables remain unchanged.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.29**.

---

# AI Stock Hunter — V6.3.9.28 Immediate 1D/2D/3D/5D Feedback Tables

## V6.3.9.28 — see per-stock results as soon as each horizon matures
- Feedback now includes a visible **Outcome results by horizon** table with selectable **1D / 2D / 3D / 5D** views.
- A stock appears in the **1D table immediately after its 1D outcome is evaluated**; users no longer have to wait for a 3D primary horizon just to inspect what happened after day 1.
- Each row shows, when available: snapshot/evaluation time, app version, ticker, market, configured primary horizon, Trade/Entry state, Decision/Entry scores, Consumed, Chase, Inflow, Outflow, Net Flow, End Return, MFE, MAE, clean Result and First Event.
- **Official Model Success remains unchanged:** it still uses each scan's configured primary horizon. The new 1D/2D tables are early forward-audit views, not substitutes for the 3D/5D official KPI.
- Feedback Excel now exports separate sheets: **Outcome Results 1D, 2D, 3D and 5D** in addition to Outcome Progress by Horizon.
- V6.3.9.27 Order Book Pressure, V6.3.9.25 Emerging Entry Guard, TASE reconstruction, Ranking V3.5, Evidence, Inflow/Outflow, Consumed/Chase and trade-plan logic are unchanged.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.28**.

---

# AI Stock Hunter — V6.3.9.27 Live Order Book Pressure (L1)

## V6.3.9.27 — Order Book Pressure in Scanner + Analyze
- Added **Order Book Pressure** to the visible decision card in both **Scanner** and **Analyze**.
- The live card shows **BULLISH / NEUTRAL / BEARISH** plus a signed top-of-book imbalance such as `Buy +38%` or `Sell 27%` when bid/ask sizes are available.
- Data is explicitly **L1 / top-of-book only**, not full Level-2 depth. If the provider does not expose reliable bid/ask sizes, the app shows **NO DATA** instead of manufacturing a signal from price/volume indicators.
- Order-book data is used only during an **OPEN** regular session and is labelled `CONFIRM / NEUTRAL / CAUTION` as a live-timing layer. Closed sessions show N/A.
- **No MACD, RSI, RVOL, Inflow/Outflow, Opportunity, Decision Rank V3.5, Top Score, Evidence, Emerging eligibility, Consumed/Chase, or trade-plan score is changed by Order Book Pressure.**
- The detailed view exposes best bid/ask, bid/ask sizes, spread, provider/source and timestamp so the signal is auditable.
- V6.3.9.26 Feedback horizon progress and all V6.3.9.25/V6.3.9.24 guards remain unchanged.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.27**.

---

# AI Stock Hunter — V6.3.9.26 Feedback Horizon Progress + Official KPI Clarity

## V6.3.9.26 — early outcomes are visible without contaminating the official score
- **Feedback now shows 1D / 2D / 3D / 5D outcome progress separately**: resolved cases, wins/losses and clean win rate are visible as soon as each horizon matures.
- **Official Model Success remains primary-horizon only.** A 1D result never substitutes for a Scanner run configured for 3D, 5D, etc.
- When the official KPI is still blank, the UI now explains exactly why: no V6.3.9.26 Scanner snapshots yet, or primary-horizon outcomes have not matured yet.
- The former ambiguous `0 wins / 0 losses` state is replaced by an explicit distinction between **Early Outcome Progress** and **Official Primary-Horizon Success**.
- Feedback Excel adds an **Outcome Progress by Horizon** sheet, while Model Version Improvement / Market Improvement / Shadow A/B remain unchanged.
- Historical Replay stays research-only and remains excluded from live success percentages.
- V6.3.9.25 Emerging Entry Guard, V6.3.9.24 TASE session reconstruction, Ranking V3.5, Evidence rules, Inflow/Outflow/Net Flow, Consumed/Chase, Entry gates and trade-plan geometry are unchanged.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.26**.

---

# AI Stock Hunter — V6.3.9.25 Emerging Entry-Guard Hotfix

## V6.3.9.25 — E# can no longer contradict the live Entry engine
- **Emerging hard guard:** a stock cannot receive `EmergingSetupEligible=True` / an **E# rank** when the live Entry state is `TOO LATE / CHASE`, `EXTENDED — DO NOT CHASE`, or `INVALIDATED`.
- **NoChaseCheck is now explicit:** `NoChaseCheck=False` blocks Emerging promotion even when the raw technical Emerging Score is above 55.
- The blocked stock remains visible in **ALL / RESEARCH** with its raw `EmergingSetupScore` and a clear `EmergingSetupReason`, so strong-but-late setups are still auditable.
- This fixes the contradiction seen in **AKAM**: a strong raw Emerging Score can remain visible, but it cannot become E#1 when Entry already says it is too late to chase.
- **No Ranking V3.5 weights, Emerging Score formula, Evidence thresholds, Inflow/Outflow formulas, Consumed/Chase calculation, TASE reconstruction, Feedback, Optimizer, or trade-plan geometry changed.**
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.25**.

---

# AI Stock Hunter — V6.3.9.24 TASE Session Repair + Simplified Optimizer/Feedback

## V6.3.9.24 — completed-session reconstruction + model-improvement dashboard
- **TASE stale-session repair:** when the Daily provider is exactly one completed Tel Aviv session behind, the app now checks confirmed 15m bars for the missing session and reconstructs a temporary OHLCV Daily row only if intraday coverage reaches the regular close. Larger gaps or incomplete intraday data remain **STALE** and blocked.
- Reconstruction is used in **Scanner, Analyze, and Top-card price freshness** and is exposed as `SessionReconstructed` / `SessionReconstructionSource` in exports. It does not overwrite provider history.
- **Optimizer simplified:** the main screen now answers whether an OOS candidate is eligible; daily/hourly OOS results stay visible, while weights, registry diagnostics, Cross-Stock Validator and Pre-Move Discovery move behind compact Details / Advanced Research sections.
- **Feedback simplified:** the top of the tab now answers one question — *is the live model getting better?* Historical Replay, Regular Signature and Explosive research remain available under **Advanced Research Labs** and do not inflate live success.
- Feedback now stores **app version** and **target %** with every new Scanner snapshot so future releases can be compared cleanly. Existing records are preserved as `LEGACY ≤6.3.9.23` unless their exact version is re-imported from a Scanner workbook.
- Added a **forward model-improvement audit**: current-version clean win rate, matched prior market/horizon baseline, percentage-point improvement, performance by version, and a same-period **Production vs Optimized shadow A/B** table.
- A strong improvement label requires at least **30 clean resolved current-version outcomes** plus statistical separation; 12–29 is explicitly **EARLY EVIDENCE**. Historical Replay alone never promotes a model.
- Feedback Excel now includes **Model Version Improvement**, **Improvement by Market**, and **Production vs Optimized Shadow** sheets.
- **No Ranking V3.5 weights, Evidence thresholds, Entry gates, Emerging ordering, Inflow/Outflow formulas, Consumed/Chase logic, or trade-plan geometry changed.**
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.24**.

---

# AI Stock Hunter — V6.3.9.23 Analyze Card NameError Hotfix

## V6.3.9.23 — shared card rendering helper
- Fixes the **NameError in Analyze → Decision cockpit** introduced when Analyze adopted the Scanner card layout in V6.3.9.22.
- The HTML-escape helper used by card rendering is now shared at module scope instead of existing only inside the Scanner renderer.
- Scanner and Analyze keep the same V6.3.9.22 visual layout and the same Inflow / Outflow / Net Flow fields.
- **No Ranking V3.5 weights, Evidence rules, Entry gates, Emerging ordering, Flow formulas, Consumed/Chase logic, or trade-plan geometry changed.**
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.23**.

---

# AI Stock Hunter — V6.3.9.22 Flow Balance + Unified Analyze UI

## V6.3.9.22 — independent Inflow / Outflow / Net Flow + Scanner-style Analyze
- Adds **Inflow Pressure 0–100**, **Outflow Pressure 0–100**, and **Net Flow Balance**. Inflow and Outflow are deliberately independent, so both can be high during a strong buyer/seller battle.
- Outflow now combines bearish-volume evidence, Exit Pressure, institutional-flow deterioration, direction-aware RVOL and current price/VWAP weakness.
- Inflow combines bullish-volume evidence, institutional-flow strength, direction-aware RVOL/acceleration and current price/VWAP strength. High RVOL by itself is neutral.
- Net Flow is `Inflow − Outflow` and labels BUYERS DOMINANT / BUYERS LEAD / MIXED / SELLERS LEAD / SELLERS DOMINANT.
- Scanner cards now show **Inflow, Outflow, Net Flow, Consumed and Chase** together.
- Consumed and Chase remain separate diagnostics, but Ranking V3.5 still uses one combined risk family (`max(Late, Chase, Exit)`), preventing double penalty.
- **Analyze** now opens with the same compact visual card as Scanner: Setup, Entry, Hourly, Inflow, Outflow, Net Flow, Consumed, Chase, R:R and Evidence. Secondary diagnostics move under **Details / Why?**.
- Scanner/Analyze Excel exports include the new flow fields.
- **No Ranking V3.5 weights, Evidence thresholds, Entry gates, Emerging ordering or trade-plan geometry changed.**
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.22**.

---

# AI Stock Hunter — V6.3.9.21 Consumed + Outflow Card

## V6.3.9.21 — cleaner timing + visible outflow pressure
- Scanner decision cards now keep **Consumed** visible as a compact percent plus EARLY / MID / LATE timing label.
- Added **Outflow Pressure 0–100** directly to the card status line. The score uses the existing bearish directional-volume/distribution evidence, with Exit Pressure only as a fallback when directional-volume evidence is unavailable.
- Outflow bands are **LOW <20, LIGHT 20–39, MODERATE 40–59, HIGH 60–79, VERY HIGH 80–100**.
- Outflow is a **pressure score, not a currency amount and not a claim about identifiable institutional cash flows**.
- Money Flow remains the positive/overall flow view; Outflow makes the bearish selling/distribution side explicit at a glance.
- Added `OutflowPressure` and `OutflowLabel` to Scanner / Decision Intelligence exports for audit.
- No Ranking, Emerging order, Evidence thresholds, Entry gates, Money Flow weights, Chase logic, or trade-plan geometry changed.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.21**.

---

# AI Stock Hunter — V6.3.9.20 Card Details + Market Rank Hotfix

## V6.3.9.20 — NameError fix + local E#/Q#/EV# ordering
- Fixed the Scanner **NameError** introduced by the clean V6.3.9.19 card: `MoveBeforeTriggerPct` and `SinceTriggerPct` are now initialized in the card scope before `Details / Why?` renders.
- Fixed cached-rank migration to recognize **Decision Score V3.5** instead of incorrectly checking for V3.4.
- When **Display market** is US / HONG KONG / TEL AVIV, lane ranks are now recomputed inside the selected market. Emerging therefore displays **E#1, E#2, E#3...** in that market instead of jumping from a global E#1 to E#15/E#19.
- Original cross-market lane ranks are preserved as `GlobalQualifiedRank`, `GlobalEmergingRank`, and `GlobalEvidenceRank` for audit.
- **Emerging order remains driven only by Emerging Score.** Evidence still controls validation/promotion and does not reorder the Emerging lane.
- No scoring weights, Entry gates, Evidence thresholds, Money Flow logic, or target/stop geometry changed.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.20**.

---

# AI Stock Hunter — V6.3.9.19 Clean Decision Cards

## V6.3.9.19 — clean mobile UI + uncapped scores + Emerging-first order
- **Emerging cards are now ranked and displayed by Emerging Score.** E#1 is the strongest live Emerging setup, E#2 the next, etc. Evidence does not reorder the Emerging lane.
- **Removed the artificial Rank=50 presentation.** Decision Score is now the real uncapped score. Evidence is counted once as the existing 15% family and then acts as a validation gate; it no longer applies an extra penalty or hard score cap.
- **Evidence still blocks promotion:** low-sample setups cannot become CONFIRMED / ACTIONABLE / VALIDATED until the Evidence guard is trade-grade.
- **Lane-aware headline:** Emerging cards show `EMERGING xx/100`; validated opportunities show `VALIDATED xx/100`; evidence-only names show an Evidence headline.
- **Cleaner Top-5 cards:** removed `Ranking V3.x • de-duplicated`, Global Rank, legacy Previous-session WATCH duplication, Movement text, and long guard paragraphs from the main card.
- Main card now focuses on **Setup, Entry, Hourly, Money Flow, Move Consumed, Chase, R:R, and Evidence N/12**.
- Evidence warning is compact: `UNVALIDATED • Evidence N/12`; model internals, Global Rank, Raw/Decision score audit, legacy TOP/Opportunity, valuation, catalyst, and detailed reasons remain under **Details / Why?**.
- The numeric model is labeled **Decision Score V3.5**. Guards determine eligibility/lane separately instead of altering the displayed score.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.19**.

---

# AI Stock Hunter — V6.3.9.18 Validated Opportunity Guard

## V6.3.9.18 — Evidence validated is not the same as a current opportunity
- **Fixes the GTLB/Q#1 problem:** trade-grade historical Evidence alone no longer creates a `VALIDATED OPPORTUNITY`. A stock can be historically validated while the current Setup/Entry state is still weak or `WAIT`.
- **Two separate validations:** `EvidenceValidated=True` means the historical/OOS evidence passed the V6.3.9.16 sample/Lift/Reliability guard. `ValidatedOpportunityEligible=True` means that Evidence is validated **and** the current setup is strong enough now.
- **Current Opportunity Guard:** Q-rank requires **Setup >=55 + Entry >=55 + Ranking V3.4 >=55 + current stage WATCH/ARMED/CONFIRMED**, in addition to the existing Evidence, timing, freshness, extension, exit and invalidation guards.
- **New decision lane:** Evidence-qualified names that are not currently strong are labelled `EVIDENCE VALIDATED / WAIT`; if timing/data/risk blocks them they are `EVIDENCE VALIDATED / BLOCKED`. They do not receive a Q-rank.
- **Evidence Rank:** a separate `EvidenceRank`/`EV#` preserves visibility of historically validated names without pretending they are current opportunities.
- **Decision priority:** `ALL` now orders **Validated Opportunities -> Emerging Setups -> Evidence Validated WAIT/BLOCKED -> Research/Blocked**. This prevents a weak current setup from sitting visually above a stronger live setup solely because its Evidence sample is larger.
- **Show menu:** `ALL | VALIDATED OPPORTUNITIES | EMERGING SETUPS | EVIDENCE VALIDATED | ACTIONABLE NOW | WATCHLIST | RESEARCH`.
- **Ranking V3.4 weights unchanged:** Setup 35% + Entry Timing 25% + Money Flow 15% + Evidence 15% + R:R 10%. The change is qualification semantics, not another weight or indicator.
- **Audit/export fields added:** `ValidatedOpportunityEligible`, `EvidenceValidated`, `CurrentOpportunityQualified`, `CurrentOpportunityQualification`, `ValidatedOpportunityReason`, and `EvidenceRank`.
- `DecisionRankEligible` is retained for backward compatibility and now means **validated current opportunity**, not merely trade-grade Evidence.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.18**.

### Expected effect on the V6.3.9.17 sample
Using the previous 350-stock scan, GTLB remains `Evidence Validated` (N=12, Lift=1.08x, Evidence=58.5) but moves out of Q-rank because Setup 28.3, Entry 36.7, Ranking 42.2 and TradeStage WAIT do not pass the Current Opportunity Guard. On that snapshot there are **0 Validated Opportunities, 24 Emerging Setups, and 3 Evidence Validated names**. A future Evidence-qualified stock with a strong ARMED/CONFIRMED current setup can receive Q#1 normally.

---

# AI Stock Hunter — V6.3.9.17 Qualified Ranking + Emerging Setups

## V6.3.9.17 — separate validated picks from strong-but-unproven setups
- **Two decision lanes:** Scanner now separates `VALIDATED PICKS` from `EMERGING SETUPS` instead of mixing both inside one Top-5 order.
- **Validated Picks:** only rows with `DecisionRankEligible=True` enter this lane. They receive a dedicated **Qualified Rank** sorted by Ranking V3.3.
- **Emerging Setups:** technically strong setups with low-sample Evidence (`N < 12`) may enter a separate research-only lane when timing, freshness, extension and exit guards are clean. They receive an **Emerging Rank** and an **Emerging Setup Score**.
- **No weakening of Evidence Guard:** Emerging setups can never become `CONFIRMED ENTRY`, `ACTIONABLE NOW` or Validated Picks until Evidence becomes trade-grade.
- **Global Rank preserved:** `Global Rank` remains the raw all-stock Ranking V3.3 order for audit. A stock can therefore be Global #15 but Qualified #1.
- **Decision Priority:** Top cards in `ALL` prioritize Validated Picks first, then Emerging Setups, then research/blocked rows. This prevents unproven names from visually sitting above the best qualified setup.
- **Top-card labels:** cards now show `Q#` for Qualified Rank, `E#` for Emerging Rank, plus the original Global Rank.
- **Cleaner Show menu:** `ALL | VALIDATED PICKS | EMERGING SETUPS | ACTIONABLE NOW | WATCHLIST | RESEARCH`. The legacy strict `TOP OPPORTUNITIES` filter remains internally supported for backward compatibility but is no longer the primary view.
- **Ranking V3.3 formula unchanged:** Setup 35% + Entry Timing 25% + Money Flow 15% + Evidence 15% + R:R 10%, with the same single risk family and qualification guards. The new lane logic changes presentation/priority, not the underlying positive weights.
- **New audit/export fields:** `QualifiedRank`, `EmergingRank`, `DecisionLane`, `EmergingSetupEligible`, `EmergingSetupScore`, `EmergingSetupReason`.
- Fixed cached-scan migration to require the exact current `DecisionRankVersion` instead of repeatedly reprocessing a valid V3.x snapshot on every UI refresh.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.17**.

---

# AI Stock Hunter — V6.3.9.16 Evidence Sample Guard

## V6.3.9.16 — evidence qualification now checks N + Lift + Reliability together
- **Evidence Guard V2:** a Reliability score by itself can no longer make a setup `QUALIFIED`. Trade-grade evidence now requires a sufficiently large out-of-sample sample plus acceptable Lift and Reliability.
- **Sample thresholds:** fewer than 8 OOS signals = `UNPROVEN`; 8–11 = `PROVISIONAL — LOW SAMPLE`; 12+ is the minimum sample size for trade-grade qualification.
- **Lift guard:** with 12+ signals, Lift below `0.75x` is `WEAK — GUARD`; Lift below `0.90x` is `WEAK LIFT`. Both block trade-grade confirmation.
- **Reliability floor:** with an adequate sample and Lift, Reliability must still be at least `30/100`. Stronger states are labelled `SUPPORTIVE` or `STRONG` when sample, Lift and Reliability are materially better.
- **CONFIRMED ENTRY / ACTIONABLE NOW protection:** an otherwise confirmed technical setup that is not trade-grade on Evidence is downgraded to `ARMED` and shown as `SETUP CONFIRMED — EVIDENCE BLOCK`. It remains visible for research but cannot be Actionable Now.
- **Ranking V3.2:** the positive formula is unchanged — **Setup 35% + Entry Timing 25% + Money Flow 15% + Evidence 15% + R:R 10%** — so there is still no double counting. Evidence qualification is applied as a separate eligibility/cap layer rather than another positive weight.
- **Top Opportunities:** requires `DecisionRankEligible=True`; low-sample / weak-lift rows cannot enter the Top Opportunities view even when technical momentum is strong.
- **Top-5 transparency:** Evidence now displays **score + N + Lift + qualification state** directly on the card, so the user can see why Evidence is or is not trade-grade.
- New audit/export fields: **EvidenceTradeGrade, EvidenceSampleN, EvidenceLiftX, EvidenceQualificationReason**.
- Cached V6.3.9.15 scans are re-profiled with the new Evidence rules on load; a fresh Scanner run is still recommended for current market data.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.16**.

### Examples from the prior V6.3.9.15 scan
- A setup such as **SMCI with N=3** stays `UNPROVEN` even if its Reliability is around 30 and its observed Lift is positive; three events are not enough for trade-grade confirmation.
- A setup with **N=8–11** is `PROVISIONAL — LOW SAMPLE` and may stay ARMED/research-only.
- A setup such as **GTLB with N=12, Lift above 1.0x and materially stronger Reliability** can qualify as supportive evidence.

---

# AI Stock Hunter — V6.3.9.15 Freshness + Qualification Guards

## V6.3.9.15 — session freshness, late-move hard gates, evidence qualification
- **Session-date Freshness Guard:** Scanner now compares the newest Daily bar with the exchange's **expected last completed regular session**. A market being `CLOSED` no longer makes an old Daily price look fresh.
- Closed/pre-open rows now expose **SessionDataFresh, PriceSessionDate, ExpectedSessionDate, PriceFreshnessStatus**. If the provider is one completed session behind, `DataQuality` becomes `STALE_SESSION`, the trade plan is blocked, and Ranking is capped until fresh data arrives.
- Top-5 render-time price refresh now shows an official Daily close only when that close belongs to the expected completed session. Otherwise it explicitly shows **STALE PRICE DATA** and keeps any old scan price labelled only as `SCAN PRICE`.
- **Ranking V3.1** keeps the de-duplicated positive formula from V6.3.9.14: **Setup 35% + Entry Timing 25% + Money Flow 15% + Evidence 15% + R:R 10%**.
- Added an **Evidence Qualification Guard**. Evidence ≥30 is `QUALIFIED`; lower evidence receives a bounded penalty and rank cap (`LOW / VERY LOW / MINIMAL / NO EVIDENCE`). Zero-evidence rows can no longer sit near the top solely because momentum/flow are strong.
- Added a **Late / Move-Consumed Qualification Guard**. A setup with ≥70% consumed is no longer treated as a fresh opportunity; ≥85% and ≥100% receive progressively harder caps. A valid retest/continuation setup is labelled `RETEST ONLY` rather than treated as a fresh trigger.
- High Chase Risk, Extension blocks, EXIT ARMED/TRIGGER and stale/data-quality failures also impose qualification caps rather than being repeatedly double-counted as extra positive/negative families.
- New audit fields include **DecisionRankEligible, DecisionRankQualification, EvidenceQualification, TimingQualification, DataFreshnessQualification, DecisionRankEvidencePenalty, DecisionRankQualificationCap**.
- `TOP OPPORTUNITIES` now requires both **Ranking V3.1 ≥68** and `DecisionRankEligible=True`.
- Old cached V6.3.9.14 closed/pre-open Daily-reference scans are conservatively marked **LEGACY SNAPSHOT — RERUN SCANNER** until a fresh V6.3.9.15 scan is run.
- `app.py` and `quant_engine.py` are synchronized to **V6.3.9.15**.

### Practical effect on the V6.3.9.14 sample
The prior 2202.HK example had **Move Consumed ≈104%** and **Evidence 0**. Under V3.1 it is capped as a late/no-evidence setup instead of remaining near the top as a fresh opportunity. A setup such as 3311.HK with low evidence remains visible for research, but carries a clear Evidence Guard and cannot qualify for `TOP OPPORTUNITIES` until evidence improves.

---

# AI Stock Hunter — V6.3.9.14 Ranking V3 Cleanup

## V6.3.9.14 — de-duplicated ranking + cleaner Scanner controls
- **Decision Ranking V3** removes repeated weighting of the same information. Final rank now uses five positive decision families once each: **Setup/Momentum 35% + Entry Timing 25% + Money Flow 15% + Evidence/Reliability 15% + R:R 10%**.
- **Hourly confirmation is no longer a separate rank weight** because it already contributes to the Entry engine. It remains visible as a timing diagnostic.
- **Market Cycle is descriptive/research-only** in the final rank because it reuses Money Flow, momentum, late/chase and exit inputs. Catalyst and Valuation also remain research-only.
- Late/Move-Consumed, Chase Risk and Exit Pressure are consolidated into **one combined risk family / one penalty**, preventing the same lateness problem from being subtracted multiple times.
- Legacy **TOP Score** and **Opportunity Score** are retained in exports/Details for audit and historical comparison, but no longer drive final Scanner rank.
- The Scanner UI now separates **Decision model** (`PRODUCTION` / `OOS OPTIMIZED`) from **Scan depth** (`FULL` / `FAST`). `FULL` deep-analyzes every requested symbol; `FAST` uses a daily prefilter first. This removes the ambiguous old `Discovery` scan mode.
- The main **Show** control is reduced to `ALL | TOP OPPORTUNITIES | ACTIONABLE NOW | WATCHLIST | RESEARCH`; research-only subviews appear only when `RESEARCH` is selected.
- Valuation and Catalyst controls were moved under **Research overlays (optional)**. Catalyst defaults OFF; Valuation remains available and research-only.
- Top-5 cards prioritize **Ranking V3, Setup, Entry, Hourly diagnostic, Money Flow, Evidence, Move Consumed, Chase Risk, R:R and Exit**. Market Cycle/Catalyst/Valuation and legacy TOP/Opportunity moved to Details.
- `TOP OPPORTUNITIES` now filters from **Ranking V3** instead of legacy TOP/Opportunity thresholds.
- Analyze cockpit now promotes **Ranking V3 + Entry Timing** instead of legacy TOP/Opportunity.
- `quant_engine.py` is version-synchronized to **V6.3.9.14**.

### Ranking V3 formula
`Core = 35% Setup + 25% Entry Timing + 15% Money Flow + 15% Evidence + 10% R:R`

`Final = Core + bounded eligible OOS-model modifier - one combined Late/Chase/Exit risk penalty - data/invalidation guard penalties`

No new technical indicator was added in this release. The goal is to make the existing signals cleaner, less redundant and easier to audit before adding more features.

---

# AI Stock Hunter — V6.3.9.13 Official-Close Price Fallback

## V6.3.9.13 — do not present a stale Scanner snapshot as the current Top-5 price
- Top-5 price display now separates **current/official price** from the older Scanner snapshot.
- When a market is **CLOSED**, the card prefers the latest daily/official close over a quote endpoint that may still expose an earlier intraday print.
- Example addressed: 2202.HK could show `2.500` from the scan even though the 22-Sep-2026 daily close is `2.440`.
- If a current/official price cannot be resolved, the large PRICE field shows `—`; the old value is labeled only as `SCAN PRICE`, so it cannot be mistaken for a live/current quote.
- The 1196.HK → 2922.HK temporary-counter bridge remains active and daily fallback uses the bridged series while the temporary counter is primary.
- Ranking, Entry, R:R and all decision metrics remain scan-time values until Scanner is rerun.

---

# AI Stock Hunter — V6.3.9.12 Top-5 Current Price Refresh

## V6.3.9.12 — Top-5 price refresh for every ticker
- Top-5 cards no longer trust only the stored Scanner-row `Price`.
- Every displayed Top-5 ticker gets a render-time current/delayed quote refresh (30s cache).
- The price line now shows the quote symbol and provider timestamp when available.
- 1196.HK still uses the temporary 2922.HK bridge while active; stale pre-split fallback remains blocked.
- Ranking, Entry, R:R and other decision metrics remain the scan snapshot; rerun Scanner to recompute them from the newest market state.

## V6.3.9.11 — current price on 1196.HK is forced from active temporary counter 2922.HK

During the active 1196→2922 temporary-counter window, the Top-5 card no longer trusts a cached Scanner-row `Price` for 1196.HK. On render it resolves a current quote through the temporary-counter bridge and displays the **2922.HK price scale** beside Ranking V2. If a current temporary-counter quote cannot be verified, the card shows **PRICE — / LIVE PRICE UNAVAILABLE** rather than falling back to a stale pre-split 1196 price.

The secondary line now identifies **TEMP DATA 2922.HK**, **LIVE PRICE 2922.HK**, and the provider timestamp when available. This is a price-display/data-integrity hotfix only: Ranking V2 weights, Entry logic, Money Flow, Market Cycle, Catalyst, targets/stops and feedback definitions are unchanged.

---

# AI Stock Hunter — V6.3.9.10 1196↔2922 Temporary Counter Bridge

## V6.3.9.10 — Realord 1196.HK temporarily uses HKEX counter 2922.HK

During the official temporary-counter period, the app keeps **1196.HK** as the logical ticker in the universe, UI, feedback database and historical research, while sourcing current Hong Kong market bars/quotes from **2922.HK**. The bridge is active from **14-Sep-2026 through 27-Sep-2026**; production routing returns to the original **1196** counter when it reopens on **28-Sep-2026**. The temporary 2922 counter remains a parallel counter later in the official timetable, but it is no longer the primary production symbol after 1196 reopens.

To avoid destroying indicator history, Daily / 1H / 15m downloads stitch the long 1196 history to the new 2922 bars. The bridge detects whether the provider has already back-adjusted the old history; only when the endpoint scale clearly reflects the official **1 old share → 4 subdivided shares** ratio does it normalize legacy OHLC by 4 (and volume by 4 in the opposite direction).

Live quote fallbacks (Yahoo bar feed, Yahoo quote endpoints and TradingView display fallback) also route to 2922 while the temporary bridge is primary. Top-5 cards keep displaying **1196.HK** and add **TEMP DATA 2922.HK** so the source is explicit. No Ranking V2 weights, Entry rules, Money Flow, Market Cycle, Catalyst, target/stop geometry or feedback outcome definitions changed in this release.

---

# AI Stock Hunter — V6.3.9.9 Current Price Beside Ranking

## V6.3.9.9 — current scan price promoted next to Ranking V2

The mobile Top-5 header now shows **PRICE** directly beside the large **RANK / Ranking V2** score so the decision score and the latest price captured by the Scanner are visible together without opening Details. The price uses the Scanner row's `Price` value (the same current/fallback price used by the scan), shows three decimals below 10 and two decimals otherwise, and displays the available currency code (with market fallback to HKD / USD / ILA when the fundamentals currency field is blank).

To keep the header compact on phones, **OPP** moved to the secondary line beside **TOP**. No Ranking V2 formula, Entry gate, target/stop, Money Flow, Market Cycle, Catalyst, or trade-decision logic changed in this release.

---

# AI Stock Hunter — V6.3.9.8 Ranking-First Top 5 UI

## V6.3.9.8 — Ranking is now the primary Top-5 headline

The Top-5 card header now promotes **Ranking V2** to the large, bold primary score because it is the score that actually determines #1–#5. The legacy **TOP Score** remains visible as a smaller secondary reference line below the header. Opportunity stays compact at the right. This is a presentation-only change: Ranking V2 weights, penalties, filtering, and trade logic are unchanged from V6.3.9.7.


## V6.3.9.7 — cached-scan migration + guaranteed Ranking V2 display

This hotfix fixes the case where the app was upgraded to V6.3.9.6 but the Streamlit server still held an older `last_completed` scan in `st.cache_resource`. The new card UI therefore appeared, but the cached DataFrame had no `DecisionRankScore`, so cards showed **`Ranking V2 —`** and the old ARMED-first order could remain visible.

V6.3.9.7 now checks the full completed snapshot **before any Scanner filter or Top-5 selection**. If Ranking V2 is missing or incomplete, it backfills Decision Intelligence when needed, calculates Decision Ranking V2 for every stock, sorts the full universe, rewrites Global / Market / Sector / Trade Priority ranks, and stores the migrated DataFrame back in the server runtime. This makes the migration a one-time operation rather than recalculating every one-second UI refresh. New scans still calculate Ranking V2 normally at scan completion.

The ranking formula itself is unchanged from V6.3.9.6: **TOP 40% + Entry 20% + Hourly 10% + Money Flow 10% + Market Cycle 8% + T1 R:R quality 12%**, then explicit late / chase / exit / data-quality penalties and only a small Entry-stage modifier.

---

## V6.3.9.6 — timing-aware ranking that matches the Top-5 card evidence

V6.3.9.6 fixes the ranking inconsistency exposed by the compact Top-5 cards. In earlier builds, `TradePriorityRank` used a hard stage priority (`CONFIRMED > ARMED > WATCH > WAIT`) before TOP score, so an `ARMED` stock could appear #1 even when another stock had materially better TOP, Opportunity, Money Flow, Market Cycle, Entry, Hourly confirmation and R:R.

The new **Decision Ranking V2** removes that hard stage ordering. Final Scanner / Top-5 rank is now a transparent composite of **TOP Score (40%) + live Entry quality (20%) + Hourly confirmation (10%) + Money Flow (10%) + Market Cycle (8%) + T1 R:R quality (12%)**, followed by explicit penalties for **Move Consumed / lateness, Chase Risk and Exit Pressure**. Entry state is only a small modifier (`CONFIRMED +4`, `ARMED +2.5`, `WATCH +1`) instead of an automatic rank override. `EXTENDED / TOO LATE / INVALIDATED` states receive negative modifiers. TOP is not double-counted with Opportunity because TOP already contains Opportunity, Prediction and Reliability.

For `Optimized 151` and `Discovery`, an eligible Optimized Score is blended into the Decision Rank, but live timing penalties still apply. **Catalyst is intentionally not used in Ranking V2** because it is fetched only for a subset of candidates; weighting it would bias ranked stocks simply because they received coverage. Valuation also remains research-only. Production Entry gates, ARMED/CONFIRMED logic, targets, stops and Actionable Now rules are unchanged.

Every Top-5 card now shows **Ranking V2 XX/100** under the header, and `Details / Why?` shows the ranking audit string: core score, stage modifier, late penalty, chase penalty and exit penalty. Scanner Excel adds all Ranking V2 components plus legacy ranks for audit. Feedback snapshots persist the new ranking score/core/reason/version so 1D/2D/3D/5D outcomes can later test whether rank position itself adds forward lift. Existing databases are migrated in place.

# AI Stock Hunter — V6.3.9.5 Compact Top 5 Mobile UI

## V6.3.9.5 — compact decision cards for mobile

V6.3.9.5 keeps all V6.3.9.4 Decision Intelligence calculations and Production logic unchanged, but redesigns the Scanner **Top 5** cards for fast comparison on a phone. The card header now keeps **Rank + Ticker + TOP Score + Opportunity** on one compact row. The always-visible decision grid shows **Money Flow, Market Cycle, Catalyst, Entry, Move Consumed Before Trigger + EARLY/MID/LATE timing, Chase Risk, Hourly Confirmation, and live R:R**.

Long research explanations are moved into a collapsed **Details / Why?** section: Pre-Move and Regular Radar evidence, entry-gate explanation, Money Flow / Cycle / Catalyst evidence, optimization diagnostics, valuation research, volume/rank details, reliability, backtest and data quality. A material **late/extension/chase warning remains visible** and a valid live trade plan remains visible when the market is open and Entry is confirmed. No ranking thresholds, feedback rules, targets/stops, Money Flow/Cycle/Catalyst formulas or Production Entry gates are changed in this release.

On narrow screens the eight decision tiles render in a **2-column mobile grid** rather than stacking each Streamlit metric vertically, materially reducing Top-5 scrolling while preserving the same information.


## V6.3.9.4 — Money Flow + Market Cycle + Catalyst on Scanner Top 5

V6.3.9.4 adds the three research layers requested for the redesigned **Top 5** cards while preserving the V6.3.9.3 valuation overlay and all Production entry/ranking logic. The new card shows **Money Flow Score (0–100)**, **Market Cycle Score / Stage**, **Catalyst Score / label**, **Entry**, **Hourly Confirmation**, **Move consumed before trigger**, **Chase risk**, and live **R:R** when available. TOP Score remains the primary headline.

**Money Flow Score** is direction-aware. It combines the existing institutional-flow proxy, bullish-vs-bearish volume evidence, live/daily RVOL, volume acceleration and Exit safety. High volume by itself is never treated as bullish: high RVOL with bearish price/flow evidence reduces the score. Labels include `STRONG INFLOW`, `INFLOW / ACCUMULATION`, `MIXED / NEUTRAL`, `OUTFLOW / DISTRIBUTION`, and `STRONG OUTFLOW`.

**Market Cycle** classifies each analyzed stock as `ACCUMULATION → EARLY BREAKOUT → EXPANSION → EXTENDED → DISTRIBUTION`, with `NEUTRAL / BASE` when no clean stage is present. The numeric Cycle Score measures current long-entry favorability rather than cycle age, so an `EXTENDED` stock can score lower than an `EARLY BREAKOUT`. The stage uses fresh-transition state, money flow, momentum/explosive evidence, Exit Pressure, Chase Risk and `MoveConsumedBeforeTriggerPct`.

**Catalyst Score** is a best-effort research overlay based on recent Yahoo Finance headlines, simple positive/negative catalyst phrases, recency weighting and upcoming earnings proximity. It is cached for 45 minutes and fetched for the scan-time Top 12; the five cards currently shown are lazily filled as needed so filtered Top-5 views can still display catalyst context. The score is explicitly heuristic: headline absence is shown as `NO DATA`, and upcoming earnings are shown as event risk rather than automatically positive.

All three layers are **research-only** in V6.3.9.4. They do not change TOP Score, Opportunity, Entry gates, ARMED/CONFIRMED, Chase/Extension, Trade Priority, optimizer weights or targets/stops. Scanner Excel adds a dedicated **Decision Intelligence** sheet, and live Feedback snapshots persist Money Flow, Market Cycle and Catalyst fields so future 1D/2D/3D/5D analysis can measure whether they add out-of-sample Lift before any production weighting change is considered. Existing feedback databases are migrated in place; previous snapshots are preserved.

# AI Stock Hunter — V6.3.9.3 Valuation / Undervaluation Overlay

## V6.3.9.3 — research-only peer-relative valuation, without changing trade timing

V6.3.9.3 adds a **Valuation Score (0–100)** and **Estimated Discount % / Fair-Value Range** to Scanner as a separate research overlay. It uses best-effort Yahoo Finance fundamentals already supported by the project, caches raw fundamentals for six hours, and compares each stock with same-market / same-sector peers when enough peers exist (falling back to market or the scan universe only when needed). The valuation layer is explicitly informational: it does **not** change TOP Score, Opportunity, Entry, ARMED, CONFIRMED, Chase/Extension, ranking, or optimizer weights.

The model adapts the usable multiples to the company type: profitable/general companies emphasize forward/trailing P/E, EV/EBITDA, FCF yield, P/S and P/B; growth/non-profitable companies emphasize P/S, EV/Revenue, PEG and FCF yield; financials emphasize P/B and earnings multiples; real-estate companies use a **proxy** because Yahoo fundamentals do not provide a clean standardized P/FFO field for the whole universe. The fair-value range is therefore a peer-relative research estimate, **not an intrinsic DCF value**.

Scanner Top-5 cards now show `Valuation Score • label • Estimated discount • Fair-value range • Evidence`. The full table and Scanner Excel include the valuation fields, plus a dedicated **Valuation Research** sheet. A new `UNDERVALUED (RESEARCH)` filter surfaces stocks with Valuation Score >=65 and an UNDERVALUED / DEEPLY UNDERVALUED label. The overlay can be disabled before a scan; the first fundamentals pass may take longer, while subsequent scans reuse the six-hour cache.

Every live Scanner snapshot persists the valuation score, label, discount, fair-value range, evidence, archetype, peer count, currency and method into the existing `feedback_v600.sqlite3` database. Existing V6.3.9.x backups are upgraded in place; no prior snapshots are deleted. This allows later 1D/2D/3D/5D Feedback analysis to test whether valuation adds forward Lift before it is ever allowed to influence Production decisions.

# AI Stock Hunter — V6.3.9.2 Top-5 Trigger Timing

## V6.3.9.2 — show move consumed before trigger directly on Top 5 cards

V6.3.9.2 keeps the V6.3.9 Early Entry Validation logic and the V6.3.9.1 Feedback live-audit hotfix unchanged, and adds one focused Scanner UI improvement. Every stock in the Scanner **Top 5** now shows its trigger-timing evidence directly on the card: **Trigger timing**, **Move consumed before trigger**, **Move before trigger**, and **Since trigger**. This makes late confirmations visible without opening the Excel export.

Example: `Trigger timing: LATE • Move consumed before trigger: 84.1% • Move before trigger +4.54% • Since trigger +0.82%`.

This release changes **display only**. It does not change Production ranking, Entry gates, ARMED/CONFIRMED thresholds, Chase/Extension logic, Feedback schema, snapshot storage, or model weights. The same `feedback_v600.sqlite3` database is reused.

# AI Stock Hunter — V6.3.9.1 Feedback Live-Audit Hotfix

## V6.3.9.1 — preserve the 678 snapshots; fix Feedback before outcomes mature

V6.3.9.1 is a **narrow hotfix**. It does not change Production entry thresholds, weights, Chase/Extension logic, Scanner ranking, Early ARMED classification, or the Feedback database schema. It fixes the `KeyError: 'Model Status'` seen in **Feedback → Live-signal audit** when snapshots exist but forward outcomes have not yet matured enough to create stock-level result columns.

The stock scorecard now creates `Model Status`, resolved-count and return columns explicitly before sorting. A stock with snapshots but no mature outcome is shown as **WAITING FOR OUTCOME** instead of crashing the Feedback page. The existing `feedback_v600.sqlite3` path is unchanged, so an in-place V6.3.9 → V6.3.9.1 upgrade reuses the same database, including the 678 snapshots already collected.

No model logic was changed in this hotfix so the forward validation started in V6.3.9 remains comparable.

# AI Stock Hunter — V6.3.9 Early Entry Validation + Snapshot Safety

## V6.3.9 — prove the early entry stage before changing weights

V6.3.9 turns **ARMED** into a formal forward-validation event instead of treating it only as an intermediate UI label. Every completed Scanner snapshot now records an **Armed Timing Class** (`EARLY ARMED`, `MID ARMED`, or `LATE ARMED`) together with the price/entry-zone distance, live reward/risk gate, setup-confirmed state, move-consumed evidence and the full Regular Radar metadata. Feedback compares these classes against later 1D / 2D / 3D / 5D outcomes by market, so the project can test whether the earlier ARMED state really adds Lift before any production threshold or optimizer weight is changed.

The Production Entry path is also made internally consistent. A setup may be fully confirmed while the **price is no longer actionable**. `CONFIRMED ENTRY` now additionally requires the current price to be in the original entry zone or a valid retest zone and to preserve minimum live reward/risk. Otherwise the engine reports **SETUP CONFIRMED — WAIT FOR ENTRY** and keeps the trade stage at ARMED instead of simultaneously saying `CONFIRMED ENTRY` and `WAIT FOR PULLBACK`. A zero-sample backtest can no longer remain a trade-grade confirmation in the app layer; the raw engine state is retained for audit, while the user-facing trade stage is downgraded to ARMED until evidence exists.

Snapshot safety is strengthened rather than reset. V6.3.9 keeps the same historic SQLite filename (`feedback_v600.sqlite3`) so an in-place upgrade reuses the existing live snapshots. The Feedback tab still supports portable DB backup/restore and optional GitHub persistence. In addition, it can import prior Scanner `.xlsx` exports as idempotent historical snapshots, which provides a recovery path for exported scans if a Streamlit host was replaced. New Scanner exports also write the selected horizon, target, scan mode and universe into the About sheet.

A new **Early Entry Validation** table in Feedback compares `EARLY ARMED`, `MID ARMED`, `LATE ARMED`, and `CONFIRMED ENTRY` on clean resolved outcomes, reporting resolved N, win rate, market/horizon baseline, Lift, average end return, MFE and MAE. `LOW SAMPLE` remains explicit; V6.3.9 does **not** auto-promote ARMED or loosen Entry thresholds from one or two good days.

# AI Stock Hunter — V6.3.8 Market-Specific Regular Radar + High-Confidence Funnel

## V6.3.8 — from raw Hit Rate to a validated funnel

V6.3.8 turns the Regular Pre-Move Signature research into a **market-specific Scanner layer** and adds a stricter **High-Confidence Funnel** designed to test whether selective filters can raise the ordinary-rise hit rate without forcing a 70% result. The broad +2% / +3% / +5% / +8% Signature Lab still keeps its causal 70% discovery / 30% OOS audit. In parallel, a new nested path uses **60% discovery → 20% selector → 20% untouched FINAL HOLDOUT**. A combination is promoted only if it survives the selector; the final 20% is not used for selection.

The funnel reports, for every market / target / lead window, the final-holdout result after successive gates: **any promoted combination → 2+ combination consensus → Setup >= 70 → Fresh / not late → Research High Confidence**. A row is labeled **70% RESEARCH TIER** only when the untouched final holdout itself reaches >=70% with at least 30 resolved samples and meaningful Lift. Tiny samples remain `LOW SAMPLE`; the app never manufactures a 70% tier.

The Regular Radar is now integrated into **Scanner**. For every matched stock the Scanner can show the target (+2/+3/+5/+8%), lead window (1H/2H/1D/2D/3D/5D), Signature Score, empirical OOS Hit Rate, Baseline, Lift, Setup Score, Freshness, nested Funnel stage, final-holdout Hit Rate / Baseline / Lift / N, and the strongest signature. New Scanner filters include **REGULAR HIGH CONFIDENCE** and **REGULAR RADAR**. The historical research funnel is displayed separately from current live Entry timing; it never bypasses Hourly, Volume/Flow, Chase/Extension, Live R:R, Distribution or Exit guards.

Completed Regular Signature runs are cached **per market** (NASDAQ / Hong Kong / Tel Aviv) and stored inside the Feedback SQLite database as well as a local cache. This means the market-specific research radar can be backed up/restored with the Feedback DB and can be remotely persisted when Feedback GitHub persistence is configured. New live Scanner snapshots also store the attached Regular Radar / Funnel metadata so later versions can evaluate live calibration without losing which research state was present at scan time.

**Recommended first validation after upgrade:** rerun Regular Signature Lab separately for NASDAQ 100, Hong Kong 100 and Tel Aviv 50 using 3y Daily, 6mo Hourly, sample every 2, with 1H+2H enabled. Then run a full Scanner. The Scanner will merge the latest market-specific models side by side with Pre-Move and Live Entry.

No Production Entry threshold is loosened in V6.3.8. The purpose is to measure whether successive independent filters genuinely move the final-holdout hit rate toward 60–70% while preserving enough sample size.

# AI Stock Hunter — V6.3.7 Four-Score Explosive Radar + Regular Pre-Move Signature Lab

## V6.3.7 — Four scores + ordinary-rise signature research

V6.3.7 makes the Explosive Radar easier to interpret by showing **four separate 0–100 research scores** for every current stock: **Setup Score** (quality of the broader preparation), **State Score** (strength of the stock's current PRE-EXPLOSIVE / CONTINUATION BASE / RE-ACCELERATION phase), **Setup×State Consensus** (the geometric mean, so both setup and state must be strong), and **Explosive Radar Score** (state plus the stock's own historical analog Lift and matching OOS combination evidence). A Radar score of 100 is explicitly a ranking score, **not** a 100% probability. Within each status tier, candidates are now ordered first by Setup×State Consensus and then by Radar evidence.

V6.3.7 also adds a new **Regular Pre-Move Signature Lab** for ordinary rises rather than only explosive +10%/+15%/+20% moves. It automatically tests targets of **+2%, +3%, +5% and +8%** at **1H / 2H** hourly windows and **1D / 2D / 3D / 5D** daily windows. At every historical snapshot, only indicators already known at that moment are recorded; future highs are used only as labels. The earliest 70% of dates discovers individual indicators and 2–3 indicator combinations across independent families, while the final 30% is untouched OOS validation.

The Regular Signature workbook includes **Signature Summary**, **Top OOS Signatures**, **Combination Signatures**, **Indicator Signatures** and a **Current Regular Radar**. The current radar only matches today's/latest completed snapshots against combinations that survived OOS; it remains research-only and never bypasses Scanner/Analyze live timing, Chase/Extension, R:R, Distribution or Exit rules. Hourly research uses confirmed 60-minute bars when available.

No Production Entry thresholds are automatically changed in V6.3.7. The goal is to learn *which shared signature appears before a +2/+3/+5/+8% move, and how early it appears*, while preserving the separate Explosive continuation channel.

# AI Stock Hunter — V6.3.6 Explosive Continuation Engine + Universe Radar V2

## V6.3.6 — Explosive Continuation Engine

V6.3.6 adds a causal second-leg state machine to the split-safe Explosive research path. A stock is no longer rejected merely because the first move already happened. Every historical/current daily bar is classified as **PRE-EXPLOSIVE**, **CONTINUATION BASE**, **RE-ACCELERATION**, **EXTENDED / NO RESET**, or WATCH using only information available at that bar. A continuation reset requires a prior impulse, high retention near the recent peak, a tight causal base, constructive/contracting base volume, trend hold, and no distribution. Re-acceleration additionally requires a causal break of the prior base with renewed momentum plus Volume/Flow.

The Explosive Benchmark now separates independent first and continuation legs, reports the earliest *qualified* causal warning (>=3 independent families, no distribution), and adds an **Explosive State Evidence** sheet. The Universe Radar is upgraded to V2 and ranks **PRE-EXPLOSIVE**, **CONTINUATION BASE**, and **RE-ACCELERATION** candidates using state-specific historical analogs when enough examples exist, with a family-overlap fallback when the state sample is still small.

**Important:** the normal **Pre-Move +5% / 3D** discovery channel remains separate and unchanged. Production Entry, Analyze timing, Chase/Extension, R:R and Exit rules are also unchanged. Explosive V6.3.6 remains research-only until OOS and live feedback support promotion.

## Previous: V6.3.5 Explosive Event Integrity + Universe Radar

## V6.3.5 — Explosive Event Integrity + Universe Radar

V6.3.5 hardens the +10%/+15%/+20% explosive research path before using it as an early-warning radar. Historical OHLCV is normalized across confirmed/high-confidence split-like corporate-action scale breaks *before* indicators and future target labels are calculated. Unexplained giant one-day scale gaps are quarantined from learning rather than counted as explosive wins. The workbook adds an **Integrity Audit**, and every causal sample records whether a corporate action was crossed or the sample was excluded.

Explosive episodes are now split into **independent legs** instead of chaining every overlapping 5D hit into one long episode. A new leg can start after the prior hit only after a five-session cool-off or a meaningful price reset. This is designed specifically to distinguish separate August and September moves in benchmarks such as `1196.HK`.

A new **Explosive Universe Radar** can scan Hong Kong, NASDAQ, Tel Aviv or the combined universe. For each current completed-session setup it compares the active independent families with the stock's own split-safe historical +15% analogs and any OOS-promising combinations. Results are ranked as `WATCH`, `BUILDING`, `EXPLOSIVE CANDIDATE` or `STRONG EXPLOSIVE CANDIDATE`, with historical analog N / hit rate / Lift and the strongest matching OOS combination shown. The radar is research-only: it never bypasses Analyze/Scanner live timing, Chase/Extension, R:R or distribution guards.

No Production Entry thresholds were changed automatically in V6.3.5. The purpose is to find repeatable *early warnings* before large moves across many stocks while preventing corporate actions from masquerading as price explosions.


## V6.3.4 — Market-Specific Consensus + Explosive Benchmark Lab

V6.3.4 adds a stricter **market-specific consensus ensemble** on top of V6.3.3. The research split is now nested for the consensus layer: the earliest 60% of dates discovers combinations, the next 20% promotes only combinations that remain positive, and the final 20% is untouched until the consensus gate is scored. The main `MARKET CONSENSUS 2+` gate requires at least two promoted combinations with different independent-family signatures to agree on the same final-holdout row. This is designed to test NASDAQ, Hong Kong and Tel Aviv separately instead of assuming one universal formula. It remains research-only and does not modify Production Entry.

A new **Explosive Benchmark Lab** is available in Feedback. It defaults to `1196.HK`, freezes all features at each historical signal close, and then labels whether a +15% move occurred within 1D / 2D / 3D / 5D. The workbook includes explosive episodes, the earliest causal warning before each episode, an automatic August/September audit for the latest history year, indicator lift, and a separate 70/30 single-stock combination discovery. This lab is intentionally a benchmark: a pattern found on 1196.HK must later survive tests on the wider Hong Kong universe before it can influence Production.

The V6.3.3 finalization fix remains in place: Historical Replay does not display 100% until meta scoring, combination/consensus research, database persistence, scorecards and Excel generation are complete.

## V6.3.3 — search for stable shared indicator combinations, not a forced 70%

V6.3.3 adds a research-only Combination Discovery engine to Historical Replay. The earliest 70% of historical signal dates are the only data allowed to select 2-, 3- and 4-indicator combinations. Indicators from the same correlated family cannot be combined together. The final 30% of dates is untouched OOS validation and is split into three chronological folds, so a spectacular Discovery result is explicitly rejected when it fails later.

The new workbook adds **Combination Discovery**, **WalkForward Folds** and **V3 OOS Gate Comparison**. It reports Discovery/OOS sample size, win rate, Lift, delta versus baseline, stock breadth, positive folds and stability gap. A separate **70% DISCOVERY TIER** is shown only as a hypothesis: it is never called successful unless OOS results independently support it. A more practical **HIGH-CONFIDENCE DISCOVERY** tier requires >=60% in Discovery, meaningful Lift, sample size and cross-stock breadth before it is tested OOS.

Replay V3 also fixes the lingering Streamlit Stop/running appearance after a completed large replay by reusing the workbook already built by the background job instead of rebuilding the multi-megabyte Excel file on the completion rerun. No Production Scanner/Entry/Chase/R:R rule is changed automatically from this research.


## V6.3.2 — Replay 200/3y completion hotfix

V6.3.2 fixes the Historical Replay behavior where large runs such as NASDAQ 200 / 3y could reach 100% of tickers and appear to run forever. The cause was the strict-date Meta Probability finalization step: V6.3.1 repeatedly rebuilt and filtered the full prior replay history for every row, which became effectively quadratic on large samples. V6.3.2 preserves the same causal empirical-Bayes logic but computes it with cumulative sufficient statistics, reducing finalization to approximately linear work.

Replay progress now reserves four explicit finalization steps after the ticker loop: causal meta scoring, database save, scorecards/calibration and Excel generation. The UI therefore does **not** show 100% until the workbook is actually ready. Historical Replay is also registered explicitly in the server-side job runtime. No Production Entry, Scanner, Chase/R:R, Feedback success definition, or High Confidence thresholds were changed in this hotfix.


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
