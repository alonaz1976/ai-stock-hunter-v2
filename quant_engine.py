from __future__ import annotations
import math
import numpy as np
import pandas as pd
import yfinance as yf
import json as _json
import urllib.request as _urlrequest
import urllib.error as _urlerror
import urllib.parse as _urlparse

ENGINE_VERSION = "6.0.8"
ENGINE_BUILD_ID = "V608-HK-TEMP-COUNTER-LIVE-QUOTE-20260917-A"

def get_engine_version():
    return ENGINE_VERSION



# HKEX temporary trading counters created during corporate actions.
# Keep the permanent ticker for history/research, but route CURRENT quote lookup
# through the active temporary counter while it replaces / parallels the old one.
# Dates are exchange-local and inclusive. 1196 -> 2922 is the 1-into-4
# subdivision effective 2026-09-14; the temporary counter remains relevant
# through the published parallel-trading window ending 2026-10-20.
_HK_TEMP_QUOTE_COUNTERS = {
    "1196.HK": {
        "temporary": "2922.HK",
        "start": "2026-09-14",
        "end": "2026-10-20",
        "reason": "HKEX temporary counter for 1-into-4 share subdivision",
    },
}

def _current_quote_ticker_candidates(ticker: str, now=None):
    """Return current-quote symbols, prioritising an active HKEX temp counter.

    Historical calculations stay on the user's permanent ticker. This helper is
    ONLY for current-price discovery so a corporate-action counter change cannot
    leave the app reading the last print from the retired/paused old counter.
    """
    t=str(ticker or '').upper().strip()
    rows=[]
    spec=_HK_TEMP_QUOTE_COUNTERS.get(t)
    if spec:
        try:
            tz=_market_timezone_for_ticker(t)
            local=pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz=tz)
            if local.tzinfo is None: local=local.tz_localize(tz)
            else: local=local.tz_convert(tz)
            today=local.date()
            start=pd.Timestamp(spec['start']).date(); end=pd.Timestamp(spec['end']).date()
            if start <= today <= end:
                rows.append((str(spec['temporary']).upper(), {
                    'temporary_counter_active':True,
                    'temporary_counter':str(spec['temporary']).upper(),
                    'underlying_symbol':t,
                    'counter_reason':spec.get('reason','HKEX temporary counter'),
                }))
        except Exception:
            pass
    rows.append((t, {
        'temporary_counter_active':False,
        'temporary_counter':None,
        'underlying_symbol':t,
        'counter_reason':None,
    }))
    # de-duplicate while preserving priority
    out=[]; seen=set()
    for sym,meta in rows:
        if sym in seen: continue
        seen.add(sym); out.append((sym,meta))
    return out

def _counter_source_suffix(meta):
    if meta and meta.get('temporary_counter_active'):
        temp=str(meta.get('temporary_counter','')).replace('.HK','')
        under=str(meta.get('underlying_symbol','')).replace('.HK','')
        return f' • HKEX temporary counter {temp} for {under}'
    return ''

def _finite(value, default=np.nan):
    """Return a finite float or a caller-supplied default."""
    try:
        x=float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _series1d(obj, index=None, name=None):
    if isinstance(obj, pd.DataFrame):
        if obj.shape[1] == 0:
            idx = index if index is not None else obj.index
            return pd.Series(np.full(len(idx), np.nan), index=idx, name=name, dtype='float64')
        obj = obj.iloc[:, 0]
    if isinstance(obj, pd.Series):
        idx = obj.index if index is None else index
        vals = pd.to_numeric(obj, errors='coerce').to_numpy(dtype='float64', na_value=np.nan)
        return pd.Series(vals.reshape(-1), index=idx, name=name, dtype='float64')
    arr = np.asarray(obj, dtype='float64').reshape(-1)
    if index is None or len(index) != len(arr):
        index = pd.RangeIndex(len(arr))
    return pd.Series(arr, index=index, name=name, dtype='float64')


def _canonical_ohlcv(df: pd.DataFrame, ticker: str | None = None):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    required = ['Open', 'High', 'Low', 'Close', 'Volume']
    cols = list(df.columns)
    ticker_u = str(ticker).upper() if ticker else None

    def parts(col):
        return [str(x) for x in col] if isinstance(col, tuple) else [str(col)]

    chosen = {}
    for field in required:
        matches = []
        for pos, col in enumerate(cols):
            pp = parts(col)
            if any(x.lower() == field.lower() for x in pp):
                ticker_match = bool(ticker_u and any(x.upper() == ticker_u for x in pp))
                matches.append((0 if ticker_match else 1, pos))
        if not matches:
            return None
        matches.sort()
        chosen[field] = matches[0][1]

    out = pd.DataFrame(index=df.index.copy())
    for field in required:
        s = _series1d(df.iloc[:, chosen[field]], index=df.index, name=field)
        out[field] = s.to_numpy(dtype='float64')
    out = out.replace([np.inf, -np.inf], np.nan)
    out = out.dropna(subset=required)
    return out if not out.empty else None


def fetch_ohlcv(ticker: str, period='6mo', interval='1d'):
    try:
        raw = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
            threads=False,
            group_by='column',
        )
        return _canonical_ohlcv(raw, ticker=ticker)
    except Exception:
        return None





def _market_timezone_for_ticker(ticker: str):
    t=str(ticker or '').upper()
    if t.endswith('.HK'):
        return 'Asia/Hong_Kong'
    if t.endswith('.TA'):
        return 'Asia/Jerusalem'
    return 'America/New_York'


def fetch_recent_split_events(ticker: str, lookback_days: int = 45):
    """Best-effort recent split metadata from the market-data provider.

    Returns a list of dicts with date/ratio.  Failure is non-fatal because some
    providers expose adjusted prices before their corporate-action endpoint is
    refreshed.
    """
    try:
        ser=yf.Ticker(str(ticker).upper()).splits
        if ser is None or len(ser)==0:
            return []
        out=[]
        now=pd.Timestamp.now(tz='UTC')
        for idx,val in ser.items():
            try:
                ts_local=pd.Timestamp(idx)
                event_date=ts_local.date().isoformat()
                if ts_local.tzinfo is None:
                    ts_utc=ts_local.tz_localize('UTC')
                else:
                    ts_utc=ts_local.tz_convert('UTC')
                ratio=float(val)
                if np.isfinite(ratio) and ratio>0 and (now-ts_utc).days <= int(lookback_days):
                    out.append({'date':event_date,'ratio':ratio})
            except Exception:
                continue
        return sorted(out,key=lambda x:x['date'])
    except Exception:
        return []


def _daily_reference_close(daily, ticker: str, ref_date=None):
    """Return the most recent official/adjusted Daily close before ref_date.

    If the provider already contains a row stamped with ref_date (for example a
    still-forming Daily candle), that row is deliberately excluded when looking
    for the *previous official close* used by live day-change calculations.
    """
    d=_canonical_ohlcv(daily,ticker=ticker) if daily is not None else None
    if d is None or d.empty:
        return np.nan, None
    try:
        tz=_market_timezone_for_ticker(ticker)
        ref_date=ref_date or pd.Timestamp.now(tz=tz).date()
        dates=[pd.Timestamp(x).date() for x in d.index]
        candidates=[i for i,dt in enumerate(dates) if dt < ref_date]
        if candidates:
            i=candidates[-1]
            return float(d['Close'].iloc[i]), dates[i]
        if len(d):
            return float(d['Close'].iloc[-1]), dates[-1]
    except Exception:
        pass
    return np.nan, None


def _latest_daily_close(daily, ticker: str):
    d=_canonical_ohlcv(daily,ticker=ticker) if daily is not None else None
    if d is None or d.empty:
        return np.nan, None
    try:
        return float(d['Close'].iloc[-1]), pd.Timestamp(d.index[-1]).date()
    except Exception:
        return np.nan, None


def _align_current_quote_to_daily(price, daily, ticker: str, split_ratio=np.nan):
    """Protect the current quote from mixed pre/post-split provider scales.

    A fresh quote is never blindly trusted as the scale anchor when it is far
    from the newest Daily scale.  With explicit recent split metadata we may
    transform the quote by that ratio.  Without metadata, a >55% scale gap is
    treated as suspicious and the quote is not allowed to anchor other frames.
    """
    out={'price':_finite(price,np.nan),'adjusted':False,'scale_suspect':False,'details':[]}
    p=out['price']
    ref,_=_latest_daily_close(daily,ticker)
    if not (np.isfinite(p) and p>0 and np.isfinite(ref) and ref>0):
        return out
    r=p/ref
    if 0.45 <= r <= 1.55:
        return out
    sr=_finite(split_ratio,np.nan)
    if np.isfinite(sr) and sr>0:
        candidates=[('divide',p/sr),('multiply',p*sr)]
        best=None
        for mode,val in candidates:
            if not (np.isfinite(val) and val>0):
                continue
            err=abs(val/ref-1.0)
            if best is None or err<best[0]:
                best=(err,mode,val)
        if best is not None and best[0] <= 0.45:
            out['price']=float(best[2]); out['adjusted']=True
            out['details'].append(f'fresh quote split-normalized ({best[1]} by {sr:g})')
            return out
    out['scale_suspect']=True
    out['details'].append(f'fresh quote scale {r:.3f}x vs latest Daily; no safe corporate-action normalization')
    return out


def frame_price_snapshot(ticker: str, frame, max_age_minutes: float=60.0):
    """Summarize the newest bar of an already-fetched intraday frame.

    `fresh` is intentionally strict: the newest bar must belong to the current
    local market date *and* be recent enough.  This prevents an old pre-split
    15m/1H candle from being presented as today's online price.
    """
    out={'price':np.nan,'timestamp':None,'timestamp_label':'—','age_minutes':np.nan,
         'same_session_date':False,'fresh':False,'source':'unavailable'}
    x=_canonical_ohlcv(frame,ticker=ticker) if frame is not None else None
    if x is None or x.empty or not isinstance(x.index,pd.DatetimeIndex):
        return out
    try:
        tz=_market_timezone_for_ticker(ticker)
        idx=pd.DatetimeIndex(x.index)
        if idx.tz is None:
            idx=idx.tz_localize(tz,ambiguous='NaT',nonexistent='shift_forward')
        else:
            idx=idx.tz_convert(tz)
        x=x.copy(); x.index=idx; x=x[~x.index.isna()].dropna(subset=['Close'])
        if x.empty:return out
        ts=pd.Timestamp(x.index[-1]); now=pd.Timestamp.now(tz=tz)
        age=max(0.0,(now-ts).total_seconds()/60.0); same=ts.date()==now.date()
        out.update({'price':float(x['Close'].iloc[-1]),'timestamp':ts.isoformat(),
                    'timestamp_label':ts.strftime('%Y-%m-%d %H:%M'),'age_minutes':age,
                    'same_session_date':bool(same),'fresh':bool(same and age<=float(max_age_minutes))})
    except Exception:
        pass
    return out


def _quote_timestamp_local(value, ticker: str):
    """Convert provider epoch/datetime to the exchange-local timestamp."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(float(value)):
            ts=pd.to_datetime(float(value),unit='s',utc=True)
        else:
            ts=pd.Timestamp(value)
            if ts.tzinfo is None:
                ts=ts.tz_localize('UTC')
        return ts.tz_convert(_market_timezone_for_ticker(ticker))
    except Exception:
        return None


def _quote_age_snapshot(price, ts, ticker: str, source: str, max_age_minutes: float=35.0,
                        trade_age_minutes: float=8.0, latency_hint: str='DELAYED/CURRENT-SESSION'):
    """Build a timestamp-verified current-session quote candidate."""
    out={'price':_finite(price,np.nan),'timestamp':None,'timestamp_label':'—','age_minutes':np.nan,
         'same_session_date':False,'fresh':False,'display_current':False,'trade_fresh':False,
         'anchor_eligible':False,'provider_timestamp_verified':False,'source':source,
         'quote_status':latency_hint}
    p=out['price']; local=_quote_timestamp_local(ts,ticker)
    if not (np.isfinite(p) and p>0 and local is not None):
        return out
    try:
        tz=_market_timezone_for_ticker(ticker); now=pd.Timestamp.now(tz=tz)
        age=max(0.0,(now-local).total_seconds()/60.0); same=local.date()==now.date()
        current=bool(same and age<=float(max_age_minutes))
        trade_ok=bool(current and age<=float(trade_age_minutes))
        status='LIVE/NEAR-REALTIME' if trade_ok else ('DELAYED/CURRENT-SESSION' if current else 'STALE')
        out.update({'timestamp':local.isoformat(),'timestamp_label':local.strftime('%Y-%m-%d %H:%M'),
                    'age_minutes':age,'same_session_date':same,'fresh':current,
                    'display_current':current,'trade_fresh':trade_ok,'anchor_eligible':current,
                    'provider_timestamp_verified':True,'quote_status':status})
    except Exception:
        pass
    return out


def _fetch_yahoo_direct_quote(ticker: str):
    """Direct Yahoo quote endpoint with exchange timestamp, independent of bar history."""
    try:
        symbol=_urlparse.quote(str(ticker).upper(),safe='')
        url=f'https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}'
        req=_urlrequest.Request(url,headers={'Accept':'application/json','User-Agent':'Mozilla/5.0 (AI Stock Hunter quote fallback)'})
        with _urlrequest.urlopen(req,timeout=6) as resp:
            obj=_json.loads(resp.read().decode('utf-8','replace'))
        rows=((obj or {}).get('quoteResponse') or {}).get('result') or []
        if not rows:return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False}
        r=rows[0] if isinstance(rows[0],dict) else {}
        cand=_quote_age_snapshot(r.get('regularMarketPrice',np.nan),r.get('regularMarketTime'),ticker,
                                 'Yahoo direct quote',35.0,8.0)
        cand['provider_prev_close']=_finite(r.get('regularMarketPreviousClose',np.nan),np.nan)
        cand['market_state']=r.get('marketState')
        return cand
    except Exception:
        return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False}


def _fetch_yahoo_metadata_quote(ticker: str):
    """Second Yahoo path: quote/history metadata instead of intraday-bar download."""
    try:
        tk=yf.Ticker(str(ticker).upper())
        meta=tk.get_history_metadata() if hasattr(tk,'get_history_metadata') else {}
        if not isinstance(meta,dict):meta={}
        price=meta.get('regularMarketPrice',meta.get('currentPrice',np.nan))
        ts=meta.get('regularMarketTime')
        return _quote_age_snapshot(price,ts,ticker,'Yahoo quote metadata',35.0,8.0)
    except Exception:
        return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False}


def _fetch_yahoo_info_quote(ticker: str):
    """Third Yahoo path: quoteSummary/info. Slower, so used only after metadata fails."""
    try:
        tk=yf.Ticker(str(ticker).upper())
        info=tk.get_info() if hasattr(tk,'get_info') else getattr(tk,'info',{})
        if not isinstance(info,dict):info={}
        price=info.get('regularMarketPrice',info.get('currentPrice',np.nan))
        ts=info.get('regularMarketTime')
        return _quote_age_snapshot(price,ts,ticker,'Yahoo quote info',35.0,8.0)
    except Exception:
        return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False}


def _tradingview_route(ticker: str):
    """Map Yahoo-style symbols to TradingView scanner symbols/endpoints."""
    t=str(ticker or '').upper().strip()
    if t.endswith('.HK'):
        raw=t[:-3]
        try:raw=str(int(raw))
        except Exception:raw=raw.lstrip('0') or '0'
        return 'https://scanner.tradingview.com/hongkong/scan',f'HKEX:{raw}'
    if t.endswith('.TA'):
        return 'https://scanner.tradingview.com/israel/scan',f'TASE:{t[:-3]}'
    if t and all(ch.isalnum() or ch in '.-' for ch in t):
        return 'https://scanner.tradingview.com/america/scan',f'NASDAQ:{t}'
    return None,None


def _fetch_tradingview_display_quote(ticker: str, daily=None, split_ratio=np.nan):
    """Best-effort second-provider DISPLAY quote.

    TradingView's scanner response does not reliably expose an exchange trade
    timestamp, so this candidate is never trade-grade and never anchors split
    normalization. It may still be shown as a clearly labelled delayed/current
    price reference when its scale is plausible versus the latest adjusted Daily.
    """
    url,symbol=_tradingview_route(ticker)
    if not url:return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False}
    try:
        payload={'symbols':{'tickers':[symbol],'query':{'types':[]}},
                 'columns':['close','change','volume','update_mode']}
        body=_json.dumps(payload).encode('utf-8')
        req=_urlrequest.Request(url,data=body,method='POST',headers={
            'Content-Type':'application/json','Accept':'application/json',
            'User-Agent':'Mozilla/5.0 (AI Stock Hunter quote fallback)',
            'Origin':'https://www.tradingview.com','Referer':'https://www.tradingview.com/'})
        with _urlrequest.urlopen(req,timeout=6) as resp:
            obj=_json.loads(resp.read().decode('utf-8','replace'))
        rows=obj.get('data',[]) if isinstance(obj,dict) else []
        if not rows:return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False}
        vals=rows[0].get('d',[]) if isinstance(rows[0],dict) else []
        if not vals:return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False}
        raw=_finite(vals[0],np.nan); change=_finite(vals[1],np.nan) if len(vals)>1 else np.nan
        mode=str(vals[3]) if len(vals)>3 and vals[3] is not None else 'delayed/unknown'
        aligned=_align_current_quote_to_daily(raw,daily,ticker,split_ratio)
        price=_finite(aligned.get('price'),np.nan)
        ref,_=_latest_daily_close(daily,ticker)
        # Without a provider timestamp, reject implausible >25% gaps. This also
        # catches many stale pre-split prints that can otherwise look current.
        if not (np.isfinite(price) and price>0):
            return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False}
        if np.isfinite(ref) and ref>0 and abs(price/ref-1.0)>0.25:
            return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False,
                    'details':[f'TradingView fallback rejected: {price/ref:.3f}x vs latest Daily']}
        tz=_market_timezone_for_ticker(ticker); now=pd.Timestamp.now(tz=tz)
        return {'price':float(price),'change_pct':change,'timestamp':None,
                'timestamp_label':now.strftime('%Y-%m-%d %H:%M')+' fetch',
                'age_minutes':np.nan,'same_session_date':True,'fresh':False,
                'display_current':True,'trade_fresh':False,'anchor_eligible':False,
                'provider_timestamp_verified':False,
                'source':f'TradingView fallback ({mode})','quote_status':'DELAYED/UNVERIFIED TIMESTAMP',
                'quote_split_adjusted':bool(aligned.get('adjusted',False)),
                'scale_suspect':bool(aligned.get('scale_suspect',False)),
                'details':list(aligned.get('details',[]))}
    except Exception as e:
        return {'price':np.nan,'display_current':False,'fresh':False,'trade_fresh':False,'anchor_eligible':False,
                'details':[f'TradingView fallback unavailable: {type(e).__name__}']}


def fetch_live_intraday_snapshot(ticker: str, daily=None):
    """Current-price resolver with hard stale gates and multiple quote paths.

    V6.0.6 priority:
      1) Yahoo 1m current-session bar
      2) Yahoo 5m current-session bar
      3) Yahoo direct quote endpoint with regularMarketTime
      4) Yahoo quote metadata with regularMarketTime
      5) Yahoo quote info with regularMarketTime
      6) TradingView display-only fallback (never trade-grade without timestamp)

    A prior-session bar is diagnostic only. A fallback without a verifiable trade
    timestamp can be displayed as delayed/current reference, but cannot enable a
    LIVE TRIGGER or anchor corporate-action normalization.
    """
    out={'price':np.nan,'prev_close':np.nan,'change_pct':np.nan,'timestamp':None,
         'timestamp_label':'—','source':'LIVE PRICE UNAVAILABLE','fresh':False,
         'display_current':False,'trade_fresh':False,'anchor_eligible':False,
         'provider_timestamp_verified':False,'quote_status':'UNAVAILABLE',
         'same_session_date':False,'age_minutes':np.nan,'split_ratio':np.nan,
         'split_date':None,'split_detected':False,'quote_split_adjusted':False,
         'scale_suspect':False,'details':[],'stale_price':np.nan,
         'stale_timestamp_label':'—','stale_age_minutes':np.nan,
         'quote_symbol':str(ticker).upper(),'underlying_symbol':str(ticker).upper(),
         'temporary_counter_active':False,'temporary_counter':None}
    try:
        events=fetch_recent_split_events(ticker,45)
        if events:
            ev=events[-1]
            out.update({'split_ratio':float(ev.get('ratio',np.nan)),
                        'split_date':ev.get('date'),'split_detected':True})
        tz=_market_timezone_for_ticker(ticker); now=pd.Timestamp.now(tz=tz)
        quote_candidates=_current_quote_ticker_candidates(ticker,now)
        best_stale=None
        attempts=[('1m','1d',15.0,6.0),('5m','5d',35.0,10.0)]
        for interval,period,max_age,trade_age in attempts:
            for quote_ticker,counter_meta in quote_candidates:
              try:
                raw=yf.download(str(quote_ticker).upper(),period=period,interval=interval,prepost=True,
                                auto_adjust=True,progress=False,threads=False,group_by='column')
                q=_canonical_ohlcv(raw,ticker=quote_ticker)
                if q is None or q.empty or not isinstance(q.index,pd.DatetimeIndex):continue
                idx=pd.DatetimeIndex(q.index)
                if idx.tz is None:idx=idx.tz_localize(tz,ambiguous='NaT',nonexistent='shift_forward')
                else:idx=idx.tz_convert(tz)
                q=q.copy();q.index=idx;q=q[~q.index.isna()].dropna(subset=['Close'])
                if q.empty:continue
                ts=pd.Timestamp(q.index[-1]);raw_price=float(q['Close'].iloc[-1])
                age=max(0.0,(now-ts).total_seconds()/60.0);same=ts.date()==now.date()
                diag={'price':raw_price,'timestamp_label':ts.strftime('%Y-%m-%d %H:%M'),'age_minutes':age}
                if best_stale is None or ts>best_stale[0]:best_stale=(ts,diag)
                if not (same and age<=max_age):continue
                aligned=_align_current_quote_to_daily(raw_price,daily,ticker,out.get('split_ratio',np.nan))
                if aligned.get('scale_suspect'):
                    out['scale_suspect']=True;out['details'].extend(aligned.get('details',[]));continue
                price=float(aligned['price']);prev_close,prev_date=_daily_reference_close(daily,ticker,ref_date=now.date())
                sr=_finite(out.get('split_ratio'),np.nan)
                if np.isfinite(prev_close) and prev_close>0 and np.isfinite(sr) and sr>0 and out.get('split_date') and prev_date is not None:
                    try:
                        sdate=pd.Timestamp(out['split_date']).date()
                        if prev_date < sdate <= now.date():
                            options=[prev_close,prev_close/sr,prev_close*sr]
                            prev_close=min([v for v in options if np.isfinite(v) and v>0],key=lambda v:abs(price/v-1.0))
                    except Exception:pass
                change=(price/prev_close-1.0)*100.0 if np.isfinite(prev_close) and prev_close>0 else np.nan
                out.update({'price':price,'prev_close':prev_close,'change_pct':change,
                            'timestamp':ts.isoformat(),'timestamp_label':ts.strftime('%Y-%m-%d %H:%M'),
                            'source':f'Yahoo {interval} current-session feed'+_counter_source_suffix(counter_meta),'fresh':True,
                            'display_current':True,'trade_fresh':bool(age<=trade_age),'anchor_eligible':True,
                            'provider_timestamp_verified':True,
                            'quote_status':'LIVE/NEAR-REALTIME' if age<=trade_age else 'DELAYED/CURRENT-SESSION',
                            'same_session_date':True,'age_minutes':age,
                            'quote_split_adjusted':bool(aligned.get('adjusted',False)),
                            'quote_symbol':quote_ticker,'underlying_symbol':str(ticker).upper(),
                            'temporary_counter_active':bool(counter_meta.get('temporary_counter_active')),
                            'temporary_counter':counter_meta.get('temporary_counter')})
                out['details'].extend(aligned.get('details',[]));return out
              except Exception:continue

        # Preserve the rejected bar as diagnostics even when a later fallback succeeds.
        if best_stale is not None:
            _,diag=best_stale
            out.update({'stale_price':diag['price'],'stale_timestamp_label':diag['timestamp_label'],
                        'stale_age_minutes':diag['age_minutes']})

        # Separate Yahoo quote endpoints can stay current even when history bars
        # temporarily lag around a split/corporate action.
        for getter in (_fetch_yahoo_direct_quote,_fetch_yahoo_metadata_quote,_fetch_yahoo_info_quote):
          for quote_ticker,counter_meta in quote_candidates:
            cand=getter(quote_ticker)
            if not cand.get('display_current'):continue
            aligned=_align_current_quote_to_daily(cand.get('price'),daily,ticker,out.get('split_ratio',np.nan))
            if aligned.get('scale_suspect'):
                out['details'].extend(aligned.get('details',[]));continue
            price=_finite(aligned.get('price'),np.nan)
            if not (np.isfinite(price) and price>0):continue
            prev_close,prev_date=_daily_reference_close(daily,ticker,ref_date=now.date())
            sr=_finite(out.get('split_ratio'),np.nan)
            if np.isfinite(prev_close) and prev_close>0 and np.isfinite(sr) and sr>0 and out.get('split_date') and prev_date is not None:
                try:
                    sdate=pd.Timestamp(out['split_date']).date()
                    if prev_date < sdate <= now.date():
                        options=[prev_close,prev_close/sr,prev_close*sr]
                        prev_close=min([v for v in options if np.isfinite(v) and v>0],key=lambda v:abs(price/v-1.0))
                except Exception:pass
            change=(price/prev_close-1.0)*100.0 if np.isfinite(prev_close) and prev_close>0 else np.nan
            out.update(cand);out.update({'price':price,'prev_close':prev_close,'change_pct':change,
                                        'quote_split_adjusted':bool(aligned.get('adjusted',False)),
                                        'scale_suspect':False,'quote_symbol':quote_ticker,
                                        'underlying_symbol':str(ticker).upper(),
                                        'temporary_counter_active':bool(counter_meta.get('temporary_counter_active')),
                                        'temporary_counter':counter_meta.get('temporary_counter'),
                                        'source':str(cand.get('source','Yahoo quote'))+_counter_source_suffix(counter_meta)})
            out['details'].extend(aligned.get('details',[]));return out

        for quote_ticker,counter_meta in quote_candidates:
            tv=_fetch_tradingview_display_quote(quote_ticker,daily,out.get('split_ratio',np.nan))
            if tv.get('display_current'):
                price=_finite(tv.get('price'),np.nan);prev_close,_=_daily_reference_close(daily,ticker,ref_date=now.date())
                change=_finite(tv.get('change_pct'),np.nan)
                if not np.isfinite(change) and np.isfinite(prev_close) and prev_close>0:
                    change=(price/prev_close-1.0)*100.0
                out.update(tv);out.update({'prev_close':prev_close,'change_pct':change,
                                           'quote_symbol':quote_ticker,'underlying_symbol':str(ticker).upper(),
                                           'temporary_counter_active':bool(counter_meta.get('temporary_counter_active')),
                                           'temporary_counter':counter_meta.get('temporary_counter'),
                                           'source':str(tv.get('source','TradingView fallback'))+_counter_source_suffix(counter_meta)})
                return out

        if best_stale is not None:
            _,diag=best_stale
            out.update({'stale_price':diag['price'],'stale_timestamp_label':diag['timestamp_label'],
                        'stale_age_minutes':diag['age_minutes']})
        return out
    except Exception:
        return out

def resolve_current_market_snapshot(ticker: str, daily=None, hourly=None, m15=None,
                                    primary=None, market_open: bool=False):
    """Choose the best current display price without relaxing live-trade safety.

    V6.0.6 separates two ideas:
      * display_current: good enough to show as the current/delayed market price
      * trade_fresh: timestamp-fresh enough to enable LIVE TRIGGER / Actionable Now

    A second-provider quote without a verifiable trade timestamp may be displayed
    with an explicit DELAYED/UNVERIFIED label, but it can never enable live trading
    logic or anchor split normalization.
    """
    p=dict(primary or {})
    base={'price':np.nan,'fallback_price':np.nan,'prev_close':np.nan,'change_pct':np.nan,
          'timestamp':None,'timestamp_label':'—','source':'LIVE PRICE UNAVAILABLE','fresh':False,
          'display_current':False,'trade_fresh':False,'anchor_eligible':False,
          'provider_timestamp_verified':False,'quote_status':'UNAVAILABLE',
          'same_session_date':False,'age_minutes':np.nan,'split_ratio':p.get('split_ratio',np.nan),
          'split_date':p.get('split_date'),'split_detected':bool(p.get('split_detected',False)),
          'quote_split_adjusted':bool(p.get('quote_split_adjusted',False)),
          'scale_suspect':bool(p.get('scale_suspect',False)),'details':list(p.get('details',[])),
          'stale_price':p.get('stale_price',np.nan),'stale_timestamp_label':p.get('stale_timestamp_label','—'),
          'stale_age_minutes':p.get('stale_age_minutes',np.nan),
          'quote_symbol':p.get('quote_symbol',str(ticker).upper()),
          'underlying_symbol':p.get('underlying_symbol',str(ticker).upper()),
          'temporary_counter_active':bool(p.get('temporary_counter_active',False)),
          'temporary_counter':p.get('temporary_counter')}
    daily_last,daily_date=_latest_daily_close(daily,ticker);base['fallback_price']=daily_last
    tz=_market_timezone_for_ticker(ticker);today=pd.Timestamp.now(tz=tz).date()

    candidates=[]
    # Primary may be timestamp-verified Yahoo OR display-only TradingView fallback.
    if p.get('display_current') and np.isfinite(_finite(p.get('price'),np.nan)) and not p.get('scale_suspect'):
        candidates.append(('primary',p))

    ms=frame_price_snapshot(ticker,m15,45.0);ms.update({
        'source':'15m current-session confirmed bar','display_current':bool(ms.get('fresh')),
        'trade_fresh':False,'anchor_eligible':False,'provider_timestamp_verified':True,
        'quote_status':'DELAYED/CONFIRMED 15m'})
    hs=frame_price_snapshot(ticker,hourly,110.0);hs.update({
        'source':'1H current-session confirmed bar','display_current':bool(hs.get('fresh')),
        'trade_fresh':False,'anchor_eligible':False,'provider_timestamp_verified':True,
        'quote_status':'DELAYED/CONFIRMED 1H'})
    if ms.get('display_current'):candidates.append(('15m',ms))
    if hs.get('display_current'):candidates.append(('1H',hs))

    if candidates:
        _,sel=candidates[0]
        price=_finite(sel.get('price'),np.nan)
        prev_close,prev_date=_daily_reference_close(daily,ticker,ref_date=today)
        sr=_finite(base.get('split_ratio'),np.nan)
        if np.isfinite(prev_close) and prev_close>0 and np.isfinite(sr) and sr>0 and base.get('split_date') and prev_date is not None:
            try:
                sdate=pd.Timestamp(base['split_date']).date()
                if prev_date < sdate <= today:
                    options=[prev_close,prev_close/sr,prev_close*sr]
                    prev_close=min([v for v in options if np.isfinite(v) and v>0],key=lambda v:abs(price/v-1.0))
            except Exception:pass
        change=_finite(sel.get('change_pct'),np.nan)
        if not np.isfinite(change):
            change=(price/prev_close-1.0)*100.0 if np.isfinite(prev_close) and prev_close>0 else np.nan
        base.update({'price':price,'prev_close':prev_close,'change_pct':change,
                     'timestamp':sel.get('timestamp'),'timestamp_label':sel.get('timestamp_label','—'),
                     'source':sel.get('source','current-session quote'),
                     'fresh':bool(sel.get('fresh',False)),
                     'display_current':bool(sel.get('display_current',True)),
                     'trade_fresh':bool(sel.get('trade_fresh',False)),
                     'anchor_eligible':bool(sel.get('anchor_eligible',False)),
                     'provider_timestamp_verified':bool(sel.get('provider_timestamp_verified',False)),
                     'quote_status':sel.get('quote_status','CURRENT/DELAYED'),
                     'same_session_date':bool(sel.get('same_session_date',True)),
                     'age_minutes':sel.get('age_minutes',np.nan),
                     'quote_symbol':sel.get('quote_symbol',base.get('quote_symbol')),
                     'underlying_symbol':sel.get('underlying_symbol',base.get('underlying_symbol')),
                     'temporary_counter_active':bool(sel.get('temporary_counter_active',base.get('temporary_counter_active',False))),
                     'temporary_counter':sel.get('temporary_counter',base.get('temporary_counter'))})
        return base

    if market_open:
        base['source']='LIVE PRICE UNAVAILABLE — using last official close only as reference'
        return base

    # Closed/pre-open: latest official Daily close is a safe reference, not a live quote.
    if np.isfinite(daily_last) and daily_last>0:
        d=_canonical_ohlcv(daily,ticker=ticker);prev=np.nan
        if d is not None and len(d)>=2:prev=float(d['Close'].iloc[-2])
        change=(daily_last/prev-1.0)*100.0 if np.isfinite(prev) and prev>0 else np.nan
        base.update({'price':daily_last,'prev_close':prev,'change_pct':change,
                     'timestamp_label':str(daily_date) if daily_date else '—',
                     'source':'latest official Daily close','fresh':False,
                     'display_current':False,'trade_fresh':False,
                     'same_session_date':bool(daily_date==today),'age_minutes':np.nan,
                     'quote_status':'OFFICIAL CLOSE'})
    return base


def fetch_premarket_snapshots(tickers):
    """Return real US pre-market snapshots from Yahoo intraday extended-hours data.

    The volume-strength ratio compares today's cumulative pre-market volume with
    prior available pre-market sessions through the same clock time.  Non-US
    tickers are intentionally left to the UI as N/A rather than fabricating an
    auction/pre-open equivalent.
    """
    from datetime import datetime, time as dtime
    from zoneinfo import ZoneInfo

    names=[str(t).upper().strip() for t in tickers if str(t).strip()]
    if not names:
        return {}
    out={}
    try:
        raw=yf.download(names, period='5d', interval='5m', prepost=True,
                        auto_adjust=False, progress=False, threads=True, group_by='ticker')
    except Exception:
        return out
    if raw is None or raw.empty:
        return out

    now=datetime.now(ZoneInfo('America/New_York'))
    today=now.date(); cutoff=now.time().replace(tzinfo=None)
    for tkr in names:
        try:
            if len(names)==1:
                q=raw.copy()
            elif isinstance(raw.columns,pd.MultiIndex):
                if tkr in raw.columns.get_level_values(0): q=raw[tkr].copy()
                elif tkr in raw.columns.get_level_values(-1): q=raw.xs(tkr,axis=1,level=-1).copy()
                else: continue
            else:
                continue
            if q.empty: continue
            idx=pd.DatetimeIndex(q.index)
            if idx.tz is None: idx=idx.tz_localize('UTC')
            idx=idx.tz_convert('America/New_York'); q.index=idx
            close=pd.to_numeric(q.get('Close'),errors='coerce'); vol=pd.to_numeric(q.get('Volume'),errors='coerce').fillna(0)
            dates=pd.Series(q.index.date,index=q.index)
            times=pd.Series(q.index.time,index=q.index)
            pm_mask=(dates==today) & (times>=dtime(4,0)) & (times<dtime(9,30)) & (times<=cutoff)
            pm=q.loc[pm_mask]
            if pm.empty: continue
            pm_close=pd.to_numeric(pm['Close'],errors='coerce').dropna()
            if pm_close.empty: continue
            last_price=float(pm_close.iloc[-1]); pm_volume=float(pd.to_numeric(pm['Volume'],errors='coerce').fillna(0).sum())
            regular=(times>=dtime(9,30)) & (times<dtime(16,0)) & (dates<today)
            prev=q.loc[regular]
            if prev.empty: continue
            prev_dates=sorted(set(prev.index.date))
            prev_day=prev_dates[-1]; prev_day_rows=prev[prev.index.date==prev_day]
            prev_close_series=pd.to_numeric(prev_day_rows['Close'],errors='coerce').dropna()
            if prev_close_series.empty: continue
            prev_close=float(prev_close_series.iloc[-1])
            change=(last_price/prev_close-1.0)*100.0 if prev_close else np.nan

            hist=[]
            for d in sorted(set(q.index.date)):
                if d>=today: continue
                m=(q.index.date==d) & (q.index.time>=dtime(4,0)) & (q.index.time<dtime(9,30)) & (q.index.time<=cutoff)
                v=float(pd.to_numeric(q.loc[m,'Volume'],errors='coerce').fillna(0).sum())
                if v>0: hist.append(v)
            baseline=float(np.median(hist)) if hist else np.nan
            strength=(pm_volume/baseline) if baseline and np.isfinite(baseline) and baseline>0 else np.nan
            out[tkr]={'PMPrice':last_price,'PMChangePct':change,'PMVolume':pm_volume,'PMVolumeStrength':strength,'PMData':'REAL 5M'}
        except Exception:
            continue
    return out


def fetch_aftermarket_snapshots(tickers):
    """Return real US after-hours snapshots from Yahoo 5-minute extended-hours data.

    AH volume strength compares cumulative after-hours volume through the current
    clock time with prior available sessions through the same elapsed AH window.
    """
    from datetime import datetime, time as dtime
    from zoneinfo import ZoneInfo
    names=[str(t).upper().strip() for t in tickers if str(t).strip()]
    if not names: return {}
    out={}
    try:
        raw=yf.download(names, period='5d', interval='5m', prepost=True,
                        auto_adjust=False, progress=False, threads=True, group_by='ticker')
    except Exception:
        return out
    if raw is None or raw.empty: return out
    now=datetime.now(ZoneInfo('America/New_York')); today=now.date(); cutoff=now.time().replace(tzinfo=None)
    for tkr in names:
        try:
            if len(names)==1: q=raw.copy()
            elif isinstance(raw.columns,pd.MultiIndex):
                if tkr in raw.columns.get_level_values(0): q=raw[tkr].copy()
                elif tkr in raw.columns.get_level_values(-1): q=raw.xs(tkr,axis=1,level=-1).copy()
                else: continue
            else: continue
            if q.empty: continue
            idx=pd.DatetimeIndex(q.index)
            if idx.tz is None: idx=idx.tz_localize('UTC')
            idx=idx.tz_convert('America/New_York'); q.index=idx
            ah=q[(q.index.date==today) & (q.index.time>=dtime(16,0)) & (q.index.time<dtime(20,0)) & (q.index.time<=cutoff)]
            if ah.empty: continue
            ah_close=pd.to_numeric(ah['Close'],errors='coerce').dropna()
            if ah_close.empty: continue
            last_price=float(ah_close.iloc[-1]); ah_volume=float(pd.to_numeric(ah['Volume'],errors='coerce').fillna(0).sum())
            reg=q[(q.index.date==today) & (q.index.time>=dtime(9,30)) & (q.index.time<dtime(16,0))]
            if reg.empty: continue
            reg_close=pd.to_numeric(reg['Close'],errors='coerce').dropna()
            if reg_close.empty: continue
            close=float(reg_close.iloc[-1]); change=(last_price/close-1.0)*100.0 if close else np.nan
            hist=[]
            for d in sorted(set(q.index.date)):
                if d>=today: continue
                m=(q.index.date==d) & (q.index.time>=dtime(16,0)) & (q.index.time<dtime(20,0)) & (q.index.time<=cutoff)
                v=float(pd.to_numeric(q.loc[m,'Volume'],errors='coerce').fillna(0).sum())
                if v>0: hist.append(v)
            baseline=float(np.median(hist)) if hist else np.nan
            strength=(ah_volume/baseline) if baseline and np.isfinite(baseline) and baseline>0 else np.nan
            out[tkr]={'AHPrice':last_price,'AHChangePct':change,'AHVolume':ah_volume,'AHVolumeStrength':strength,'AHData':'REAL 5M'}
        except Exception: continue
    return out


def ema(s, span):
    s = _series1d(s)
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close, n=14):
    c = _series1d(close, name='Close')
    d = c.diff()
    gain = d.clip(lower=0.0)
    loss = -d.clip(upper=0.0)
    ag = gain.ewm(alpha=1.0/float(n), adjust=False, min_periods=int(n)).mean()
    al = loss.ewm(alpha=1.0/float(n), adjust=False, min_periods=int(n)).mean()
    num = ag.to_numpy(dtype='float64')
    den = al.to_numpy(dtype='float64')
    rs = np.full(len(num), np.nan, dtype='float64')
    np.divide(num, den, out=rs, where=np.isfinite(den) & (den != 0.0))
    out = 100.0 - (100.0 / (1.0 + rs))
    out[(den == 0.0) & np.isfinite(num) & (num > 0.0)] = 100.0
    return pd.Series(out, index=c.index, dtype='float64')


def true_range(df):
    high = _series1d(df['High'], index=df.index)
    low = _series1d(df['Low'], index=df.index)
    close = _series1d(df['Close'], index=df.index)
    prev = close.shift(1)
    arr = np.vstack([
        (high-low).to_numpy(),
        (high-prev).abs().to_numpy(),
        (low-prev).abs().to_numpy(),
    ])
    return pd.Series(np.nanmax(arr, axis=0), index=df.index, dtype='float64')


def _wilder(series, n):
    s = _series1d(series)
    return s.ewm(alpha=1.0/float(n), adjust=False, min_periods=int(n)).mean()


def adx(df, n=14):
    high = _series1d(df['High'], index=df.index)
    low = _series1d(df['Low'], index=df.index)
    up = high.diff()
    down = -low.diff()
    pdm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index, dtype='float64')
    mdm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index, dtype='float64')
    atr = _wilder(true_range(df), n)
    atr_arr = atr.to_numpy(dtype='float64')
    pnum = 100 * _wilder(pdm, n).to_numpy(dtype='float64')
    mnum = 100 * _wilder(mdm, n).to_numpy(dtype='float64')
    pdi = np.full(len(atr), np.nan)
    mdi = np.full(len(atr), np.nan)
    np.divide(pnum, atr_arr, out=pdi, where=np.isfinite(atr_arr) & (atr_arr != 0))
    np.divide(mnum, atr_arr, out=mdi, where=np.isfinite(atr_arr) & (atr_arr != 0))
    den = pdi + mdi
    dx = np.full(len(den), np.nan)
    np.divide(100*np.abs(pdi-mdi), den, out=dx, where=np.isfinite(den) & (den != 0))
    return _wilder(pd.Series(dx, index=df.index), n)


def _clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))





def confirmed_intraday_bars(df: pd.DataFrame):
    """Return only bars that are very likely closed.

    Yahoo can include the currently-forming 15m/1h candle. Using it as if it were
    final makes Entry/Hourly scores jump around. We infer the bar interval from
    recent timestamps and drop the last row when it is still inside that interval.
    """
    x=_canonical_ohlcv(df)
    if x is None or len(x)<3 or not isinstance(x.index,pd.DatetimeIndex):
        return x
    try:
        idx=x.index
        recent=idx[-min(12,len(idx)):]
        deltas=pd.Series(recent[1:]-recent[:-1]).dt.total_seconds()
        sec=float(deltas[deltas>0].median())
        if not np.isfinite(sec) or sec<=0:return x
        last=pd.Timestamp(idx[-1])
        now=pd.Timestamp.now(tz=last.tz) if last.tz is not None else pd.Timestamp.now()
        age=(now-last).total_seconds()
        # Most providers timestamp a bar at its opening time. A 10% grace handles latency.
        if -60 <= age < sec*0.90:
            return x.iloc[:-1].copy() if len(x)>3 else x
    except Exception:
        pass
    return x


def normalize_cross_timeframes(daily, hourly=None, m15=None, anchor_price=None, split_ratio=None):
    """Normalize Daily/1H/15m to one current price scale.

    V6.0.5 accepts only a validated current-session intraday anchor when supplied.  Without one,
    the established Daily anchor behavior is retained for backward compatibility.
    Clear split-like multiplicative differences are normalized; unexplained
    intraday disagreements remain a hard MISMATCH.
    """
    d=_canonical_ohlcv(daily)
    h=_canonical_ohlcv(hourly) if hourly is not None else None
    m=_canonical_ohlcv(m15) if m15 is not None else None
    report={'split_adjusted':False,'split_detected':bool(np.isfinite(_finite(split_ratio,np.nan)) and _finite(split_ratio,np.nan)>0),
            'split_ratio':_finite(split_ratio,np.nan),'data_quality':'OK','details':[],'anchor_source':'daily'}
    if d is None or d.empty:return d,h,m,report

    def lp(frame):
        try:return float(frame['Close'].iloc[-1]) if frame is not None and len(frame) else np.nan
        except Exception:return np.nan
    dp,hp,mp=lp(d),lp(h),lp(m)
    ap=_finite(anchor_price,np.nan)
    if np.isfinite(ap) and ap>0:
        anchor=ap; report['anchor_source']='5m intraday'
    elif np.isfinite(dp) and dp>0:
        anchor=dp; report['anchor_source']='daily'
    elif np.isfinite(mp) and mp>0:
        anchor=mp; report['anchor_source']='15m fallback'
    else:
        anchor=hp; report['anchor_source']='1H fallback'

    generic=[0.1,0.2,0.25,1/3,0.5,2,3,4,5,10]
    sr=_finite(split_ratio,np.nan)
    if np.isfinite(sr) and sr>0:
        generic.extend([sr,1.0/sr])
    factors=np.array(sorted(set(float(x) for x in generic if np.isfinite(x) and x>0)),dtype=float)

    def fix(frame,label,is_daily=False):
        nonlocal report
        if frame is None or frame.empty:return frame
        p=lp(frame)
        if not (np.isfinite(anchor) and anchor>0 and np.isfinite(p) and p>0):return frame
        ratio=anchor/p
        # A normal intraday move is not a scale problem. Daily is allowed a wider
        # difference because its newest bar may still be the prior official close.
        normal_tol=0.35 if is_daily else 0.20
        if abs(ratio-1.0)<=normal_tol:return frame
        nearest=float(factors[np.argmin(np.abs(np.log(factors)-np.log(ratio)))])
        err=abs(ratio/nearest-1.0)
        if err<=0.14:
            z=frame.copy()
            for c in ['Open','High','Low','Close']:
                if c in z:z[c]=pd.to_numeric(z[c],errors='coerce')*nearest
            report['split_adjusted']=True
            report['split_detected']=True
            report['details'].append(f'{label} split-scale normalized x{nearest:.6g} (observed {ratio:.4g}x)')
            return z
        # A Daily-vs-current gap alone can be a genuine large price move; an
        # intraday-vs-intraday disagreement is much more suspicious.
        if (not is_daily) or abs(ratio-1.0)>0.55:
            report['data_quality']='MISMATCH'
            report['details'].append(f'{label} unexplained scale mismatch {ratio:.3f}x')
        return frame

    d=fix(d,'Daily',True); h=fix(h,'1H',False); m=fix(m,'15m',False)
    hp2,mp2=lp(h),lp(m)
    if np.isfinite(hp2) and hp2>0 and np.isfinite(mp2) and mp2>0 and abs(hp2/mp2-1.0)>0.18:
        report['data_quality']='MISMATCH'
        report['details'].append(f'1H/15m remain inconsistent ({hp2/mp2:.3f}x)')
    return d,h,m,report


def _volume_direction_context(r):
    """Directional interpretation of volume. High volume is evidence, not direction.

    Returns bullish support and bearish distribution pressure on a 0..1 scale.
    """
    ret=_finite(r.get('ret1',np.nan),0.0)
    cl=_finite(r.get('close_location',np.nan),0.5)
    c=_finite(r.get('Close',np.nan)); vw=_finite(r.get('vwap',np.nan))
    cmf=_finite(r.get('cmf20',np.nan),0.0); obv=_finite(r.get('obv_slope5',np.nan),0.0); ad=_finite(r.get('ad_slope5',np.nan),0.0)
    mh=_finite(r.get('macd_hist',np.nan),0.0); ms=_finite(r.get('macd_hist_slope',np.nan),0.0)
    bullish=0.0; bearish=0.0
    bullish += 0.22 if ret>0.002 else (0.10 if ret>=-0.002 else 0.0)
    bearish += 0.25 if ret<-0.012 else (0.16 if ret<-0.003 else 0.0)
    bullish += 0.18 if cl>=0.65 else (0.08 if cl>=0.50 else 0.0)
    bearish += 0.20 if cl<=0.30 else (0.10 if cl<=0.45 else 0.0)
    if np.isfinite(c) and np.isfinite(vw):
        bullish += 0.16 if c>=vw else 0.0
        bearish += 0.16 if c<vw else 0.0
    bullish += 0.14 if cmf>0.05 else (0.06 if cmf>0 else 0.0)
    bearish += 0.14 if cmf<-0.05 else (0.06 if cmf<0 else 0.0)
    bullish += 0.10 if obv>0 else 0.0; bearish += 0.10 if obv<0 else 0.0
    bullish += 0.08 if ad>0 else 0.0; bearish += 0.08 if ad<0 else 0.0
    bullish += 0.12 if mh>0 and ms>=0 else (0.05 if mh>0 else 0.0)
    bearish += 0.12 if mh<0 and ms<=0 else (0.05 if mh<0 else 0.0)
    return min(1.0,bullish),min(1.0,bearish)


def directional_volume_row(r):
    """Return volume magnitude plus direction-aware bullish/bearish evidence."""
    rr=_finite(r.get('time_adjusted_rvol',r.get('robust_volume_ratio',r.get('volume_ratio',np.nan))))
    vz=_finite(r.get('volume_z',np.nan)); va=_finite(r.get('vol_accel',np.nan))
    mag=0.0
    if np.isfinite(rr): mag=1.0 if rr>=2.5 else 0.85 if rr>=1.8 else 0.65 if rr>=1.35 else 0.40 if rr>=1.10 else 0.15 if rr>=0.85 else 0.0
    if np.isfinite(vz) and vz>=2:mag=min(1.0,mag+0.12)
    if np.isfinite(va) and va>=1.25:mag=min(1.0,mag+0.10)
    bull,bear=_volume_direction_context(r)
    bullish=mag*bull
    bearish=mag*bear
    label='ACCUMULATION' if bullish>=0.45 and bullish>bearish*1.15 else ('DISTRIBUTION' if bearish>=0.45 and bearish>bullish*1.15 else 'MIXED / NEUTRAL')
    return {'magnitude':mag,'bullish':bullish,'bearish':bearish,'label':label,'rvol':rr}


def exit_pressure_row(r):
    """0..100 Distribution / Exit Pressure score for long setups."""
    dv=directional_volume_row(r); pts=[]
    pts.append(('Bearish volume / distribution',30*dv['bearish'],30))
    c=_finite(r.get('Close',np.nan)); vw=_finite(r.get('vwap',np.nan)); e20=_finite(r.get('ema20',np.nan)); sup=_finite(r.get('support20',np.nan))
    struct=0.0
    if np.isfinite(c) and np.isfinite(vw) and c<vw:struct+=8
    if np.isfinite(c) and np.isfinite(e20) and c<e20:struct+=8
    if np.isfinite(c) and np.isfinite(sup) and c<sup:struct+=8
    pts.append(('VWAP / EMA / support loss',min(24,struct),24))
    cmf=_finite(r.get('cmf20',np.nan),0); obv=_finite(r.get('obv_slope5',np.nan),0); ad=_finite(r.get('ad_slope5',np.nan),0)
    flow=(8 if cmf<-0.05 else 4 if cmf<0 else 0)+(7 if obv<0 else 0)+(7 if ad<0 else 0)
    pts.append(('Money-flow deterioration',min(22,flow),22))
    mh=_finite(r.get('macd_hist',np.nan),0); ms=_finite(r.get('macd_hist_slope',np.nan),0); rs=_finite(r.get('rsi14',np.nan),50)
    mom=(7 if mh<0 else 0)+(7 if ms<0 else 0)+(6 if rs<45 else 3 if rs<50 else 0)
    pts.append(('Momentum deterioration',min(20,mom),20))
    persistence=_finite(r.get('distribution_persistence3',np.nan),0)
    pts.append(('Persistence',min(4,4*persistence),4))
    score=float(_clamp(sum(float(x[1]) for x in pts)))
    # EXIT WATCH is deliberately only an early warning. ARMED/TRIGGER require
    # persistent distribution plus structure/flow confirmation so one red high-volume
    # bar (including possible capitulation) cannot become an exit command by itself.
    armed_confirm = persistence >= 0.34 and dv['bearish'] >= 0.30 and (struct >= 8 or flow >= 8)
    trigger_confirm = persistence >= 0.67 and dv['bearish'] >= 0.45 and struct >= 16 and flow >= 8
    if score>=72 and trigger_confirm:
        stage='EXIT TRIGGER'
    elif score>=55 and armed_confirm:
        stage='EXIT ARMED'
    elif score>=35:
        stage='EXIT WATCH'
    else:
        stage='CLEAR'
    return score,pts,stage


def _smooth01(x, center=0.0, width=1.0):
    if not np.isfinite(x):return 0.0
    w=max(1e-9,float(width))
    return float(1.0/(1.0+np.exp(-(float(x)-center)/w)))


def entry_score_row(r, quant_score=50.0):
    """Continuous production Entry Score with direction-aware volume."""
    p=_finite(r.get('Close',np.nan)); atr=_finite(r.get('atr14',np.nan)); vw=_finite(r.get('vwap',np.nan)); e9=_finite(r.get('ema9',np.nan)); e20=_finite(r.get('ema20',np.nan)); mh=_finite(r.get('macd_hist',np.nan)); ms=_finite(r.get('macd_hist_slope',np.nan)); rs=_finite(r.get('rsi14',np.nan))
    a=atr if np.isfinite(atr) and atr>0 else (p*.02 if np.isfinite(p) else 1.0)
    vwap_part=20*_smooth01((p-vw)/a if np.isfinite(p) and np.isfinite(vw) else np.nan,0,0.35)
    ema_part=18*_smooth01((e9-e20)/a if np.isfinite(e9) and np.isfinite(e20) else np.nan,0,0.25)
    dv=directional_volume_row(r); vol_part=16*dv['bullish']
    macd_part=14*(0.70*(1.0 if np.isfinite(mh) and mh>0 else 0.0)+0.30*(1.0 if np.isfinite(ms) and ms>0 else 0.0))
    if np.isfinite(rs):
        rsi_part=12*max(0.0,1.0-abs(rs-60.0)/18.0)
    else:rsi_part=0.0
    quant_part=20*_smooth01(float(quant_score),62.0,5.5)
    raw=vwap_part+ema_part+vol_part+macd_part+rsi_part+quant_part
    exit_score,_,_=exit_pressure_row(r)
    # Exit pressure can veto a superficially attractive entry without creating negative scores.
    score=raw*(1.0-0.45*exit_score/100.0)
    return float(_clamp(score)), [('VWAP structure',vwap_part,20),('EMA structure',ema_part,18),('Directional volume',vol_part,16),('MACD',macd_part,14),('RSI window',rsi_part,12),('Quant support',quant_part,20)]


def compute_features(df: pd.DataFrame, intraday=False):
    x = _canonical_ohlcv(df)
    if x is None or len(x) == 0:
        raise ValueError('No valid OHLCV rows')
    c = _series1d(x['Close'], index=x.index)
    v = _series1d(x['Volume'], index=x.index)

    x['ret1'] = c.pct_change()
    x['mom3'] = c.pct_change(3)
    x['mom5'] = c.pct_change(5)
    x['mom10'] = c.pct_change(10)
    x['ema9'] = ema(c, 9)
    x['ema20'] = ema(c, 20)
    x['ema50'] = ema(c, 50)

    vm20 = v.rolling(20).mean()
    vs20 = v.rolling(20).std()
    x['volume_ratio'] = v / vm20.replace(0, np.nan)
    x['volume_z'] = (v-vm20) / vs20.replace(0, np.nan)
    x['vol_accel'] = v.rolling(3).mean() / v.rolling(10).mean().replace(0, np.nan)
    # V5.9 robust/transition volume features. Median-based RVOL is intentionally
    # less sensitive to one-off extreme sessions than the ordinary rolling mean.
    vmed20 = v.rolling(20, min_periods=10).median()
    x['robust_volume_ratio'] = v / vmed20.replace(0, np.nan)
    x['volume_reexpansion'] = x['robust_volume_ratio'] / x['robust_volume_ratio'].shift(1).replace(0, np.nan)
    x['volume_dryup'] = (1.0 - v / v.rolling(5, min_periods=2).max().replace(0, np.nan)).clip(0, 1)

    x['rsi14'] = rsi(c, 14)
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd, 9)
    x['macd'] = macd
    x['macd_signal'] = sig
    x['macd_hist'] = macd - sig
    x['macd_hist_slope'] = x['macd_hist'].diff(2)
    x['ema9_cross_up'] = ((x['ema9'] > x['ema20']) & (x['ema9'].shift(1) <= x['ema20'].shift(1))).fillna(False).astype('int8')
    x['macd_cross_up'] = ((x['macd'] > x['macd_signal']) & (x['macd'].shift(1) <= x['macd_signal'].shift(1))).fillna(False).astype('int8')
    x['macd_hist_turn_pos'] = ((x['macd_hist'] > 0) & (x['macd_hist'].shift(1) <= 0)).fillna(False).astype('int8')

    tr = true_range(x)
    x['atr14'] = _wilder(tr, 14)
    x['atr_pct'] = x['atr14'] / c * 100
    x['adx14'] = adx(x, 14)

    ph = x['High'].rolling(20).max().shift(1)
    pl = x['Low'].rolling(20).min().shift(1)
    x['breakout20_pct'] = (c/ph - 1) * 100
    x['support20'] = pl
    x['resistance20'] = ph

    rng = (x['High'] - x['Low']).replace(0, np.nan)
    x['close_location'] = (c - x['Low']) / rng
    x['turnover'] = c * v
    x['turnover_median60'] = x['turnover'].rolling(60, min_periods=20).median()
    x['turnover_ratio60'] = x['turnover'] / x['turnover_median60'].replace(0, np.nan)

    direction = np.sign(c.diff()).fillna(0)
    x['obv'] = (direction * v).cumsum()
    basev = (v.rolling(20).mean() * 5).replace(0, np.nan)
    x['obv_slope5'] = x['obv'].diff(5) / basev

    mfm = ((c-x['Low']) - (x['High']-c)) / rng
    mfv = mfm.fillna(0) * v
    x['ad_line'] = mfv.cumsum()
    x['ad_slope5'] = x['ad_line'].diff(5) / basev
    x['cmf20'] = mfv.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)

    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    bb_u = mid + 2*sd
    bb_l = mid - 2*sd
    kc_u = x['ema20'] + 1.5*x['atr14']
    kc_l = x['ema20'] - 1.5*x['atr14']
    sq = ((bb_u < kc_u) & (bb_l > kc_l)).fillna(False).astype('int8')
    x['squeeze'] = sq
    x['squeeze_release'] = ((sq.shift(1) == 1) & (sq == 0)).fillna(False).astype('int8')

    x['roc5'] = c.pct_change(5)
    x['roc10'] = c.pct_change(10)
    x['roc_accel'] = x['roc5'] - x['roc10']/2
    x['rs20'] = c/c.shift(20) - 1
    x['pv_divergence'] = ((c.pct_change(5) <= 0.02) & (x['obv'].diff(5) > 0)).fillna(False).astype('int8')

    typical = (x['High'] + x['Low'] + x['Close']) / 3
    if intraday and isinstance(x.index, pd.DatetimeIndex):
        dates = pd.Series(x.index.date, index=x.index)
        x['vwap'] = (typical*v).groupby(dates).cumsum() / v.groupby(dates).cumsum().replace(0, np.nan)
    else:
        x['vwap'] = (typical*v).rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)
    x['vwap_cross_up'] = ((c > x['vwap']) & (c.shift(1) <= x['vwap'].shift(1))).fillna(False).astype('int8')
    # Impulse -> hold -> dry-up -> re-expansion sequence features. All are causal.
    x['impulse_1d'] = x['ret1']
    x['impulse_3d'] = c.pct_change(3)
    x['recent_impulse'] = x['ret1'].rolling(5, min_periods=1).max()
    recent_close_high = c.rolling(5, min_periods=1).max()
    x['post_impulse_retention'] = (c / recent_close_high.replace(0, np.nan)).clip(0, 1.05)
    x['fresh_transition_count'] = (x['ema9_cross_up'] + x['macd_cross_up'] + x['macd_hist_turn_pos'] + x['vwap_cross_up']).astype('float64')

    # Time-of-day normalized intraday RVOL. Compare each bar with the same ordinal
    # bar in prior sessions instead of comparing a partial day with a full day.
    x['time_adjusted_rvol']=x['robust_volume_ratio']
    if intraday and isinstance(x.index,pd.DatetimeIndex) and len(x)>=20:
        try:
            dates=pd.Series(x.index.date,index=x.index)
            ordinal=dates.groupby(dates).cumcount()
            tmp=pd.DataFrame({'v':v.to_numpy(float),'date':dates.to_numpy(),'ord':ordinal.to_numpy()},index=x.index)
            baseline=np.full(len(tmp),np.nan)
            vals=tmp['v'].to_numpy(float); ords=tmp['ord'].to_numpy(int)
            for i in range(len(tmp)):
                prior=np.where((ords[:i]==ords[i]))[0]
                prior=prior[-20:]
                if len(prior)>=3: baseline[i]=float(np.nanmedian(vals[prior]))
            x['time_adjusted_rvol']=v/pd.Series(baseline,index=x.index).replace(0,np.nan)
        except Exception:
            pass

    # Corporate-action guard. auto_adjust normally removes splits; this marks any
    # residual split-like jump so momentum/feedback layers can treat it cautiously.
    ratio=c/c.shift(1)
    factors=np.array([0.1,0.2,0.25,1/3,0.5,2,3,4,5,10],dtype=float)
    ca=[]
    for z in ratio.to_numpy(float):
        if not np.isfinite(z) or z<=0 or abs(z-1)<0.35: ca.append(False); continue
        nearest=float(factors[np.argmin(np.abs(np.log(factors)-np.log(z)))])
        ca.append(abs(z/nearest-1.0)<=0.08)
    x['corporate_action_flag']=pd.Series(ca,index=x.index).fillna(False).astype('int8')
    # Rebuild a synthetic continuous price index for return/momentum features only.
    # This prevents a residual split/reverse-split print from becoming a fake +100%/-50% signal.
    try:
        clean_ret=c.pct_change().copy(); rr_ratio=(c/c.shift(1)).to_numpy(float); ca_mask=x['corporate_action_flag'].astype(bool).to_numpy()
        for i in range(1,len(clean_ret)):
            if not ca_mask[i] or not np.isfinite(rr_ratio[i]) or rr_ratio[i]<=0:continue
            nearest=float(factors[np.argmin(np.abs(np.log(factors)-np.log(rr_ratio[i])))])
            clean_ret.iloc[i]=rr_ratio[i]/nearest-1.0
        clean_price=100.0*(1.0+clean_ret.fillna(0.0)).cumprod()
        x['ret1']=clean_ret
        x['mom3']=clean_price.pct_change(3); x['mom5']=clean_price.pct_change(5); x['mom10']=clean_price.pct_change(10)
        x['roc5']=clean_price.pct_change(5); x['roc10']=clean_price.pct_change(10); x['roc_accel']=x['roc5']-x['roc10']/2
        x['rs20']=clean_price/clean_price.shift(20)-1
        x['impulse_1d']=x['ret1']; x['impulse_3d']=clean_price.pct_change(3); x['recent_impulse']=x['ret1'].rolling(5,min_periods=1).max()
        ch=clean_price.rolling(5,min_periods=1).max(); x['post_impulse_retention']=(clean_price/ch.replace(0,np.nan)).clip(0,1.05)
    except Exception:
        pass

    # Persistence of heavy selling: confirmed negative-price bars with elevated volume.
    dv_bear=[]; dv_bull=[]
    for _,rr in x.iterrows():
        dv=directional_volume_row(rr); dv_bear.append(dv['bearish']); dv_bull.append(dv['bullish'])
    x['bullish_volume_evidence']=pd.Series(dv_bull,index=x.index,dtype=float)
    x['bearish_volume_evidence']=pd.Series(dv_bear,index=x.index,dtype=float)
    x['distribution_persistence3']=(x['bearish_volume_evidence']>=0.35).rolling(3,min_periods=1).mean()
    return x



def explosive_score_row(r):
    """V6.0 Explosive Move fingerprint with direction-aware volume."""
    comps=[]
    imp=max(_finite(r.get('impulse_1d',np.nan),-1),_finite(r.get('impulse_3d',np.nan),-2)/2)
    p=18 if imp>=.08 else 14 if imp>=.045 else 9 if imp>=.025 else 4 if imp>0 else 0
    comps.append(('Impulse strength',p,18))

    dv=directional_volume_row(r)
    p=18*dv['bullish']
    comps.append(('Directional volume shock',p,18))

    ret=_finite(r.get('post_impulse_retention',np.nan)); ri=_finite(r.get('recent_impulse',np.nan))
    p=14 if np.isfinite(ret) and np.isfinite(ri) and ri>=.035 and ret>=.97 else 10 if np.isfinite(ret) and np.isfinite(ri) and ri>=.025 and ret>=.94 else 4 if np.isfinite(ret) and ret>=.92 else 0
    comps.append(('Post-impulse retention',p,14))

    dry=_finite(r.get('volume_dryup',np.nan)); p=10 if np.isfinite(dry) and dry>=.55 and np.isfinite(ret) and ret>=.94 else 7 if np.isfinite(dry) and dry>=.35 and np.isfinite(ret) and ret>=.92 else 0
    comps.append(('Volume dry-up',p,10))

    re=_finite(r.get('volume_reexpansion',np.nan)); p=(10 if re>=1.8 else 7 if re>=1.35 else 3 if re>=1.1 else 0)*max(0.0,min(1.0,dv['bullish']*1.7))
    comps.append(('Bullish volume re-expansion',p,10))

    tr=_finite(r.get('fresh_transition_count',np.nan),0); mh=_finite(r.get('macd_hist_slope',np.nan)); va=_finite(r.get('vol_accel',np.nan))
    p=min(12,(4*int(tr) if np.isfinite(tr) else 0)+(2 if np.isfinite(mh) and mh>0 else 0)+(2 if np.isfinite(va) and va>1.1 and dv['bullish']>=.25 else 0))
    comps.append(('Fresh transitions',p,12))

    atr=_finite(r.get('atr_pct',np.nan)); p=8 if atr>=6 else 6 if atr>=4 else 4 if atr>=2.5 else 1 if np.isfinite(atr) else 0
    comps.append(('ATR move capacity',p,8))

    e9=_finite(r.get('ema9',np.nan)); e20=_finite(r.get('ema20',np.nan)); c=_finite(r.get('Close',np.nan)); vw=_finite(r.get('vwap',np.nan)); rs=_finite(r.get('rsi14',np.nan))
    p=(4 if np.isfinite(e9) and np.isfinite(e20) and e9>=e20 else 0)+(4 if np.isfinite(c) and np.isfinite(vw) and c>=vw else 0)+(2 if np.isfinite(rs) and 48<=rs<=75 else 0)
    comps.append(('Trend/VWAP structure',p,10))

    raw=float(_clamp(sum(float(x[1]) for x in comps)))
    exit_score,_,_=exit_pressure_row(r)
    score=float(_clamp(raw*(1.0-0.35*exit_score/100.0)))
    exhausted=(np.isfinite(rs) and rs>80) or (_finite(r.get('mom5',np.nan),0)>.28)
    if exit_score>=72: stage='DISTRIBUTION'
    elif exhausted and score<82: stage='EXHAUSTED'
    elif score>=82 and p>=6: stage='TRIGGERED'
    elif score>=68: stage='ARMED'
    elif score>=52: stage='BUILDING'
    elif score>=35: stage='RESET'
    else: stage='COLD'
    return score, comps, stage


def hourly_confirmation(feat):
    if feat is None or len(feat)==0:return {'score':np.nan,'status':'NO DATA','exit_pressure':np.nan}
    f=feat.dropna(subset=['Close'])
    if f.empty:return {'score':np.nan,'status':'NO DATA','exit_pressure':np.nan}
    r=f.iloc[-1]
    score=0.0
    c=_finite(r.get('Close',np.nan)); vw=_finite(r.get('vwap',np.nan)); e9=_finite(r.get('ema9',np.nan)); e20=_finite(r.get('ema20',np.nan)); mh=_finite(r.get('macd_hist',np.nan)); rs=_finite(r.get('rsi14',np.nan)); tr=_finite(r.get('fresh_transition_count',0),0)
    dv=directional_volume_row(r)
    if np.isfinite(c) and np.isfinite(vw) and c>=vw:score+=20
    if np.isfinite(e9) and np.isfinite(e20) and e9>=e20:score+=20
    if np.isfinite(mh) and mh>0:score+=16
    if np.isfinite(rs) and 50<=rs<=72:score+=14
    score+=14*dv['bullish']
    score+=min(16,4*tr)
    exit_score,_,exit_stage=exit_pressure_row(r)
    score=float(_clamp(score*(1.0-0.45*exit_score/100.0)))
    return {'score':round(score,1),'status':'CONFIRMED' if score>=70 and exit_score<35 else 'PARTIAL' if score>=50 and exit_score<55 else 'WEAK','exit_pressure':round(exit_score,1),'exit_stage':exit_stage,'volume_context':dv['label']}


def explosive_probabilities(feat, current_score=None, min_sample=8):
    """Empirical, shrinkage-calibrated probabilities from prior causal rows only."""
    f=feat.copy().dropna(subset=['Close'])
    if len(f)<35:return {'sample':0,'threshold':np.nan,'probs':{}}
    scores=np.array([explosive_score_row(r)[0] for _,r in f.iterrows()],dtype=float)
    cs=float(scores[-1] if current_score is None else current_score)
    threshold=max(45.0, cs-10.0)
    out={}
    highs=f['High'].to_numpy(dtype=float); closes=f['Close'].to_numpy(dtype=float)
    for h in (1,3,5):
        for target in (.05,.10,.15):
            vals=[]; base=[]
            for i in range(0,len(f)-h-1):
                hit=1.0 if np.nanmax(highs[i+1:i+1+h])>=closes[i]*(1+target) else 0.0
                base.append(hit)
                if scores[i]>=threshold: vals.append(hit)
            n=len(vals); b=float(np.mean(base)) if base else np.nan
            if n:
                # mild prior toward the unconditional base rate; prevents tiny buckets from reading 0/100%.
                p=(float(np.sum(vals))+4.0*b)/(n+4.0) if np.isfinite(b) else float(np.mean(vals))
            else:p=np.nan
            out[f'p{int(target*100)}_{h}d']={'prob':100*p if np.isfinite(p) else np.nan,'n':n,'baseline':100*b if np.isfinite(b) else np.nan,'reliable':n>=min_sample}
    return {'sample':int(sum(1 for x in scores[:-6] if x>=threshold)),'threshold':round(threshold,1),'probs':out}


def explosive_latest(feat, hourly_feat=None):
    r=feat.dropna(subset=['Close']).iloc[-1]
    score, comps, stage=explosive_score_row(r)
    pr=explosive_probabilities(feat,score)
    hc=hourly_confirmation(hourly_feat) if hourly_feat is not None else {'score':np.nan,'status':'NO DATA'}
    out={'score':round(score,1),'stage':stage,'components':comps,'hourly_confirmation':hc['score'],'hourly_status':hc['status'],'prob_threshold':pr.get('threshold',np.nan),'prob_sample':pr.get('sample',0)}
    for k,v in pr.get('probs',{}).items():
        out[k]=v.get('prob',np.nan); out[k+'_n']=v.get('n',0); out[k+'_reliable']=v.get('reliable',False)
    for k in ['robust_volume_ratio','post_impulse_retention','volume_dryup','volume_reexpansion','fresh_transition_count','atr_pct']:
        val=r.get(k,np.nan); out[k]=float(val) if pd.notna(val) else np.nan
    return out


def explosive_walkforward(feat, threshold=68):
    """Chronological four-fold validation of the static V5.9 fingerprint."""
    f=feat.copy().dropna(subset=['Close'])
    if len(f)<120:return pd.DataFrame()
    scores=np.array([explosive_score_row(r)[0] for _,r in f.iterrows()],dtype=float)
    highs=f['High'].to_numpy(dtype=float); closes=f['Close'].to_numpy(dtype=float)
    rows=[]; specs=[(.40,.55),(.55,.70),(.70,.85),(.85,1.00)]
    for target in (.05,.10,.15):
        for h in (1,3,5):
            fold_lifts=[]; fold_hits=[]; fold_ns=[]
            for fold,(a,b) in enumerate(specs,1):
                i1=int(len(f)*a); i2=min(int(len(f)*b),len(f)-h-1)
                sig=[]; base=[]
                for i in range(i1,i2):
                    hit=1.0 if np.nanmax(highs[i+1:i+1+h])>=closes[i]*(1+target) else 0.0
                    base.append(hit)
                    if scores[i]>=threshold:sig.append(hit)
                n=len(sig); bhr=float(np.mean(base)) if base else np.nan; hr=float(np.mean(sig)) if sig else np.nan
                lift=hr/bhr if np.isfinite(hr) and np.isfinite(bhr) and bhr>0 else np.nan
                if np.isfinite(lift):fold_lifts.append(lift)
                if np.isfinite(hr):fold_hits.append(hr)
                fold_ns.append(n)
            pos=sum(1 for x in fold_lifts if x>1.0)
            rows.append({'Target':f'+{int(target*100)}%','Horizon':f'{h}D','Signals':sum(fold_ns),'Hit Rate %':100*np.average(fold_hits,weights=[max(1,n) for n in fold_ns if n>0]) if fold_hits and len(fold_hits)==sum(1 for n in fold_ns if n>0) else (100*np.mean(fold_hits) if fold_hits else np.nan),'Median Lift':float(np.median(fold_lifts)) if fold_lifts else np.nan,'Positive Folds':f'{pos}/{len(fold_lifts)}'})
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# V5.9.2 Adaptive Target/Horizon Research Layer
# Strictly causal features: scores at row t use row t and earlier only. Forward
# highs are used only as labels after the score has been frozen.
# -----------------------------------------------------------------------------
def move_score_row(r):
    """Short-horizon move score. High volume is bullish only with bullish price/flow context."""
    pts=[]
    dv=directional_volume_row(r)
    p=25*dv['bullish']; pts.append(('Directional volume acceleration',p,25))
    m3=_finite(r.get('mom3',np.nan)); m5=_finite(r.get('mom5',np.nan)); p=0
    if np.isfinite(m3): p += 12 if .01<=m3<=.08 else 7 if m3>0 else 0
    if np.isfinite(m5): p += 8 if .015<=m5<=.12 else 4 if m5>0 else 0
    pts.append(('Near-term momentum',min(20,p),20))
    tr=_finite(r.get('fresh_transition_count',0),0); mh=_finite(r.get('macd_hist_slope',np.nan))
    p=min(20,5*tr + (5 if np.isfinite(mh) and mh>0 else 0)); pts.append(('Fresh transitions',p,20))
    c=_finite(r.get('Close',np.nan)); vw=_finite(r.get('vwap',np.nan)); e9=_finite(r.get('ema9',np.nan)); e20=_finite(r.get('ema20',np.nan))
    p=(8 if np.isfinite(c) and np.isfinite(vw) and c>=vw else 0)+(7 if np.isfinite(e9) and np.isfinite(e20) and e9>=e20 else 0); pts.append(('VWAP/EMA structure',p,15))
    rs=_finite(r.get('rsi14',np.nan)); p=10 if 50<=rs<=72 else 5 if 45<=rs<=78 else 0; pts.append(('RSI window',p,10))
    atr=_finite(r.get('atr_pct',np.nan)); p=10 if atr>=3 else 7 if atr>=2 else 3 if np.isfinite(atr) else 0; pts.append(('Move capacity',p,10))
    raw=float(_clamp(sum(float(x[1]) for x in pts)))
    exit_score,_,_=exit_pressure_row(r)
    return float(_clamp(raw*(1.0-0.40*exit_score/100.0))),pts


def _entry_proxy_row(r, quant=None):
    return entry_score_row(r,50.0 if quant is None else quant)[0]


def historical_signal_timeline(feat):
    f=feat.copy().dropna(subset=['Close'])
    if f.empty:return pd.DataFrame()
    highs=f['High'].to_numpy(float); closes=f['Close'].to_numpy(float)
    rows=[]
    for i,(idx,r) in enumerate(f.iterrows()):
        ex,_,stage=explosive_score_row(r); mv,_=move_score_row(r); q,_=score_row(r,0); en=_entry_proxy_row(r,q)
        xp,_,xs=exit_pressure_row(r); row={'Date':idx,'Close':closes[i],'Move Score':round(mv,1),'Explosive Score':round(ex,1),'Entry Score':round(en,1),'Exit Pressure':round(xp,1),'Exit Stage':xs,'Stage':stage,'Volume Ratio':r.get('robust_volume_ratio',np.nan),'Time Adjusted RVOL':r.get('time_adjusted_rvol',np.nan),'Volume Context':directional_volume_row(r).get('label'),'ATR %':r.get('atr_pct',np.nan)}
        for h in (1,3,5):
            if i+h < len(f):
                row[f'+{h}D Close Return %']=100*(closes[i+h]/closes[i]-1)
                row[f'+{h}D Max Return %']=100*(np.nanmax(highs[i+1:i+1+h])/closes[i]-1)
            else:
                row[f'+{h}D Close Return %']=np.nan; row[f'+{h}D Max Return %']=np.nan
        rows.append(row)
    out=pd.DataFrame(rows)
    # Signal Timing V5.9.4: causal score acceleration. Positive means the score is strengthening now.
    for score in ("Move Score","Explosive Score","Entry Score"):
        for lag in (1,2,3):
            out[f"{score} Accel {lag}D"] = pd.to_numeric(out[score],errors="coerce") - pd.to_numeric(out[score],errors="coerce").shift(lag)
    ex=pd.to_numeric(out["Explosive Score"],errors="coerce")
    out["Explosive Rising 3D"] = ((ex.diff()>0)&(ex.diff().shift(1)>0)&(ex.diff().shift(2)>0))
    out["Signal Acceleration"] = out["Explosive Score Accel 3D"]
    return out

def signal_timing_latest(feat, hourly_feat=None):
    """Movement timing layer. TRIGGER here means Movement Trigger, not Trade Trigger."""
    tl=historical_signal_timeline(feat)
    if tl.empty:return {}
    r=tl.iloc[-1]
    hc=hourly_confirmation(hourly_feat) if hourly_feat is not None and len(hourly_feat) else {'score':np.nan,'status':'NO DATA','exit_pressure':np.nan}
    ex=_finite(r.get('Explosive Score',np.nan)); mv=_finite(r.get('Move Score',np.nan)); en=_finite(r.get('Entry Score',np.nan))
    a1=_finite(r.get('Explosive Score Accel 1D',np.nan)); a2=_finite(r.get('Explosive Score Accel 2D',np.nan)); a3=_finite(r.get('Explosive Score Accel 3D',np.nan))
    rising=bool(r.get('Explosive Rising 3D',False)); hcs=_finite(hc.get('score',np.nan)); xp=_finite(r.get('Exit Pressure',np.nan),0)
    if xp>=72: stage='WEAKENED'
    elif max(ex,mv) < 50: stage='WAIT'
    elif max(ex,mv) < 60 or (np.isfinite(a3) and a3<=0): stage='WATCH'
    elif max(ex,mv)>=60 and en>=55 and (rising or (np.isfinite(a3) and a3>=6)): stage='ARMED'
    else: stage='WATCH'
    if xp<45 and max(ex,mv)>=68 and en>=62 and np.isfinite(a3) and a3>=8 and np.isfinite(hcs) and hcs>=60:
        stage='TRIGGER'
    return {'move_score':round(mv,1),'explosive_score':round(ex,1),'entry_score':round(en,1),
            'accel_1d':round(a1,1) if np.isfinite(a1) else np.nan,'accel_2d':round(a2,1) if np.isfinite(a2) else np.nan,'accel_3d':round(a3,1) if np.isfinite(a3) else np.nan,
            'rising_3d':rising,'hourly_confirmation':round(hcs,1) if np.isfinite(hcs) else np.nan,'hourly_status':hc.get('status','NO DATA'),'timing_stage':stage,
            'movement_stage':'MOVEMENT TRIGGER' if stage=='TRIGGER' else stage,'exit_pressure':round(xp,1),'exit_stage':str(r.get('Exit Stage','CLEAR'))}


def acceleration_validation(timeline, targets=(3,5,10,15), horizons=(1,3,5), accel_thresholds=(0,3,5,8,10,15)):
    """Validate whether score acceleration adds lift; future returns are labels only."""
    if timeline is None or timeline.empty:return pd.DataFrame()
    t=timeline.copy(); rows=[]
    for window in (1,2,3):
      acol=f"Explosive Score Accel {window}D"
      if acol not in t:continue
      a=pd.to_numeric(t[acol],errors="coerce")
      for th in accel_thresholds:
       mask=a>=th
       for target in targets:
        for h in horizons:
         col=f"+{h}D Max Return %"
         if col not in t:continue
         y=pd.to_numeric(t[col],errors="coerce")>=target; valid=pd.to_numeric(t[col],errors="coerce").notna() & a.notna()
         n=int((mask&valid).sum()); base=float(y[valid].mean()) if valid.any() else np.nan; hit=float(y[mask&valid].mean()) if n else np.nan
         lift=hit/base if np.isfinite(hit) and np.isfinite(base) and base>0 else np.nan
         rows.append({"Window":f"{window}D","Accel Threshold":th,"Target":f"+{target}%","Horizon":f"{h}D","Signals":n,"Hit Rate %":100*hit if np.isfinite(hit) else np.nan,"Baseline %":100*base if np.isfinite(base) else np.nan,"Lift":lift})
    return pd.DataFrame(rows)

def threshold_optimization(feat, thresholds=(50,55,60,65,70,75,80), targets=(.03,.05,.10,.15), horizons=(1,3,5), score_kind='explosive'):
    f=feat.copy().dropna(subset=['Close'])
    if len(f)<120:return pd.DataFrame()
    scorer=(lambda r: move_score_row(r)[0]) if score_kind=='move' else (lambda r: explosive_score_row(r)[0])
    scores=np.array([scorer(r) for _,r in f.iterrows()]); highs=f['High'].to_numpy(float); closes=f['Close'].to_numpy(float)
    specs=[(.40,.55),(.55,.70),(.70,.85),(.85,1.00)]; rows=[]
    for th in thresholds:
      for target in targets:
       for h in horizons:
        lifts=[]; ns=[]; hrs=[]; fwds=[]
        for a,b in specs:
          i1=int(len(f)*a); i2=min(int(len(f)*b),len(f)-h)
          base=[]; sig=[]; rets=[]
          for i in range(i1,i2):
            mx=np.nanmax(highs[i+1:i+1+h])/closes[i]-1; hit=float(mx>=target); base.append(hit)
            if scores[i]>=th:sig.append(hit); rets.append(mx)
          if sig:
            hr=float(np.mean(sig)); br=float(np.mean(base)) if base else np.nan; lift=hr/br if br>0 else np.nan
            if np.isfinite(lift):lifts.append(lift)
            hrs.extend(sig); fwds.extend(rets); ns.append(len(sig))
        rows.append({'Score':score_kind.title(),'Threshold':th,'Target':f'+{int(target*100)}%','Horizon':f'{h}D','Signals':sum(ns),'Hit Rate %':100*np.mean(hrs) if hrs else np.nan,'Median Lift':np.median(lifts) if lifts else np.nan,'Positive Folds':f'{sum(x>1 for x in lifts)}/{len(lifts)}','Avg Max Forward %':100*np.mean(fwds) if fwds else np.nan})
    return pd.DataFrame(rows)

def adaptive_target_horizon(opt, min_signals=20, min_positive_fold_ratio=.5):
    if opt is None or opt.empty:return {}
    x=opt.copy(); x['FoldRatio']=x['Positive Folds'].astype(str).apply(lambda z:(float(z.split('/')[0])/float(z.split('/')[1])) if '/' in z and float(z.split('/')[1]) else 0)
    x=x[(x['Signals']>=min_signals)&(x['FoldRatio']>=min_positive_fold_ratio)&pd.notna(x['Median Lift'])]
    if x.empty:return {}
    x=x.assign(RankScore=x['Median Lift']*np.sqrt(x['Signals'].clip(lower=1))*x['FoldRatio'])
    r=x.sort_values(['RankScore','Median Lift'],ascending=False).iloc[0]
    return {'Score':r['Score'],'Threshold':int(r['Threshold']),'Target':r['Target'],'Horizon':r['Horizon'],'Signals':int(r['Signals']),'Median Lift':float(r['Median Lift']),'Positive Folds':r['Positive Folds'],'Avg Max Forward %':float(r['Avg Max Forward %'])}



def reliability_score_row(r, min_signals=20):
    """0-100 research reliability: lift + sample + fold consistency, with explicit penalties for thin folds."""
    try:
        lift=float(r.get('Median Lift', np.nan)); n=int(r.get('Signals',0)); pf=str(r.get('Positive Folds','0/0'))
        a,b=pf.split('/'); pos=float(a); folds=float(b); fr=pos/folds if folds else 0.0
    except Exception:
        return 0.0
    if not np.isfinite(lift) or n<=0 or folds<=0:return 0.0
    lift_component=35*min(1.0,max(0.0,(lift-1.0)/2.0))
    sample_component=25*min(1.0,math.sqrt(n/max(1.0,float(min_signals)*4.0)))
    fold_component=25*fr
    coverage_component=15*min(1.0,folds/4.0)
    penalty=0.55 if folds<2 else (0.82 if folds<3 else 1.0)
    return round(_clamp((lift_component+sample_component+fold_component+coverage_component)*penalty),1)

def adaptive_target_horizon_v2(opt, min_signals=20, min_positive_fold_ratio=.5, min_folds=2, min_reliability=45):
    if opt is None or opt.empty:return {}
    x=opt.copy()
    def parts(z):
        try:
            a,b=str(z).split('/'); return float(a),float(b)
        except:return 0.0,0.0
    pp=x['Positive Folds'].apply(parts); x['PositiveFoldCount']=[z[0] for z in pp]; x['FoldCount']=[z[1] for z in pp]
    x['FoldRatio']=x['PositiveFoldCount']/x['FoldCount'].replace(0,np.nan)
    x['Reliability Score']=x.apply(lambda r: reliability_score_row(r,min_signals),axis=1)
    x=x[(x['Signals']>=min_signals)&(x['FoldCount']>=min_folds)&(x['FoldRatio']>=min_positive_fold_ratio)&(x['Reliability Score']>=min_reliability)&pd.notna(x['Median Lift'])]
    if x.empty:return {}
    # Reliability dominates; lift and sample break ties without allowing a 1-fold anomaly to win.
    x=x.assign(RankScore=x['Reliability Score'] + 8*np.log1p(x['Median Lift'].clip(lower=1)) + 2*np.log1p(x['Signals']))
    r=x.sort_values(['RankScore','Reliability Score','Median Lift','Signals'],ascending=False).iloc[0]
    return {'Score':r['Score'],'Threshold':int(r['Threshold']),'Target':r['Target'],'Horizon':r['Horizon'],'Signals':int(r['Signals']),'Median Lift':float(r['Median Lift']),'Positive Folds':r['Positive Folds'],'Reliability Score':float(r['Reliability Score']),'Avg Max Forward %':float(r['Avg Max Forward %'])}

def pre_move_study(timeline, targets=(5,10,15), horizons=(1,3,5)):
    if timeline is None or timeline.empty:return pd.DataFrame()
    t=timeline.reset_index(drop=True).copy(); rows=[]
    for target in targets:
      for h in horizons:
        col=f'+{h}D Max Return %'
        if col not in t:continue
        events=t.index[pd.to_numeric(t[col],errors='coerce')>=target].tolist()
        for lag in (3,2,1,0):
          ix=[i-lag for i in events if i-lag>=0]
          if not ix:continue
          z=t.loc[ix]
          rows.append({'Target':f'+{target}%','Horizon':f'{h}D','Days Before':lag,'Events':len(z),'Move Score Avg':pd.to_numeric(z['Move Score'],errors='coerce').mean(),'Explosive Score Avg':pd.to_numeric(z['Explosive Score'],errors='coerce').mean(),'Entry Score Avg':pd.to_numeric(z['Entry Score'],errors='coerce').mean(),'Volume Ratio Avg':pd.to_numeric(z['Volume Ratio'],errors='coerce').mean(),'ATR % Avg':pd.to_numeric(z['ATR %'],errors='coerce').mean()})
    return pd.DataFrame(rows)

def topk_daily_validation(timeline_all, k_values=(5,10), horizons=(1,3,5), score_col='Explosive Score'):
    if timeline_all is None or timeline_all.empty or 'Ticker' not in timeline_all:return pd.DataFrame()
    x=timeline_all.copy(); x['Date']=pd.to_datetime(x['Date']); rows=[]
    for k in k_values:
      for h in horizons:
        retcol=f'+{h}D Max Return %'
        if retcol not in x:continue
        top=[]; rest=[]; days=0
        for _,g in x.dropna(subset=[score_col,retcol]).groupby('Date'):
          if len(g)<=k:continue
          g=g.sort_values(score_col,ascending=False); top.extend(g.head(k)[retcol].astype(float)); rest.extend(g.iloc[k:][retcol].astype(float)); days+=1
        if top and rest:
          ta=float(np.mean(top)); ra=float(np.mean(rest)); rows.append({'Score':score_col,'Top K':k,'Horizon':f'{h}D','Days':days,'TopK Avg Max Return %':ta,'Rest Avg Max Return %':ra,'Excess %':ta-ra,'TopK Positive %':100*np.mean(np.array(top)>0)})
    return pd.DataFrame(rows)

def atr_target_validation(feat, threshold=60, atr_multiples=(1.0,1.5,2.0), horizons=(1,3,5)):
    f=feat.copy().dropna(subset=['Close']); rows=[]
    if len(f)<120:return pd.DataFrame()
    scores=np.array([explosive_score_row(r)[0] for _,r in f.iterrows()]); highs=f.High.to_numpy(float); closes=f.Close.to_numpy(float); atrp=f['atr_pct'].to_numpy(float)/100
    for mult in atr_multiples:
      for h in horizons:
        sig=[]; base=[]
        for i in range(int(len(f)*.4),len(f)-h):
          if not np.isfinite(atrp[i]):continue
          hit=float(np.nanmax(highs[i+1:i+1+h])/closes[i]-1 >= mult*atrp[i]); base.append(hit)
          if scores[i]>=threshold:sig.append(hit)
        hr=np.mean(sig) if sig else np.nan; br=np.mean(base) if base else np.nan
        rows.append({'ATR Target':f'+{mult:g} ATR','Horizon':f'{h}D','Signals':len(sig),'Hit Rate %':100*hr if np.isfinite(hr) else np.nan,'Baseline %':100*br if np.isfinite(br) else np.nan,'Lift':hr/br if np.isfinite(hr) and br>0 else np.nan})
    return pd.DataFrame(rows)

def score_row(r, min_turnover=3_000_000):
    comp=[]
    m3=_finite(r.get('mom3',np.nan)); m5=_finite(r.get('mom5',np.nan)); s=0
    if np.isfinite(m3) and np.isfinite(m5):
        s += 5 if m3>0 else 0; s += 4 if m5>0 else 0; s += 3 if m3>.02 else 0; s += 2 if m5>.04 else 0
    s=_clamp(s,0,16); comp.append(('Momentum',s,16))
    dv=directional_volume_row(r); s=20*dv['bullish']; comp.append(('Directional volume',s,20))
    b=_finite(r.get('breakout20_pct',np.nan)); s=0
    if np.isfinite(b):
        if -3<=b<=0:s=9
        elif 0<b<=4:s=14
        elif 4<b<=8:s=10
    comp.append(('20D breakout/proximity',s,14))
    rv=_finite(r.get('rsi14',np.nan)); s=8 if 52<=rv<=67 else 5 if 48<=rv<=72 else 0; comp.append(('RSI',s,8))
    mh=_finite(r.get('macd_hist',np.nan)); ms=_finite(r.get('macd_hist_slope',np.nan)); s=(7 if mh>0 else 0)+(5 if ms>0 else 0); comp.append(('MACD histogram',s,12))
    av=_finite(r.get('adx14',np.nan)); s=10 if av>=30 else 8 if av>=25 else 5 if av>=20 else 0; comp.append(('ADX trend strength',s,10))
    at=_finite(r.get('atr_pct',np.nan)); s=8 if 2<=at<=7 else 5 if 1.2<=at<=10 else 0; comp.append(('ATR / volatility',s,8))
    cl=_finite(r.get('close_location',np.nan)); s=6 if cl>=.75 else 4 if cl>=.55 else 2 if cl>=.4 else 0; comp.append(('Candle strength',s,6))
    tv=_finite(r.get('turnover',np.nan)); tr=_finite(r.get('turnover_ratio60',np.nan));
    if np.isfinite(tv) and min_turnover > 0 and tv < min_turnover:s=0
    elif np.isfinite(tr):s=6 if tr>=1.5 else 4 if tr>=1.2 else 2 if tr>=0.8 else 0
    else:s=0
    comp.append(('Liquidity',s,6))
    raw=float(_clamp(sum(float(p) for _,p,_ in comp)))
    exit_score,_,_=exit_pressure_row(r)
    return float(_clamp(raw*(1.0-0.30*exit_score/100.0))), comp


def early_score_row(r):
    pts=[]
    ob=float(r.get('obv_slope5',np.nan)); pts.append(('OBV accumulation',18 if np.isfinite(ob) and ob>.08 else 12 if np.isfinite(ob) and ob>0 else 0,18))
    cm=float(r.get('cmf20',np.nan)); pts.append(('CMF money flow',18 if np.isfinite(cm) and cm>.12 else 12 if np.isfinite(cm) and cm>0 else 0,18))
    ad=float(r.get('ad_slope5',np.nan)); pts.append(('Accumulation/Distribution',12 if np.isfinite(ad) and ad>.05 else 8 if np.isfinite(ad) and ad>0 else 0,12))
    sq=bool(r.get('squeeze',0)); rel=bool(r.get('squeeze_release',0)); pts.append(('Bollinger/Keltner squeeze',14 if rel else 9 if sq else 0,14))
    rs=float(r.get('rs20',np.nan)); pts.append(('Relative strength',12 if np.isfinite(rs) and rs>.08 else 8 if np.isfinite(rs) and rs>0 else 0,12))
    ra=float(r.get('roc_accel',np.nan)); pts.append(('ROC acceleration',10 if np.isfinite(ra) and ra>.02 else 6 if np.isfinite(ra) and ra>0 else 0,10))
    pts.append(('Price/Volume divergence',10 if bool(r.get('pv_divergence',0)) else 0,10))
    dv=directional_volume_row(r); va=_finite(r.get('vol_accel',np.nan)); pts.append(('Directional Early RVOL',6*dv['bullish'] if np.isfinite(va) and va>1 else 3*dv['bullish'],6))
    return float(_clamp(sum(p for _,p,_ in pts))), pts


def score_latest(feat, min_turnover=3_000_000):
    r=feat.dropna(subset=['Close']).iloc[-1]
    score,components=score_row(r,min_turnover)
    early,early_components=early_score_row(r)
    xp,xpc,xps=exit_pressure_row(r); dv=directional_volume_row(r); out={'score':score,'early_score':early,'price':float(r['Close']),'daily_change_pct':float(r.get('ret1',np.nan))*100,'components':components,'early_components':early_components,'exit_pressure':round(xp,1),'exit_stage':xps,'exit_components':xpc,'volume_context':dv['label'],'bullish_volume_evidence':round(100*dv['bullish'],1),'bearish_volume_evidence':round(100*dv['bearish'],1)}
    for k in ['volume_ratio','rsi14','adx14','atr_pct','cmf20','obv_slope5','ad_slope5','rs20','roc_accel','vwap','ema9','ema20','ema50','support20','resistance20','macd_hist','robust_volume_ratio','post_impulse_retention','volume_dryup','volume_reexpansion','fresh_transition_count','time_adjusted_rvol','distribution_persistence3','corporate_action_flag']:
        val=r.get(k,np.nan); out[k]=float(val) if not pd.isna(val) else np.nan
    return out


def backtest_signal(feat, horizon=5, target_pct=.06, score_threshold=66, min_turnover=3_000_000):
    f=feat.copy(); f['score']=[score_row(r,min_turnover)[0] for _,r in f.iterrows()]
    highs=f['High'].to_numpy(dtype='float64'); lows=f['Low'].to_numpy(dtype='float64'); closes=f['Close'].to_numpy(dtype='float64')
    hits=np.full(len(f),np.nan); rets=np.full(len(f),np.nan); dds=np.full(len(f),np.nan)
    for i in range(len(f)-horizon):
        fh=highs[i+1:i+1+horizon]; fl=lows[i+1:i+1+horizon]; end=closes[i+horizon]
        hits[i]=1. if np.nanmax(fh)>=closes[i]*(1+target_pct) else 0.
        rets[i]=end/closes[i]-1; dds[i]=np.nanmin(fl)/closes[i]-1
    f['hit']=hits; f['fwd_return']=rets; f['drawdown']=dds
    valid=f[(f['score']>=score_threshold)&f['hit'].notna()].copy(); n=len(valid)
    if n==0:return {'n':0,'hits':0,'misses':0,'hit_rate':np.nan,'avg_return':np.nan,'max_drawdown':np.nan,'confidence':0,'confidence_label':'LOW','backtest_performance':0.0,'sample_reliability':0.0}
    hr=float(valid['hit'].mean())
    sample_factor=min(1.,math.sqrt(n/60))
    # V5.3.1: confidence gives more weight to demonstrated hit-rate performance,
    # while sample size remains an explicit reliability adjustment.
    conf=100*(.80*hr+.20*sample_factor)
    label='HIGH' if n>=30 and hr>=.60 else 'MEDIUM' if n>=12 and hr>=.45 else 'LOW'
    hits=int(valid['hit'].sum())
    return {
        'n':int(n),'hits':hits,'misses':int(n-hits),'hit_rate':hr,
        'avg_return':float(valid['fwd_return'].mean()),'max_drawdown':float(valid['drawdown'].min()),
        'confidence':round(conf,1),'confidence_label':label,
        'backtest_performance':round(hr*100,1),'sample_reliability':round(sample_factor*100,1)
    }


def entry_timing(feat, quant_score, early_score):
    f=feat.dropna(subset=['Close'])
    if f.empty:return {'entry_score':0.0,'status':'NO DATA','zone_low':np.nan,'zone_high':np.nan,'trigger':np.nan,'invalidation':np.nan,'target1':np.nan,'target2':np.nan,'plan_valid':False,'plan_reason':'No data'}
    r=f.iloc[-1]; p=float(r['Close']); atr=_finite(r.get('atr14',np.nan)); vwap=_finite(r.get('vwap',np.nan)); e9=_finite(r.get('ema9',np.nan)); e20=_finite(r.get('ema20',np.nan)); res=_finite(r.get('resistance20',np.nan)); sup=_finite(r.get('support20',np.nan))
    score,_=entry_score_row(r,quant_score)
    a=atr if np.isfinite(atr) and atr>0 else p*.02
    anchors=[p-.35*a]
    for x in (vwap,e9,e20):
        if np.isfinite(x) and p-.8*a<=x<=p+.08*a:anchors.append(x)
    zone_low=max(anchors); zone_high=max(p+.10*a,zone_low+.08*a)
    trigger=p+.08*a
    if np.isfinite(res) and p<=res<=p+1.5*a:trigger=max(trigger,res+.08*a)
    supports=[x for x in (sup,e20,vwap) if np.isfinite(x) and x<p]
    nearest=max(supports) if supports else p-.9*a
    invalid=min(zone_low-.35*a,nearest-.12*a,p-.45*a)
    entry_mid=(zone_low+zone_high)/2.0; risk=max(entry_mid-invalid,0.55*a)
    target1=entry_mid+max(1.35*risk,0.90*a)
    if np.isfinite(res) and res>entry_mid:target1=max(target1,res+0.15*a)
    target2=max(entry_mid+max(2.25*risk,1.75*a),target1+0.60*a)
    xp,_,xs=exit_pressure_row(r)
    stretched=np.isfinite(e20) and p>e20+1.5*a; near_break=np.isfinite(res) and 0 <= (res-p)/p <= .015
    plan_valid=all(np.isfinite(x) for x in [zone_low,zone_high,trigger,invalid,target1,target2]) and zone_low<=zone_high and invalid<zone_low and trigger>=p and target1>entry_mid and target2>target1
    plan_reason='OK' if plan_valid else 'Invalid trade-plan geometry / data-scale mismatch'
    if not plan_valid:status='DATA CHECK'
    elif xp>=72:status='EXIT PRESSURE — NO ENTRY'
    elif xp>=55:status='WAIT — DISTRIBUTION RISK'
    elif stretched:status='WAIT FOR PULLBACK'
    elif near_break and directional_volume_row(r)['bullish']<.35:status='WAIT FOR BREAKOUT'
    elif score>=72 and xp<45:status='ENTER ZONE'
    else:status='WATCH ENTRY'
    if not plan_valid:
        zone_low=zone_high=trigger=invalid=target1=target2=np.nan
    return {'entry_score':round(score,1),'status':status,'zone_low':zone_low,'zone_high':zone_high,'trigger':trigger,'invalidation':invalid,'target1':target1,'target2':target2,'plan_valid':bool(plan_valid),'plan_reason':plan_reason,'exit_pressure':round(xp,1),'exit_stage':xs,'volume_context':directional_volume_row(r)['label']}


def scan_universe(tickers,daily_period='6mo',use_hourly=True,hourly_period='1mo',horizon=5,target_pct=.06,min_turnover=3_000_000,buy_threshold=66,prefilter_top=30):
    stage1=[]
    for ticker in tickers:
        try:
            d=fetch_ohlcv(ticker,daily_period,'1d')
            if d is None or len(d)<35: continue
            f=compute_features(d); latest=score_latest(f,min_turnover); pre=.72*latest['score']+.28*latest['early_score']
            stage1.append((pre,ticker,d,f,latest))
        except Exception:
            continue
    if not stage1:return pd.DataFrame()
    stage1.sort(key=lambda z:z[0],reverse=True); finalists=stage1[:max(5,min(int(prefilter_top),len(stage1)))]
    rows=[]
    for pre,ticker,d,f,latest in finalists:
        try:
            hs=he=np.nan; hfeat=m15feat=None
            if use_hourly:
                h=fetch_ohlcv(ticker,hourly_period,'1h')
                if h is not None and len(h)>=30:
                    hfeat=compute_features(h,True); hl=score_latest(hfeat,0); hs=hl['score']; he=hl['early_score']
                m15=fetch_ohlcv(ticker,'1mo','15m')
                if m15 is not None and len(m15)>=30:m15feat=compute_features(m15,True)
            final=latest['score'] if not np.isfinite(hs) else .78*latest['score']+.22*hs
            early=latest['early_score'] if not np.isfinite(he) else .70*latest['early_score']+.30*he
            precision_feat=m15feat if m15feat is not None else hfeat if hfeat is not None else f
            ent=entry_timing(precision_feat,final,early); bt=backtest_signal(f,horizon,target_pct,buy_threshold,min_turnover)
            rows.append({'Ticker':ticker,'Score':round(final,1),'EarlyScore':round(early,1),'EntryScore':ent['entry_score'],'EntryStatus':ent['status'],'EntryLow':round(ent['zone_low'],4),'EntryHigh':round(ent['zone_high'],4),'Trigger':round(ent['trigger'],4),'Invalidation':round(ent['invalidation'],4),'Price':round(latest['price'],4),'VolumeRatio':round(latest['volume_ratio'],2) if np.isfinite(latest['volume_ratio']) else np.nan,'RSI14':round(latest['rsi14'],1) if np.isfinite(latest['rsi14']) else np.nan,'ADX14':round(latest['adx14'],1) if np.isfinite(latest['adx14']) else np.nan,'CMF20':round(latest['cmf20'],3) if np.isfinite(latest['cmf20']) else np.nan,'EmpiricalHitRate':round(bt['hit_rate']*100,1) if bt['n'] else np.nan,'BacktestN':bt['n'],'Confidence':bt['confidence_label'],'ConfidenceScore':bt['confidence'],'AvgReturn':round(bt['avg_return']*100,2) if bt['n'] else np.nan,'MaxDrawdown':round(bt['max_drawdown']*100,2) if bt['n'] else np.nan})
        except Exception:
            continue
    return pd.DataFrame(rows).sort_values(['Score','EarlyScore','EntryScore'],ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def early_event_backtest(feat, event_pct=.06, lookbacks=(1, 2, 3), min_turnover=0):
    """Analyze Quant/Early scores before single-day close-to-close gains >= event_pct.

    This is intentionally a single-ticker diagnostic. An event is a trading day whose
    Close is at least event_pct above the previous trading day's Close. For each event,
    return the Quant and Early scores 1/2/3 trading days before it.
    """
    f = feat.copy()
    if f is None or len(f) == 0:
        return pd.DataFrame()
    f['quant_score_bt'] = [score_row(r, min_turnover)[0] for _, r in f.iterrows()]
    f['early_score_bt'] = [early_score_row(r)[0] for _, r in f.iterrows()]
    f['day_return_bt'] = f['Close'].pct_change()
    rows = []
    for i in range(1, len(f)):
        day_ret = float(f['day_return_bt'].iloc[i]) if pd.notna(f['day_return_bt'].iloc[i]) else np.nan
        if not np.isfinite(day_ret) or day_ret < float(event_pct):
            continue
        row = {
            'EventDate': f.index[i],
            'EventReturnPct': day_ret * 100.0,
            'PrevClose': float(f['Close'].iloc[i-1]),
            'EventClose': float(f['Close'].iloc[i]),
        }
        for lb in lookbacks:
            j = i - int(lb)
            row[f'Quant_D{lb}'] = float(f['quant_score_bt'].iloc[j]) if j >= 0 else np.nan
            row[f'Early_D{lb}'] = float(f['early_score_bt'].iloc[j]) if j >= 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)

# ========================= V5.4 Dynamic Calibration =========================

def _component_dict(r, kind='early', min_turnover=0):
    comps = early_score_row(r)[1] if kind == 'early' else score_row(r, min_turnover)[1]
    return {name: (float(pts), float(mx)) for name, pts, mx in comps}


def calibrate_components(feat, kind='early', event_pct=.03, lookbacks=(1,2,3), min_turnover=0):
    """Ticker-specific, evidence-weighted component calibration.

    Calibration uses historical close-to-close up-events. Multipliers are deliberately
    shrunk toward 1.0 when event samples are small and capped to prevent overfitting.
    """
    f = feat.copy()
    if f is None or len(f) < 35:
        return {'events':0, 'confidence':0.0, 'multipliers':{}, 'table':pd.DataFrame()}
    event_ret = f['Close'].pct_change()
    events = [i for i in range(1, len(f)) if pd.notna(event_ret.iloc[i]) and float(event_ret.iloc[i]) >= float(event_pct) and abs(float(event_ret.iloc[i])) <= 0.60]
    sample_rel = min(1.0, math.sqrt(len(events)/30.0)) if events else 0.0
    baseline = {}
    maxima = {}
    for _, r in f.iterrows():
        for name,(pts,mx) in _component_dict(r,kind,min_turnover).items():
            maxima[name]=mx; baseline.setdefault(name,[]).append(pts>0)
    rows=[]; multipliers={}
    for name,mx in maxima.items():
        pre=[]; seen=set(); by_lb={lb:[] for lb in lookbacks}
        for eno,i in enumerate(events):
            for lb in lookbacks:
                j=i-int(lb)
                if j<0: continue
                active=_component_dict(f.iloc[j],kind,min_turnover).get(name,(0,mx))[0] > 0
                pre.append(active); by_lb[lb].append(active)
                if active: seen.add(eno)
        pre_rate=float(np.mean(pre)) if pre else np.nan
        base_rate=float(np.mean(baseline.get(name,[]))) if baseline.get(name) else np.nan
        lift=pre_rate/base_rate if np.isfinite(pre_rate) and np.isfinite(base_rate) and base_rate>0 else 1.0
        coverage=len(seen)/len(events) if events else 0.0
        lb_rates=[float(np.mean(v)) for v in by_lb.values() if v]
        stability=max(0.55, 1.0-(float(np.std(lb_rates))/0.35)) if lb_rates else 0.55
        # Evidence-shrunk multiplier. High lift + coverage + sample quality earns weight;
        # weak/negative lift loses weight. Hard caps keep one ticker from dominating.
        evidence=sample_rel*(0.55+0.45*coverage)*stability
        mult=1.0 + evidence*(lift-1.0)*1.65
        mult=float(np.clip(mult,0.45,1.80))
        multipliers[name]=mult
        rows.append({'Component':name,'Base Weight':mx,'Dynamic Weight':mx*mult,'Lift x':lift,'Coverage %':coverage*100,'Sample Reliability %':sample_rel*100,'Stability %':stability*100,'Multiplier':mult})
    table=pd.DataFrame(rows)
    if not table.empty: table=table.sort_values(['Dynamic Weight','Lift x'],ascending=False).reset_index(drop=True)
    return {'events':len(events),'confidence':sample_rel*100,'multipliers':multipliers,'table':table}


def dynamic_score_row(r, calibration, kind='early', min_turnover=0):
    comps=_component_dict(r,kind,min_turnover); mults=(calibration or {}).get('multipliers',{})
    num=den=0.0; details=[]
    for name,(pts,mx) in comps.items():
        m=float(mults.get(name,1.0)); dw=mx*m
        strength=(pts/mx) if mx>0 else 0.0
        num += strength*dw; den += dw
        details.append((name,pts,mx,dw,m))
    score=100.0*num/den if den>0 else 0.0
    return float(_clamp(score)), details


def calibrate_combinations(feat, event_pct=.03, lookbacks=(1,2,3), min_turnover=0, top_n=12):
    """Find Early+Quant component pairs whose joint activation has historical lift."""
    f=feat.copy()
    if f is None or len(f)<35:return pd.DataFrame()
    er=f['Close'].pct_change(); events=[i for i in range(1,len(f)) if pd.notna(er.iloc[i]) and float(er.iloc[i])>=float(event_pct)]
    if not events:return pd.DataFrame()
    def active_set(r):
        e={f'E:{n}' for n,(p,m) in _component_dict(r,'early',min_turnover).items() if p>0}
        q={f'Q:{n}' for n,(p,m) in _component_dict(r,'quant',min_turnover).items() if p>0}
        return e|q
    sets=[active_set(r) for _,r in f.iterrows()]
    names=sorted(set().union(*sets)); pairs=[]
    for a_i,a in enumerate(names):
        for b in names[a_i+1:]:
            # only cross-family pairs to keep the search interpretable and reduce overfit
            if a[0]==b[0]: continue
            base=np.mean([(a in s and b in s) for s in sets])
            if base<=0: continue
            pre=[]; seen=set()
            for eno,i in enumerate(events):
                for lb in lookbacks:
                    j=i-int(lb)
                    if j<0:continue
                    on=a in sets[j] and b in sets[j]; pre.append(on)
                    if on:seen.add(eno)
            pr=np.mean(pre) if pre else 0; lift=pr/base if base else np.nan; cov=100*len(seen)/len(events)
            if np.isfinite(lift): pairs.append({'Combination':a[2:]+' + '+b[2:],'Lift x':lift,'Coverage %':cov,'Pre-event active %':100*pr,'Baseline active %':100*base})
    z=pd.DataFrame(pairs)
    if z.empty:return z
    return z.sort_values(['Lift x','Coverage %'],ascending=False).head(top_n).reset_index(drop=True)


def dynamic_scores(feat, event_pct=.03, min_turnover=0):
    """Current static vs dynamically calibrated scores for one ticker."""
    r=feat.dropna(subset=['Close']).iloc[-1]
    ec=calibrate_components(feat,'early',event_pct,(1,2,3),min_turnover)
    qc=calibrate_components(feat,'quant',event_pct,(1,2,3),min_turnover)
    se=early_score_row(r)[0]; sq=score_row(r,min_turnover)[0]
    de,ed=dynamic_score_row(r,ec,'early',min_turnover); dq,qd=dynamic_score_row(r,qc,'quant',min_turnover)
    # Dynamic final weighting: base 35% Early, shifted modestly by relative calibration evidence.
    er=float(ec.get('confidence',0))/100; qr=float(qc.get('confidence',0))/100
    early_w=float(np.clip(.35 + .10*(er-qr),.25,.45)); quant_w=1.0-early_w
    pred=quant_w*dq+early_w*de
    return {'static_early':se,'static_quant':sq,'dynamic_early':de,'dynamic_quant':dq,'final_prediction':float(_clamp(pred)),'early_weight':early_w,'quant_weight':quant_w,'early_calibration':ec,'quant_calibration':qc,'combinations':calibrate_combinations(feat,event_pct,(1,2,3),min_turnover)}


def _forward_outcomes(f,horizon,target_pct):
    highs=f['High'].to_numpy(dtype='float64'); lows=f['Low'].to_numpy(dtype='float64'); closes=f['Close'].to_numpy(dtype='float64')
    hit=np.full(len(f),np.nan); ret=np.full(len(f),np.nan); dd=np.full(len(f),np.nan)
    for i in range(len(f)-horizon):
        hit[i]=1. if np.nanmax(highs[i+1:i+1+horizon])>=closes[i]*(1+target_pct) else 0.
        ret[i]=closes[i+horizon]/closes[i]-1; dd[i]=np.nanmin(lows[i+1:i+1+horizon])/closes[i]-1
    return hit,ret,dd


def compare_static_dynamic_backtest(feat,horizon=5,target_pct=.03,score_threshold=66,min_turnover=0,train_fraction=.70):
    """Leakage-reduced holdout comparison: calibrate on earlier history, evaluate later history."""
    f=feat.copy().dropna(subset=['Close'])
    if len(f)<60:return {'static':{},'dynamic':{},'baseline':np.nan,'signal_lift_static':np.nan,'signal_lift_dynamic':np.nan,'train_rows':0,'test_rows':0}
    cut=max(35,min(len(f)-int(horizon)-10,int(len(f)*train_fraction))); train=f.iloc[:cut].copy(); test=f.iloc[cut:].copy()
    ec=calibrate_components(train,'early',target_pct,(1,2,3),min_turnover); qc=calibrate_components(train,'quant',target_pct,(1,2,3),min_turnover)
    hit,ret,dd=_forward_outcomes(f,int(horizon),float(target_pct)); f['_hit']=hit; f['_ret']=ret; f['_dd']=dd
    rows=[]
    for i in range(cut,len(f)):
        if not np.isfinite(hit[i]):continue
        r=f.iloc[i]; ss=score_row(r,min_turnover)[0]; de,_=dynamic_score_row(r,ec,'early',min_turnover); dq,_=dynamic_score_row(r,qc,'quant',min_turnover)
        ew=float(np.clip(.35+.10*((ec.get('confidence',0)-qc.get('confidence',0))/100),.25,.45)); pred=(1-ew)*dq+ew*de
        rows.append((ss,pred,hit[i],ret[i],dd[i]))
    if not rows:return {'static':{},'dynamic':{},'baseline':np.nan,'signal_lift_static':np.nan,'signal_lift_dynamic':np.nan,'train_rows':len(train),'test_rows':0}
    z=pd.DataFrame(rows,columns=['static','dynamic','hit','ret','dd']); baseline=float(z.hit.mean())
    def pack(col):
        v=z[z[col]>=score_threshold]; n=len(v)
        if not n:return {'n':0,'hits':0,'hit_rate':np.nan,'avg_return':np.nan,'max_drawdown':np.nan,'sample_reliability':0.0}
        return {'n':n,'hits':int(v.hit.sum()),'hit_rate':float(v.hit.mean()),'avg_return':float(v.ret.mean()),'max_drawdown':float(v.dd.min()),'sample_reliability':100*min(1.,math.sqrt(n/60))}
    s=pack('static'); d=pack('dynamic')
    return {'static':s,'dynamic':d,'baseline':baseline,'signal_lift_static':(s.get('hit_rate',np.nan)/baseline if baseline>0 and np.isfinite(s.get('hit_rate',np.nan)) else np.nan),'signal_lift_dynamic':(d.get('hit_rate',np.nan)/baseline if baseline>0 and np.isfinite(d.get('hit_rate',np.nan)) else np.nan),'train_rows':len(train),'test_rows':len(z)}

# V5.4.3 dynamic scanner follows.

def scan_universe_dynamic(tickers,daily_period='6mo',use_hourly=True,hourly_period='1mo',horizon=5,target_pct=.03,min_turnover=0,buy_threshold=66,prefilter_top=30):
    """V5.4 scanner: dynamic ticker calibration + prediction rank + entry timing."""
    stage=[]
    for ticker in tickers:
        try:
            d=fetch_ohlcv(ticker,daily_period,'1d')
            if d is None or len(d)<35:continue
            f=compute_features(d); ds=dynamic_scores(f,target_pct,min_turnover)
            # Fast ranking favors calibrated prediction, with a small static anchor.
            pre=.85*ds['final_prediction']+.15*(.72*ds['static_quant']+.28*ds['static_early'])
            stage.append((pre,ticker,f,ds))
        except Exception:continue
    if not stage:return pd.DataFrame()
    stage.sort(key=lambda x:x[0],reverse=True); stage=stage[:max(5,min(int(prefilter_top),len(stage)))]
    rows=[]
    for pre,ticker,f,ds in stage:
        try:
            # Intraday remains a timing/confirmation layer; daily calibration remains the evidence base.
            hfeat=m15feat=None; hq=he=np.nan
            if use_hourly:
                h=fetch_ohlcv(ticker,hourly_period,'1h')
                if h is not None and len(h)>=30:
                    hfeat=compute_features(h,True); hr=hfeat.dropna(subset=['Close']).iloc[-1]
                    hq,_=dynamic_score_row(hr,ds['quant_calibration'],'quant',0); he,_=dynamic_score_row(hr,ds['early_calibration'],'early',0)
                m15=fetch_ohlcv(ticker,'1mo','15m')
                if m15 is not None and len(m15)>=30:m15feat=compute_features(m15,True)
            dq=ds['dynamic_quant'] if not np.isfinite(hq) else .78*ds['dynamic_quant']+.22*hq
            de=ds['dynamic_early'] if not np.isfinite(he) else .70*ds['dynamic_early']+.30*he
            ew=ds['early_weight']; pred=(1-ew)*dq+ew*de
            precision=m15feat if m15feat is not None else hfeat if hfeat is not None else f
            ent=entry_timing(precision,dq,de)
            cmp=compare_static_dynamic_backtest(f,horizon,target_pct,buy_threshold,min_turnover)
            db=cmp.get('dynamic',{}); conf=float(ds['early_calibration'].get('confidence',0)+ds['quant_calibration'].get('confidence',0))/2
            lr=f.dropna(subset=['Close']).iloc[-1]
            rows.append({'Ticker':ticker,'Prediction':round(pred,1),'DynamicQuant':round(dq,1),'DynamicEarly':round(de,1),'StaticQuant':round(ds['static_quant'],1),'StaticEarly':round(ds['static_early'],1),'EntryScore':ent['entry_score'],'EntryStatus':ent['status'],'SignalLift':round(cmp.get('signal_lift_dynamic',np.nan),2) if np.isfinite(cmp.get('signal_lift_dynamic',np.nan)) else np.nan,'CalibrationConfidence':round(conf,1),'BacktestN':int(db.get('n',0) or 0),'EmpiricalHitRate':round(float(db.get('hit_rate'))*100,1) if db.get('n',0) and np.isfinite(db.get('hit_rate',np.nan)) else np.nan,'Price':round(float(lr['Close']),4),'VolumeRatio':round(float(lr.get('volume_ratio',np.nan)),2) if np.isfinite(float(lr.get('volume_ratio',np.nan))) else np.nan,'RSI14':round(float(lr.get('rsi14',np.nan)),1) if np.isfinite(float(lr.get('rsi14',np.nan))) else np.nan})
        except Exception:continue
    return pd.DataFrame(rows).sort_values(['Prediction','DynamicEarly','EntryScore'],ascending=False).reset_index(drop=True) if rows else pd.DataFrame()
