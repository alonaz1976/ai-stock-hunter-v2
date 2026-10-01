# AI Stock Hunter — V6.3.9.55 Pre-Move Accumulation + Original Signal Memory

## What this version is for
V6.3.9.55 is focused on finding a move **before** the obvious breakout, while preserving the original signal so a new session trigger cannot make an old move look young again. It also carries forward the Scanner/Analyze visual and decision-board work from V6.3.9.54.

## 1. New PRE-MOVE Accumulation Radar
- Adds a dedicated **Pre-move Radar** layer to both Scanner and Analyze.
- Looks for a participation/volume-regime change before price expansion:
  - abnormal volume shock vs a robust prior baseline;
  - limited price movement on the shock day (absorption candidate);
  - persistent elevated volume after the shock;
  - price retention / higher lows;
  - optional CMF / OBV / A-D confirmation.
- Output is explicit and auditable: `PreBreakoutAccumulationScore`, stage, reason, shock ratio/date/return, regime ratio, persistence ratio, price retention, higher-low count and absorption flag.
- **Important:** this is a discovery/radar layer, not a buy signal. It cannot bypass Entry, R:R, Chase, Timing, Evidence or data-quality gates.
- Once the recent 5-day price move is already about 8%+, accumulation evidence remains visible for context but is labelled **ACCUMULATION PERSISTS • MOVE ALREADY EXTENDED** rather than pretending the setup is still early.

### 1780.HK replay sanity check
Using the Daily history already exported by V6.3.9.54, the new causal detector would have produced approximately:
- **15-Sep-2026:** Pre-move score **64/100 — PRE-BREAKOUT ACCUMULATION** while the close was about **4.585**. The dominant signal was a roughly **51× volume shock** versus the robust prior baseline with only about **+1.2%** daily price change.
- **17-Sep-2026:** score about **82/100 — STRONG PRE-BREAKOUT ACCUMULATION** while the close was about **4.535**, before the later run toward the mid/high 5s.
This replay is a design sanity check on one known case, not proof of predictive accuracy; Forward/OOS outcome collection remains required.

## 2. Discovery funnel now protects early-volume shocks
The new pattern is useful only if the broad scanner lets the stock reach Deep Analysis.
- MARKET DISCOVERY now gives a dedicated Stage-0 priority lane to the strongest relative-volume names and to abnormal `VolumeRatio >= 3x` names (turnover-ranked cap).
- Stage-1 computes the causal Pre-Move accumulation detector from Daily history for every Stage-0 candidate.
- A fresh Pre-Breakout candidate gets a **Deep-analysis selection boost only**. This does not change its final trade score and does not make it actionable by itself.
- `DiscoveryEarlyVolumePriority` is retained in Discovery Audit so later misses can be investigated.

## 3. Persistent Original Signal / Original Trigger
Daily/session triggers remain useful for current timing, but they no longer erase the beginning of the move.
- New persistent `signal_memory` table stores the first meaningful signal of the current move.
- Scanner + Analyze now separate:
  - **Original Signal** — the first radar/armed/entry observation;
  - **Original Trigger → T1** — progress of the move we originally identified;
  - **Current Trigger → T1** — current-session/reconfirmation progress.
- If the first observation is radar-only, the memory later locks the **first causal trigger and T1** when they become available; it never resets them every day.
- Existing recent Feedback snapshots are backfilled when possible.
- The original move memory closes when it is invalidated **or reaches Original T1**, allowing a genuinely new move to start its own memory.

## 4. Feedback / future validation
Scanner snapshots now persist the new Pre-Move and Original-Signal fields so they can be evaluated after 1D / 3D / 5D instead of being judged from screenshots alone. This prepares a clean future comparison of:
- EARLY RADAR / Pre-Move Accumulation;
- PRIMARY ENTRY;
- CONTINUATION READY;
- RETEST.
No Optimizer weights were changed in this version.

## 5. 1196.HK ↔ 2922.HK session-reference hardening
- During the temporary/reopened HK counter bridge, Scanner and quote fallbacks now derive the previous-close reference from the **same provider counter and scale** as the current price.
- Closed/weekend/holiday scans anchor that lookup to the latest completed exchange session, not simply the calendar date.
- Stitched logical history remains available for indicators; session-return math no longer needs to borrow a mismatched historical reference when the provider counter is available.

## 6. Existing V6.3.9.54 UI retained
- Unified Scanner + Analyze ticket.
- Visual **WHY YES** (green) and **WHY NOT / RISKS** (red/orange).
- Momentum aggregate + 15m + 1H.
- Continuation state and entry-path explanation.
- Action Queue rank integrity.
- Compact scan summary with technical diagnostics hidden by default.
- Bright green **SCAN COMPLETED** banner with exact **Asia/Jerusalem** completion time including seconds.
- Closed/holiday session display semantics remain separate from a live `ENTRY NOW` instruction.

## Version
- App version: **6.3.9.55**
- Engine version: **6.3.9.55**
- Build: `V63955-PREMOVE-ACCUMULATION-ORIGINAL-SIGNAL-20261002-A`
- Package contract: exactly `app.py`, `quant_engine.py`, `README.md`, `requirements.txt`.

## Upgrade notes
- No Optimizer rerun is required for this upgrade.
- Keep the existing Feedback SQLite DB if available; V6.3.9.55 migrates it in place and uses recent snapshots to recover Original Signal memory when possible.
- After deployment, the recommended verification run is **MARKET DISCOVERY + SMART**. Review EARLY RADAR candidates and the `Discovery Audit` worksheet, then use 1D/3D/5D outcomes to validate whether the new Pre-Move layer adds lift before changing thresholds or weights.
