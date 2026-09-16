# AI Stock Hunter V6.0.0 — Decision Intelligence Upgrade

V6.0.0 is a major model and UX upgrade built on the stable V5.9.9 background-scanner baseline. The goal is simpler decisions, cleaner visual hierarchy, and materially better evidence handling rather than adding more raw indicators.

## What changed

- **Direction-aware volume:** high RVOL no longer earns bullish points by itself. Volume supports Move / Explosive / Quant / Entry only when price action and money-flow context confirm accumulation. Heavy volume with falling price, weak close, VWAP/EMA/support loss or negative CMF/OBV/A-D feeds bearish distribution instead.
- **Distribution / Exit Pressure:** new 0–100 exit-risk engine with `CLEAR → EXIT WATCH → EXIT ARMED → EXIT TRIGGER`. It uses direction-aware volume, structure breakdown, money-flow deterioration, momentum weakening and persistence.
- **Movement Trigger vs Trade Trigger:** a movement trigger is no longer presented as permission to enter. Trade Trigger requires the full Opportunity + Entry + Hourly + momentum + Exit Pressure gate.
- **Entry Score V2:** continuous/smoother scoring replaces several hard 0-or-full-point jumps. Directional volume and Exit Pressure are included.
- **Validated trade-plan geometry:** EntryLow must be ≤ EntryHigh, invalidation must be below a long entry, trigger must be at/above current price, and targets must be coherent. Invalid plans are suppressed instead of displayed.
- **Confirmed intraday bars:** 15m/1h timing drops a likely unfinished final candle before confirmation calculations.
- **Time-adjusted intraday RVOL:** intraday volume compares with the same bar position in prior sessions. Deep analysis uses this for live decision context.
- **Corporate actions / splits:** cross-timeframe split-like scale mismatches are detected and normalized. Residual split-like return jumps are suppressed from momentum features. Analyze shows a Split Adjusted badge when normalization is applied.
- **LOW SAMPLE protection:** thin backtests are de-emphasized and their influence on Reliability is capped. Scanner hides fragile hit-rate percentages below the minimum sample.
- **True global scan workflow:** fixed NASDAQ / Hong Kong / Tel Aviv views scan the full 150-stock universe, then filter display. Global Rank is therefore based on all successfully analyzed stocks from the 150 requested.
- **Trade Priority Rank:** actionable hierarchy sorts by Trade Stage first and then TOP Score, while Global Rank remains a separate quality rank. Market Rank and Sector Rank are also shown.
- **PM/AH confirmation:** price-only strength is labeled `PRICE CONFIRMED • VOLUME UNAVAILABLE`; it does not receive the same confirmation boost as price + volume evidence.

## Analyze redesign

The primary hierarchy is now **Last Price → TOP Score → Opportunity → Trade Stage → Why not Trade Trigger? → supporting metrics → risk plan → chart**. Dynamic Prediction and Entry remain visible but no longer dominate the card. BUY Threshold was removed from the main decision UI; it is now an AUTO/MANUAL **Backtest Signal Threshold** under Advanced settings.

The default chart is deliberately simple: candles, last price, EMA20/EMA50 and volume with 5D / 1M / 3M / 6M / 1Y / MAX ranges. Advanced chart controls expose EMA9, VWAP, RSI and MACD. Valid Entry/Trigger/Invalidation/Targets are overlaid only when the data-quality gate passes.

## Feedback / Outcome Tracker

Every completed live scan is snapshotted into a lightweight SQLite audit store. Due 1D / 3D / 5D windows can be evaluated for end return, maximum favorable excursion (MFE), maximum adverse excursion (MAE), Target1/Target2 hits, invalidation hits and which event happened first. The Feedback tab aggregates results by stage and keeps WAIT/WATCH rows too, so false positives and false negatives can be studied.

The app **does not auto-retrain production weights from small samples**. Feedback is evidence for later walk-forward validation. Local SQLite storage is persistent only while the Streamlit host storage survives; redeploys/host resets can clear it. Use an external database in a later release for durable multi-deploy history.

## Scanner resilience preserved

The lazy background scan still starts only when requested. It can continue while the phone disconnects as long as the Streamlit server process remains alive. Progress, elapsed time, ETA, Last Completed Scan, Requested / Successful / Skipped counts and error details are preserved.

## Deployment

Replace **all four files together**: `app.py`, `quant_engine.py`, `requirements.txt`, and `README.md`. App and engine versions must both show **6.0.0**.

This is a research prototype. Scores, stages, trade levels and outcome statistics are quantitative research outputs, not guarantees or personalized investment advice. Market data may be delayed, incomplete or temporarily inconsistent.
