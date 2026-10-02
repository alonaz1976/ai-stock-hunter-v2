# AI Stock Hunter — V6.3.9.57 Session + Original Memory + Pre-Move Integrity

## Purpose
V6.3.9.57 is an integrity release. It does **not** retune the optimizer or loosen entry thresholds. It fixes the meaning of Original vs Current Trigger, hardens local-market session freshness, separates a strong Pre-Move pattern from an actionable early entry, and exports the audit fields needed to validate these layers over 1D / 3D / 5D.

## 1. Original Trigger is now truly historical and locked
The previous implementation could initialize `OriginalTriggerPrice` from the same current-session trigger used by `Current Trigger`, which made the two percentages identical and could make a mature move look young again.

V6.3.9.57 enforces these rules:
- `Original Signal` comes only from persisted signal memory or a real historical Feedback snapshot.
- `Original Trigger` is the **first causal trigger attached to that original move** and is locked once.
- `Original T1` is locked with that trigger snapshot and is not re-priced every session.
- `Current Trigger` and `Current T1` remain dynamic and may change each session/reconfirmation.
- If no historical memory exists yet, the UI/export shows `NO ORIGINAL SIGNAL MEMORY`; it never copies Current into Original just to fill the tile.
- A newly detected signal is persisted **after** the completed snapshot, so it becomes a historical Original reference on the next scan.

New audit fields include:
- `OriginalSignalId`
- `OriginalMemoryIntegrity`
- `OriginalTriggerLocked`
- `OriginalEqualsCurrentTrigger`
- `CurrentTriggerPrice`
- `CurrentTriggerTime`
- `CurrentTarget1`
- `CurrentProgressToT1Pct`

The old misleading export label `SinceOriginalTriggerPct` is replaced by `SinceCurrentTriggerPct` where the value is based on the live/current trigger.

## 2. Original vs Current display
Scanner and Analyze now keep two independent timelines:

**Original move**
`Original Signal → Original Trigger → Original T1`

**Current session / reconfirmation**
`Current Trigger → Current T1`

The card explicitly says `NO ORIGINAL SIGNAL MEMORY` if a historical original is not available. If a Current Trigger exists in that case, the UI states that it is deliberately kept separate and is not copied into Original.

## 3. Pre-Move pattern strength is not the same as actionable now
The selective V6.3.9.56 detector remains intact, but V6.3.9.57 adds a second layer:
- `PreMovePatternStrength` — HIGH / WATCH / RAW / EXTENDED / NONE
- `PreMoveActionableNow` — strict live boolean
- `PreMoveActionabilityState`
- `PreMoveActionabilityReason`

A `HIGH-CONFIDENCE PRE-MOVE` pattern is green/actionable only when timing, data freshness, chase, recent-run and decision-board gates still say the move is early. A strong historical accumulation signature can therefore remain visible while being labeled **NOT ACTIONABLE NOW** if the price has already become extended or TOO LATE.

This prevents a stock with a strong 1780-style accumulation history from being presented as a fresh early entry after the early window has passed.

## 4. Local-exchange session integrity
Session freshness is checked against the **local cash-market calendar**. For Hong Kong the audit source is explicitly:

`HKEX LOCAL CASH MARKET (NOT STOCK CONNECT)`

Stock Connect closures are not treated as HKEX local cash-market holidays. Freshness now requires the latest required session date to match the expected local-exchange session date exactly. During an open market, a verified same-session intraday/live observation can confirm session freshness even when the provider's daily endpoint has not yet printed its partial daily candle.

New audit fields:
- `SessionCalendarSource`
- `SessionCalendarReason`
- `SessionFreshnessVerified`

Stale/unverified data remains a decision/actionability veto rather than being silently treated as current.

## 5. Active Original Signal reserve remains enabled
A stock with an active persisted Original Signal continues to receive reserved Deep-analysis coverage until Original T1, invalidation or expiry. This protects tracked moves from disappearing solely because of SMART depth quotas.

An inactive/closed Original memory is not resurrected by historical backfill. A later genuinely new setup can create a new Signal ID.

## 6. Scanner / Analyze audit parity
The dedicated `Early Entry Snapshot` and `Decision Intelligence` sheets now expose the selective Pre-Move evidence and actionability fields instead of relying only on the full Scanner Results sheet.

Analyze exports also receive the same Original/Current memory integrity, Pre-Move actionability and session-calendar fields used by Scanner.

## 7. Why Yes / Why Not semantics
`WHY YES` shows a Pre-Move item in green only when it is **Actionable Pre-Move Now**. A high-confidence pattern that is no longer early is shown under `WHY NOT / RISKS` with the veto reason.

`Original Trigger → T1` and `Current Trigger → T1` use separate values. The Original tile also displays memory integrity so a persisted/backfilled historical reference can be distinguished from `NO MEMORY`.

## 8. What did not change
- No optimizer rerun is required.
- Core scoring weights were not retuned.
- Continuation thresholds were not loosened.
- V6.3.9.56 selective Pre-Move family logic remains in place.
- Existing Decision Board, Continuation, Why Yes / Why Not, ranking and Scan Completed UI remain available.

## Recommended validation after upload
1. Run `MARKET DISCOVERY + SMART`.
2. Check that HK session freshness uses the HKEX local-market calendar and does not reference Stock Connect.
3. Inspect a tracked name such as 1780.HK: Original and Current Trigger should only match when they genuinely are the same historical price, not because of fallback copying.
4. On a ticker with no historical memory, verify `NO ORIGINAL SIGNAL MEMORY` while Current Trigger still displays normally.
5. Compare `HIGH-CONFIDENCE PRE-MOVE` with `PreMoveActionableNow` and confirm already-extended names are retained as pattern context rather than fresh early-entry signals.
6. Send the Scanner Excel so 1D/3D/5D validation can continue without changing weights from a single case.
