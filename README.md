# AI Stock Hunter V6.0.8 — HK Temporary Counter Live-Quote Fix

V6.0.8 fixes a corporate-action edge case exposed by 1196.HK. HKEX replaced the old-share counter 1196 with temporary counter 2922 after the 1-into-4 subdivision effective 14-Sep-2026. Querying 1196 for a current quote can therefore return the last old-counter print (for example the split-adjusted 11-Sep value) instead of today's traded price.

## Fix
- Historical/research symbol stays 1196.HK.
- Current-price discovery checks the active HKEX temporary counter first (2922.HK for 1196.HK during the published temporary/parallel-trading window), then the permanent symbol.
- The alias is applied across Yahoo 1m/5m, Yahoo quote endpoints, and TradingView fallback.
- The Decision Cockpit explicitly says when a current quote came from an HKEX temporary counter.
- Stale old-counter prints remain unable to enable LIVE TRIGGER / Actionable Now.
- All V6.0.7 runtime helper restorations and V6.0.6 current-quote fallback logic are retained.

## Deploy
Replace all four files together: `app.py`, `quant_engine.py`, `requirements.txt`, `README.md`. Both app and engine must show V6.0.8.
