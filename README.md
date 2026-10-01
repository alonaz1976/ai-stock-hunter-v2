# AI Stock Hunter — V6.3.9.56 Selective Pre-Move + Active Signal Reserve

## What this version fixes
V6.3.9.56 hardens the new early-detection layer introduced in V6.3.9.55. The goal is to keep the 1780-style advantage — identifying abnormal participation before the obvious price move — while preventing raw volume anomalies from turning almost every Deep candidate into an accumulation signal.

## 1. Raw Accumulation is no longer the same as a confirmed Pre-Move
The live detector now separates four states:
- **HIGH-CONFIDENCE PRE-MOVE** — rare, multi-family confirmation.
- **PRE-MOVE WATCH** — promising, but still missing one or more independent confirmations.
- **RAW ACCUMULATION** — useful evidence for audit/research only; it cannot promote a ticker by itself.
- **ACCUMULATION PERSISTS • MOVE ALREADY EXTENDED** — accumulation evidence remains visible after the move is no longer early.

A giant volume ratio alone is never enough for HIGH-CONFIDENCE PRE-MOVE.

## 2. Independent-family confirmation
HIGH-CONFIDENCE PRE-MOVE requires agreement across independent evidence families rather than multiple correlated volume metrics:
1. **Volume shock / regime change**
2. **Absorption or a verified recovery after a negative shock**
3. **Price structure / retention / higher lows**
4. **Flow + momentum confirmation**
5. **Persistence** is an additional supporting family and can strengthen the signal

The card and Excel now expose the family count/signature so the reason is auditable.

## 3. Baseline + liquidity guard and shock normalization
V6.3.9.55 could over-reward ratios such as 100x–500x when the historical volume denominator was tiny.
V6.3.9.56 therefore adds:
- minimum baseline-volume and baseline-turnover quality checks;
- an **effective volume-shock cap** so a 544x observation is not treated as dozens of times stronger than a genuine 10x shock;
- separate raw and effective shock evidence in the audit fields.

These are denominator-quality safeguards. They are not personal trade-liquidity recommendations.

## 4. Large red shock days need recovery evidence
A high-volume day with a sharp negative return is no longer allowed to look like classic absorption merely because volume is huge.
- A roughly -5% to -8% shock needs explicit recovery/retention evidence.
- A very large negative shock receives a strong penalty until the price recovers and forms constructive structure/higher lows.

This is intended to prevent cases such as a large selloff from receiving the same label as a 1780-style high-volume absorption day.

## 5. Selective Deep priority
Stage-0 Discovery can remain broad and sensitive, but expensive Deep Analysis is now more selective:
- **HIGH-CONFIDENCE PRE-MOVE** receives strong Deep-selection priority.
- **PRE-MOVE WATCH** receives only a moderate nudge.
- **RAW ACCUMULATION** receives no automatic Deep boost.

The detector remains a radar layer. It never bypasses Entry, R:R, Chase, Timing, Evidence or data-quality gates.

## 6. Active Original Signal → reserved Deep Analysis
A stock already identified by the system must not disappear only because newer names outrank it in the SMART quota.
V6.3.9.56 adds an active-signal reserve:
- active Original Signals are re-added to Stage-0 if necessary;
- they receive a **reserved Deep slot** until Original T1, invalidation, or expiry;
- recent Feedback snapshots are used as a migration/backfill path for signals created before the `signal_memory` table existed;
- Discovery Audit adds `ReservedActiveOriginalSignal` and records active-memory rows even when a broad provider does not return the ticker.

This directly addresses the V6.3.9.55 case where 1780.HK was visible in broad discovery but could still be cut by the SMART depth quota.

## 7. Original Signal memory is stricter
V6.3.9.55 could start persistent memory from raw accumulation evidence. V6.3.9.56 starts a new move memory only from a meaningful decision-stage signal, continuation signal, research Pre-Move candidate, or **HIGH-CONFIDENCE PRE-MOVE**.
Raw accumulation alone no longer creates long-lived move memory.

## 8. EARLY RADAR is more selective
The live EARLY RADAR logic now gives the large boost only to **HIGH-CONFIDENCE PRE-MOVE**. PRE-MOVE WATCH can contribute with supporting entry/live evidence; RAW ACCUMULATION is only a small contextual input and cannot promote a ticker by itself.

## 9. New audit / Feedback fields
Scanner/Analyze/Feedback now carry fields including:
- `PreMoveConfirmed`
- `PreMoveConfidenceTier`
- `PreMoveFamilyCount`
- `PreMoveFamilySignature`
- `PreMoveBaselineGuardOK`
- `PreMoveBaselineVolume`
- `PreMoveBaselineTurnover`
- `EffectiveVolumeShockRatio`
- `PreMoveShockRecoveryOK`
- `PreMoveFlowConfirmation`
- `PreMoveMomentumConfirmation`

These fields are persisted for future 1D / 3D / 5D validation.

## Existing improvements retained
- Market Discovery across US / Hong Kong / Tel Aviv.
- Unified Scanner + Analyze ticket.
- Visual **WHY YES / WHY NOT** block.
- Momentum aggregate + 15m + 1H.
- PRIMARY / CONTINUATION / RETEST entry paths.
- Persistent Original Signal / Original Trigger → T1 and Current Trigger → T1.
- Action Queue rank integrity.
- Bright green **SCAN COMPLETED** with exact Asia/Jerusalem completion time.
- 1196.HK ↔ 2922.HK session-reference hardening.

## Version
- App version: **6.3.9.56**
- Engine version: **6.3.9.56**
- Build: `V63956-SELECTIVE-PREMOVE-ACTIVE-SIGNAL-RESERVE-20261002-A`
- Package contract: exactly `app.py`, `quant_engine.py`, `README.md`, `requirements.txt`.

## Upgrade notes
- **No Optimizer rerun is required.** No trained weights were changed.
- Keep the existing Feedback SQLite DB if available. The app migrates it in place and uses recent snapshots to recover active Original Signals where possible.
- Recommended verification: run **MARKET DISCOVERY + SMART**, then inspect how many candidates are `HIGH-CONFIDENCE PRE-MOVE`, `PRE-MOVE WATCH`, and `RAW ACCUMULATION`, and confirm that previously active signals remain in Deep Analysis.
