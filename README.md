# AI Stock Hunter — V6.3.9.58 Live Entry + Core Revalidation

## Purpose
V6.3.9.58 is a scanner decision-integrity release. It keeps the V6.3.9.57 Original/Current Trigger memory and selective Pre-Move model, while fixing two issues exposed by the latest scan: true `ENTRY NOW` rows could disappear from Top Tickets because of a second legacy sort, and liquid core US names such as NVDA could be removed from Deep Analysis by SMART depth quotas.

No optimizer weights or Pre-Move thresholds are retuned in this release.

## 1. Strict live `ENTRY NOW`
`ENTRY NOW` is now allowed only when the current snapshot passes one common hard gate:
- market session is actionable (`OPEN`, or confirmed US pre-market context),
- `TimingDataComplete = TRUE` and no timing hard block,
- `ConfirmedEntryGateOK = TRUE`,
- `PriceActionableNow = TRUE`,
- `RRActionable = TRUE`,
- current session data is fresh,
- current price is fresh,
- trade plan and data quality are valid,
- extension/evidence/exit hard guards are clear.

A technical/historical `CONFIRMED ENTRY` label can no longer create a live `ENTRY NOW` by itself. If the setup is still mature but one of the live gates is missing, it is shown as `ARMED` with the blocking reason.

New audit fields:
- `RawDecisionBoardStage`
- `EffectiveDecisionStage`
- `DecisionDisplayStage`
- `EffectiveDecisionReason`
- `EntryNowHardGateOK`
- `EntryNowHardGateReason`
- `NeedsOpenRevalidation`
- `CurrentMarketPhaseNow`

## 2. Top Tickets rank integrity
The Top Tickets panel no longer re-sorts an already ordered result by legacy `TradePriorityRank`.

For `ALL`, the display order is now based on the current effective decision lane and its `ActionQueueRank`:
1. `ENTRY NOW`
2. `ARMED`
3. `EARLY RADAR`
4. `LAST SESSION ENTRY`
5. `RETEST`
6. `WAIT`
7. `TOO LATE`

Therefore a genuine live `ENTRY NOW #1` cannot be pushed out of the Top 5 by an older research/priority rank.

## 3. Closed / previous-session semantics
A previous-session confirmed signal is retained for audit, but outside the regular session it is displayed as:

`LAST SESSION ENTRY • RECHECK AT OPEN`

It does not compete with a genuinely live `ENTRY NOW`.

## 4. US Core Deep reserve — including NVDA
When the US market is selected, the liquid `US 51` core set is guaranteed a Deep Analysis slot in SMART scans. This includes NVDA and prevents a prefilter/depth cutoff from skipping a major core name just before or during a fast intraday move.

The reserve applies to both:
- `MARKET DISCOVERY + SMART`
- curated SMART scans

Active Original Signals, explicit priority tickers and temporary-counter bridges remain reserved separately.

## 5. Market balance is preserved
Reserved US core names are counted *inside* the normal market quotas instead of being added on top of them.

For a 160-name Deep cap across all three markets, the selector still targets approximately:
- US: 88
- Hong Kong: 48
- Tel Aviv: 24

Mandatory names are guaranteed, but they no longer unintentionally crowd out discovery from the other markets.

## 6. US open revalidation guard
If a completed US snapshot was created before the current regular session and the market is now open, the scanner marks it:

`US OPEN REVALIDATION REQUIRED`

Pre-open scores are not treated as live `ENTRY NOW`. Re-running Scanner refreshes 15m / 1H momentum, RVOL, Flow and Entry geometry. Because the US core is now Deep-reserved, NVDA and the other core names are guaranteed to receive that revalidation when they are in the selected universe.

## 7. Existing V6.3.9.57 integrity remains
This release preserves:
- locked Original Signal / Original Trigger / Original T1,
- separate Current Trigger / Current T1,
- HK local-session freshness logic,
- selective High-Confidence Pre-Move detection,
- active Original Signal Deep reserve,
- Scanner / Analyze shared decision presentation,
- visual WHY YES / WHY NOT,
- Continuation READY/WATCH/BLOCKED,
- SCAN COMPLETED banner in Israel time.

## Files
The deployment ZIP contains exactly:
- `app.py`
- `quant_engine.py`
- `README.md`
- `requirements.txt`
