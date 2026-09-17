# AI Stock Hunter V6.0.3 — Unified Background Runs + Logic Cleanup

V6.0.3 extends the Scanner/Research background-job model to every run-oriented tab and applies the logic/clarity fixes agreed after the V6.0.1 scan and 1570.HK Analyze reviews.

## Background / Stop controls across the app

Server-side Start/Stop execution now covers:

- Analyze
- Scanner
- Historical Quant Backtest
- Walk-Forward Validate
- Entry Validation
- Explosive Lab
- Research
- Feedback outcome refresh

A running job continues if the phone switches to another app or the browser tab is backgrounded, as long as the Streamlit server process remains alive. Stop is cooperative: the current provider/calculation step finishes safely before the job stops. Progress, elapsed time and ETA are shown for long-running jobs. Validate, Entry and Research preserve partial completed work when stopped and can export partial results.

This is still an in-memory server worker, not a durable external queue. A Streamlit host restart, sleep or redeploy can terminate an active job.

## Live-decision logic cleanup

- **Quant is no longer a standalone live entry threshold.** The old `Quant >= 66` requirement was removed from `entry_timing()`.
- **Historical Quant Threshold is research-only.** It is no longer exposed as a live Scanner/Analyze buy control. The Backtest tab explicitly labels it as historical research evidence, not Top Score and not Trade Trigger.
- **Trade Trigger remains multi-factor:** Opportunity, Entry Timing, Hourly confirmation, momentum/acceleration, direction-aware volume, Exit Pressure, valid plan geometry and data-quality gates.
- **DataQuality mismatch hard-blocks the Trade Plan.** `PlanValid` is forced false and Entry/Trigger/Invalidation/Targets are suppressed until cross-timeframe consistency passes.
- **Plan geometry remains validated:** long EntryLow ≤ EntryHigh, invalidation below entry, future trigger at/above current price, targets coherent.

## Evidence / score clarity

- `Prediction` is labeled **Prediction Score** so it is not mistaken for a probability.
- TOP/Analyze views add **Evidence Quality: STRONG / MEDIUM / LOW** based on sample size, Reliability and calibration confidence.
- Backtest success is shown beside risk, including **worst historical drawdown**.
- Tiny samples remain de-emphasized; hit-rate percentages are not treated as strong evidence when sample size is insufficient.
- Dynamic superiority is not assumed from tiny holdout samples.

## RVOL clarity

V6.0.3 separates:

- **Live Intraday RVOL** — time-of-day adjusted intraday participation.
- **Daily Robust RVOL** — daily robust/median-relative volume context.

They are shown and exported separately so a low live intraday reading cannot look contradictory next to a high daily robust reading.

## Exit Pressure refinement

- `EXIT WATCH` is explicitly an **early warning, not a sell signal**.
- Numeric Exit Pressure thresholds remain unchanged, but `EXIT ARMED` and `EXIT TRIGGER` now require stronger persistence plus distribution/structure/flow confirmation.
- One red high-volume candle alone cannot escalate directly into a high-confidence exit stage.
- Direction-aware volume remains the rule: high volume receives bullish credit only when price/flow confirms accumulation; bearish high-volume evidence feeds Distribution / Exit Pressure instead.

## Corporate actions / outliers

- Daily / 1H / 15m split-like scale mismatches continue to be normalized before timing calculations.
- Remaining cross-timeframe mismatches block Trade Plan output.
- Extreme one-day research events are flagged `OUTLIER REVIEW` and excluded from dynamic component calibration above the robust anomaly cap, reducing contamination from corporate actions/data anomalies.

## Feedback Tracker improvements

The Feedback tab now also runs server-side with Stop. It shows:

- Snapshots
- Evaluated windows
- Pending 1D
- Pending 3D
- Pending 5D
- Approximate next evaluation window

Outcome tracking still measures end return, MFE, MAE, target/invalidation hits and first event. It does **not** auto-retrain production weights from small samples.

## Scanner / ranking behavior

For fixed NASDAQ / Hong Kong / Tel Aviv views, the Scanner still scans the complete 150-stock universe and only filters the display afterward. Therefore:

- Global Rank = ranking across all successfully analyzed stocks from the 150 requested.
- Market Rank = ranking within that exchange.
- Trade Priority Rank = stage-first trade priority, separate from global quality rank.

## Deployment

Replace **all four files together**:

- `app.py`
- `quant_engine.py`
- `requirements.txt`
- `README.md`

The app and quant engine must both show **V6.0.3**.

This is a quantitative research prototype. Scores, stages, trade levels, backtests and outcome statistics are research outputs, not guarantees or personalized investment advice. Market data can be delayed, incomplete or temporarily inconsistent.
