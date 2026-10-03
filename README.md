# AI Stock Hunter — V6.3.9.61 Original Memory + ARMED Qualification + Stage Sync

## Purpose
V6.3.9.61 is a focused integrity release built on V6.3.9.60. It keeps the persistent Last Completed Scan, selective Pre-Move Radar, strict live ENTRY NOW, Continuation logic, common-stock discovery guard and current ranking model unchanged, while fixing the three issues exposed by the latest Scanner review.

No Optimizer weights, Pre-Move thresholds, Continuation thresholds or entry thresholds are retuned in this release.

## 1. BUILDING SETUP is now the canonical stage everywhere
`EARLY RADAR` is accepted only when reading legacy cached/Feedback data. New output uses `BUILDING SETUP` consistently in:
- Scanner cards and filters;
- Analyze;
- DecisionBoardStage / EffectiveDecisionStage / DecisionDisplayStage;
- Excel exports and Decision Intelligence;
- Top Action ordering and memory coverage logic.

The progression is now:

`PRE-MOVE RADAR → BUILDING SETUP → ARMED → ENTRY NOW → RETEST / TOO LATE`

This removes the old ambiguity between the separate Pre-Move Radar and the former EARLY RADAR name.

## 2. ARMED is split into qualified vs blocked/incomplete
A stock can look mature technically while still lacking trustworthy timing/session/plan integrity. V6.3.9.61 therefore adds:
- `ArmedQualified`
- `ArmedQualificationState`
- `ArmedQualificationReason`

A normal `ARMED` stage now requires structural integrity such as complete timing data, fresh session data, valid data quality/trade plan, no timing/extension hard block and no hard exit-pressure block.

If the setup looks mature but those structural gates are incomplete, the effective stage becomes:

`ARMED BLOCKED` / `ARMED • BLOCKED`

Important: PriceActionableNow and ConfirmedEntryGateOK are **not** required merely to remain qualified ARMED; those are live-entry gates. This avoids incorrectly demoting a healthy ARMED setup just because price has not yet reached the entry window.

Top Action ordering is now:

`ENTRY NOW → ARMED → BUILDING SETUP → ARMED BLOCKED → LAST SESSION ENTRY → RETEST → WAIT → TOO LATE`

So incomplete ARMED rows cannot outrank clean BUILDING SETUP candidates.

## 3. 1780.HK Original Signal migration
The persistent Original-Signal system still prefers genuine Feedback history first. V6.3.9.61 adds a verified one-time migration for 1780.HK using the user's own V6.3.9.47 Analyze export, created before persistent Original Memory existed.

Verified legacy reference:
- Original causal trigger: approximately `5.055`
- Trigger time: `2026-09-28 10:15 +08:00`
- Original T1: approximately `5.9765`
- Original invalidation: approximately `4.8854`

The migration is used only when no earlier real Feedback memory is available. It is never generated from the current trigger, so Original and Current remain independent concepts.

The migrated row is persisted into the same Feedback SQLite `signal_memory` table and is marked as a BACKFILLED verified legacy scan.

## 4. Existing persistence remains unchanged
The V6.3.9.60 Last Completed Scan behavior is retained:
- the latest successful Scanner snapshot survives refresh/restart;
- the exact completion time is shown in Israel time;
- stopped/failed scans never replace the last successful snapshot;
- the saved scan remains inside the portable Feedback DB.

## 5. Existing protections retained
V6.3.9.61 retains:
- Top Action + Top Pre-Move split;
- HIGH / WATCH selective Pre-Move Radar;
- strict live ENTRY NOW hard gate;
- LAST SESSION ENTRY / recheck-at-open semantics;
- Core Deep reserve including NVDA;
- market-balanced SMART Deep quotas;
- HK local-session freshness logic;
- common-stock-only broad discovery guard;
- Continuation READY / WATCH / BLOCKED;
- Original Trigger vs Current Trigger separation;
- visual WHY YES / WHY NOT;
- Momentum 15m / 1H;
- persistent glowing Last Completed Scan banner.

## Validation after upload
No Optimizer rerun is required.

Recommended validation:
1. Run `MARKET DISCOVERY + SMART`.
2. Confirm Scanner/Excel no longer output `EARLY RADAR`; they should say `BUILDING SETUP`.
3. Confirm incomplete timing/data ARMED rows appear as `ARMED BLOCKED` and rank below clean BUILDING SETUP candidates.
4. Check 1780.HK: Original Trigger should populate near 5.055 and remain separate from the Current Trigger/T1/progress.
5. Refresh/restart and verify the same Last Completed Scan still restores with the exact Israel completion time.

## Files
The deployment ZIP contains exactly:
- `app.py`
- `quant_engine.py`
- `README.md`
- `requirements.txt`
