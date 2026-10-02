# AI Stock Hunter — V6.3.9.59 Pre-Move Top + Original Signal Backfill

## Purpose
V6.3.9.59 keeps the live-entry, Core Deep reserve, session-integrity and selective Pre-Move logic from V6.3.9.58, while fixing two issues exposed by the latest scan:

1. a strong `Pre-Move HIGH` pattern could be hidden from Top Tickets because the Top panel ranked only current trade actionability;
2. older valid moves such as 1780.HK could still show `NO ORIGINAL SIGNAL MEMORY` even though prior Feedback snapshots contained an earlier signal.

No optimizer weights, Continuation thresholds or selective Pre-Move thresholds are retuned in this release.

## 1. Dual Top queues
The main `ALL` Scanner view now shows two separate headline sections.

### Top Action / Decision Queue
Ranks what is actionable *now* using the current effective decision stage:
1. `ENTRY NOW`
2. `ARMED`
3. `EARLY RADAR`
4. `LAST SESSION ENTRY`
5. `RETEST`

This queue still uses current Entry/Timing/R:R/session gates. A live `ENTRY NOW` cannot be pushed out by research ranks.

### Top Pre-Move Radar
Ranks early-pattern discovery separately:
- `HIGH` before `WATCH`;
- actionable-early patterns first inside the same tier;
- then Pre-Breakout Accumulation score, independent family count and flow confirmation.

A `HIGH` pattern remains visible even if the current trade decision has already become `TOO LATE`.

Example display states:
- `HIGH PRE-MOVE • ACTIONABLE EARLY`
- `HIGH PRE-MOVE PATTERN • WATCH`
- `HIGH PRE-MOVE PATTERN • TOO LATE NOW`

`RAW ACCUMULATION` is intentionally not promoted into the headline Top Pre-Move Radar.

## 2. Dedicated Pre-Move radar audit fields
New derived fields:
- `PreMoveRadarEligible`
- `PreMoveRadarRank`
- `PreMoveRadarStatus`

They are included in Scanner decision/audit exports and visible in the main results table.

The research filters `STRONG PRE-MOVE CANDIDATE` and `PRE-MOVE CANDIDATE` now use the selective `PreMovePatternStrength` layer (`HIGH` / `WATCH`) instead of relying only on the older research overlay stage.

## 3. Original Signal backfill — event aware
Original Signal memory is now reconstructed from the earliest meaningful Feedback snapshot of the *same move* whenever possible.

Backfill recognizes historical evidence such as:
- `EARLY RADAR`
- `ARMED`
- `ENTRY NOW`
- `LAST SESSION ENTRY`
- `CONFIRMED ENTRY`
- `HIGH-CONFIDENCE PRE-MOVE`
- a confirmed-entry gate with actionable price

The first causal trigger found at or after that original signal locks the Original Trigger, Original T1 and invalidation.

## 4. No more generic Original == Current fallback
`Current Trigger` remains session/reconfirmation timing.

`Original Trigger` is historical memory only. The current trigger is never copied into Original merely to fill the UI.

If there is no historical evidence, the UI continues to show:

`NO ORIGINAL SIGNAL MEMORY`

instead of inventing an Original value.

## 5. Repair of later/contaminated memories
Every persisted memory is compared with earlier Feedback evidence. If a prior valid signal exists for the same move, V6.3.9.59 repairs the memory to the earlier event even if the bad memory was created by a later version/source.

The repair is not limited to V6.3.9.55/.56 source labels.

When stable Feedback `EventID` information exists, it is used to prevent an unrelated older move in the same ticker from becoming the new Original. Legacy rows without EventID use the latest contiguous meaningful signal cluster.

Original memory can remain visible for audit for up to 90 days; the much shorter Active-Signal Deep reserve rule remains separate and does not keep old closed moves permanently reserved.

## 6. Existing V6.3.9.58 protections remain
This release preserves:
- strict live `ENTRY NOW` hard gate;
- `LAST SESSION ENTRY • RECHECK AT OPEN` semantics;
- US Core Deep reserve including NVDA;
- market-balanced SMART Deep quotas;
- US-open revalidation warning;
- HK local-session freshness logic;
- selective High-Confidence Pre-Move detection;
- Continuation READY/WATCH/BLOCKED;
- Scanner / Analyze shared ticket presentation;
- visual WHY YES / WHY NOT;
- `SCAN COMPLETED` banner with Israel time.

## Upgrade / validation
No Optimizer rerun is required.

Recommended validation after upload:
1. run `MARKET DISCOVERY + SMART`;
2. verify that the `ALL` view shows both `Top Action / Decision Queue` and `Top Pre-Move Radar`;
3. confirm that every `Pre-Move HIGH` appears in the Pre-Move Top section even when its current Decision is `TOO LATE`;
4. inspect 1780.HK and verify that Original Trigger / Original T1 are restored from prior Feedback when that history exists, while Current Trigger / Current T1 remain separate.

## Files
The deployment ZIP contains exactly:
- `app.py`
- `quant_engine.py`
- `README.md`
- `requirements.txt`
