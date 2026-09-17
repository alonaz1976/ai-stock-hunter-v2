# AI Stock Hunter V6.0.5 — Stale Quote Hard Gate

V6.0.5 is an urgent correctness hotfix on top of V6.0.4. It fixes the case where a provider returned an old pre-split intraday bar (for example 1196.HK at 10.85 from 11-Sep) and the app displayed it as the current online price on 17-Sep.

## Critical rule: stale intraday can never become live price

- Analyze now tries current-session **1m**, then **5m**, then normalized confirmed **15m**, then **1H**.
- A bar whose local market date is not today is rejected as a live-price candidate even if it is the newest bar returned by the provider.
- During an OPEN market, if no trustworthy current-session intraday bar exists, the app shows **Last official close** and a red **LIVE PRICE UNAVAILABLE** warning. It does not label an old bar as Intraday price.
- Live day-change, `LIVE TRIGGER` and `ActionableNow` are blocked until a trustworthy current-session price is available.
- Rejected stale provider bars remain visible only as diagnostics in the warning/export (`StaleProviderPrice`, `StaleProviderTimestamp`).

## Split / corporate-action protection

- A stale/prior-session quote is never allowed to anchor cross-timeframe normalization.
- A fresh quote that is dramatically off the latest Daily scale is also prevented from becoming the anchor unless explicit recent split metadata can safely reconcile the scale.
- With known split metadata, a current quote can be normalized to the post-split Daily scale without double-adjusting already-correct data.
- Daily / 1H / 15m continue to use the V6.0.4 corporate-action normalization and the hard `DataQuality=MISMATCH` Trade Plan gate.

## Scanner

- Scanner no longer treats the newest 15m/1H bar as current merely because it exists.
- During an open market, the intraday price must be from the current local market date and pass the freshness gate. Otherwise `LivePriceFresh=False`, live confirmation is blocked, and `PriceSource` explains the fallback.
- No extra 1m/5m request is added to every scanned stock, preserving scan speed/provider load.

## Existing functionality retained

- All V6.0.3 background Start/Stop upgrades.
- V6.0.4 corporate-action normalization.
- Quant threshold is research-only, not a live buy threshold.
- Direction-aware Volume, Exit Pressure, Evidence Quality and Feedback/Outcome Tracker.

## Deployment

Replace all four files together:

- `app.py`
- `quant_engine.py`
- `requirements.txt`
- `README.md`

The app and quant engine must both show **V6.0.5**.

Market data is provider-delayed and may be incomplete. The application explicitly blocks live confirmation when a trustworthy current-session quote is unavailable.
