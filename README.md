# AI Stock Hunter — V6.3.9.62 Analyze Feedback + Decision Outcome Validation

## Purpose
V6.3.9.62 builds on V6.3.9.61 without changing Optimizer weights, Pre-Move thresholds, Continuation thresholds, Ranking weights or live-entry thresholds. The release closes the Feedback gap between Scanner and Analyze and makes the model evaluate the **recommendation that was actually shown** against what happened later.

## 1. Analyze now saves Feedback automatically
Every completed Analyze run now writes one snapshot into the same portable Feedback SQLite DB used by Scanner.

- `snapshot_source = ANALYZE`
- deterministic EventID uses the same causal setup/session rules as Scanner;
- repeated Analyze runs for the same event overwrite one Analyze event row;
- if Scanner already captured the same event, Analyze is stored as `TRACKING`;
- if Analyze was first, it can be the `ORIGIN` and the later Scanner observation becomes tracking;
- ORIGIN-only learning therefore prevents Scanner + Analyze from double-counting the same market event.

Analyze displays a small audit line after completion showing whether its Feedback snapshot was saved, EventID and ORIGIN/TRACKING role. The Analyze Excel also contains Feedback snapshot metadata.

## 2. Recommendation-aware Feedback
Snapshots now persist the decision that existed at the time of analysis:

- `DecisionDisplayStage`
- `EffectiveDecisionStage`
- `RecommendationType`
- `RecommendationText`
- `EntryPath`
- `ContinuationEntryState`
- `RetestStatus`
- `PreMoveRadarStatus`

This lets Feedback separate the model's recommendation from later price outcomes instead of judging every event only as a generic trade.

## 3. Decision Outcome Validation
Feedback adds a new **Decision Outcome Validation** table by recommendation, entry path and 1D/2D/3D/5D horizon. It reports:

- independent Event N;
- Target1-before-Invalidation rate;
- realized +3% MFE hit rate;
- realized +5% MFE hit rate;
- realized +10% MFE hit rate;
- average MFE;
- average MAE;
- average end return.

Interpretation remains stage-aware:

- `ENTRY NOW` / `CONTINUATION READY`: trade audit focuses on Target1-first plus MFE/MAE;
- `ARMED`: checks whether a meaningful move followed readiness;
- `BUILDING SETUP`: checks whether early setup observations led to +3%/+5% movement;
- `TOO LATE`: explicitly measures false negatives — how often price still added +3%/+5%/+10% after the warning;
- `RETEST`: current table shows MFE/MAE as an audit proxy; exact pullback-before-continuation sequencing remains research/audit only until sufficient intraday outcome history is available.

The table is shown in Feedback and exported to the Feedback workbook as `Decision Outcome Validation`.

## 4. Scanner + Analyze source audit
Feedback now displays and exports `Feedback Source Audit`, showing Scanner vs Analyze and ORIGIN vs TRACKING counts. This makes duplicate-control visible instead of implicit.

## 5. Original Trigger progress display
When the Original Trigger → T1 path reaches or exceeds 100%, the shared Scanner/Analyze ticket no longer shows a confusing value such as `100.4%` as the headline. It displays:

`TARGET REACHED • 100%+`

The exact percentage is still retained in audit/details/Excel.

## 6. Existing V6.3.9.61 behavior retained
V6.3.9.62 retains:

- persistent Last Completed Scan + exact Israel completion time;
- BUILDING SETUP canonical naming;
- qualified ARMED vs ARMED BLOCKED;
- 1780.HK verified Original Signal migration;
- Top Action + Top Pre-Move separation;
- selective Pre-Move HIGH/WATCH model;
- common-stock discovery guard;
- strict live ENTRY NOW gate and LAST SESSION semantics;
- market-balanced SMART Deep quotas and Core reserve;
- Continuation READY / WATCH / BLOCKED;
- Original Trigger vs Current Trigger separation;
- Scanner/Analyze shared ticket, Momentum 15m/1H and WHY YES / WHY NOT.

## Validation after upload
No Optimizer rerun is required.

Recommended validation:
1. Run one Analyze on a ticker that is also present in the latest Scanner result.
2. Open Feedback and confirm the Analyze snapshot is visible with `snapshot_source = ANALYZE`.
3. Confirm the same EventID is not counted twice as independent ORIGIN observations.
4. After outcomes mature, inspect `Decision Outcome Validation` for +3/+5/+10, Target1-first, MFE and MAE by recommendation.
5. On 1780.HK, confirm Original progress displays `TARGET REACHED • 100%+` while Current Trigger progress remains independent.

## Files
The deployment ZIP contains exactly:
- `app.py`
- `quant_engine.py`
- `README.md`
- `requirements.txt`
