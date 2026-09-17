# AI Stock Hunter V6.0.6 — Current Quote Fallback

V6.0.6 builds on V6.0.5 and fixes the remaining current-price gap: when Yahoo intraday history temporarily lags (notably around a split/corporate action), Analyze now tries additional quote paths before falling back to the last official close.

## Current-price fallback chain

Analyze now tries, in order:

1. Yahoo 1-minute current-session bars
2. Yahoo 5-minute current-session bars
3. Yahoo direct quote endpoint (`regularMarketPrice` + `regularMarketTime`)
4. Yahoo quote/history metadata (`regularMarketPrice` + `regularMarketTime`)
5. Yahoo quote info (`regularMarketPrice` + `regularMarketTime`)
6. TradingView scanner as a display-only fallback when the price scale is plausible
7. Only then: Last official close

A prior-session intraday bar can never be promoted to today's current price.

## Display price vs trade-grade freshness

V6.0.6 deliberately separates two concepts:

- **Current / delayed price** — may be shown in the Decision Cockpit as a useful market-price reference.
- **Trade-fresh price** — sufficiently fresh and timestamp-verified to enable `LIVE TRIGGER` / `ActionableNow`.

A TradingView fallback without a provider trade timestamp may be displayed, but it can never enable live-trade confirmation or anchor split normalization. The UI explicitly labels such a quote as delayed/unverified.

## Split / corporate-action safety retained

- Old pre-split bars remain rejected as live prices.
- Only timestamp-verified current-session quotes may anchor cross-timeframe normalization.
- Known split metadata is used to reconcile quote scale with adjusted Daily data.
- Unexplained cross-timeframe mismatches still force `PlanValid=False` and suppress Trade Plan levels.

## Scanner

The full 150-stock scan remains lightweight. For deep-analysis finalists, the richer current-quote fallback is invoked only when current-session 15m/1H data is unavailable.

## Existing functionality retained

- Background Start / Stop across the computational tabs.
- Direction-aware Volume and Exit Pressure.
- Evidence Quality and Feedback / Outcome Tracker.
- Quant threshold remains research-only, not a live buy threshold.
- Corporate-action normalization and hard data-quality gates.

## Deployment

Replace all four files together:

- `app.py`
- `quant_engine.py`
- `requirements.txt`
- `README.md`

The app and quant engine must both show **V6.0.6**.

Market data can be delayed or temporarily unavailable. The UI now prefers a clearly labelled current/delayed quote over silently showing an old intraday print, while keeping live-trade confirmation behind the stricter freshness gate.
