# AI Stock Hunter V6.0.4 — Live Price + Split Normalization Hotfix

V6.0.4 is an urgent market-data correctness hotfix on top of V6.0.3. It keeps all V6.0.3 background/Stop controls and logic cleanup, and fixes the Analyze price/session issue exposed by 1196.HK after its September 2026 share subdivision.

## Critical live-price fix

Analyze no longer uses the newest Daily row as if it were the current online price.

- The Decision Cockpit now fetches a fresh **5-minute intraday provider price**.
- Day change is calculated against the prior trading-session close from intraday history, with a Daily fallback only when necessary.
- The UI shows the intraday timestamp and quote age.
- Market data is explicitly labeled as **provider-delayed**, not exchange-direct real time.
- During an OPEN market, if today's intraday quote is older than the freshness gate, the app shows **STALE DATA**, suppresses the live day-change, and prevents `ActionableNow` from being treated as confirmed.
- Closed-bar Daily features remain Daily features; the hotfix does not overwrite historical Daily candles with the current intraday price.

This prevents a previous Daily close such as 3.09 from being displayed with an old positive Daily return while the current intraday market is materially lower.

## Corporate-action / split hotfix

V6.0.4 adds a second corporate-action layer around the existing residual split guard:

- Best-effort recent split metadata is requested from the market-data provider.
- A fresh 5-minute price can be used as the **current price-scale anchor** for Daily / 1H / 15m consistency checks.
- Known split ratios and generic split-like factors are used to normalize clear multiplicative scale mismatches.
- If provider frames are already correctly adjusted, the app reports the recent corporate action without double-adjusting them.
- If an unexplained 1H / 15m mismatch remains after normalization, `DataQuality=MISMATCH`, `PlanValid=False`, and Entry / Trigger / Invalidation / Targets stay suppressed.
- Analyze export now records quote source/time/freshness, previous close, split detection/ratio/date, and data-quality details.

For Realord Technology (1196.HK), the Hong Kong Exchange announced a **1-into-4 share subdivision effective 14 September 2026**. V6.0.4 is designed to avoid interpreting mixed pre/post-subdivision provider scales as genuine price movement.

## Scanner

The Scanner retains the V6.0.3 full-150 ranking behavior. For deep-analysis finalists, the displayed price now prefers the latest confirmed 15m/1H price after scale normalization instead of always showing the Daily close. The Scanner does not add a separate 5-minute request for every one of the 150 stocks, to avoid materially increasing scan time/provider load.

## Existing V6.0.3 functionality retained

- Server-side Start / Stop: Analyze, Scanner, Backtest, Validate, Entry Validation, Explosive Lab, Research, Feedback.
- Background jobs continue when the phone/browser is backgrounded while the Streamlit server process remains alive.
- Quant is research evidence, not a standalone live buy threshold.
- Direction-aware Volume and Exit Pressure.
- Evidence Quality (STRONG / MEDIUM / LOW).
- Live Intraday RVOL vs Daily Robust RVOL labels.
- EXIT WATCH is an early warning, not a sell instruction.
- Trade Plan geometry and DataQuality hard gates.
- Feedback / Outcome Tracker with 1D / 3D / 5D windows.

## Deployment

Replace **all four files together**:

- `app.py`
- `quant_engine.py`
- `requirements.txt`
- `README.md`

The app and quant engine must both show **V6.0.4**.

This is a quantitative research prototype. Scores, stages, trade levels, backtests and outcome statistics are research outputs, not guarantees or personalized investment advice. Provider market data can be delayed, incomplete or temporarily inconsistent.
