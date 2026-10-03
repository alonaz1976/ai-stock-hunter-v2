# AI Stock Hunter — V6.3.9.60 Persistent Last Scan + Building Setup + Common-Stock Guard

## Purpose
V6.3.9.60 is a stability / clarity release. It keeps the V6.3.9.59 decision, selective Pre-Move, strict live-entry, Continuation and Original-Signal logic, while fixing four issues exposed by the latest review:

1. the last Scanner result could disappear after a refresh/server restart;
2. `EARLY RADAR` was easy to confuse with the separate Pre-Move Radar;
3. broad discovery could admit exchange-traded debt/preferred/unit instruments such as SOJE;
4. Original-Signal memory coverage was hard to audit when historical Feedback was missing.

No Optimizer weights, Continuation thresholds, live-entry thresholds or selective Pre-Move thresholds are retuned in this release.

## 1. Persistent Last Completed Scan
The most recent **successful** Scanner snapshot is now stored inside the same portable Feedback SQLite database.

Behavior:
- reopening / refreshing the app restores the last successful Scanner result automatically;
- a new scan can run while the prior completed result remains visible below the live progress panel;
- a stopped or failed scan never overwrites the last completed snapshot;
- the saved snapshot is included in the normal Feedback DB backup and optional remote GitHub persistence flow;
- only one latest Scanner snapshot is cached, so the DB does not grow with a duplicate full workbook on every run.

The main Scanner banner now shows:

`LAST COMPLETED SCAN • DD/MM/YYYY • HH:MM:SS • ISRAEL • SAVED`

The exact completion time is calculated in `Asia/Jerusalem`. When the saved result is old, the UI also shows its age.

## 2. BUILDING SETUP replaces the confusing EARLY RADAR UI label
The internal stage value remains `EARLY RADAR` for backward compatibility with Feedback, exports and prior versions, but the human-facing UI now calls it:

`BUILDING SETUP`

The intended progression is shown clearly as:

`PRE-MOVE RADAR → BUILDING SETUP → ARMED → ENTRY NOW → RETEST / TOO LATE`

Meanings:
- **Pre-Move Radar**: abnormal accumulation / volume / absorption can appear before a normal trade setup exists;
- **Building Setup**: the trade setup itself has started forming, but is not mature enough for ARMED or ENTRY NOW;
- **Armed**: setup is mature and close to an entry window;
- **Entry Now**: live entry hard gates are satisfied.

A new `DecisionStageLabel` export gives the clearer human-facing label while the stable internal fields remain available for audit.

## 3. Common-stock-only broad discovery guard
Broad Market Discovery now rejects identifiable non-common instruments before Stage-0, including:
- exchange-traded notes / bonds / debentures;
- junior or senior subordinated notes;
- preferred / preference shares when identified as such;
- warrants, rights and units;
- ETFs / ETNs and similar listed products.

This specifically prevents cases like **SOJE — Southern Company junior subordinated notes** from consuming Pre-Move / Deep Analysis capacity as if they were an ordinary common stock.

Curated mandatory anchors remain trusted and are not removed by the public-name guard. `Discovery Audit` carries an `InstrumentType` field for admitted rows and `Scan diagnostics` states that the common-stock guard is active.

## 4. Original Signal Memory coverage audit
Scanner now reports Original-Signal memory coverage for signal-relevant names and classifies each available memory as:

- `BACKFILLED`
- `NEW`
- `PERSISTED`
- `MISSING`

New fields include:
- `OriginalMemoryStatus`
- `OriginalMemoryAvailable`

If real historical memory is missing, the system still **does not invent an Original Trigger from the Current Trigger**.

For historical cases such as 1780.HK where the live Feedback DB no longer contains the early event, prior Scanner XLSX files can be imported once from:

`Feedback → Import prior Scanner workbooks`

The existing event-aware backfill can then reconstruct the earliest real signal from those imported snapshots. The Scanner shows a guidance note whenever relevant memory remains missing.

## 5. Existing protections retained
V6.3.9.60 preserves:
- dual Top Action / Top Pre-Move queues;
- HIGH / WATCH selective Pre-Move model;
- strict live `ENTRY NOW` hard gate;
- `LAST SESSION ENTRY • RECHECK AT OPEN` semantics;
- Core Deep reserve including NVDA;
- active Original-Signal Deep reserve;
- market-balanced SMART Deep quotas;
- HK local-session freshness logic;
- Continuation READY / WATCH / BLOCKED;
- Original Trigger vs Current Trigger separation;
- visual WHY YES / WHY NOT;
- Momentum 15m / 1H display;
- glowing scan-completion banner with exact Israel time.

## Upgrade / validation
No Optimizer rerun is required.

Recommended validation after upload:
1. open Scanner before running anything and verify the saved last completed result restores automatically after a restart/refresh;
2. start a new scan and confirm the prior result stays visible while the new scan runs;
3. confirm the Decision filter says `BUILDING SETUP`, not `EARLY RADAR`;
4. run `MARKET DISCOVERY + SMART` and confirm exchange-traded note names such as SOJE are absent from Discovery/Deep results;
5. inspect `Original Signal Memory` coverage and import older Scanner XLSX files in Feedback if 1780.HK is still `MISSING`.

## Files
The deployment ZIP contains exactly:
- `app.py`
- `quant_engine.py`
- `README.md`
- `requirements.txt`
