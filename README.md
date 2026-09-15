# AI Stock Hunter V5.9.9

V5.9.9 is built directly from the known-good V5.9.8 baseline and adds the agreed scanner usability upgrades while preserving the 150-stock multi-market model and V5.9.8 PM/AH logic.

## Scanner resilience and progress
- The scanner runs as a lazy server-side background job only after **Start / Restart Scan** is pressed.
- No background thread is started during app startup/deployment.
- Leaving the browser, switching apps, or locking the phone does not cancel the scan as long as the Streamlit server process remains alive.
- Reopening the app reconnects to the active in-memory scan.
- Progress shows stage, market/ticker, elapsed time and a dynamic estimated remaining time (ETA).
- The last completed scan stays available in server memory, including duration and scan counts.
- Requested / daily-success / deep-analysis / skipped-error counts are shown, with an expandable skipped/error table.
- A full Streamlit server/container restart clears the in-memory job and last-scan cache; this version does not use an external database/job queue.

## Session-aware ranking and display
- NASDAQ: PRE-MARKET → OPEN → AFTER-MARKET → CLOSED.
- Hong Kong / Tel Aviv: PRE-OPEN → OPEN → CLOSED.
- Pre-market and after-market use the existing real yfinance snapshots when available.
- Main cards no longer repeat `PRE-MARKET • PM`; they show a single status such as `PRE-MARKET: WEAKENED (-0.84%)`.
- PM/AH volume is explicitly shown as unavailable when no real volume-strength snapshot exists.
- Status colors are separated: confirmed/live = green, setup/armed/previous-session = yellow, weakened/negative = red. TOP and Opportunity numbers are neutral rather than inheriting a red status color.

## Filters and stage guide
- Show filter: ALL / TOP OPPORTUNITIES / ACTIONABLE NOW / WATCHLIST.
- ACTIONABLE NOW is restricted to a real OPEN `LIVE TRIGGERED` signal or a confirmed NASDAQ extended-hours setup that is ARMED/TRIGGER.
- After the TOP cards, a compact chronological guide explains WAIT/COLD → WATCH/BUILDING → ARMED → TRIGGER → LIVE TRIGGERED.

## LIVE TRIGGER trade levels
When the regular market is OPEN and the stock is genuinely `LIVE TRIGGERED`, the TOP card displays:
- Entry Zone
- Stop / Invalidation
- Target 1
- Target 2
- Risk/Reward to T1 and T2

Targets are now structure/ATR based, using the existing entry zone, ATR and resistance context instead of fixed +3% / +6% targets.

## Preserved from V5.9.8
- 50 NASDAQ + 50 Hong Kong + 50 Tel Aviv.
- Hong Kong universe includes `1196.HK` (Realord) and `1570.HK`.
- Real NASDAQ pre-market and after-market layers.
- TOP Score / Opportunity / Reliability layers.
- Hourly/15m deep analysis, Entry Score, Explosive/Move/Acceleration research, walk-forward validation and Excel exports.
- Mobile-friendly Plotly chart at the end of Analyze.

## Important
This remains a research prototype. TOP / Opportunity / Entry / LIVE TRIGGER labels and displayed price levels are model-derived research outputs, not guarantees or personalized investment advice. Extended-hours Yahoo/yfinance data may be delayed, missing or incomplete.
