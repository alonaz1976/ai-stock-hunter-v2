import streamlit as st
import pandas as pd
import numpy as np
import math
import threading
import sqlite3
import json
import os
import time as time_module
from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
from datetime import datetime, time
from io import BytesIO
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
from plotly.subplots import make_subplots

APP_VERSION = "6.0.3"
APP_BUILD_ID = "V603-ALL-LABS-BG-LOGIC-20260917-A"

# Always load the quant engine from the quant_engine.py file that sits next to
# this app.py.  Using a unique module name deliberately bypasses a stale
# sys.modules entry that Streamlit can keep alive across hot-reloads.
def _load_local_quant_engine():
    engine_path = Path(__file__).resolve().with_name("quant_engine.py")
    if not engine_path.exists():
        raise FileNotFoundError(f"Missing quant engine file: {engine_path}")
    unique_name = f"ai_stock_hunter_quant_{APP_BUILD_ID.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(unique_name, engine_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create import spec for {engine_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

qe = _load_local_quant_engine()
# Bind engine functions defensively so an out-of-sync quant_engine.py does not crash
# the whole Streamlit app during import. The UI below will show an explicit sync error
# if any required V5.4.x function is missing.
fetch_ohlcv = getattr(qe, "fetch_ohlcv", None)
fetch_premarket_snapshots = getattr(qe, "fetch_premarket_snapshots", lambda tickers: {})
fetch_aftermarket_snapshots = getattr(qe, "fetch_aftermarket_snapshots", lambda tickers: {})
compute_features = getattr(qe, "compute_features", None)
score_latest = getattr(qe, "score_latest", None)
backtest_signal = getattr(qe, "backtest_signal", None)
scan_universe_dynamic = getattr(qe, "scan_universe_dynamic", None)
entry_timing = getattr(qe, "entry_timing", None)
score_row = getattr(qe, "score_row", None)
early_score_row = getattr(qe, "early_score_row", None)
dynamic_scores = getattr(qe, "dynamic_scores", None)
compare_static_dynamic_backtest = getattr(qe, "compare_static_dynamic_backtest", None)
explosive_latest = getattr(qe, "explosive_latest", None)
explosive_walkforward = getattr(qe, "explosive_walkforward", None)
historical_signal_timeline = getattr(qe, "historical_signal_timeline", None)
threshold_optimization = getattr(qe, "threshold_optimization", None)
adaptive_target_horizon = getattr(qe, "adaptive_target_horizon", None)
adaptive_target_horizon_v2 = getattr(qe, "adaptive_target_horizon_v2", None)
pre_move_study = getattr(qe, "pre_move_study", None)
topk_daily_validation = getattr(qe, "topk_daily_validation", None)
atr_target_validation = getattr(qe, "atr_target_validation", None)
hourly_confirmation = getattr(qe, "hourly_confirmation", None)
signal_timing_latest = getattr(qe, "signal_timing_latest", None)
acceleration_validation = getattr(qe, "acceleration_validation", None)
confirmed_intraday_bars = getattr(qe, "confirmed_intraday_bars", lambda x: x)
normalize_cross_timeframes = getattr(qe, "normalize_cross_timeframes", lambda d,h=None,m=None: (d,h,m,{"split_adjusted":False,"data_quality":"OK","details":[]}))
directional_volume_row = getattr(qe, "directional_volume_row", lambda r: {"magnitude":0.0,"bullish":0.0,"bearish":0.0,"label":"N/A","rvol":np.nan})
exit_pressure_row = getattr(qe, "exit_pressure_row", lambda r: (0.0,[],"CLEAR"))
entry_score_row = getattr(qe, "entry_score_row", None)


# -----------------------------------------------------------------------------
# V5.5 robust dynamic-calibration fallback
# The dynamic layer is duplicated locally on purpose. If Streamlit ever serves an
# older cached quant_engine.py during a deploy, Analyze/Scanner/Backtest still work
# instead of stopping with an incompatibility error.
# -----------------------------------------------------------------------------
def _v544_clamp(x, lo=0.0, hi=100.0):
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return lo


def _v544_component_dict(r, kind='early', min_turnover=0):
    comps = early_score_row(r)[1] if kind == 'early' else score_row(r, min_turnover)[1]
    return {name: (float(pts), float(mx)) for name, pts, mx in comps}


def _v544_calibrate_components(feat, kind='early', event_pct=.03, lookbacks=(1,2,3), min_turnover=0):
    f = feat.copy()
    if f is None or len(f) < 35:
        return {'events':0,'confidence':0.0,'multipliers':{},'table':pd.DataFrame()}
    event_ret = f['Close'].pct_change()
    events = [i for i in range(1,len(f)) if pd.notna(event_ret.iloc[i]) and float(event_ret.iloc[i]) >= float(event_pct) and abs(float(event_ret.iloc[i])) <= 0.60]
    sample_rel = min(1.0, math.sqrt(len(events)/30.0)) if events else 0.0
    baseline, maxima = {}, {}
    for _, r in f.iterrows():
        for name,(pts,mx) in _v544_component_dict(r,kind,min_turnover).items():
            maxima[name]=mx
            baseline.setdefault(name,[]).append(pts>0)
    rows=[]; multipliers={}
    for name,mx in maxima.items():
        pre=[]; seen=set(); by_lb={lb:[] for lb in lookbacks}
        for eno,i in enumerate(events):
            for lb in lookbacks:
                j=i-int(lb)
                if j<0: continue
                active=_v544_component_dict(f.iloc[j],kind,min_turnover).get(name,(0,mx))[0] > 0
                pre.append(active); by_lb[lb].append(active)
                if active: seen.add(eno)
        pre_rate=float(np.mean(pre)) if pre else np.nan
        base_rate=float(np.mean(baseline.get(name,[]))) if baseline.get(name) else np.nan
        lift=pre_rate/base_rate if np.isfinite(pre_rate) and np.isfinite(base_rate) and base_rate>0 else 1.0
        coverage=len(seen)/len(events) if events else 0.0
        lb_rates=[float(np.mean(v)) for v in by_lb.values() if v]
        stability=max(0.55,1.0-(float(np.std(lb_rates))/0.35)) if lb_rates else 0.55
        evidence=sample_rel*(0.55+0.45*coverage)*stability
        mult=float(np.clip(1.0 + evidence*(lift-1.0)*1.65,0.45,1.80))
        multipliers[name]=mult
        rows.append({'Component':name,'Base Weight':mx,'Dynamic Weight':mx*mult,'Lift x':lift,'Coverage %':coverage*100,'Sample Reliability %':sample_rel*100,'Stability %':stability*100,'Multiplier':mult})
    table=pd.DataFrame(rows)
    if not table.empty:
        table=table.sort_values(['Dynamic Weight','Lift x'],ascending=False).reset_index(drop=True)
    return {'events':len(events),'confidence':sample_rel*100,'multipliers':multipliers,'table':table}


def _v544_dynamic_score_row(r, calibration, kind='early', min_turnover=0):
    comps=_v544_component_dict(r,kind,min_turnover)
    mults=(calibration or {}).get('multipliers',{})
    num=den=0.0; details=[]
    for name,(pts,mx) in comps.items():
        m=float(mults.get(name,1.0)); dw=mx*m
        strength=(pts/mx) if mx>0 else 0.0
        num += strength*dw; den += dw
        details.append((name,pts,mx,dw,m))
    score=100.0*num/den if den>0 else 0.0
    return float(_v544_clamp(score)), details


def _v544_calibrate_combinations(feat,event_pct=.03,lookbacks=(1,2,3),min_turnover=0,top_n=12):
    f=feat.copy()
    if f is None or len(f)<35: return pd.DataFrame()
    er=f['Close'].pct_change()
    events=[i for i in range(1,len(f)) if pd.notna(er.iloc[i]) and float(er.iloc[i])>=float(event_pct)]
    if not events: return pd.DataFrame()
    def active_set(r):
        e={f'E:{n}' for n,(p,m) in _v544_component_dict(r,'early',min_turnover).items() if p>0}
        q={f'Q:{n}' for n,(p,m) in _v544_component_dict(r,'quant',min_turnover).items() if p>0}
        return e|q
    sets=[active_set(r) for _,r in f.iterrows()]
    names=sorted(set().union(*sets)) if sets else []
    pairs=[]
    for a_i,a in enumerate(names):
        for b in names[a_i+1:]:
            if a[0]==b[0]: continue
            base=np.mean([(a in ss and b in ss) for ss in sets])
            if base<=0: continue
            pre=[]; seen=set()
            for eno,i in enumerate(events):
                for lb in lookbacks:
                    j=i-int(lb)
                    if j<0: continue
                    on=a in sets[j] and b in sets[j]
                    pre.append(on)
                    if on: seen.add(eno)
            pr=np.mean(pre) if pre else 0.0
            lift=pr/base if base else np.nan
            cov=100*len(seen)/len(events)
            if np.isfinite(lift):
                pairs.append({'Combination':a[2:]+' + '+b[2:],'Lift x':lift,'Coverage %':cov,'Pre-event active %':100*pr,'Baseline active %':100*base})
    z=pd.DataFrame(pairs)
    if z.empty: return z
    return z.sort_values(['Lift x','Coverage %'],ascending=False).head(top_n).reset_index(drop=True)


def _v544_dynamic_scores(feat,event_pct=.03,min_turnover=0):
    r=feat.dropna(subset=['Close']).iloc[-1]
    ec=_v544_calibrate_components(feat,'early',event_pct,(1,2,3),min_turnover)
    qc=_v544_calibrate_components(feat,'quant',event_pct,(1,2,3),min_turnover)
    se=early_score_row(r)[0]; sq=score_row(r,min_turnover)[0]
    de,ed=_v544_dynamic_score_row(r,ec,'early',min_turnover)
    dq,qd=_v544_dynamic_score_row(r,qc,'quant',min_turnover)
    er=float(ec.get('confidence',0))/100.0; qr=float(qc.get('confidence',0))/100.0
    early_w=float(np.clip(.35+.10*(er-qr),.25,.45)); quant_w=1.0-early_w
    pred=quant_w*dq+early_w*de
    return {'static_early':se,'static_quant':sq,'dynamic_early':de,'dynamic_quant':dq,'final_prediction':float(_v544_clamp(pred)),'early_weight':early_w,'quant_weight':quant_w,'early_calibration':ec,'quant_calibration':qc,'combinations':_v544_calibrate_combinations(feat,event_pct,(1,2,3),min_turnover)}


def _v544_forward_outcomes(f,horizon,target_pct):
    highs=f['High'].to_numpy(dtype='float64'); lows=f['Low'].to_numpy(dtype='float64'); closes=f['Close'].to_numpy(dtype='float64')
    hit=np.full(len(f),np.nan); ret=np.full(len(f),np.nan); dd=np.full(len(f),np.nan)
    for i in range(len(f)-horizon):
        hit[i]=1.0 if np.nanmax(highs[i+1:i+1+horizon])>=closes[i]*(1+target_pct) else 0.0
        ret[i]=closes[i+horizon]/closes[i]-1.0
        dd[i]=np.nanmin(lows[i+1:i+1+horizon])/closes[i]-1.0
    return hit,ret,dd


def _v544_compare_static_dynamic_backtest(feat,horizon=5,target_pct=.03,score_threshold=66,min_turnover=0,train_fraction=.70):
    f=feat.copy().dropna(subset=['Close'])
    if len(f)<60:
        return {'static':{},'dynamic':{},'baseline':np.nan,'signal_lift_static':np.nan,'signal_lift_dynamic':np.nan,'train_rows':0,'test_rows':0}
    cut=max(35,min(len(f)-int(horizon)-10,int(len(f)*train_fraction)))
    train=f.iloc[:cut].copy()
    ec=_v544_calibrate_components(train,'early',target_pct,(1,2,3),min_turnover)
    qc=_v544_calibrate_components(train,'quant',target_pct,(1,2,3),min_turnover)
    hit,ret,dd=_v544_forward_outcomes(f,int(horizon),float(target_pct))
    rows=[]
    for i in range(cut,len(f)):
        if not np.isfinite(hit[i]): continue
        r=f.iloc[i]
        ss=score_row(r,min_turnover)[0]
        de,_=_v544_dynamic_score_row(r,ec,'early',min_turnover)
        dq,_=_v544_dynamic_score_row(r,qc,'quant',min_turnover)
        ew=float(np.clip(.35+.10*((ec.get('confidence',0)-qc.get('confidence',0))/100.0),.25,.45))
        pred=(1-ew)*dq+ew*de
        rows.append((ss,pred,hit[i],ret[i],dd[i]))
    if not rows:
        return {'static':{},'dynamic':{},'baseline':np.nan,'signal_lift_static':np.nan,'signal_lift_dynamic':np.nan,'train_rows':len(train),'test_rows':0}
    z=pd.DataFrame(rows,columns=['static','dynamic','hit','ret','dd']); baseline=float(z.hit.mean())
    def pack(col):
        v=z[z[col]>=score_threshold]; n=len(v)
        if not n: return {'n':0,'hits':0,'hit_rate':np.nan,'avg_return':np.nan,'max_drawdown':np.nan,'sample_reliability':0.0}
        return {'n':n,'hits':int(v.hit.sum()),'hit_rate':float(v.hit.mean()),'avg_return':float(v.ret.mean()),'max_drawdown':float(v.dd.min()),'sample_reliability':100*min(1.0,math.sqrt(n/60.0))}
    sb=pack('static'); db=pack('dynamic')
    return {'static':sb,'dynamic':db,'baseline':baseline,'signal_lift_static':(sb.get('hit_rate',np.nan)/baseline if baseline>0 and np.isfinite(sb.get('hit_rate',np.nan)) else np.nan),'signal_lift_dynamic':(db.get('hit_rate',np.nan)/baseline if baseline>0 and np.isfinite(db.get('hit_rate',np.nan)) else np.nan),'train_rows':len(train),'test_rows':len(z)}


def _v544_scan_universe_dynamic(tickers,daily_period='6mo',use_hourly=True,hourly_period='1mo',horizon=5,target_pct=.03,min_turnover=0,buy_threshold=66,prefilter_top=30,progress_callback=None):
    stage=[]
    skipped=[]
    for scan_i,ticker in enumerate(tickers,1):
        if progress_callback:
            progress_callback('stage1',scan_i,len(tickers),ticker)
        try:
            d=fetch_ohlcv(ticker,daily_period,'1d')
            if d is None or len(d)<35:
                skipped.append({'Ticker':ticker,'Stage':'Daily','Reason':'Insufficient daily data'})
                continue
            f=compute_features(d); ds=_v544_dynamic_scores(f,target_pct,min_turnover)
            pre=.85*ds['final_prediction']+.15*(.72*ds['static_quant']+.28*ds['static_early'])
            stage.append((pre,ticker,f,ds))
        except Exception as e:
            skipped.append({'Ticker':ticker,'Stage':'Daily','Reason':f'{type(e).__name__}: {str(e)[:140]}'})
            continue
    if not stage:
        out=pd.DataFrame(); out.attrs['scan_meta']={'requested':len(tickers),'daily_success':0,'finalists':0,'deep_success':0,'skipped':skipped}
        return out
    daily_success=len(stage)
    stage.sort(key=lambda x:x[0],reverse=True)
    stage=stage[:max(5,min(int(prefilter_top),len(stage)))]
    rows=[]
    for deep_i,(pre,ticker,f,ds) in enumerate(stage,1):
        if progress_callback:
            progress_callback('stage2',deep_i,len(stage),ticker)
        try:
            hfeat=m15feat=None; hq=he=np.nan
            ca_report={'split_adjusted':False,'data_quality':'OK','details':[]}
            if use_hourly:
                h=confirmed_intraday_bars(fetch_ohlcv(ticker,hourly_period,'1h'))
                m15=confirmed_intraday_bars(fetch_ohlcv(ticker,'1mo','15m'))
                _,h,m15,ca_report=normalize_cross_timeframes(f,h,m15)
                if h is not None and len(h)>=30:
                    hfeat=compute_features(h,True); hr=hfeat.dropna(subset=['Close']).iloc[-1]
                    hq,_=_v544_dynamic_score_row(hr,ds['quant_calibration'],'quant',0)
                    he,_=_v544_dynamic_score_row(hr,ds['early_calibration'],'early',0)
                if m15 is not None and len(m15)>=30: m15feat=compute_features(m15,True)
            dq=ds['dynamic_quant'] if not np.isfinite(hq) else .78*ds['dynamic_quant']+.22*hq
            de=ds['dynamic_early'] if not np.isfinite(he) else .70*ds['dynamic_early']+.30*he
            ew=ds['early_weight']; pred=(1-ew)*dq+ew*de
            precision=m15feat if m15feat is not None else hfeat if hfeat is not None else f
            ent=entry_timing(precision,dq,de)
            if str(ca_report.get('data_quality','OK'))!='OK':
                ent=dict(ent)
                ent.update({'plan_valid':False,'plan_reason':'Blocked by cross-timeframe data-quality gate',
                            'zone_low':np.nan,'zone_high':np.nan,'trigger':np.nan,'invalidation':np.nan,'target1':np.nan,'target2':np.nan})
            cmp=_v544_compare_static_dynamic_backtest(f,horizon,target_pct,buy_threshold,min_turnover)
            db=cmp.get('dynamic',{})
            conf=float(ds['early_calibration'].get('confidence',0)+ds['quant_calibration'].get('confidence',0))/2.0
            daily_lr=f.dropna(subset=['Close']).iloc[-1]
            live_f=f.copy()
            if hfeat is not None and len(hfeat):
                try:
                    hr_live=hfeat.dropna(subset=['Close']).iloc[-1]; rv_live=float(hr_live.get('time_adjusted_rvol',np.nan))
                    if np.isfinite(rv_live):
                        live_f.loc[live_f.index[-1],'robust_volume_ratio']=rv_live; live_f.loc[live_f.index[-1],'volume_ratio']=rv_live
                except Exception:pass
            lr=live_f.dropna(subset=['Close']).iloc[-1]
            ex=explosive_latest(live_f,hfeat) if callable(explosive_latest) else {}
            timing=signal_timing_latest(live_f,hfeat) if callable(signal_timing_latest) else {}
            latest_live=score_latest(live_f,0)
            rows.append({'Ticker':ticker,'Prediction':round(pred,1),'DynamicQuant':round(dq,1),'DynamicEarly':round(de,1),'StaticQuant':round(ds['static_quant'],1),'StaticEarly':round(ds['static_early'],1),'EntryScore':ent['entry_score'],'EntryStatus':ent['status'],'EntryLow':round(float(ent.get('zone_low',np.nan)),4) if np.isfinite(float(ent.get('zone_low',np.nan))) else np.nan,'EntryHigh':round(float(ent.get('zone_high',np.nan)),4) if np.isfinite(float(ent.get('zone_high',np.nan))) else np.nan,'BreakoutTrigger':round(float(ent.get('trigger',np.nan)),4) if np.isfinite(float(ent.get('trigger',np.nan))) else np.nan,'Invalidation':round(float(ent.get('invalidation',np.nan)),4) if np.isfinite(float(ent.get('invalidation',np.nan))) else np.nan,'Target1':round(float(ent.get('target1',np.nan)),4) if np.isfinite(float(ent.get('target1',np.nan))) else np.nan,'Target2':round(float(ent.get('target2',np.nan)),4) if np.isfinite(float(ent.get('target2',np.nan))) else np.nan,'ExplosiveScore':ex.get('score',np.nan),'ExplosiveStage':ex.get('stage','—'),'MoveScore':timing.get('move_score',np.nan),'Accel1D':timing.get('accel_1d',np.nan),'Accel2D':timing.get('accel_2d',np.nan),'Accel3D':timing.get('accel_3d',np.nan),'Rising3D':timing.get('rising_3d',False),'TimingStage':timing.get('timing_stage','—'),'HourlyConfirm':ex.get('hourly_confirmation',np.nan),'P5_5D':ex.get('p5_5d',np.nan),'P10_5D':ex.get('p10_5d',np.nan),'P15_5D':ex.get('p15_5d',np.nan),'P15_5D_N':ex.get('p15_5d_n',0),'RobustRVOL':ex.get('robust_volume_ratio',np.nan),'Retention':ex.get('post_impulse_retention',np.nan),'DryUp':ex.get('volume_dryup',np.nan),'ReExpansion':ex.get('volume_reexpansion',np.nan),'SignalLift':round(cmp.get('signal_lift_dynamic',np.nan),2) if np.isfinite(cmp.get('signal_lift_dynamic',np.nan)) else np.nan,'CalibrationConfidence':round(conf,1),'BacktestN':int(db.get('n',0) or 0),'EmpiricalHitRate':round(float(db.get('hit_rate'))*100,1) if db.get('n',0) and np.isfinite(db.get('hit_rate',np.nan)) else np.nan,'Price':round(float(lr['Close']),4),'VolumeRatio':round(float(lr.get('volume_ratio',np.nan)),2) if np.isfinite(float(lr.get('volume_ratio',np.nan))) else np.nan,'LiveIntradayRVOL':round(float(hfeat.dropna(subset=['Close']).iloc[-1].get('time_adjusted_rvol',np.nan)),2) if hfeat is not None and len(hfeat) and np.isfinite(float(hfeat.dropna(subset=['Close']).iloc[-1].get('time_adjusted_rvol',np.nan))) else np.nan,'DailyRobustRVOL':round(float(daily_lr.get('robust_volume_ratio',np.nan)),2) if np.isfinite(float(daily_lr.get('robust_volume_ratio',np.nan))) else np.nan,'TimeAdjustedRVOL':round(float((hfeat.dropna(subset=['Close']).iloc[-1].get('time_adjusted_rvol',np.nan) if hfeat is not None and len(hfeat) else daily_lr.get('robust_volume_ratio',np.nan))),2) if np.isfinite(float((hfeat.dropna(subset=['Close']).iloc[-1].get('time_adjusted_rvol',np.nan) if hfeat is not None and len(hfeat) else daily_lr.get('robust_volume_ratio',np.nan)))) else np.nan,'VolumeContext':latest_live.get('volume_context','N/A'),'BullishVolumeEvidence':latest_live.get('bullish_volume_evidence',np.nan),'BearishVolumeEvidence':latest_live.get('bearish_volume_evidence',np.nan),'ExitPressure':timing.get('exit_pressure',latest_live.get('exit_pressure',np.nan)),'ExitStage':timing.get('exit_stage',latest_live.get('exit_stage','CLEAR')),'PlanValid':bool(ent.get('plan_valid',False)),'PlanReason':ent.get('plan_reason',''),'SplitAdjusted':bool(ca_report.get('split_adjusted',False)),'DataQuality':str(ca_report.get('data_quality','OK')),'RSI14':round(float(lr.get('rsi14',np.nan)),1) if np.isfinite(float(lr.get('rsi14',np.nan))) else np.nan})
        except Exception as e:
            skipped.append({'Ticker':ticker,'Stage':'Deep','Reason':f'{type(e).__name__}: {str(e)[:140]}'})
            continue
    out=pd.DataFrame(rows).sort_values(['Prediction','DynamicEarly','EntryScore'],ascending=False).reset_index(drop=True) if rows else pd.DataFrame()
    out.attrs['scan_meta']={'requested':len(tickers),'daily_success':daily_success,'finalists':len(stage),'deep_success':len(rows),'skipped':skipped}
    return out

# Prefer engine implementations when present; otherwise use the verified local copy.
dynamic_scores = dynamic_scores if callable(dynamic_scores) else _v544_dynamic_scores
compare_static_dynamic_backtest = compare_static_dynamic_backtest if callable(compare_static_dynamic_backtest) else _v544_compare_static_dynamic_backtest
scan_universe_dynamic = scan_universe_dynamic if callable(scan_universe_dynamic) else _v544_scan_universe_dynamic

def early_event_backtest(feat, event_pct=.06, lookbacks=(1, 2, 3), min_turnover=0):
    """Single-ticker diagnostic: scores 1/2/3 trading days before close-to-close gains >= target."""
    f = feat.copy()
    if f is None or len(f) == 0:
        return pd.DataFrame()
    f["quant_score_bt"] = [score_row(r, min_turnover)[0] for _, r in f.iterrows()]
    f["early_score_bt"] = [early_score_row(r)[0] for _, r in f.iterrows()]
    f["day_return_bt"] = f["Close"].pct_change()
    rows = []
    for i in range(1, len(f)):
        day_ret = float(f["day_return_bt"].iloc[i]) if pd.notna(f["day_return_bt"].iloc[i]) else np.nan
        if not np.isfinite(day_ret) or day_ret < float(event_pct):
            continue
        row = {
            "EventDate": f.index[i],
            "EventReturnPct": day_ret * 100.0,
            "EventQuality": "OUTLIER REVIEW" if abs(day_ret) > 0.60 else "NORMAL",
            "PrevClose": float(f["Close"].iloc[i-1]),
            "EventClose": float(f["Close"].iloc[i]),
        }
        for lb in lookbacks:
            j = i - int(lb)
            row[f"Quant_D{lb}"] = float(f["quant_score_bt"].iloc[j]) if j >= 0 else np.nan
            row[f"Early_D{lb}"] = float(f["early_score_bt"].iloc[j]) if j >= 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def component_calibration(feat, event_pct=.03, lookbacks=(1,2,3), min_turnover=0):
    """Compare component activation before strong up-days with its normal historical baseline.

    Returns two summary DataFrames (Early and Quant). The event sample is made of the
    1/2/3 trading days before each close-to-close gain >= event_pct. Baseline is all
    eligible historical days. Lift > 1 means the component was active more often before
    strong up-days than on a typical historical day.
    """
    f = feat.copy()
    if f is None or len(f) == 0:
        return pd.DataFrame(), pd.DataFrame(), 0
    f['event_ret_cal'] = f['Close'].pct_change()
    event_indices = [i for i in range(1, len(f)) if pd.notna(f['event_ret_cal'].iloc[i]) and float(f['event_ret_cal'].iloc[i]) >= float(event_pct)]
    if not event_indices:
        return pd.DataFrame(), pd.DataFrame(), 0

    def build(kind):
        # Historical baseline: how often each component is active on an ordinary eligible row.
        baseline = {}
        component_max = {}
        for _, r in f.iterrows():
            comps = early_score_row(r)[1] if kind == 'early' else score_row(r, min_turnover)[1]
            for name, pts, mx in comps:
                component_max[name] = float(mx)
                baseline.setdefault(name, []).append(float(pts) if np.isfinite(float(pts)) else 0.0)

        event_records = []
        event_component_seen = {name: set() for name in component_max}
        by_lb = {lb: {name: [] for name in component_max} for lb in lookbacks}
        for event_no, i in enumerate(event_indices):
            for lb in lookbacks:
                j = i - int(lb)
                if j < 0:
                    continue
                r = f.iloc[j]
                comps = early_score_row(r)[1] if kind == 'early' else score_row(r, min_turnover)[1]
                for name, pts, mx in comps:
                    pts = float(pts) if np.isfinite(float(pts)) else 0.0
                    mx = float(mx)
                    active = pts > 0
                    event_records.append((event_no, lb, name, pts, mx, active))
                    by_lb[lb][name].append(active)
                    if active:
                        event_component_seen.setdefault(name, set()).add(event_no)

        rows=[]
        total_events=len(event_indices)
        for name,mx in component_max.items():
            rec=[x for x in event_records if x[2]==name]
            pts=[x[3] for x in rec]
            active=[x[5] for x in rec]
            base=baseline.get(name,[])
            event_active=100*np.mean(active) if active else np.nan
            base_active=100*np.mean([p>0 for p in base]) if base else np.nan
            lift=(event_active/base_active) if np.isfinite(event_active) and np.isfinite(base_active) and base_active>0 else np.nan
            strength=100*np.mean([p/mx for p in pts]) if pts and mx>0 else np.nan
            coverage=100*len(event_component_seen.get(name,set()))/total_events if total_events else np.nan
            row={
                'Component':name,
                'Event coverage %':coverage,
                'Pre-event active %':event_active,
                'Baseline active %':base_active,
                'Lift x':lift,
                'Avg strength %':strength,
            }
            for lb in sorted(lookbacks, reverse=True):
                vals=by_lb[lb].get(name,[])
                row[f'D-{lb} active %']=100*np.mean(vals) if vals else np.nan
            rows.append(row)
        z=pd.DataFrame(rows)
        if not z.empty:
            z=z.sort_values(['Lift x','Event coverage %','Avg strength %'],ascending=[False,False,False],na_position='last').reset_index(drop=True)
        return z

    return build('early'), build('quant'), len(event_indices)




def normalize_backtest_confidence(bt):
    """V5.3.3 single source of truth for confidence UI and decision logic.

    Recomputes the 80/20 confidence from raw backtest outputs so the displayed
    Backtest Performance, Sample Reliability and Combined Confidence can never
    disagree, even if app.py and quant_engine.py were uploaded out of sync.
    """
    out = dict(bt or {})
    n = int(out.get("n", 0) or 0)
    hr = out.get("hit_rate", np.nan)
    try:
        hr = float(hr)
    except Exception:
        hr = np.nan
    if n <= 0 or not np.isfinite(hr):
        performance = 0.0
        reliability = 0.0
        confidence = 0.0
        label = "LOW"
    else:
        performance = 100.0 * hr
        reliability = 100.0 * min(1.0, math.sqrt(n / 60.0))
        confidence = 0.80 * performance + 0.20 * reliability
        label = "HIGH" if n >= 30 and hr >= 0.60 else ("MEDIUM" if n >= 12 and hr >= 0.45 else "LOW")
    out["backtest_performance"] = round(performance, 1)
    out["sample_reliability"] = round(reliability, 1)
    out["confidence"] = round(confidence, 1)
    out["confidence_label"] = label
    return out

def backtest_display(bt):
    """Avoid presenting a fragile percentage as strong evidence when the sample is tiny."""
    n=int(bt.get('n',0) or 0)
    if n == 0:
        return '—', 'NO SAMPLE'
    hits=int(bt.get('hits', round(float(bt.get('hit_rate',0))*n)))
    if n < 12:
        return f'{hits}/{n} hits', 'LOW SAMPLE'
    return f"{float(bt.get('hit_rate',np.nan))*100:.1f}%", bt.get('confidence_label','')

st.set_page_config(page_title=f"AI Stock Hunter — V{APP_VERSION}",page_icon="📈",layout="wide",initial_sidebar_state="collapsed")
st.markdown("""<style>
:root{--bg:#080b12;--panel:#111722;--panel2:#151d2b;--text:#f5f7fb;--muted:#8f9bad;--accent:#8b6cff;--cyan:#39d9e8;--good:#35d49a;--warn:#f6c85f;--bad:#ff647c;--line:#243044}
html,body,[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 15% 0%,#151a2e 0,#080b12 34%);color:var(--text)} [data-testid="stHeader"]{background:transparent}.block-container{max-width:1180px;padding-top:2rem;padding-bottom:5rem} h1,h2,h3,h4,p,label,span,div{font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}.hero{padding:30px 30px;border:1px solid #2b3954;border-radius:26px;background:radial-gradient(circle at 85% 15%,rgba(57,217,232,.12),transparent 34%),linear-gradient(135deg,rgba(139,108,255,.20),rgba(17,23,34,.95));box-shadow:0 24px 70px rgba(0,0,0,.32);margin-bottom:22px}.hero-title{font-size:clamp(2.4rem,6vw,4.5rem);font-weight:850;line-height:.98;letter-spacing:-.05em}.hero-sub{color:var(--muted);font-size:1.08rem;margin-top:14px}.badge{display:inline-block;padding:5px 10px;border-radius:999px;background:#20283a;color:#b8c2d5;font-size:.78rem;font-weight:700;letter-spacing:.04em}.card{background:linear-gradient(180deg,rgba(22,30,45,.98),rgba(14,20,31,.98));border:1px solid #2a3851;border-radius:20px;padding:18px 20px;margin-bottom:14px;box-shadow:0 14px 34px rgba(0,0,0,.20)}.good{color:var(--good);font-weight:800}.warn{color:var(--warn);font-weight:800}.bad{color:var(--bad);font-weight:800}.muted{color:var(--muted)}.section{font-size:1.55rem;font-weight:800;margin:28px 0 12px}.score{font-size:2.1rem;font-weight:850}.stButton>button{width:100%;min-height:52px;border-radius:14px;background:linear-gradient(90deg,#6e56ff,#3c8cff);border:0;color:white;font-weight:750}.stButton>button:hover{filter:brightness(1.08);color:white}.stTextArea textarea,.stTextInput input,div[data-baseweb="select"]>div{background:#111722!important;border-color:#29354a!important;border-radius:13px!important}.stDataFrame{border:1px solid #263249;border-radius:16px;overflow:hidden}[data-testid="stMetric"]{background:#111722;border:1px solid #263249;padding:14px;border-radius:16px}[data-testid="stMetricValue"]{font-size:1.55rem}.stTabs [data-baseweb="tab-list"]{gap:10px}.stTabs [data-baseweb="tab"]{border-radius:12px;padding:8px 14px}.stTabs [aria-selected="true"]{background:#171f31}
@media (max-width: 700px){
  .block-container{padding-left:.85rem;padding-right:.85rem;padding-top:1rem}
  .stTabs [data-baseweb="tab-list"]{gap:2px;width:100%;overflow:visible}
  .stTabs [data-baseweb="tab"]{flex:1 1 0;min-width:0;padding:7px 4px;font-size:.82rem;white-space:nowrap;justify-content:center}
  .stTabs [data-baseweb="tab"] p{font-size:.82rem!important;white-space:nowrap!important}
}

</style>""",unsafe_allow_html=True)
st.markdown(f"""<div class='hero'><span class='badge'>V{APP_VERSION} • DIRECTIONAL VOLUME • EXIT PRESSURE • FEEDBACK LOOP • 150 STOCKS</span><div class='hero-title'>📈 AI Stock Hunter<br>V{APP_VERSION}</div><div class='hero-sub'>Decision Intelligence • Direction-aware Volume • Trade + Exit Signals • Outcome Learning</div></div>""",unsafe_allow_html=True)

DEFAULT_TICKERS="1196.HK,NVDA,NVMI,MU,AMD,AVGO,AMZN,META,GOOGL,MSFT,AAPL,TSLA,PLTR,CRWV,NBIS,GILD,ORCL,SMCI,ARM,TSM,QCOM,NFLX,UBER,COIN,HOOD,TTWO"
BROAD_200="1196.HK,NVDA,NVMI,MU,AMD,AVGO,AMZN,META,GOOGL,MSFT,AAPL,TSLA,PLTR,CRWV,NBIS,GILD,ORCL,SMCI,ARM,TSM,QCOM,NFLX,UBER,COIN,HOOD,TTWO,ADBE,CRM,INTC,CSCO,AMAT,LRCX,KLAC,MRVL,ADI,TXN,MCHP,ON,MPWR,DELL,HPE,ANET,NET,DDOG,SNOW,ZS,CRWD,PANW,FTNT,OKTA,SHOP,MELI,SE,ABNB,BKNG,DASH,RBLX,SPOT,SNAP,PINS,ROKU,PYPL,XYZ,V,MA,JPM,BAC,WFC,C,GS,MS,AXP,BLK,SCHW,COF,USB,PNC,TFC,BK,STT,BRK-B,UNH,LLY,JNJ,ABBV,MRK,PFE,AMGN,REGN,VRTX,ISRG,MDT,SYK,BSX,EW,TMO,DHR,ABT,MDLZ,KO,PEP,PG,COST,WMT,TGT,HD,LOW,NKE,SBUX,MCD,CMG,YUM,DIS,CMCSA,T,VZ,TMUS,CHTR,XOM,CVX,COP,SLB,EOG,OXY,MPC,VLO,PSX,KMI,WMB,NEE,DUK,SO,AEP,SRE,EXC,D,CEG,VST,CAT,DE,GE,GEV,HON,RTX,LMT,NOC,BA,GD,ETN,EMR,PH,MMM,UPS,FDX,UNP,CSX,NSC,WM,RSG,LIN,APD,SHW,FCX,NEM,NUE,STLD,AA,DOW,DD,GM,F,TM,RIVN,LCID,APO,KKR,BX,ARES,SPGI,MCO,CME,ICE,NDAQ,CB,MMC,AON,PGR,ALL,MET,PRU,AFL,CI,CVS,HUM,CNC,ELV,HCA,IQV,ZTS,BIIB"
NASDAQ_50="NVDA,AMD,MU,AVGO,NVMI,QCOM,ARM,INTC,AMAT,MSFT,GOOGL,META,AMZN,AAPL,ORCL,ADBE,PLTR,CSCO,NFLX,COST,PEP,MDLZ,AMGN,GILD,REGN,VRTX,ISRG,MRNA,BIIB,TSLA,TTWO,EA,RBLX,ABNB,BKNG,DASH,CRWD,PANW,FTNT,DDOG,ZS,MRVL,ADI,MCHP,ON,LRCX,KLAC,CDNS,SNPS,INTU"
HK_50="1196.HK,1570.HK,0700.HK,9988.HK,3690.HK,9618.HK,1810.HK,9999.HK,1024.HK,9888.HK,0005.HK,0939.HK,1398.HK,3988.HK,1299.HK,2318.HK,0388.HK,0883.HK,0857.HK,0386.HK,0941.HK,0762.HK,0728.HK,0002.HK,0003.HK,0006.HK,0011.HK,0016.HK,0012.HK,0823.HK,1109.HK,1997.HK,2020.HK,2331.HK,2313.HK,1928.HK,0291.HK,9633.HK,1211.HK,0175.HK,9866.HK,2015.HK,6690.HK,2269.HK,6160.HK,1177.HK,3750.HK,2899.HK,2600.HK,0669.HK"
TASE_50="TEVA.TA,NICE.TA,LUMI.TA,POLI.TA,MZTF.TA,FIBI.TA,DSCT.TA,ESLT.TA,ICL.TA,CAMT.TA,NVMI.TA,TSEM.TA,ENLT.TA,OPCE.TA,DORL.TA,ORL.TA,DELG.TA,FTAL.TA,FOX.TA,RMLI.TA,SHUF.TA,STRA.TA,ILCO.TA,PTNR.TA,CEL.TA,BEZQ.TA,AZRG.TA,MLSR.TA,AMOT.TA,GCT.TA,ALHE.TA,MGDL.TA,CLIS.TA,PHOE.TA,HAREL.TA,MMHD.TA,ONE.TA,MTRX.TA,HIPR.TA,AURA.TA,DLEKG.TA,NWMD.TA,ISRA.TA,ELAL.TA,FORTY.TA,SPNS.TA,AQAR.TA,ARGO.TA,KRNT.TA,PERI.TA"
VALIDATION_50=NASDAQ_50
VALIDATION_150=NASDAQ_50+","+HK_50+","+TASE_50
MARKET_MAP={**{t:'NASDAQ' for t in NASDAQ_50.split(',')},**{t:'HONG KONG' for t in HK_50.split(',')},**{t:'TEL AVIV' for t in TASE_50.split(',')}}
SECTOR_MAP={}
for t in NASDAQ_50.split(','): SECTOR_MAP[t]='Diversified NASDAQ'
for t in HK_50.split(','): SECTOR_MAP[t]='Diversified HK'
for t in TASE_50.split(','): SECTOR_MAP[t]='Diversified TASE'
# Explicit anchors/case-study names are always included in Hong Kong 50.
SECTOR_MAP.update({'1196.HK':'Conglomerate / Digital','1570.HK':'Industrial / Property','0700.HK':'Technology','0005.HK':'Banking','0883.HK':'Energy','1211.HK':'EV','2269.HK':'Healthcare','0823.HK':'REIT','3750.HK':'Battery','2899.HK':'Materials'})
def _clip100(x):
    try: return float(np.clip(float(x),0,100))
    except: return 0.0

def opportunity_fields(row):
    """V6.0 unified long-side decision layer. Volume is direction-aware; exit pressure can veto bullish setups."""
    move=_clip100(row.get('MoveScore',0)); explosive=_clip100(row.get('ExplosiveScore',0)); entry=_clip100(row.get('EntryScore',0)); hourly=_clip100(row.get('HourlyConfirm',50))
    exitp=_clip100(row.get('ExitPressure',0))
    a1=float(row.get('Accel1D',0) or 0); a2=float(row.get('Accel2D',0) or 0)
    accel=_clip100(50 + 2.0*a1 + 1.5*a2)
    conf=_clip100(row.get('CalibrationConfidence',0)); n=max(0,float(row.get('BacktestN',0) or 0)); lift=float(row.get('SignalLift',1) or 1)
    # Thin backtests cannot dominate reliability. Full evidence weight is reached around 20+ signals.
    evidence=min(1.0,math.sqrt(n/20.0)) if n>0 else 0.0
    sample=_clip100(100*np.sqrt(n/60.0))
    lift_score=_clip100(max(0,50+35*(lift-1)))
    reliability=_clip100(.45*conf*evidence + .30*sample + .25*lift_score*evidence)
    raw=_clip100(.19*move+.24*explosive+.19*entry+.12*accel+.10*hourly+.16*reliability)
    score=_clip100(raw*(1.0-0.40*exitp/100.0))
    if exitp>=72: stage='WAIT'
    elif score>=78 and entry>=65 and hourly>=60 and exitp<45 and (a1>=5 or a2>=8): stage='TRIGGER'
    elif score>=68 and entry>=55 and exitp<55: stage='ARMED'
    elif score>=55 and exitp<72: stage='WATCH'
    else: stage='WAIT'
    return round(score,1),round(reliability,1),stage


def _market_phase(market):
    # Operational clock labels only; exchange holidays/half-days are not inferred here.
    cfg={
        'NASDAQ':('America/New_York',time(4,0),time(9,30),time(16,0)),
        'HONG KONG':('Asia/Hong_Kong',time(9,0),time(9,30),time(16,0)),
        'TEL AVIV':('Asia/Jerusalem',time(9,0),time(9,59),time(17,25)),
    }
    if market not in cfg:return 'UNKNOWN'
    tz,pre,op,cl=cfg[market]; now=datetime.now(ZoneInfo(tz)); t=now.time().replace(tzinfo=None)
    if now.weekday()>=5:return 'CLOSED'
    if pre<=t<op:return 'PRE-MARKET' if market=='NASDAQ' else 'PRE-OPEN'
    if op<=t<cl:return 'OPEN'
    if market=='NASDAQ' and cl<=t<time(20,0): return 'AFTER-MARKET'
    return 'CLOSED'


def _trade_stage_label(stage):
    return 'TRADE TRIGGER' if str(stage)=='TRIGGER' else str(stage)


def _movement_stage_label(stage):
    return 'MOVEMENT TRIGGER' if str(stage)=='TRIGGER' else str(stage)


def _why_not_trade_trigger(r):
    reasons=[]
    opp=float(r.get('OpportunityScore',0) or 0); ent=float(r.get('EntryScore',0) or 0); hr=float(r.get('HourlyConfirm',0) or 0); xp=float(r.get('ExitPressure',0) or 0)
    a1=float(r.get('Accel1D',0) or 0); a2=float(r.get('Accel2D',0) or 0)
    if opp<78: reasons.append(f'Opportunity +{78-opp:.1f}')
    if ent<65: reasons.append(f'Entry +{65-ent:.1f}')
    if hr<60: reasons.append(f'Hourly +{60-hr:.1f}')
    if not (a1>=5 or a2>=8): reasons.append('Momentum confirmation')
    if xp>=45: reasons.append(f'Exit pressure {xp:.0f}')
    if not bool(r.get('PlanValid',True)): reasons.append('Trade-plan data check')
    if str(r.get('DataQuality','OK'))!='OK': reasons.append('Cross-timeframe data mismatch')
    return ' • '.join(reasons[:4]) if reasons else 'All core trade-trigger conditions aligned'


def add_market_and_opportunity(df):
    z=df.copy()
    z['Market']=z['Ticker'].map(MARKET_MAP).fillna('CUSTOM')
    z['Sector']=z['Ticker'].map(SECTOR_MAP).fillna('Other')
    if 'ExitPressure' not in z:z['ExitPressure']=0.0
    if 'ExitStage' not in z:z['ExitStage']='CLEAR'
    vals=z.apply(opportunity_fields,axis=1,result_type='expand'); vals.columns=['OpportunityScore','Reliability','OpportunityStage']
    z=pd.concat([z,vals],axis=1)
    def _evidence_quality(r):
        n=float(r.get('BacktestN',0) or 0); rel=float(r.get('Reliability',0) or 0); conf=float(r.get('CalibrationConfidence',0) or 0)
        if n>=30 and rel>=65 and conf>=55:return 'STRONG'
        if n>=12 and rel>=45:return 'MEDIUM'
        return 'LOW'
    z['EvidenceQuality']=z.apply(_evidence_quality,axis=1)
    z['TradeStage']=z['OpportunityStage'].map(_trade_stage_label)
    z['MovementStage']=z.get('TimingStage',pd.Series(['—']*len(z),index=z.index)).map(_movement_stage_label)
    z['WhyNotTradeTrigger']=z.apply(_why_not_trade_trigger,axis=1)
    z['MarketPhase']=z['Market'].map(_market_phase)
    z['PreviousSessionTrigger']=z['OpportunityStage'].eq('TRIGGER')

    z['PMPrice']=np.nan; z['PMChangePct']=np.nan; z['PMVolume']=np.nan; z['PMVolumeStrength']=np.nan; z['PMData']='N/A'; z['PMConfirmation']='N/A'
    nas_pm=z[(z['Market'].eq('NASDAQ')) & (z['MarketPhase'].eq('PRE-MARKET'))]['Ticker'].tolist()
    pm=fetch_premarket_snapshots(nas_pm) if nas_pm else {}
    for i,r in z.iterrows():
        snap=pm.get(str(r['Ticker']).upper())
        if snap:
            for k in ['PMPrice','PMChangePct','PMVolume','PMVolumeStrength','PMData']: z.at[i,k]=snap.get(k,np.nan if k!='PMData' else 'N/A')
            ch=float(snap.get('PMChangePct',np.nan)); vr=float(snap.get('PMVolumeStrength',np.nan))
            if np.isfinite(ch):
                if ch>=0.6 and np.isfinite(vr) and vr>=0.8: c='CONFIRMED'
                elif ch>=0.6 and not np.isfinite(vr): c='PRICE CONFIRMED • VOLUME UNAVAILABLE'
                elif ch<=-1.5 and np.isfinite(vr) and vr>=1.0: c='STRONGLY WEAKENED'
                elif ch<=-0.5: c='WEAKENED'
                else: c='NEUTRAL'
                z.at[i,'PMConfirmation']=c

    z['AHPrice']=np.nan; z['AHChangePct']=np.nan; z['AHVolume']=np.nan; z['AHVolumeStrength']=np.nan; z['AHData']='N/A'; z['AHConfirmation']='N/A'
    nas_ah=z[(z['Market'].eq('NASDAQ')) & (z['MarketPhase'].eq('AFTER-MARKET'))]['Ticker'].tolist()
    ah=fetch_aftermarket_snapshots(nas_ah) if nas_ah else {}
    for i,r in z.iterrows():
        snap=ah.get(str(r['Ticker']).upper())
        if snap:
            for k in ['AHPrice','AHChangePct','AHVolume','AHVolumeStrength','AHData']: z.at[i,k]=snap.get(k,np.nan if k!='AHData' else 'N/A')
            ch=float(snap.get('AHChangePct',np.nan)); vr=float(snap.get('AHVolumeStrength',np.nan))
            if np.isfinite(ch):
                if ch>=0.6 and np.isfinite(vr) and vr>=0.8: c='CONFIRMED'
                elif ch>=0.6 and not np.isfinite(vr): c='PRICE CONFIRMED • VOLUME UNAVAILABLE'
                elif ch<=-1.5 and np.isfinite(vr) and vr>=1.0: c='STRONGLY WEAKENED'
                elif ch<=-0.5: c='WEAKENED'
                else: c='NEUTRAL'
                z.at[i,'AHConfirmation']=c

    z['LiveStage']=z['OpportunityStage']
    live_ok=z['PreviousSessionTrigger'] & z['MarketPhase'].eq('OPEN') & (pd.to_numeric(z['ExitPressure'],errors='coerce').fillna(0)<55)
    z.loc[live_ok,'LiveStage']='LIVE TRIGGERED'
    pm_trigger=z['PreviousSessionTrigger'] & z['MarketPhase'].eq('PRE-MARKET')
    z.loc[pm_trigger,'LiveStage']='PRE-MARKET SETUP'; z.loc[pm_trigger & z['PMConfirmation'].eq('CONFIRMED'),'LiveStage']='PRE-MARKET CONFIRMED'; z.loc[pm_trigger & z['PMConfirmation'].isin(['WEAKENED','STRONGLY WEAKENED']),'LiveStage']='PRE-MARKET WEAKENED'
    ah_trigger=z['PreviousSessionTrigger'] & z['MarketPhase'].eq('AFTER-MARKET')
    z.loc[ah_trigger,'LiveStage']='AFTER-MARKET SETUP'; z.loc[ah_trigger & z['AHConfirmation'].eq('CONFIRMED'),'LiveStage']='AFTER-MARKET CONFIRMED'; z.loc[ah_trigger & z['AHConfirmation'].isin(['WEAKENED','STRONGLY WEAKENED']),'LiveStage']='AFTER-MARKET WEAKENED'
    z.loc[z['PreviousSessionTrigger'] & z['MarketPhase'].eq('CLOSED'),'LiveStage']='PREVIOUS SESSION TRIGGER'

    def session_status(r):
        phase=str(r.get('MarketPhase','UNKNOWN')); stage=_trade_stage_label(r.get('OpportunityStage','WAIT')); live=str(r.get('LiveStage',stage))
        if phase=='CLOSED': return f'CLOSED • PREVIOUS SESSION: {stage}'
        if phase=='PRE-OPEN': return f'PRE-OPEN • PREVIOUS SESSION: {stage}'
        if phase=='PRE-MARKET':
            pmc=str(r.get('PMConfirmation','N/A')); ch=r.get('PMChangePct',np.nan); move=f' ({float(ch):+.2f}%)' if pd.notna(ch) else ''; label='DATA UNAVAILABLE' if pmc=='N/A' else pmc
            return f'PRE-MARKET: {label}{move} • PREVIOUS SESSION: {stage}'
        if phase=='AFTER-MARKET':
            ahc=str(r.get('AHConfirmation','N/A')); ch=r.get('AHChangePct',np.nan); move=f' ({float(ch):+.2f}%)' if pd.notna(ch) else ''; label='DATA UNAVAILABLE' if ahc=='N/A' else ahc
            return f'AFTER-MARKET: {label}{move} • REGULAR SESSION: {stage}'
        if phase=='OPEN': return f'OPEN • {live}'
        return f'{phase} • {stage}'
    z['SessionStatus']=z.apply(session_status,axis=1)

    def decision(r):
        stg=str(r.get('OpportunityStage','WAIT')); pred=float(r.get('Prediction',0) or 0); xp=float(r.get('ExitPressure',0) or 0)
        if xp>=72:return 'EXIT TRIGGER'
        if xp>=55:return 'EXIT ARMED'
        if stg=='TRIGGER':return 'TRADE TRIGGER'
        if stg=='ARMED':return 'ARMED'
        if stg=='WATCH' or pred>=58:return 'WATCH'
        return 'WAIT'
    z['Signal']=z.apply(decision,axis=1)

    def top_score(r):
        # Entry is already inside Opportunity; no direct duplicate Entry weight here.
        base=_clip100(.66*float(r.get('OpportunityScore',0) or 0)+.20*_clip100(r.get('Prediction',0))+.14*_clip100(r.get('Reliability',0)))
        pmc=str(r.get('PMConfirmation','N/A')); ahc=str(r.get('AHConfirmation','N/A')); scale={'CONFIRMED':3.0,'NEUTRAL':0.0,'WEAKENED':-5.0,'STRONGLY WEAKENED':-9.0,'PRICE CONFIRMED • VOLUME UNAVAILABLE':0.5}
        mod=scale.get(pmc,0.0)+scale.get(ahc,0.0)
        return round(_clip100(base+mod),1)
    z['TopScore']=z.apply(top_score,axis=1)
    z=z.sort_values(['TopScore','OpportunityScore','ExplosiveScore'],ascending=False).reset_index(drop=True)
    z['GlobalRank']=np.arange(1,len(z)+1)
    z['MarketRank']=z.groupby('Market')['TopScore'].rank(method='first',ascending=False).astype(int)
    z['SectorRank']=z.groupby(['Market','Sector'])['TopScore'].rank(method='first',ascending=False).astype(int)
    priority={'TRIGGER':5,'ARMED':4,'WATCH':3,'WAIT':2}
    z['_StagePriority']=z['OpportunityStage'].map(priority).fillna(1)
    z['_ExitPenalty']=(pd.to_numeric(z['ExitPressure'],errors='coerce').fillna(0)>=55).astype(int)
    order=z.sort_values(['_ExitPenalty','_StagePriority','TopScore'],ascending=[True,False,False]).index.tolist()
    pr={idx:i+1 for i,idx in enumerate(order)}; z['TradePriorityRank']=[pr[i] for i in z.index]
    _plan_ok=z['PlanValid'].astype(bool) if 'PlanValid' in z else True
    _data_ok=z['DataQuality'].eq('OK') if 'DataQuality' in z else True
    z['ActionableNow']=(((z['MarketPhase'].eq('OPEN')) & z['LiveStage'].eq('LIVE TRIGGERED')) | ((z['MarketPhase'].eq('PRE-MARKET')) & z['PMConfirmation'].eq('CONFIRMED') & z['OpportunityStage'].isin(['ARMED','TRIGGER'])) | ((z['MarketPhase'].eq('AFTER-MARKET')) & z['AHConfirmation'].eq('CONFIRMED') & z['OpportunityStage'].isin(['ARMED','TRIGGER']))) & (pd.to_numeric(z['ExitPressure'],errors='coerce').fillna(0)<55) & _plan_ok & _data_ok
    return z.drop(columns=['_StagePriority','_ExitPenalty'],errors='ignore')


def safe(x,d=2):
    try:return "—" if pd.isna(x) else f"{float(x):.{d}f}"
    except:return "—"
def cls(s):
    s=str(s).upper()
    # Order matters: previous-session/closed labels must never turn green just because they contain “TRIGGER”.
    if any(x in s for x in ["WEAKENED","AVOID","COLD","EXIT TRIGGER","EXIT ARMED","DISTRIBUTION","DATA CHECK"]): return "bad"
    if any(x in s for x in ["CLOSED","PREVIOUS SESSION","PRE-OPEN","WATCH","WAIT","ARMED","SETUP","NEUTRAL","MOVEMENT TRIGGER"]): return "warn"
    if any(x in s for x in ["PRE-MARKET CONFIRMED","AFTER-MARKET CONFIRMED","LIVE TRIGGERED","TRADE TRIGGER","ENTER"]): return "good"
    return "warn"
def chart(df,title,layers=None,show_rsi=False,show_macd=False,trade_plan=None,current_price=None):
    """Stable display-only Plotly chart with persistent UI state and mobile-safe controls."""
    q=df.copy()
    layers=layers or ["EMA9","EMA20","EMA50","VWAP","Volume"]
    extra_rows=int(bool(show_rsi))+int(bool(show_macd))
    rows=2+extra_rows
    heights=[.68,.20]
    if show_rsi: heights.append(.12)
    if show_macd: heights.append(.16)
    # normalize heights for Plotly
    total=sum(heights); heights=[h/total for h in heights]
    fig=make_subplots(rows=rows,cols=1,shared_xaxes=True,row_heights=heights,vertical_spacing=.035)
    fig.add_trace(go.Candlestick(x=q.index,open=q.Open,high=q.High,low=q.Low,close=q.Close,name="Price"),row=1,col=1)
    if current_price is not None and np.isfinite(float(current_price)):
        fig.add_hline(y=float(current_price),line_dash="dot",line_width=1.2,annotation_text="Last price",row=1,col=1)
    if isinstance(trade_plan,dict) and bool(trade_plan.get('plan_valid',False)):
        try:
            zl=float(trade_plan.get('zone_low')); zh=float(trade_plan.get('zone_high')); inv=float(trade_plan.get('invalidation')); trg=float(trade_plan.get('trigger')); t1=float(trade_plan.get('target1')); t2=float(trade_plan.get('target2'))
            if all(np.isfinite(v) for v in [zl,zh,inv,trg,t1,t2]):
                fig.add_hrect(y0=zl,y1=zh,opacity=.10,line_width=0,annotation_text="Entry zone",row=1,col=1)
                fig.add_hline(y=trg,line_dash="dash",line_width=1,annotation_text="Trade trigger",row=1,col=1)
                fig.add_hline(y=inv,line_dash="dash",line_width=1,annotation_text="Invalidation",row=1,col=1)
                fig.add_hline(y=t1,line_dash="dot",line_width=1,annotation_text="T1",row=1,col=1)
                fig.add_hline(y=t2,line_dash="dot",line_width=1,annotation_text="T2",row=1,col=1)
        except Exception:
            pass
    overlays={"EMA9":"ema9","EMA20":"ema20","EMA50":"ema50","VWAP":"vwap"}
    for label,col in overlays.items():
        if label in layers and col in q:
            fig.add_trace(go.Scatter(x=q.index,y=q[col],name=label,line=dict(width=1.25)),row=1,col=1)
    if "Volume" in layers:
        fig.add_trace(go.Bar(x=q.index,y=q.Volume,name="Volume",opacity=.65),row=2,col=1)
    else:
        fig.add_trace(go.Bar(x=q.index,y=[0]*len(q),name="Volume",opacity=0,showlegend=False),row=2,col=1)
    next_row=3
    if show_rsi:
        if 'rsi14' in q:
            fig.add_trace(go.Scatter(x=q.index,y=q.rsi14,name="RSI14",line=dict(width=1.2)),row=next_row,col=1)
            fig.add_hline(y=70,line_dash="dot",row=next_row,col=1)
            fig.add_hline(y=30,line_dash="dot",row=next_row,col=1)
            fig.update_yaxes(range=[0,100],row=next_row,col=1)
        next_row+=1
    if show_macd:
        if 'macd_hist' in q:
            fig.add_trace(go.Bar(x=q.index,y=q.macd_hist,name="MACD hist",opacity=.75),row=next_row,col=1)
        if 'macd' in q:
            fig.add_trace(go.Scatter(x=q.index,y=q.macd,name="MACD",line=dict(width=1.1)),row=next_row,col=1)
        if 'macd_signal' in q:
            fig.add_trace(go.Scatter(x=q.index,y=q.macd_signal,name="MACD signal",line=dict(width=1.0)),row=next_row,col=1)
    fig.update_layout(
        height=610 + 100*extra_rows,
        title=title,
        template="plotly_dark",
        paper_bgcolor="#0b0f17",plot_bgcolor="#0b0f17",
        margin=dict(l=8,r=8,t=45,b=8),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="left",x=0),
        uirevision=f"stable-stock-chart-v590-{title}",
        dragmode="pan",
        autosize=True,
    )
    # Quick range buttons live on the bottom shared x-axis. Double-click also resets.
    fig.update_xaxes(
        rangeselector=dict(buttons=[
            dict(count=5,label="5D",step="day",stepmode="backward"),
            dict(count=1,label="1M",step="month",stepmode="backward"),
            dict(count=3,label="3M",step="month",stepmode="backward"),
            dict(count=6,label="6M",step="month",stepmode="backward"),
            dict(count=1,label="1Y",step="year",stepmode="backward"),
            dict(label="MAX",step="all"),
        ]),
        row=rows,col=1
    )
    return fig

CHART_CONFIG={
    "displaylogo":False,
    "responsive":True,
    "scrollZoom":True,
    "staticPlot":False,
    "displayModeBar":True,
    "modeBarButtonsToAdd":["zoom2d","pan2d","zoomIn2d","zoomOut2d","autoScale2d","resetScale2d"],
    "doubleClick":"reset",
    "modeBarButtonsToRemove":["select2d","lasso2d"],
    "toImageButtonOptions":{"format":"png","filename":"AI_Stock_Hunter_chart","scale":2},
}

def _entry_score_from_row(r, quant_score, early_score=0.0):
    """Single-source V6.0 Entry Score used by live analysis and validation."""
    if callable(entry_score_row):
        try:return float(entry_score_row(r,quant_score)[0])
        except Exception:pass
    return 0.0


def _entry_forward_metrics(feat, horizon, target_pct):
    f=feat.copy(); n=len(f)
    highs=f['High'].to_numpy(dtype='float64'); lows=f['Low'].to_numpy(dtype='float64'); closes=f['Close'].to_numpy(dtype='float64')
    hit=np.full(n,np.nan); ret=np.full(n,np.nan); dd=np.full(n,np.nan); days=np.full(n,np.nan)
    for i in range(n-int(horizon)):
        p=closes[i]; fh=highs[i+1:i+1+int(horizon)]; fl=lows[i+1:i+1+int(horizon)]
        target=p*(1+float(target_pct)); reached=np.where(fh>=target)[0]
        hit[i]=1.0 if len(reached) else 0.0
        days[i]=float(reached[0]+1) if len(reached) else np.nan
        ret[i]=closes[i+int(horizon)]/p-1.0
        dd[i]=np.nanmin(fl)/p-1.0
    return hit,ret,dd,days


def _entry_bucket(score):
    if score>=80:return '80–100'
    if score>=70:return '70–79'
    if score>=60:return '60–69'
    return '<60'


def _aggregate_entry_validation(rows):
    z=pd.DataFrame(rows)
    if z.empty:return pd.DataFrame(),pd.DataFrame()
    base=float(z['Hit'].mean()) if len(z) else np.nan
    out=[]
    for mode in ['Static','Dynamic']:
        m=z[z['Mode']==mode]
        for bucket in ['80–100','70–79','60–69','<60']:
            g=m[m['Bucket']==bucket]
            if g.empty:continue
            stock_rates=g.groupby('Ticker')['Hit'].mean()
            out.append({
                'Mode':mode,'Entry Score':bucket,'Signals':len(g),'Hit Rate %':100*float(g['Hit'].mean()),
                'Lift vs baseline':float(g['Hit'].mean()/base) if np.isfinite(base) and base>0 else np.nan,
                'Avg Forward Return %':100*float(g['ForwardReturn'].mean()),
                'Avg Drawdown %':100*float(g['Drawdown'].mean()),
                'Median Days to Target':float(g.loc[g['Hit']>0,'DaysToTarget'].median()) if (g['Hit']>0).any() else np.nan,
                'Positive stocks %':100*float((stock_rates>base).mean()) if len(stock_rates) and np.isfinite(base) else np.nan,
            })
    summary=pd.DataFrame(out)
    # Production-like gate: entry score >=72 and quant >=66.
    gates=[]
    for mode in ['Static','Dynamic']:
        g=z[(z.Mode==mode)&(z.EntryScore>=72)]
        if g.empty:continue
        gates.append({'Mode':mode,'Signals':len(g),'Hit Rate %':100*float(g.Hit.mean()),
                      'Lift vs baseline':float(g.Hit.mean()/base) if np.isfinite(base) and base>0 else np.nan,
                      'Avg Forward Return %':100*float(g.ForwardReturn.mean()),
                      'Avg Drawdown %':100*float(g.Drawdown.mean()),
                      'Median Days to Target':float(g.loc[g.Hit>0,'DaysToTarget'].median()) if (g.Hit>0).any() else np.nan})
    return summary,pd.DataFrame(gates)

def chart_request(timeframe_label, period_label):
    interval_map={"15m":"15m","1H":"1h","1D":"1d","1W":"1wk"}
    period_map={"1D":"1d","1W":"5d","5D":"5d","1M":"1mo","3M":"3mo","6M":"6mo","1Y":"1y","MAX":"max"}
    interval=interval_map[timeframe_label]
    period=period_map[period_label]
    capped=False
    # Short display periods should actually show intraday structure rather than one daily candle.
    if period_label=="1D":
        interval="5m"
    elif period_label in ("1W","5D") and timeframe_label in ("1D","1W"):
        interval="30m"
    # Yahoo intraday history is limited. Cap only the display request, never model calculations.
    if interval=="15m" and period not in ("1d","5d","1mo"):
        period="1mo"; capped=True
    if interval=="30m" and period not in ("1d","5d","1mo"):
        period="1mo"; capped=True
    return interval,period,capped

def scanner_excel_bytes(df,scan_meta=None):
    bio=BytesIO()
    out_df=df.copy()
    if 'BacktestN' in out_df:
        out_df['BacktestQuality']=np.where(pd.to_numeric(out_df['BacktestN'],errors='coerce').fillna(0)>=12,'EVIDENCE OK',np.where(pd.to_numeric(out_df['BacktestN'],errors='coerce').fillna(0)>0,'LOW SAMPLE','NO SAMPLE'))
        if 'EmpiricalHitRate' in out_df:out_df.loc[pd.to_numeric(out_df['BacktestN'],errors='coerce').fillna(0)<12,'EmpiricalHitRate']=np.nan
    with pd.ExcelWriter(bio,engine="openpyxl") as writer:
        out_df.to_excel(writer,index=False,sheet_name="Scanner Results")
        exp_cols=[c for c in ["Rank","Ticker","Signal","TradeStage","MovementStage","ExitPressure","ExitStage","VolumeContext","LiveIntradayRVOL","DailyRobustRVOL","TimeAdjustedRVOL","ExplosiveScore","ExplosiveStage","HourlyConfirm","P5_5D","P10_5D","P15_5D","P15_5D_N","EntryScore","Prediction","EvidenceQuality","BacktestQuality"] if c in out_df.columns]
        out_df[exp_cols].to_excel(writer,index=False,sheet_name="Explosive Move")
        hk=out_df[out_df["Ticker"].astype(str).str.endswith(".HK")].copy() if "Ticker" in out_df else pd.DataFrame()
        hk.to_excel(writer,index=False,sheet_name="Hong Kong Universe")
        sm=scan_meta or {}
        skipped=sm.get('skipped') or []
        meta=pd.DataFrame({"Field":["Version","Generated","Rows in export","Requested","Daily success","Deep success","Skipped/errors"],"Value":[APP_VERSION,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),len(df),sm.get('requested','—'),sm.get('daily_success','—'),sm.get('deep_success','—'),len(skipped)]})
        meta.to_excel(writer,index=False,sheet_name="About")
        if skipped:pd.DataFrame(skipped).to_excel(writer,index=False,sheet_name="Skipped")
    return bio.getvalue()


def _auto_backtest_threshold(feat,horizon,target_pct):
    rows=[]
    for th in [60,62,64,66,68,70,72,75]:
        b=normalize_backtest_confidence(backtest_signal(feat,int(horizon),float(target_pct),th,0))
        n=int(b.get('n',0) or 0); hr=float(b.get('hit_rate',np.nan)); ar=float(b.get('avg_return',np.nan))
        # Reward evidence first; tiny samples cannot win only because of 100% hit rate.
        evidence=min(1.0,math.sqrt(n/20.0)) if n else 0.0
        quality=(100*hr if np.isfinite(hr) else 0)*evidence + 10*max(-.1,min(.2,ar if np.isfinite(ar) else 0))*evidence + min(15,n/2)
        rows.append({'Threshold':th,'Signals':n,'Hit Rate %':100*hr if n>=12 and np.isfinite(hr) else np.nan,'Avg Return %':100*ar if n and np.isfinite(ar) else np.nan,'Evidence':round(100*evidence,1),'Quality':quality})
    tb=pd.DataFrame(rows)
    qualified=tb[tb.Signals>=12]
    pick=int((qualified if not qualified.empty else tb).sort_values(['Quality','Signals'],ascending=False).iloc[0].Threshold)
    return pick,tb


def _feedback_db_path_v600():
    base=Path.home()/'.ai_stock_hunter'
    try:base.mkdir(parents=True,exist_ok=True)
    except Exception:base=Path('/tmp')
    return base/'feedback_v600.sqlite3'


def _feedback_conn_v600():
    con=sqlite3.connect(str(_feedback_db_path_v600()),timeout=30)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute("""CREATE TABLE IF NOT EXISTS snapshots(
        id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT, ts_utc TEXT, ticker TEXT, market TEXT, price REAL,
        top_score REAL, opportunity REAL, trade_stage TEXT, movement_stage TEXT, prediction REAL, move_score REAL,
        explosive REAL, entry_score REAL, hourly REAL, exit_pressure REAL, global_rank INTEGER, market_rank INTEGER,
        session_status TEXT, entry_low REAL, entry_high REAL, trigger REAL, invalidation REAL, target1 REAL, target2 REAL,
        horizon_days INTEGER, UNIQUE(scan_id,ticker))""")
    con.execute("""CREATE TABLE IF NOT EXISTS outcomes(
        snapshot_id INTEGER, horizon INTEGER, evaluated_at TEXT, end_return REAL, max_favorable REAL, max_adverse REAL,
        target1_hit INTEGER, target2_hit INTEGER, invalidation_hit INTEGER, first_event TEXT,
        PRIMARY KEY(snapshot_id,horizon))""")
    return con


def _feedback_store_scan_v600(scan_id,df,config):
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:return
    try:
        con=_feedback_conn_v600(); ts=datetime.utcnow().replace(microsecond=0).isoformat()+'Z'
        cols=['Ticker','Market','Price','TopScore','OpportunityScore','TradeStage','MovementStage','Prediction','MoveScore','ExplosiveScore','EntryScore','HourlyConfirm','ExitPressure','GlobalRank','MarketRank','SessionStatus','EntryLow','EntryHigh','BreakoutTrigger','Invalidation','Target1','Target2']
        for _,r in df.iterrows():
            vals=[r.get(c,np.nan) for c in cols]
            def num(v):
                try:return float(v) if pd.notna(v) and np.isfinite(float(v)) else None
                except:return None
            con.execute("""INSERT OR REPLACE INTO snapshots(scan_id,ts_utc,ticker,market,price,top_score,opportunity,trade_stage,movement_stage,prediction,move_score,explosive,entry_score,hourly,exit_pressure,global_rank,market_rank,session_status,entry_low,entry_high,trigger,invalidation,target1,target2,horizon_days) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
                scan_id,ts,str(vals[0]),str(vals[1]),num(vals[2]),num(vals[3]),num(vals[4]),str(vals[5]),str(vals[6]),num(vals[7]),num(vals[8]),num(vals[9]),num(vals[10]),num(vals[11]),num(vals[12]),int(vals[13]) if pd.notna(vals[13]) else None,int(vals[14]) if pd.notna(vals[14]) else None,str(vals[15]),num(vals[16]),num(vals[17]),num(vals[18]),num(vals[19]),num(vals[20]),num(vals[21]),int(config.get('horizon',5))))
        con.commit(); con.close()
    except Exception:
        pass


def _feedback_evaluate_due_v600(max_snapshots=30):
    """Evaluate due 1D/3D/5D outcomes. Runs safely in the background after scans."""
    try:
        con=_feedback_conn_v600(); snap=pd.read_sql_query('SELECT * FROM snapshots ORDER BY id DESC LIMIT 600',con)
        done=pd.read_sql_query('SELECT snapshot_id,horizon FROM outcomes',con)
        done_set=set(zip(done.snapshot_id.astype(int),done.horizon.astype(int))) if not done.empty else set()
        evaluated=0
        for _,r in snap.iterrows():
            if evaluated>=max_snapshots:break
            scan_date=pd.Timestamp(str(r.ts_utc)).date()
            due=[h for h in (1,3,5) if (int(r.id),h) not in done_set and (datetime.utcnow().date()-scan_date).days>=h]
            if not due:continue
            d=fetch_ohlcv(str(r.ticker),'1mo','1d')
            if d is None or d.empty:continue
            z=d.copy(); dates=pd.to_datetime(z.index).date
            for h in due:
                future=z[np.array([x>scan_date for x in dates])].head(h)
                if len(future)<h:continue
                base=float(r.price) if pd.notna(r.price) else np.nan
                if not np.isfinite(base) or base<=0:continue
                endret=float(future.Close.iloc[-1]/base-1); mfe=float(future.High.max()/base-1); mae=float(future.Low.min()/base-1)
                t1=float(r.target1) if pd.notna(r.target1) else np.nan; t2=float(r.target2) if pd.notna(r.target2) else np.nan; inv=float(r.invalidation) if pd.notna(r.invalidation) else np.nan
                t1h=bool(np.isfinite(t1) and (future.High>=t1).any()); t2h=bool(np.isfinite(t2) and (future.High>=t2).any()); invh=bool(np.isfinite(inv) and (future.Low<=inv).any())
                first='NONE'
                for _,bar in future.iterrows():
                    hit_t=bool(np.isfinite(t1) and float(bar.High)>=t1); hit_i=bool(np.isfinite(inv) and float(bar.Low)<=inv)
                    if hit_t and hit_i:first='AMBIGUOUS SAME DAY'; break
                    if hit_i:first='INVALIDATION FIRST'; break
                    if hit_t:first='TARGET1 FIRST'; break
                con.execute('INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?,?,?,?,?,?,?)',(int(r.id),h,datetime.utcnow().replace(microsecond=0).isoformat()+'Z',endret,mfe,mae,int(t1h),int(t2h),int(invh),first))
                con.commit(); evaluated+=1; done_set.add((int(r.id),h))
                if evaluated>=max_snapshots:break
        con.close(); return evaluated
    except Exception:return 0


def _feedback_frames_v600():
    try:
        con=_feedback_conn_v600(); sn=pd.read_sql_query('SELECT * FROM snapshots ORDER BY id DESC',con); oc=pd.read_sql_query('SELECT * FROM outcomes ORDER BY evaluated_at DESC',con); con.close(); return sn,oc
    except Exception:return pd.DataFrame(),pd.DataFrame()


def workbook_bytes(sheets, meta=None):
    """Build a safe multi-sheet Excel workbook for any tab."""
    bio=BytesIO()
    with pd.ExcelWriter(bio,engine="openpyxl") as writer:
        used=set()
        for raw_name,obj in (sheets or {}).items():
            if obj is None:
                continue
            if isinstance(obj,dict):
                obj=pd.DataFrame([obj])
            elif isinstance(obj,list):
                obj=pd.DataFrame(obj)
            elif not isinstance(obj,pd.DataFrame):
                try: obj=pd.DataFrame(obj)
                except Exception: continue
            name=''.join(ch for ch in str(raw_name) if ch not in '[]:*?/\\')[:31] or 'Sheet'
            base=name; n=2
            while name in used:
                suffix=f'_{n}'; name=(base[:31-len(suffix)]+suffix); n+=1
            used.add(name)
            obj.to_excel(writer,index=False,sheet_name=name)
        about={"Version":APP_VERSION,"Generated":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        if meta: about.update(meta)
        pd.DataFrame({"Field":list(about.keys()),"Value":list(about.values())}).to_excel(writer,index=False,sheet_name="About")
    return bio.getvalue()

def tab_download(key,label,filename_prefix):
    if key in st.session_state:
        st.download_button(label,data=st.session_state[key],file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key=f"dl_{key}")

def _fmt_seconds(seconds):
    try:
        seconds=max(0,int(float(seconds)))
    except Exception:
        return "—"
    m,s=divmod(seconds,60); h,m=divmod(m,60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

class _ScannerCancelled(Exception):
    """Internal cooperative-cancel signal for the background scanner."""


@st.cache_resource(show_spinner=False)
def _scanner_runtime_v599():
    # No background thread is started at app startup. The executor is created lazily
    # only after the user presses Scan, which keeps deployment/startup behavior simple.
    return {
        'lock':threading.RLock(),
        'executor':None,
        'active':None,
        'last_completed':None,
    }

def _scanner_progress_percent(stage,i,total):
    if stage=='stage1':
        return int(np.clip(55*max(0,i-1)/max(1,total),0,55))
    return int(np.clip(55+45*max(0,i-1)/max(1,total),55,99))

def _scanner_worker_v599(runtime,job_id,config):
    started=time_module.time()
    skipped=[]
    def progress(stage,i,total,ticker_name):
        now=time_module.time()
        with runtime['lock']:
            job=runtime.get('active')
            if not job or job.get('id')!=job_id:
                raise _ScannerCancelled()
            if job.get('cancel_requested') or job.get('status') in ('stopping','stopped'):
                raise _ScannerCancelled()
            if job.get('stage')!=stage:
                job['stage_started_at']=now
                job['stage_samples']=[]
            else:
                prev=job.get('last_callback_at')
                if prev and job.get('last_stage')==stage:
                    dt=max(0.01,now-prev)
                    samples=list(job.get('stage_samples',[])); samples.append(dt); job['stage_samples']=samples[-8:]
            job['stage']=stage; job['last_stage']=stage; job['last_callback_at']=now
            job['index']=int(i); job['total']=int(total); job['ticker']=ticker_name
            job['market']=MARKET_MAP.get(str(ticker_name).upper(),'CUSTOM')
            job['progress']=_scanner_progress_percent(stage,i,total)
            job['elapsed']=now-started
            samples=job.get('stage_samples',[])
            avg=float(np.mean(samples)) if samples else (job['elapsed']/max(1,i))
            if stage=='stage1':
                rem=max(0,total-i+1)*avg
                # Deep analysis is heavier than daily prefilter. This is intentionally approximate.
                rem += min(int(config['prefilter_top']),len(config['tickers']))*max(avg*2.3,2.0)
            else:
                rem=max(0,total-i+1)*avg
            job['eta']=rem
    try:
        res=_v544_scan_universe_dynamic(
            config['tickers'],config['history'],True,'1mo',config['horizon'],config['target'],0,
            config['threshold'],config['prefilter_top'],progress_callback=progress)
        # A stop can be requested while the final network/data call is still in flight.
        # Re-check before publishing/storing a completed result.
        with runtime['lock']:
            job=runtime.get('active')
            if (not job or job.get('id')!=job_id or job.get('cancel_requested') or job.get('status') in ('stopping','stopped')):
                raise _ScannerCancelled()
        meta=dict(getattr(res,'attrs',{}).get('scan_meta',{})) if isinstance(res,pd.DataFrame) else {}
        if isinstance(res,pd.DataFrame) and not res.empty:
            res=add_market_and_opportunity(res)
            res=res.sort_values(['TopScore','OpportunityScore','ExplosiveScore','EntryScore'],ascending=False).reset_index(drop=True)
        finished=time_module.time()
        try:
            _feedback_store_scan_v600(job_id,res,config)
            threading.Thread(target=_feedback_evaluate_due_v600,kwargs={'max_snapshots':20},daemon=True).start()
        except Exception:
            pass
        snapshot={
            'id':job_id,'status':'completed','result':res,'meta':meta,'started_at':started,'finished_at':finished,
            'duration':finished-started,'completed_label':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'requested':len(config['tickers']),'config':config,
        }
        with runtime['lock']:
            runtime['last_completed']=snapshot
            if runtime.get('active') and runtime['active'].get('id')==job_id:
                runtime['active'].update({'status':'completed','progress':100,'elapsed':finished-started,'eta':0,'result':res,'meta':meta,'finished_at':finished,'cancel_requested':False})
    except _ScannerCancelled:
        finished=time_module.time()
        with runtime['lock']:
            if runtime.get('active') and runtime['active'].get('id')==job_id:
                runtime['active'].update({'status':'stopped','finished_at':finished,'elapsed':finished-started,'eta':0,'ticker':'—','market':'—','cancel_requested':True})
    except Exception as e:
        finished=time_module.time()
        with runtime['lock']:
            if runtime.get('active') and runtime['active'].get('id')==job_id:
                runtime['active'].update({'status':'failed','error':f'{type(e).__name__}: {e}','finished_at':finished,'elapsed':finished-started,'eta':0,'cancel_requested':False})

def _start_scanner_job_v599(config):
    runtime=_scanner_runtime_v599()
    with runtime['lock']:
        active=runtime.get('active')
        if active and active.get('status')=='running':
            return False,'A scan is already running.'
        if runtime.get('executor') is None:
            runtime['executor']=ThreadPoolExecutor(max_workers=1,thread_name_prefix='stock-hunter-scan')
        job_id=f"scan-{int(time_module.time()*1000)}"
        runtime['active']={
            'id':job_id,'status':'running','stage':'starting','index':0,'total':len(config['tickers']),
            'ticker':'—','market':'—','progress':0,'started_at':time_module.time(),'elapsed':0,'eta':None,
            'stage_started_at':time_module.time(),'stage_samples':[],'last_callback_at':None,'last_stage':None,
            'config':config,'cancel_requested':False,
        }
        runtime['executor'].submit(_scanner_worker_v599,runtime,job_id,config)
    return True,job_id

def _request_scanner_stop_v601():
    runtime=_scanner_runtime_v599()
    with runtime['lock']:
        active=runtime.get('active')
        if not active or active.get('status') not in ('running','stopping'):
            return False,'No scan is currently running.'
        if active.get('status')=='stopping':
            return True,'Stop already requested.'
        active['cancel_requested']=True
        active['status']='stopping'
        active['eta']=0
        return True,'Stop requested. Finishing the current data call safely…'

def _scanner_status_v601():
    runtime=_scanner_runtime_v599()
    with runtime['lock']:
        active=runtime.get('active')
        return str(active.get('status','idle')) if active else 'idle'

def _filter_scanner_results_v599(df,show_mode,market_filter="ALL 150"):
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:
        return pd.DataFrame()
    z=df.copy()
    market_name={'NASDAQ 50':'NASDAQ','HONG KONG 50':'HONG KONG','TEL AVIV 50':'TEL AVIV'}.get(market_filter)
    if market_name and 'Market' in z:z=z[z.Market.eq(market_name)]
    if show_mode=='TOP OPPORTUNITIES':
        z=z[(z.TopScore>=68) | (z.OpportunityScore>=72)]
    elif show_mode=='ACTIONABLE NOW':
        if 'ActionableNow' in z: z=z[z.ActionableNow.astype(bool)]
    elif show_mode=='WATCHLIST':
        z=z[z.OpportunityStage.isin(['WATCH','ARMED'])]
    if 'TradePriorityRank' in z.columns:z=z.sort_values(['TradePriorityRank','TopScore'],ascending=[True,False])
    z=z.reset_index(drop=True)
    if 'Rank' in z.columns: z=z.drop(columns=['Rank'])
    z.insert(0,'Rank',range(1,len(z)+1))
    return z

def _session_badges_html_v599(r):
    phase=str(r.get('MarketPhase','UNKNOWN')); stage=str(r.get('OpportunityStage','WAIT')); live=str(r.get('LiveStage',stage))
    if phase=='PRE-MARKET':
        conf=str(r.get('PMConfirmation','N/A')); ch=r.get('PMChangePct',np.nan)
        status='DATA UNAVAILABLE' if conf=='N/A' else conf
        c='good' if conf=='CONFIRMED' else ('bad' if 'WEAKENED' in conf else 'warn')
        mv=f" ({float(ch):+.2f}%)" if pd.notna(ch) else ''
        return f"<span class='{c}'>PRE-MARKET: {status}{mv}</span><br><span class='warn'>Previous session: {stage}</span>"
    if phase=='AFTER-MARKET':
        conf=str(r.get('AHConfirmation','N/A')); ch=r.get('AHChangePct',np.nan)
        status='DATA UNAVAILABLE' if conf=='N/A' else conf
        c='good' if conf=='CONFIRMED' else ('bad' if 'WEAKENED' in conf else 'warn')
        mv=f" ({float(ch):+.2f}%)" if pd.notna(ch) else ''
        return f"<span class='{c}'>AFTER-MARKET: {status}{mv}</span><br><span class='warn'>Regular session: {stage}</span>"
    if phase=='OPEN':
        c='good' if live=='LIVE TRIGGERED' else ('bad' if 'WEAKENED' in live else 'warn')
        return f"<span class='{c}'>OPEN: {live}</span>"
    if phase=='PRE-OPEN': return f"<span class='warn'>PRE-OPEN • Previous session: {stage}</span>"
    if phase=='CLOSED': return f"<span class='warn'>CLOSED • Previous session: {stage}</span>"
    return f"<span class='warn'>{phase}: {stage}</span>"

def _live_levels_html_v599(r):
    if str(r.get('MarketPhase',''))!='OPEN' or str(r.get('LiveStage',''))!='LIVE TRIGGERED':
        return ''
    vals={k:pd.to_numeric(pd.Series([r.get(k,np.nan)]),errors='coerce').iloc[0] for k in ['EntryLow','EntryHigh','Invalidation','Target1','Target2']}
    if not all(np.isfinite(vals[k]) for k in vals): return ''
    entry=(vals['EntryLow']+vals['EntryHigh'])/2.0; risk=entry-vals['Invalidation']
    if risk<=0:return ''
    rr1=max(0,(vals['Target1']-entry)/risk); rr2=max(0,(vals['Target2']-entry)/risk)
    return (f"<div style='margin-top:12px;padding:12px 14px;border:1px solid #284a3d;border-radius:14px;background:rgba(39,190,120,.06)'>"
            f"<b class='good'>🟢 LIVE TRADE LEVELS</b><br>"
            f"Entry Zone <b>{vals['EntryLow']:.3f}–{vals['EntryHigh']:.3f}</b> • "
            f"<span class='bad'>Stop / Invalidation <b>{vals['Invalidation']:.3f}</b></span><br>"
            f"Target 1 <b>{vals['Target1']:.3f}</b> • Target 2 <b>{vals['Target2']:.3f}</b> • "
            f"R/R <b>1:{rr1:.1f} / 1:{rr2:.1f}</b> (T1/T2)"
            f"</div>")

def _scanner_stage_guide_v599():
    with st.expander("ℹ️ Setup progression — stage guide", expanded=False):
        st.markdown(
            "**WAIT / COLD** → **WATCH / BUILDING** → **ARMED** → **MOVEMENT TRIGGER** → **TRADE TRIGGER** → **LIVE TRIGGERED**"
        )
        st.caption(
            "WAIT/COLD = not ready • WATCH/BUILDING = early setup • ARMED = most conditions aligned • "
            "MOVEMENT TRIGGER = momentum/price behavior triggered • TRADE TRIGGER = full Opportunity + Entry + Hourly + risk filters aligned • LIVE TRIGGERED = Trade Trigger confirmed while the regular market is open."
        )
        st.caption(
            "WEAKENED = current pre/after-market behavior is weakening the previous-session setup. "
            "A previous-session Trade Trigger is not treated as live until the current session confirms it."
        )

def _render_scanner_results_v599(show_mode,market_filter="ALL 150"):
    runtime=_scanner_runtime_v599()
    with runtime['lock']:
        active=dict(runtime['active']) if runtime.get('active') else None
        last=runtime.get('last_completed')
    if active and active.get('status') in ('running','stopping'):
        pct=int(active.get('progress',0))
        elapsed=active.get('elapsed',time_module.time()-active.get('started_at',time_module.time()))
        eta=active.get('eta')
        if active.get('status')=='stopping':
            st.progress(max(0,min(100,pct)),text=f"Stopping safely… • {pct}% • waiting for current data call to finish")
        else:
            st.progress(max(0,min(100,pct)),text=f"Scanning • {pct}% • {active.get('stage','').upper()} • {active.get('market','—')} • {active.get('ticker','—')}")
        c1,c2,c3=st.columns(3)
        c1.metric("Current",f"{active.get('index',0)}/{active.get('total',0)}")
        c2.metric("Elapsed",_fmt_seconds(elapsed))
        c3.metric("Estimated remaining","Stopping…" if active.get('status')=='stopping' else (f"~{_fmt_seconds(eta)}" if eta is not None else "Calculating…"))
        st.caption("The scan runs on the Streamlit server. Stop is cooperative: it cancels before the next ticker after the current provider/data call returns.")
        return
    if active and active.get('status')=='stopped':
        st.info(f"Scan stopped by user after {_fmt_seconds(active.get('elapsed',0))}.")
    if active and active.get('status')=='failed':
        st.error("Scan failed: "+str(active.get('error','Unknown error')))
    if not last:
        st.info("No completed scan yet on this server session.")
        return
    full=last.get('result')
    res=_filter_scanner_results_v599(full,show_mode,market_filter)
    meta=last.get('meta') or {}
    skipped=meta.get('skipped') or []
    requested=int(last.get('requested',meta.get('requested',0)) or 0)
    daily_ok=int(meta.get('daily_success',0) or 0)
    deep_ok=int(meta.get('deep_success',len(full) if isinstance(full,pd.DataFrame) else 0) or 0)
    st.caption(f"Last Completed Scan: {last.get('completed_label','—')} • Duration {_fmt_seconds(last.get('duration',0))} • Requested {requested} • Daily OK {daily_ok} • Deep analyzed {deep_ok} • Skipped/errors {len(skipped)}")
    if res is None or res.empty:
        st.warning("The selected Show filter has no matching stocks in the last completed scan.")
    else:
        topcards=res.sort_values(['TradePriorityRank','TopScore'],ascending=[True,False]).head(5) if 'TradePriorityRank' in res else res.head(5)
        for _,r in topcards.iterrows():
            status_html=_session_badges_html_v599(r)
            with st.container(border=True):
                h1,h2,h3=st.columns([1.45,1,1])
                with h1:
                    st.markdown(f"### #{int(r.get('TradePriorityRank',r.Rank))} {r.Ticker}")
                    st.markdown(status_html,unsafe_allow_html=True)
                with h2: st.metric("TOP SCORE",f"{float(r.get('TopScore',0)):.1f}")
                with h3: st.metric("Opportunity",f"{float(r.get('OpportunityScore',0)):.1f}")
                st.markdown(f"**Trade:** :{'green' if str(r.get('TradeStage'))=='TRADE TRIGGER' else 'orange'}[**{r.get('TradeStage','—')}**]  •  **Movement:** {r.get('MovementStage','—')}  •  **Exit:** :{'red' if float(r.get('ExitPressure',0) or 0)>=55 else 'orange' if float(r.get('ExitPressure',0) or 0)>=35 else 'green'}[**{r.get('ExitStage','CLEAR')} {safe(r.get('ExitPressure'),0)}**]")
                st.caption("Why not Trade Trigger? "+str(r.get('WhyNotTradeTrigger','—')))
                m1,m2,m3,m4=st.columns(4)
                m1.metric("Prediction Score",safe(r.get('Prediction'),1)); m2.metric("Evidence",str(r.get('EvidenceQuality','LOW'))); m3.metric("Entry timing",safe(r.get('EntryScore'),1)); m4.metric("Hourly",safe(r.get('HourlyConfirm'),1))
                st.caption(f"Move {safe(r.get('MoveScore'),1)} • Explosive {safe(r.get('ExplosiveScore'),1)} • Volume {r.get('VolumeContext','N/A')} • Live RVOL {safe(r.get('LiveIntradayRVOL',r.get('TimeAdjustedRVOL')))}x • Daily RVOL {safe(r.get('DailyRobustRVOL'))}x • Global #{int(r.get('GlobalRank',0) or 0)} • {r.get('Market','—')} #{int(r.get('MarketRank',0) or 0)} • Sector #{int(r.get('SectorRank',0) or 0)}")
                n=int(r.get('BacktestN',0) or 0)
                bt_txt=f"{safe(r.get('EmpiricalHitRate'),1)}% ({n} signals)" if n>=12 else f"LOW SAMPLE — {n} signals"
                st.caption(f"Evidence {r.get('EvidenceQuality','LOW')} • Reliability {safe(r.get('Reliability'),1)} • Backtest {bt_txt} • Lift {safe(r.get('SignalLift'))}x • RSI {safe(r.get('RSI14'),1)} • Data quality {r.get('DataQuality','OK')}{' • Split adjusted' if bool(r.get('SplitAdjusted',False)) else ''}")
                if bool(r.get('PlanValid',False)) and str(r.get('MarketPhase',''))=='OPEN' and str(r.get('LiveStage',''))=='LIVE TRIGGERED':
                    vals={k:pd.to_numeric(pd.Series([r.get(k,np.nan)]),errors='coerce').iloc[0] for k in ['EntryLow','EntryHigh','Invalidation','Target1','Target2']}
                    if all(np.isfinite(vals[k]) for k in vals):
                        e1,e2,e3,e4=st.columns(4); e1.metric("Entry zone",f"{vals['EntryLow']:.3f}–{vals['EntryHigh']:.3f}"); e2.metric("Invalidation",f"{vals['Invalidation']:.3f}"); e3.metric("Target 1",f"{vals['Target1']:.3f}"); e4.metric("Target 2",f"{vals['Target2']:.3f}")
        _scanner_stage_guide_v599()
        # Clear ranking table:
        # Rank = position inside the CURRENT selected view/filter.
        # GlobalRank = position among the full scan result set.
        # MarketRank = position only inside the stock's exchange (NASDAQ / Hong Kong / Tel Aviv).
        cols=['Ticker','Rank','TradePriorityRank','GlobalRank','MarketRank','SectorRank','Market','Sector','MarketPhase','SessionStatus','LiveStage','ActionableNow','TradeStage','MovementStage','WhyNotTradeTrigger','TopScore','OpportunityScore','Reliability','EvidenceQuality','ExitPressure','ExitStage','VolumeContext','BullishVolumeEvidence','BearishVolumeEvidence','LiveIntradayRVOL','DailyRobustRVOL','TimeAdjustedRVOL','MoveScore','ExplosiveScore','EntryScore','PlanValid','PlanReason','EntryLow','EntryHigh','BreakoutTrigger','Invalidation','Target1','Target2','Accel1D','Accel2D','Accel3D','HourlyConfirm','Signal','Prediction','DynamicQuant','DynamicEarly','EntryStatus','ExplosiveStage','P5_5D','P10_5D','P15_5D','P15_5D_N','SignalLift','CalibrationConfidence','Price','RSI14','EmpiricalHitRate','BacktestN','SplitAdjusted','DataQuality','PMConfirmation','PMChangePct','PMVolumeStrength','AHConfirmation','AHChangePct','AHVolumeStrength']
        table=res[[c for c in cols if c in res]].copy()
        table=table.rename(columns={
            'Rank':'View Rank',
            'GlobalRank':'Global Rank',
            'MarketRank':'Market Rank','SectorRank':'Sector Rank','TradePriorityRank':'Trade Priority',
        })
        if 'BacktestN' in table:
            table['Backtest Quality']=np.where(pd.to_numeric(table['BacktestN'],errors='coerce').fillna(0)>=12,'EVIDENCE OK',np.where(pd.to_numeric(table['BacktestN'],errors='coerce').fillna(0)>0,'LOW SAMPLE','NO SAMPLE'))
            if 'EmpiricalHitRate' in table:table.loc[pd.to_numeric(table['BacktestN'],errors='coerce').fillna(0)<12,'EmpiricalHitRate']=np.nan
        if set(res.get('Market',pd.Series(dtype=str)).astype(str).unique()).isdisjoint({'NASDAQ'}):
            table=table.drop(columns=[c for c in table.columns if c.startswith('PM') or c.startswith('AH')],errors='ignore')
        st.caption("Ranking: Trade Priority = stage first, then TOP Score • Global Rank = quality rank across all successfully analyzed stocks from the 150 requested • Market Rank = exchange rank • Sector Rank = sector rank inside that market.")
        st.dataframe(table,use_container_width=True,hide_index=True)
        st.download_button("⬇️ Download Scanner to Excel",data=scanner_excel_bytes(res,meta),file_name=f"AI_Stock_Hunter_V{APP_VERSION}_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="scanner_excel_v600")
    if skipped:
        with st.expander(f"Skipped / error details ({len(skipped)})"):
            st.dataframe(pd.DataFrame(skipped),use_container_width=True,hide_index=True)

if hasattr(st,'fragment'):
    @st.fragment(run_every="1s")
    def _scanner_live_fragment_v599(show_mode,market_filter="ALL 150"):
        _render_scanner_results_v599(show_mode,market_filter)
        # V6.0.1: the 1-second fragment exists ONLY while a scan is active.
        # Once a terminal state is reached, force one full rerun so the fragment
        # is removed from the page. This stops Streamlit's stop/rerun icon from
        # blinking forever after the scan has finished.
        if _scanner_status_v601() not in ('running','stopping'):
            try:
                st.rerun(scope='app')
            except TypeError:
                st.rerun()
else:
    def _scanner_live_fragment_v599(show_mode,market_filter="ALL 150"):
        _render_scanner_results_v599(show_mode,market_filter)



# -----------------------------------------------------------------------------
# V6.0.2 server-side Research job runtime
# Research now follows the Scanner control model: it runs in a cached server-side
# worker, can be cooperatively stopped, and keeps running if the browser/app is
# backgrounded as long as the Streamlit server process itself remains alive.
# -----------------------------------------------------------------------------
class _ResearchCancelled(Exception):
    """Internal cooperative-cancel signal for the background Research worker."""


@st.cache_resource(show_spinner=False)
def _research_runtime_v602():
    return {
        'lock': threading.RLock(),
        'executor': None,
        'active': None,
        'last_completed': None,
    }


def _research_check_cancel_v602(runtime, job_id):
    with runtime['lock']:
        job = runtime.get('active')
        if not job or job.get('id') != job_id:
            raise _ResearchCancelled()
        if job.get('cancel_requested') or job.get('status') in ('stopping', 'stopped'):
            raise _ResearchCancelled()


def _research_update_v602(runtime, job_id, completed, total, ticker='—', phase='Researching'):
    now = time_module.time()
    with runtime['lock']:
        job = runtime.get('active')
        if not job or job.get('id') != job_id:
            raise _ResearchCancelled()
        job['completed'] = int(completed)
        job['total'] = int(total)
        job['ticker'] = str(ticker)
        job['market'] = MARKET_MAP.get(str(ticker).upper(), 'CUSTOM') if ticker not in (None, '—') else '—'
        job['phase'] = str(phase)
        job['progress'] = int(np.clip(100 * completed / max(1, total), 0, 99 if completed < total else 100))
        elapsed = now - float(job.get('started_at', now))
        job['elapsed'] = elapsed
        if completed > 0:
            avg = elapsed / completed
            job['eta'] = max(0.0, (total - completed) * avg)
        else:
            job['eta'] = None


def _research_payload_v602(research_rows, opt_all, atr_all, timeline_samples, premove_all, accel_all, skipped, config, partial=False):
    summary = pd.DataFrame(research_rows)
    if not summary.empty:
        summary = summary.sort_values(['Median Lift', 'Signals'], ascending=[False, False]).reset_index(drop=True)
    timeline_df = pd.concat(timeline_samples, ignore_index=True) if timeline_samples else pd.DataFrame()
    if not timeline_df.empty:
        topk_parts = [
            topk_daily_validation(timeline_df, score_col='Move Score'),
            topk_daily_validation(timeline_df, score_col='Explosive Score'),
        ]
        topk = pd.concat(topk_parts, ignore_index=True)
    else:
        topk = pd.DataFrame()
    premove_df = pd.concat(premove_all, ignore_index=True) if premove_all else pd.DataFrame()
    sheets = {
        'Adaptive Summary': summary,
        'Threshold Grid': pd.concat(opt_all, ignore_index=True) if opt_all else pd.DataFrame(),
        'ATR Validation': pd.concat(atr_all, ignore_index=True) if atr_all else pd.DataFrame(),
        'Pre-Move Study': premove_df,
        'Acceleration Validation': pd.concat(accel_all, ignore_index=True) if accel_all else pd.DataFrame(),
        'Top-K Validation': topk,
        'Historical Timeline': timeline_df,
        'Skipped': pd.DataFrame(skipped),
    }
    excel = workbook_bytes(sheets, {
        'Tab': 'Research 150',
        'Version': APP_VERSION,
        'History': config['history'],
        'Universe': len(config['tickers']),
        'MinimumSignals': config['minimum_signals'],
        'Method': 'Causal scores; future data labels only',
        'Status': 'PARTIAL / STOPPED' if partial else 'COMPLETED',
    })
    return {
        'summary': summary,
        'premove': premove_df,
        'topk': topk,
        'skipped': pd.DataFrame(skipped),
        'excel': excel,
        'partial': bool(partial),
    }


def _research_worker_v602(runtime, job_id, config):
    started = time_module.time()
    research_rows, opt_all, atr_all = [], [], []
    timeline_samples, premove_all, accel_all, skipped = [], [], [], []
    completed = 0
    current_ticker = '—'
    try:
        total = len(config['tickers'])
        for idx, tkr in enumerate(config['tickers'], start=1):
            current_ticker = tkr
            _research_check_cancel_v602(runtime, job_id)
            _research_update_v602(runtime, job_id, completed, total, tkr, 'Downloading daily history')
            try:
                dd = fetch_ohlcv(tkr, config['history'], '1d')
                _research_check_cancel_v602(runtime, job_id)
                if dd is None or len(dd) < 120:
                    skipped.append({'Ticker': tkr, 'Reason': '<120 daily rows'})
                else:
                    _research_update_v602(runtime, job_id, completed, total, tkr, 'Computing causal features')
                    ff = compute_features(dd)
                    _research_check_cancel_v602(runtime, job_id)

                    _research_update_v602(runtime, job_id, completed, total, tkr, 'Optimizing historical thresholds')
                    exo = threshold_optimization(ff, score_kind='explosive')
                    mvo = threshold_optimization(ff, score_kind='move')
                    both = pd.concat([exo, mvo], ignore_index=True)
                    both.insert(0, 'Ticker', tkr)
                    opt_all.append(both)
                    best = adaptive_target_horizon_v2(both, int(config['minimum_signals']))
                    if best:
                        research_rows.append({
                            'Ticker': tkr,
                            'Market': MARKET_MAP.get(tkr, 'CUSTOM'),
                            'Sector': SECTOR_MAP.get(tkr, 'Other'),
                            **best,
                        })
                    _research_check_cancel_v602(runtime, job_id)

                    _research_update_v602(runtime, job_id, completed, total, tkr, 'Validating ATR / pre-move / acceleration')
                    av = atr_target_validation(ff, threshold=int(best.get('Threshold', 60)) if best else 60)
                    av.insert(0, 'Ticker', tkr)
                    atr_all.append(av)
                    tl_full = historical_signal_timeline(ff)
                    pm = pre_move_study(tl_full)
                    pm.insert(0, 'Ticker', tkr)
                    premove_all.append(pm)
                    avl = acceleration_validation(tl_full) if callable(acceleration_validation) else pd.DataFrame()
                    if not avl.empty:
                        avl.insert(0, 'Ticker', tkr)
                        accel_all.append(avl)
                    tl = tl_full.tail(260)
                    tl.insert(0, 'Ticker', tkr)
                    timeline_samples.append(tl)
                    _research_check_cancel_v602(runtime, job_id)
            except _ResearchCancelled:
                raise
            except Exception as e:
                skipped.append({'Ticker': tkr, 'Reason': str(e)[:180]})
            completed = idx
            _research_update_v602(runtime, job_id, completed, total, tkr, 'Ticker complete')

        _research_update_v602(runtime, job_id, completed, total, '—', 'Building Research workbook')
        _research_check_cancel_v602(runtime, job_id)
        payload = _research_payload_v602(
            research_rows, opt_all, atr_all, timeline_samples, premove_all, accel_all, skipped, config, partial=False
        )
        # If Stop was pressed while the workbook was being assembled, honor it
        # before publishing a completed result.
        _research_check_cancel_v602(runtime, job_id)
        finished = time_module.time()
        snapshot = {
            'id': job_id,
            'status': 'completed',
            'payload': payload,
            'started_at': started,
            'finished_at': finished,
            'duration': finished - started,
            'completed_label': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'config': config,
            'completed': completed,
            'total': len(config['tickers']),
        }
        with runtime['lock']:
            runtime['last_completed'] = snapshot
            if runtime.get('active') and runtime['active'].get('id') == job_id:
                runtime['active'].update({
                    'status': 'completed', 'progress': 100, 'elapsed': finished - started, 'eta': 0,
                    'ticker': '—', 'market': '—', 'phase': 'Completed', 'payload': payload,
                    'finished_at': finished, 'cancel_requested': False, 'completed': completed,
                })
    except _ResearchCancelled:
        finished = time_module.time()
        # Keep the already-finished tickers available as a clearly marked partial result.
        try:
            payload = _research_payload_v602(
                research_rows, opt_all, atr_all, timeline_samples, premove_all, accel_all, skipped, config, partial=True
            )
        except Exception:
            payload = None
        with runtime['lock']:
            if runtime.get('active') and runtime['active'].get('id') == job_id:
                runtime['active'].update({
                    'status': 'stopped', 'finished_at': finished, 'elapsed': finished - started, 'eta': 0,
                    'ticker': current_ticker, 'phase': 'Stopped safely', 'cancel_requested': True,
                    'payload': payload, 'completed': completed,
                })
    except Exception as e:
        finished = time_module.time()
        with runtime['lock']:
            if runtime.get('active') and runtime['active'].get('id') == job_id:
                runtime['active'].update({
                    'status': 'failed', 'error': f'{type(e).__name__}: {e}', 'finished_at': finished,
                    'elapsed': finished - started, 'eta': 0, 'cancel_requested': False,
                    'phase': 'Failed', 'completed': completed,
                })


def _start_research_job_v602(config):
    runtime = _research_runtime_v602()
    with runtime['lock']:
        active = runtime.get('active')
        if active and active.get('status') in ('running', 'stopping'):
            return False, 'Research is already running.'
        if runtime.get('executor') is None:
            runtime['executor'] = ThreadPoolExecutor(max_workers=1, thread_name_prefix='stock-hunter-research')
        job_id = f"research-{int(time_module.time()*1000)}"
        runtime['active'] = {
            'id': job_id, 'status': 'running', 'progress': 0, 'completed': 0,
            'total': len(config['tickers']), 'ticker': '—', 'market': '—', 'phase': 'Starting',
            'started_at': time_module.time(), 'elapsed': 0, 'eta': None, 'config': config,
            'cancel_requested': False,
        }
        runtime['executor'].submit(_research_worker_v602, runtime, job_id, config)
    return True, job_id


def _request_research_stop_v602():
    runtime = _research_runtime_v602()
    with runtime['lock']:
        active = runtime.get('active')
        if not active or active.get('status') not in ('running', 'stopping'):
            return False, 'No Research job is currently running.'
        if active.get('status') == 'stopping':
            return True, 'Stop already requested.'
        active['cancel_requested'] = True
        active['status'] = 'stopping'
        active['eta'] = 0
        active['phase'] = 'Stop requested — finishing the current safe step'
        return True, 'Stop requested. Research will stop safely after the current data/calculation step.'


def _research_status_v602():
    runtime = _research_runtime_v602()
    with runtime['lock']:
        active = runtime.get('active')
        return str(active.get('status', 'idle')) if active else 'idle'


def _render_research_payload_v602(snapshot, label='Research results', download_key='research_download_v602'):
    if not snapshot or not snapshot.get('payload'):
        return
    payload = snapshot['payload']
    partial = bool(payload.get('partial'))
    cfg = snapshot.get('config', {})
    status_text = 'PARTIAL — stopped' if partial else 'COMPLETED'
    st.caption(
        f"{label} • {status_text} • {snapshot.get('completed', 0)}/{snapshot.get('total', len(cfg.get('tickers', [])))} tickers"
        + (f" • {snapshot.get('completed_label')}" if snapshot.get('completed_label') else '')
    )
    if payload.get('excel'):
        suffix = 'PARTIAL' if partial else 'Research150'
        st.download_button(
            '⬇️ Download Research to Excel' + (' (partial)' if partial else ''),
            data=payload['excel'],
            file_name=f"AI_Stock_Hunter_V{APP_VERSION}_{suffix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            use_container_width=True,
            key=download_key,
        )
    summary = payload.get('summary', pd.DataFrame())
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.metric('Stocks with qualified adaptive setup', f"{len(summary)}/{snapshot.get('total', len(cfg.get('tickers', [])))}")
    else:
        st.warning('No setup passed the minimum-sample/fold filters in the completed portion of this run.')
    premove = payload.get('premove', pd.DataFrame())
    topk = payload.get('topk', pd.DataFrame())
    if isinstance(premove, pd.DataFrame) and not premove.empty:
        st.markdown('#### Pre-Move Study')
        st.dataframe(premove.head(200), use_container_width=True, hide_index=True)
    if isinstance(topk, pd.DataFrame) and not topk.empty:
        st.markdown('#### Top-K Validation')
        st.dataframe(topk, use_container_width=True, hide_index=True)
    skipped = payload.get('skipped', pd.DataFrame())
    if isinstance(skipped, pd.DataFrame) and not skipped.empty:
        with st.expander(f"Skipped / error details ({len(skipped)})"):
            st.dataframe(skipped, use_container_width=True, hide_index=True)


def _render_research_status_v602():
    runtime = _research_runtime_v602()
    with runtime['lock']:
        active = dict(runtime.get('active') or {})
        last_completed = runtime.get('last_completed')
    status = active.get('status', 'idle')
    if status in ('running', 'stopping'):
        pct = int(active.get('progress', 0))
        completed = int(active.get('completed', 0)); total = int(active.get('total', 0))
        phase = active.get('phase', 'Researching')
        ticker = active.get('ticker', '—'); market = active.get('market', '—')
        st.progress(pct / 100.0, text=f"{phase} • {ticker} • {completed}/{total} ({pct}%)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Status', 'STOPPING' if status == 'stopping' else 'RUNNING')
        c2.metric('Current', f"{ticker} · {market}")
        c3.metric('Elapsed', _fmt_seconds(active.get('elapsed', 0)))
        c4.metric('ETA', '—' if status == 'stopping' or active.get('eta') is None else _fmt_seconds(active.get('eta')))
        st.info('Research is running server-side. You can switch to another app or tab and return later; the job continues while the Streamlit server process remains alive.')
        if last_completed:
            with st.expander('Last completed Research', expanded=False):
                _render_research_payload_v602(last_completed, 'Last completed Research', 'research_download_last_v602')
    elif status == 'completed':
        st.success(f"Research complete • {active.get('completed', 0)}/{active.get('total', 0)} tickers • {_fmt_seconds(active.get('elapsed', 0))}")
        _render_research_payload_v602(active, 'Current Research', 'research_download_current_v602')
    elif status == 'stopped':
        st.warning(f"Research stopped safely after {active.get('completed', 0)}/{active.get('total', 0)} tickers. Completed work is kept as a partial result.")
        if active.get('payload'):
            _render_research_payload_v602(active, 'Partial Research', 'research_download_partial_v602')
    elif status == 'failed':
        st.error('Research failed: ' + str(active.get('error', 'Unknown error')))
        if last_completed:
            with st.expander('Last completed Research', expanded=True):
                _render_research_payload_v602(last_completed, 'Last completed Research', 'research_download_failed_last_v602')
    elif last_completed:
        _render_research_payload_v602(last_completed, 'Last completed Research', 'research_download_idle_last_v602')


if hasattr(st, 'fragment'):
    @st.fragment(run_every='1s')
    def _research_live_fragment_v602():
        _render_research_status_v602()
        if _research_status_v602() not in ('running', 'stopping'):
            try:
                st.rerun(scope='app')
            except TypeError:
                st.rerun()
else:
    def _research_live_fragment_v602():
        _render_research_status_v602()




# -----------------------------------------------------------------------------
# V6.0.3 unified server-side Lab jobs
# Backtest / Validate / Entry / Explosive / Feedback use the same cooperative
# background model as Scanner + Research. Jobs continue if the phone/browser is
# backgrounded while the Streamlit server stays alive. Stop is cooperative.
# -----------------------------------------------------------------------------
class _LabCancelled(Exception):
    pass


@st.cache_resource(show_spinner=False)
def _lab_runtimes_v603():
    names=('analyze','backtest','validate','entry','explosive','feedback')
    return {name:{'lock':threading.RLock(),'executor':None,'active':None,'last_completed':None} for name in names}


def _lab_runtime_v603(name):
    return _lab_runtimes_v603()[name]


def _lab_check_v603(runtime,job_id):
    with runtime['lock']:
        j=runtime.get('active')
        if not j or j.get('id')!=job_id or j.get('cancel_requested') or j.get('status') in ('stopping','stopped'):
            raise _LabCancelled()


def _lab_update_v603(runtime,job_id,completed,total,item='—',phase='Running'):
    now=time_module.time()
    with runtime['lock']:
        j=runtime.get('active')
        if not j or j.get('id')!=job_id: raise _LabCancelled()
        j.update({'completed':int(completed),'total':int(total),'item':str(item),'phase':str(phase)})
        j['progress']=int(np.clip(100*completed/max(1,total),0,99 if completed<total else 100))
        elapsed=now-float(j.get('started_at',now)); j['elapsed']=elapsed
        j['eta']=max(0,(total-completed)*(elapsed/max(1,completed))) if completed else None


def _lab_publish_v603(runtime,job_id,payload,status='completed'):
    finished=time_module.time()
    with runtime['lock']:
        j=runtime.get('active')
        if not j or j.get('id')!=job_id:return
        snap={**j,'status':status,'payload':payload,'finished_at':finished,'duration':finished-float(j.get('started_at',finished)),'completed_label':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        if status=='completed':runtime['last_completed']=snap
        j.update(snap)
        j['progress']=100 if status=='completed' else j.get('progress',0)
        j['eta']=0


def _lab_fail_v603(runtime,job_id,e):
    finished=time_module.time()
    with runtime['lock']:
        j=runtime.get('active')
        if j and j.get('id')==job_id:
            j.update({'status':'failed','error':f'{type(e).__name__}: {e}','finished_at':finished,'elapsed':finished-float(j.get('started_at',finished)),'eta':0,'phase':'Failed'})


def _start_lab_v603(name,worker,config,total=1):
    runtime=_lab_runtime_v603(name)
    with runtime['lock']:
        a=runtime.get('active')
        if a and a.get('status') in ('running','stopping'):return False,f'{name.title()} is already running.'
        if runtime.get('executor') is None:
            runtime['executor']=ThreadPoolExecutor(max_workers=1,thread_name_prefix=f'stock-hunter-{name}')
        jid=f'{name}-{int(time_module.time()*1000)}'
        runtime['active']={'id':jid,'status':'running','progress':0,'completed':0,'total':int(total),'item':'—','phase':'Starting','started_at':time_module.time(),'elapsed':0,'eta':None,'config':config,'cancel_requested':False}
        runtime['executor'].submit(worker,runtime,jid,config)
    return True,jid


def _stop_lab_v603(name):
    runtime=_lab_runtime_v603(name)
    with runtime['lock']:
        a=runtime.get('active')
        if not a or a.get('status') not in ('running','stopping'):return False,f'No {name} job is running.'
        if a.get('status')=='stopping':return True,'Stop already requested.'
        a['cancel_requested']=True;a['status']='stopping';a['phase']='Stop requested — finishing current safe step';a['eta']=0
        return True,'Stop requested. The current safe calculation/data step will finish first.'


def _lab_snapshot_v603(name):
    runtime=_lab_runtime_v603(name)
    with runtime['lock']:
        a=dict(runtime['active']) if runtime.get('active') else None
        last=dict(runtime['last_completed']) if runtime.get('last_completed') else None
    return a,last


def _render_lab_status_v603(name):
    a,last=_lab_snapshot_v603(name)
    if a and a.get('status') in ('running','stopping'):
        status='STOPPING' if a.get('status')=='stopping' else 'RUNNING'
        st.progress(int(a.get('progress',0)),text=f"{status} • {a.get('phase','')} • {a.get('item','—')} • {a.get('completed',0)}/{a.get('total',0)}")
        c1,c2,c3=st.columns(3);c1.metric('Elapsed',_fmt_seconds(a.get('elapsed',0)));c2.metric('ETA',_fmt_seconds(a.get('eta')) if a.get('eta') is not None else '—');c3.metric('Progress',f"{a.get('progress',0)}%")
        st.caption('Server-side background run: you can switch apps/tabs and return later. A Streamlit host restart/sleep can still end an in-memory job.')
    elif a and a.get('status')=='failed':
        st.error('Run failed: '+str(a.get('error','Unknown error')))
    elif a and a.get('status')=='stopped':
        st.warning(f"Run stopped safely • {a.get('completed',0)}/{a.get('total',0)} steps completed")
    elif a and a.get('status')=='completed':
        st.success(f"Run completed • {_fmt_seconds(a.get('duration',a.get('elapsed',0)))}")
    elif last:
        st.caption(f"Last completed run • {last.get('completed_label','—')} • {_fmt_seconds(last.get('duration',0))}")


if hasattr(st,'fragment'):
    @st.fragment(run_every=1.0)
    def _lab_live_fragment_v603(name):
        _render_lab_status_v603(name)
        a,_=_lab_snapshot_v603(name)
        if not a or a.get('status') not in ('running','stopping'):
            try:st.rerun(scope='app')
            except TypeError:st.rerun()
else:
    def _lab_live_fragment_v603(name):
        _render_lab_status_v603(name)


def _analyze_worker_v603(runtime,jid,cfg):
    try:
        t=cfg['ticker'];hist=cfg['history'];horizon=int(cfg['horizon']);target=float(cfg['target'])
        _lab_update_v603(runtime,jid,0,8,t,'Downloading daily history')
        d=fetch_ohlcv(t,hist,'1d');_lab_check_v603(runtime,jid)
        if d is None or len(d)<35:raise ValueError('Not enough market data.')
        _lab_update_v603(runtime,jid,1,8,t,'Quant + Early features')
        f=compute_features(d);latest=score_latest(f,0);dyn=dynamic_scores(f,target/100,0);_lab_check_v603(runtime,jid)
        _lab_update_v603(runtime,jid,2,8,t,'Confirmed 1H / 15m data')
        h=confirmed_intraday_bars(fetch_ohlcv(t,'1mo','1h'));m15=confirmed_intraday_bars(fetch_ohlcv(t,'1mo','15m'));_,h,m15,ca_report=normalize_cross_timeframes(d,h,m15);_lab_check_v603(runtime,jid)
        hfeat=compute_features(h,True) if h is not None and len(h)>=30 else None;m15feat=compute_features(m15,True) if m15 is not None and len(m15)>=30 else None
        hs=he=np.nan
        if hfeat is not None:
            hl=score_latest(hfeat,0);hs=hl['score'];he=hl['early_score']
        qscore=latest['score'] if not np.isfinite(hs) else .78*latest['score']+.22*hs;escore=latest['early_score'] if not np.isfinite(he) else .70*latest['early_score']+.30*he
        _lab_update_v603(runtime,jid,3,8,t,'Historical evidence')
        auto_threshold,auto_table=_auto_backtest_threshold(f,horizon,target/100);buy_threshold=int(auto_threshold);bt=normalize_backtest_confidence(backtest_signal(f,horizon,target/100,buy_threshold,0));_lab_check_v603(runtime,jid)
        _lab_update_v603(runtime,jid,4,8,t,'Entry + live timing')
        precision=m15feat if m15feat is not None else (hfeat if hfeat is not None else f);ent=entry_timing(precision,qscore,escore)
        if str(ca_report.get('data_quality','OK'))!='OK':
            ent=dict(ent);ent.update({'plan_valid':False,'plan_reason':'Blocked by cross-timeframe data-quality gate','zone_low':np.nan,'zone_high':np.nan,'trigger':np.nan,'invalidation':np.nan,'target1':np.nan,'target2':np.nan})
        daily_lr=f.dropna(subset=['Close']).iloc[-1];live_f=f.copy()
        if hfeat is not None and len(hfeat):
            try:
                rv=float(hfeat.iloc[-1].get('time_adjusted_rvol',np.nan))
                if np.isfinite(rv):live_f.loc[live_f.index[-1],'robust_volume_ratio']=rv;live_f.loc[live_f.index[-1],'volume_ratio']=rv
            except Exception:pass
        latest_live=score_latest(live_f,0);ex=explosive_latest(live_f,hfeat) if callable(explosive_latest) else {};timing=signal_timing_latest(live_f,hfeat) if callable(signal_timing_latest) else {}
        row=pd.DataFrame([{'Ticker':t,'Prediction':dyn.get('final_prediction',0),'EntryScore':ent.get('entry_score',0),'MoveScore':timing.get('move_score',0),'ExplosiveScore':ex.get('score',0),'Accel1D':timing.get('accel_1d',0),'Accel2D':timing.get('accel_2d',0),'Accel3D':timing.get('accel_3d',0),'HourlyConfirm':timing.get('hourly_confirmation',ex.get('hourly_confirmation',0)),'CalibrationConfidence':bt.get('confidence',0),'BacktestN':bt.get('n',0),'SignalLift':1.0,'ExitPressure':timing.get('exit_pressure',latest_live.get('exit_pressure',0)),'ExitStage':timing.get('exit_stage',latest_live.get('exit_stage','CLEAR')),'TimingStage':timing.get('timing_stage','—'),'PlanValid':ent.get('plan_valid',False),'EntryLow':ent.get('zone_low'),'EntryHigh':ent.get('zone_high'),'BreakoutTrigger':ent.get('trigger'),'Invalidation':ent.get('invalidation'),'Target1':ent.get('target1'),'Target2':ent.get('target2'),'Price':latest_live.get('price'),'VolumeContext':latest_live.get('volume_context','N/A'),'LiveIntradayRVOL':(hfeat.iloc[-1].get('time_adjusted_rvol',np.nan) if hfeat is not None and len(hfeat) else np.nan),'DailyRobustRVOL':daily_lr.get('robust_volume_ratio',np.nan),'TimeAdjustedRVOL':(hfeat.iloc[-1].get('time_adjusted_rvol',np.nan) if hfeat is not None and len(hfeat) else daily_lr.get('robust_volume_ratio',np.nan)),'RSI14':latest_live.get('rsi14',np.nan),'SplitAdjusted':ca_report.get('split_adjusted',False),'DataQuality':ca_report.get('data_quality','OK')}]);decision=add_market_and_opportunity(row).iloc[0].to_dict();_lab_check_v603(runtime,jid)
        _lab_update_v603(runtime,jid,5,8,t,'Walk-forward diagnostics')
        comp=pd.DataFrame(latest['components'],columns=['Component','Points','Max']);comp['Strength %']=(100*comp.Points/comp.Max).round();ec=pd.DataFrame(latest['early_components'],columns=['Component','Points','Max']);ec['Strength %']=(100*ec.Points/ec.Max).round();cmp=compare_static_dynamic_backtest(f,horizon,target/100,buy_threshold,0);sb,db=cmp.get('static',{}),cmp.get('dynamic',{})
        def pct(v):return f'{v*100:.1f}%' if v is not None and np.isfinite(v) else '—'
        def num(v):return f'{v:.2f}x' if v is not None and np.isfinite(v) else '—'
        compare_df=pd.DataFrame([{'Model':'Static','Signals':sb.get('n',0),'Hit Rate':pct(sb.get('hit_rate',np.nan)),'Signal Lift':num(cmp.get('signal_lift_static',np.nan)),'Avg Fwd Return':pct(sb.get('avg_return',np.nan)),'Max Drawdown':pct(sb.get('max_drawdown',np.nan)),'Sample Reliability %':round(sb.get('sample_reliability',0),1)},{'Model':'Dynamic','Signals':db.get('n',0),'Hit Rate':pct(db.get('hit_rate',np.nan)),'Signal Lift':num(cmp.get('signal_lift_dynamic',np.nan)),'Avg Fwd Return':pct(db.get('avg_return',np.nan)),'Max Drawdown':pct(db.get('max_drawdown',np.nan)),'Sample Reliability %':round(db.get('sample_reliability',0),1)}])
        _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,6,8,t,'Event study + calibration')
        ev=early_event_backtest(f,target/100,(1,2,3),0);early_cal,quant_cal,cal_events=component_calibration(f,target/100,(1,2,3),0);_lab_check_v603(runtime,jid)
        _lab_update_v603(runtime,jid,7,8,t,'Building Analyze workbook')
        summary=pd.DataFrame([{'Ticker':t,'Version':APP_VERSION,'History':hist,'ForecastDays':horizon,'TargetPct':target,'HistoricalQuantThreshold':buy_threshold,'ThresholdMode':'AUTO-RESEARCH','Price':latest_live.get('price'),'TopScore':decision.get('TopScore'),'OpportunityScore':decision.get('OpportunityScore'),'TradeStage':decision.get('TradeStage'),'MovementStage':decision.get('MovementStage'),'ExitPressure':decision.get('ExitPressure'),'ExitStage':decision.get('ExitStage'),'VolumeContext':latest_live.get('volume_context'),'LiveIntradayRVOL':decision.get('LiveIntradayRVOL'),'DailyRobustRVOL':decision.get('DailyRobustRVOL'),'EvidenceQuality':decision.get('EvidenceQuality'),'WhyNotTradeTrigger':decision.get('WhyNotTradeTrigger'),'SplitAdjusted':ca_report.get('split_adjusted'),'DataQuality':ca_report.get('data_quality'),'DynamicQuant':dyn.get('dynamic_quant'),'DynamicEarly':dyn.get('dynamic_early'),'PredictionScore':dyn.get('final_prediction'),'EntryScore':ent.get('entry_score'),'EntryStatus':ent.get('status'),'EntryZoneLow':ent.get('zone_low'),'EntryZoneHigh':ent.get('zone_high'),'BreakoutTrigger':ent.get('trigger'),'Invalidation':ent.get('invalidation'),'Target1':ent.get('target1'),'Target2':ent.get('target2'),'ExplosiveScore':ex.get('score',np.nan),'MoveScore':timing.get('move_score',np.nan),'HourlyConfirmation':timing.get('hourly_confirmation',np.nan),'BacktestSignals':bt.get('n',0),'BacktestHitRate':bt.get('hit_rate',np.nan),'BacktestAvgReturn':bt.get('avg_return',np.nan),'BacktestWorstDrawdown':bt.get('max_drawdown',np.nan)}])
        sheets={'Summary':summary,'Historical Quant Threshold Evidence':auto_table,'Quant Components':comp,'Early Components':ec,'Static vs Dynamic':compare_df,'Daily Features':f.reset_index(),'Event Study':ev,'Early Calibration':early_cal,'Quant Calibration':quant_cal}
        if callable(historical_signal_timeline):
            atl=historical_signal_timeline(f);sheets['Signal Timeline']=atl
            if callable(acceleration_validation):sheets['Acceleration Validation']=acceleration_validation(atl)
        if isinstance(dyn.get('early_calibration',{}).get('table'),pd.DataFrame):sheets['Dynamic Early Calibration']=dyn['early_calibration']['table']
        if isinstance(dyn.get('quant_calibration',{}).get('table'),pd.DataFrame):sheets['Dynamic Quant Calibration']=dyn['quant_calibration']['table']
        combos=dyn.get('combinations',pd.DataFrame())
        if isinstance(combos,pd.DataFrame) and not combos.empty:sheets['Combinations']=combos
        excel=workbook_bytes(sheets,{'Tab':'Analyze','Ticker':t,'Version':APP_VERSION})
        payload={'ticker':t,'history':hist,'horizon':horizon,'target':target,'f':f,'latest':latest,'dyn':dyn,'hfeat':hfeat,'ent':ent,'latest_live':latest_live,'ex':ex,'timing':timing,'decision':decision,'ca_report':ca_report,'bt':bt,'buy_threshold':buy_threshold,'auto_table':auto_table,'comp':comp,'ec':ec,'cmp':cmp,'compare_df':compare_df,'ev':ev,'early_cal':early_cal,'quant_cal':quant_cal,'cal_events':cal_events,'excel':excel}
        _lab_update_v603(runtime,jid,8,8,t,'Completed');_lab_publish_v603(runtime,jid,payload)
    except _LabCancelled:_lab_publish_v603(runtime,jid,None,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)


def _backtest_worker_v603(runtime,jid,cfg):
    try:
        _lab_update_v603(runtime,jid,0,9,cfg['ticker'],'Downloading history')
        d=fetch_ohlcv(cfg['ticker'],cfg['history'],'1d');_lab_check_v603(runtime,jid)
        if d is None or len(d)<35: raise ValueError('Not enough market data')
        f=compute_features(d);rows=[]
        for i,x in enumerate([60,62,64,66,68,70,72,75],1):
            _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,i,9,str(x),'Testing historical Quant threshold')
            b=backtest_signal(f,int(cfg['days']),float(cfg['target'])/100,x,0)
            rows.append({'Historical Quant Threshold':x,'Hits':b.get('hits',0),'Signals':b['n'],'Hit Rate %':round(b['hit_rate']*100,1) if b['n']>=12 else np.nan,'Evidence Quality':'LOW' if b['n']<12 else ('STRONG' if b['n']>=30 and b.get('confidence_label')=='HIGH' else 'MEDIUM'),'Avg Return %':round(b['avg_return']*100,2) if b['n'] else np.nan,'Worst Drawdown %':round(b['max_drawdown']*100,2) if b['n'] else np.nan,'Confidence Score':b['confidence']})
        df=pd.DataFrame(rows);_lab_update_v603(runtime,jid,9,9,cfg['ticker'],'Building workbook')
        excel=workbook_bytes({'Threshold Backtest':df},{'Tab':'Backtest','Ticker':cfg['ticker'],'History':cfg['history'],'ForecastDays':cfg['days'],'TargetPct':cfg['target'],'Note':'Research only — not Top Score and not Trade Trigger'})
        _lab_publish_v603(runtime,jid,{'table':df,'excel':excel})
    except _LabCancelled:
        _lab_publish_v603(runtime,jid,None,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)


def _cal_table_v603(feat,ticker,kind,target,fold,phase):
    cal=_v544_calibrate_components(feat,kind,target,(1,2,3),0);tb=cal.get('table',pd.DataFrame());ev=int(cal.get('events',0) or 0);rows=[]
    if tb is not None and not tb.empty:
        for _,r in tb.iterrows():rows.append({'Ticker':ticker,'Fold':fold,'Phase':phase,'Component':r['Component'],'Lift x':float(r.get('Lift x',np.nan)),'Coverage %':float(r.get('Coverage %',np.nan)),'Events':ev,'Stability %':float(r.get('Stability %',np.nan))})
    return ev,rows


def _aggregate_wf_v603(rows):
    z=pd.DataFrame(rows)
    if z.empty:return z
    out=[]
    for comp,g in z.groupby('Component'):
        train=g[g.Phase=='Train'];val=g[g.Phase=='Validation'];keys=set(zip(train.Ticker,train.Fold)).intersection(set(zip(val.Ticker,val.Fold)))
        tr=[];va=[];cov=[];stab=[];stock_pos={};fold_pos={i:[] for i in range(1,5)};events=0
        for ticker,fold in keys:
            ar=train[(train.Ticker==ticker)&(train.Fold==fold)];br=val[(val.Ticker==ticker)&(val.Fold==fold)]
            if ar.empty or br.empty:continue
            tl=float(ar['Lift x'].iloc[0]);vl=float(br['Lift x'].iloc[0])
            if np.isfinite(tl):tr.append(tl)
            if np.isfinite(vl):va.append(vl);stock_pos.setdefault(ticker,[]).append(vl>1.0);fold_pos[fold].append(vl>1.0)
            cv=float(br['Coverage %'].iloc[0]);sv=float(br['Stability %'].iloc[0])
            if np.isfinite(cv):cov.append(cv)
            if np.isfinite(sv):stab.append(sv)
            events+=int(br['Events'].iloc[0] or 0)
        if not va:continue
        tmed=float(np.median(tr)) if tr else np.nan;vmed=float(np.median(va));vmean=float(np.mean(va));pstock=sum(1 for vals in stock_pos.values() if np.mean(vals)>0.5);ns=len(stock_pos);spr=100*pstock/ns if ns else 0;pfold=sum(1 for vals in fold_pos.values() if vals and np.mean(vals)>0.5);nf=sum(1 for vals in fold_pos.values() if vals);fpr=100*pfold/nf if nf else 0;repeat=np.isfinite(tmed) and tmed>1.0 and vmed>1.0
        verdict='ROBUST WF WINNER' if ns>=8 and nf>=3 and repeat and vmed>=1.05 and spr>=60 and fpr>=75 else ('PROMISING' if ns>=8 and repeat and spr>=50 else ('FAILED WF' if ns>=8 and np.isfinite(tmed) and tmed>1.05 and (vmed<0.95 or spr<=40) else 'MIXED / WEAK'))
        out.append({'Component':comp,'Train Median Lift':tmed,'WF Median Lift':vmed,'WF Mean Lift':vmean,'WF Coverage %':float(np.mean(cov)) if cov else np.nan,'Positive stocks':f'{pstock}/{ns}','Positive stocks %':spr,'Positive folds':f'{pfold}/{nf}','Positive folds %':fpr,'WF Stability %':float(np.mean(stab)) if stab else np.nan,'Validation events*':events,'Verdict':verdict})
    out=pd.DataFrame(out)
    if out.empty:return out
    rank={'ROBUST WF WINNER':0,'PROMISING':1,'MIXED / WEAK':2,'FAILED WF':3};out['_r']=out.Verdict.map(rank).fillna(9)
    return out.sort_values(['_r','WF Median Lift','Positive stocks %','Positive folds %'],ascending=[True,False,False,False]).drop(columns='_r').reset_index(drop=True)


def _validate_payload_v603(early_rows,quant_rows,stock_rows,skipped,overlap_frames,cfg,partial=False):
    ea=_aggregate_wf_v603(early_rows);qa=_aggregate_wf_v603(quant_rows);pp=pd.DataFrame()
    if overlap_frames:
        ovall=pd.concat(overlap_frames,ignore_index=True);comp_cols=[c for c in ovall.columns if c.startswith('Early: ') or c.startswith('Quant: ')];corr=ovall[comp_cols].corr(method='spearman');pairs=[]
        for i,a in enumerate(comp_cols):
            for b in comp_cols[i+1:]:
                v=float(corr.loc[a,b]) if a in corr.index and b in corr.columns else np.nan
                if np.isfinite(v):pairs.append({'Component A':a,'Component B':b,'Spearman correlation':v,'Abs correlation':abs(v)})
        if pairs:pp=pd.DataFrame(pairs).sort_values('Abs correlation',ascending=False).head(12).reset_index(drop=True)
    sheets={'Early WF':ea,'Quant WF':qa,'Stock Audit':pd.DataFrame(stock_rows),'Early Raw':pd.DataFrame(early_rows),'Quant Raw':pd.DataFrame(quant_rows)}
    if skipped:sheets['Skipped']=pd.DataFrame(skipped,columns=['Ticker','Reason'])
    if not pp.empty:sheets['Top Overlaps']=pp
    excel=workbook_bytes(sheets,{'Tab':'Validate','History':cfg['history'],'TargetPct':cfg['target'],'MinTrainEvents':cfg['min_events'],'Stocks':len(cfg['tickers']),'Status':'PARTIAL / STOPPED' if partial else 'COMPLETED'})
    return {'early':ea,'quant':qa,'audit':pd.DataFrame(stock_rows),'skipped':pd.DataFrame(skipped,columns=['Ticker','Reason']) if skipped else pd.DataFrame(),'overlaps':pp,'excel':excel,'partial':partial}


def _validate_worker_v603(runtime,jid,cfg):
    early_rows=[];quant_rows=[];stock_rows=[];skipped=[];overlap_frames=[];completed=0
    try:
        folds=[(.40,.55),(.55,.70),(.70,.85),(.85,1.00)];total=len(cfg['tickers'])
        for idx,t in enumerate(cfg['tickers'],1):
            _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,completed,total,t,'Walk-forward validation')
            try:
                d=fetch_ohlcv(t,cfg['history'],'1d');_lab_check_v603(runtime,jid)
                if d is None:skipped.append((t,'no price data returned'));completed=idx;continue
                if len(d)<180:skipped.append((t,f'only {len(d)} daily rows; need at least 180'));completed=idx;continue
                f=compute_features(d).dropna(subset=['Close']).copy();accepted=0;tr_events=0;va_events=0;er=[];qr=[]
                for fold,(train_end,test_end) in enumerate(folds,1):
                    _lab_check_v603(runtime,jid);i1=max(80,int(len(f)*train_end));i2=min(len(f),int(len(f)*test_end))
                    if i2-i1<20:continue
                    train=f.iloc[:i1].copy();test=f.iloc[i1:i2].copy();te,ter=_cal_table_v603(train,t,'early',float(cfg['target'])/100,fold,'Train');tq,tqr=_cal_table_v603(train,t,'quant',float(cfg['target'])/100,fold,'Train');ve,ver=_cal_table_v603(test,t,'early',float(cfg['target'])/100,fold,'Validation');vq,vqr=_cal_table_v603(test,t,'quant',float(cfg['target'])/100,fold,'Validation');tev=min(te,tq);vev=min(ve,vq)
                    if tev<int(cfg['min_events']) or vev<1:continue
                    accepted+=1;tr_events+=tev;va_events+=vev;er.extend(ter+ver);qr.extend(tqr+vqr)
                if accepted<2:skipped.append((t,f'only {accepted} usable walk-forward folds'));completed=idx;continue
                early_rows.extend(er);quant_rows.extend(qr);ov=[]
                for dt,r in f.iterrows():
                    rec={'Ticker':t,'Date':dt}
                    for name,pts,mx in early_score_row(r)[1]:rec['Early: '+name]=float(pts)/float(mx) if mx else np.nan
                    for name,pts,mx in score_row(r,0)[1]:rec['Quant: '+name]=float(pts)/float(mx) if mx else np.nan
                    ov.append(rec)
                if ov:overlap_frames.append(pd.DataFrame(ov))
                stock_rows.append({'Ticker':t,'Rows':len(f),'Usable folds':accepted,'Train events*':tr_events,'Validation events':va_events})
            except _LabCancelled:raise
            except Exception as e:skipped.append((t,f'calculation/data error: {type(e).__name__}'))
            completed=idx;_lab_update_v603(runtime,jid,completed,total,t,'Ticker complete')
        _lab_check_v603(runtime,jid);payload=_validate_payload_v603(early_rows,quant_rows,stock_rows,skipped,overlap_frames,cfg,False);_lab_publish_v603(runtime,jid,payload)
    except _LabCancelled:
        try:payload=_validate_payload_v603(early_rows,quant_rows,stock_rows,skipped,overlap_frames,cfg,True)
        except Exception:payload=None
        _lab_publish_v603(runtime,jid,payload,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)


def _entry_payload_v603(rows,audit,skipped,cfg,partial=False):
    summary,gate=_aggregate_entry_validation(rows);sheets={'Entry Summary':summary,'High Entry-Timing Gate':gate,'Raw Observations':pd.DataFrame(rows),'Stock Audit':pd.DataFrame(audit)}
    if skipped:sheets['Skipped']=pd.DataFrame(skipped,columns=['Ticker','Reason'])
    excel=workbook_bytes(sheets,{'Tab':'Entry Validation','History':cfg['history'],'TargetPct':cfg['target'],'HorizonDays':cfg['horizon'],'MinTrainEvents':cfg['min_events'],'Status':'PARTIAL / STOPPED' if partial else 'COMPLETED','Note':'Quant is supporting evidence, not a standalone live buy threshold'})
    return {'summary':summary,'gate':gate,'audit':pd.DataFrame(audit),'skipped':pd.DataFrame(skipped,columns=['Ticker','Reason']) if skipped else pd.DataFrame(),'excel':excel,'partial':partial,'observations':len(rows)//2}


def _entry_worker_v603(runtime,jid,cfg):
    rows=[];audit=[];skipped=[];completed=0;folds=[(.40,.55),(.55,.70),(.70,.85),(.85,1.00)];total=len(cfg['tickers'])
    try:
        for idx,t in enumerate(cfg['tickers'],1):
            _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,completed,total,t,'Entry walk-forward')
            try:
                stock_rows=[];d=fetch_ohlcv(t,cfg['history'],'1d');_lab_check_v603(runtime,jid)
                if d is None:skipped.append((t,'no price data returned'));completed=idx;continue
                if len(d)<180:skipped.append((t,f'only {len(d)} daily rows; need at least 180'));completed=idx;continue
                f=compute_features(d).dropna(subset=['Close']).copy();usable=0;tested=0
                for fold,(train_end,test_end) in enumerate(folds,1):
                    _lab_check_v603(runtime,jid);i1=max(80,int(len(f)*train_end));i2=min(len(f),int(len(f)*test_end))
                    if i2-i1<max(25,int(cfg['horizon'])+5):continue
                    train=f.iloc[:i1].copy();test=f.iloc[i1:i2].copy();ec=_v544_calibrate_components(train,'early',float(cfg['target'])/100,(1,2,3),0);qc=_v544_calibrate_components(train,'quant',float(cfg['target'])/100,(1,2,3),0);train_events=min(int(ec.get('events',0) or 0),int(qc.get('events',0) or 0))
                    if train_events<int(cfg['min_events']):continue
                    hit,ret,dd,days=_entry_forward_metrics(test,int(cfg['horizon']),float(cfg['target'])/100);fold_rows=0
                    for j in range(len(test)):
                        if not np.isfinite(hit[j]):continue
                        r=test.iloc[j];sq=float(score_row(r,0)[0]);se=float(early_score_row(r)[0]);dq,_=_v544_dynamic_score_row(r,qc,'quant',0);de,_=_v544_dynamic_score_row(r,ec,'early',0);static_entry=_entry_score_from_row(r,sq,se);dynamic_entry=_entry_score_from_row(r,dq,de);common={'Ticker':t,'Fold':fold,'Hit':float(hit[j]),'ForwardReturn':float(ret[j]),'Drawdown':float(dd[j]),'DaysToTarget':float(days[j]) if np.isfinite(days[j]) else np.nan};stock_rows.append({**common,'Mode':'Static','EntryScore':static_entry,'QuantScore':sq,'EarlyScore':se,'Bucket':_entry_bucket(static_entry)});stock_rows.append({**common,'Mode':'Dynamic','EntryScore':dynamic_entry,'QuantScore':dq,'EarlyScore':de,'Bucket':_entry_bucket(dynamic_entry)});fold_rows+=1
                    if fold_rows:usable+=1;tested+=fold_rows
                if usable<2:skipped.append((t,f'only {usable} usable walk-forward folds'));completed=idx;continue
                rows.extend(stock_rows);audit.append({'Ticker':t,'Rows':len(f),'Usable folds':usable,'Test rows':tested})
            except _LabCancelled:raise
            except Exception as e:skipped.append((t,f'calculation/data error: {type(e).__name__}'))
            completed=idx;_lab_update_v603(runtime,jid,completed,total,t,'Ticker complete')
        _lab_check_v603(runtime,jid);_lab_publish_v603(runtime,jid,_entry_payload_v603(rows,audit,skipped,cfg,False))
    except _LabCancelled:
        try:payload=_entry_payload_v603(rows,audit,skipped,cfg,True)
        except Exception:payload=None
        _lab_publish_v603(runtime,jid,payload,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)


def _explosive_worker_v603(runtime,jid,cfg):
    try:
        _lab_update_v603(runtime,jid,0,3,cfg['ticker'],'Downloading history');d=fetch_ohlcv(cfg['ticker'],cfg['history'],'1d');_lab_check_v603(runtime,jid)
        if d is None or len(d)<120:raise ValueError('Need at least 120 daily rows for this validation.')
        _lab_update_v603(runtime,jid,1,3,cfg['ticker'],'Computing features');f=compute_features(d);_lab_check_v603(runtime,jid)
        if not callable(explosive_walkforward):raise RuntimeError('quant engine is missing explosive_walkforward()')
        _lab_update_v603(runtime,jid,2,3,cfg['ticker'],'Explosive walk-forward');ewf=explosive_walkforward(f,cfg['threshold']);_lab_check_v603(runtime,jid)
        _lab_update_v603(runtime,jid,3,3,cfg['ticker'],'Building workbook');excel=workbook_bytes({'Explosive WalkForward':ewf},{'Tab':'Explosive Lab','Ticker':cfg['ticker'],'History':cfg['history'],'TriggerThreshold':cfg['threshold']});_lab_publish_v603(runtime,jid,{'table':ewf,'excel':excel})
    except _LabCancelled:_lab_publish_v603(runtime,jid,None,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)


def _feedback_worker_v603(runtime,jid,cfg):
    try:
        _lab_update_v603(runtime,jid,0,1,'Outcomes','Evaluating due 1D / 3D / 5D windows');_lab_check_v603(runtime,jid);n=_feedback_evaluate_due_v600(max_snapshots=int(cfg.get('max_snapshots',80)));_lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,1,1,'Outcomes','Completed');_lab_publish_v603(runtime,jid,{'evaluated':n})
    except _LabCancelled:_lab_publish_v603(runtime,jid,None,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)


tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8=st.tabs(["◉ Analyze","⌁ Scanner","▦ Backtest","◎ Validate","↗ Entry","⚡ Explosive","🧪 Research","↺ Feedback"])
with tab1:
    c1,c2,c3,c4=st.columns([1.35,1,1,1]);ticker=c1.text_input("Ticker","1196.HK",key="a603_ticker");hist=c2.selectbox("History",["3mo","6mo","1y"],1,key="a603_hist");horizon=c3.selectbox("Forecast days",[3,5,7,10],1,key="a603_horizon");target=c4.selectbox("Target %",[3,4,5,6,8,10,15,20],3,key="a603_target")
    st.caption("Live decisions do not use a Quant buy threshold. Historical Quant thresholds are research-only evidence.")
    required_engine_api=["fetch_ohlcv","compute_features","score_latest","backtest_signal","entry_timing","score_row","early_score_row"];missing_engine_api=[name for name in required_engine_api if not hasattr(qe,name)];engine_ver=getattr(qe,"ENGINE_VERSION",None);engine_build=getattr(qe,"ENGINE_BUILD_ID",None)
    if missing_engine_api:st.error("Quant engine is incompatible. Missing: "+", ".join(missing_engine_api)+". Upload all 4 files from the matching ZIP.")
    elif engine_ver is not None and str(engine_ver)!=APP_VERSION:st.warning(f"Version mismatch detected: app V{APP_VERSION} / engine {engine_ver}. Upload all 4 files from the same ZIP before trusting results.")
    elif engine_ver is not None:st.caption(f"✓ App and quant engine synced: V{APP_VERSION}"+(f" • {engine_build}" if engine_build else ""))
    a,_=_lab_snapshot_v603('analyze');busy=bool(a and a.get('status') in ('running','stopping'));b1,b2=st.columns([2,1])
    with b1:
        if st.button(f"▶ Start V{APP_VERSION} Analyze",key="an603_start",use_container_width=True,disabled=busy or bool(missing_engine_api)):
            cfg={'ticker':ticker.strip().upper(),'history':hist,'horizon':int(horizon),'target':float(target)};ok,msg=_start_lab_v603('analyze',_analyze_worker_v603,cfg,total=8)
            if ok:st.success("Analyze started server-side. You can switch apps and return later.");st.rerun()
            else:st.warning(msg)
    with b2:
        if st.button("■ Stop Analyze",key="an603_stop",use_container_width=True,disabled=not busy or (a and a.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('analyze');st.warning(msg) if ok else st.info(msg);st.rerun()
    if busy:_lab_live_fragment_v603('analyze')
    else:_render_lab_status_v603('analyze')
    a,last=_lab_snapshot_v603('analyze');snap=a if a and a.get('payload') else last
    if snap and snap.get('payload'):
        pay=snap['payload'];t=pay['ticker'];f=pay['f'];dyn=pay['dyn'];ent=pay['ent'];latest_live=pay['latest_live'];ex=pay['ex'];timing=pay['timing'];decision=pay['decision'];ca_report=pay['ca_report'];bt=pay['bt'];buy_threshold=pay['buy_threshold'];comp=pay['comp'];ec=pay['ec'];cmp=pay['cmp'];compare_df=pay['compare_df'];ev=pay['ev'];early_cal=pay['early_cal'];quant_cal=pay['quant_cal'];target_run=pay['target'];horizon_run=pay['horizon']
        phase=str(decision.get('MarketPhase','UNKNOWN'));cur=latest_live.get('price',np.nan);ch=latest_live.get('daily_change_pct',np.nan);currency='HKD' if t.endswith('.HK') else ('ILA' if t.endswith('.TA') else 'USD')
        st.markdown("<div class='section'>Decision cockpit</div>",unsafe_allow_html=True);p1,p2,p3,p4=st.columns([1.35,1,1,1]);p1.metric("Last price",f"{cur:,.3f} {currency}" if np.isfinite(cur) else '—',delta=f"{ch:+.2f}%" if np.isfinite(ch) else None);p2.metric("TOP SCORE",f"{decision.get('TopScore',0):.1f}");p3.metric("Opportunity",f"{decision.get('OpportunityScore',0):.1f}");p4.metric("Exit Pressure",f"{decision.get('ExitPressure',0):.0f}",delta=decision.get('ExitStage','CLEAR'))
        st.caption(f"{phase} • {decision.get('Market','—')} • completed {snap.get('completed_label','—')} • market data may be delayed")
        if ca_report.get('split_adjusted'):st.info("Corporate Action: Split adjusted — daily / 1H / 15m price scales were normalized before Entry and timing calculations.")
        if ca_report.get('data_quality')!='OK':st.error("DATA QUALITY CHECK: cross-timeframe price mismatch. PlanValid is forced FALSE and all Trade Plan levels are suppressed.")
        st.markdown(f"### Trade: :{'green' if decision.get('TradeStage')=='TRADE TRIGGER' else 'orange'}[{decision.get('TradeStage','—')}] · Movement: {decision.get('MovementStage','—')}");st.caption("Why not Trade Trigger? "+str(decision.get('WhyNotTradeTrigger','—')))
        q1,q2,q3,q4=st.columns(4);q1.metric("Prediction Score",f"{dyn.get('final_prediction',np.nan):.1f}");q2.metric("Evidence",str(decision.get('EvidenceQuality','LOW')));q3.metric("Live Entry Timing",f"{ent.get('entry_score',0):.1f}");q4.metric("Hourly",f"{timing.get('hourly_confirmation',np.nan):.1f}" if np.isfinite(timing.get('hourly_confirmation',np.nan)) else '—')
        r1,r2,r3,r4=st.columns(4);r1.metric("Move",f"{timing.get('move_score',np.nan):.1f}");r2.metric("Explosive",f"{ex.get('score',np.nan):.1f}");r3.metric("Volume context",latest_live.get('volume_context','N/A'));r4.metric("Live Intraday RVOL",f"{decision.get('LiveIntradayRVOL',np.nan):.2f}x" if np.isfinite(decision.get('LiveIntradayRVOL',np.nan)) else '—')
        st.caption(f"Daily Robust RVOL {decision.get('DailyRobustRVOL',np.nan):.2f}x • Reliability {decision.get('Reliability',0):.1f} • Prediction is a 0–100 setup score, not a probability.")
        st.caption(f"Exit engine: {decision.get('ExitStage','CLEAR')} • EXIT WATCH is an early warning, not a sell signal. EXIT ARMED / TRIGGER require persistent distribution / breakdown confirmation.")
        bt_value,bt_sample=backtest_display(bt);b1,b2,b3,b4=st.columns(4);b1.metric("Backtest evidence",bt_value);b2.metric("Sample",f"{int(bt.get('n',0))} signals");b3.metric("Historical Quant threshold",f"{buy_threshold} • research only");b4.metric("Worst historical drawdown",f"{bt.get('max_drawdown',np.nan)*100:.2f}%" if int(bt.get('n',0) or 0) else '—')
        if int(bt.get('n',0) or 0)<12:st.caption("LOW SAMPLE: hit-rate is de-emphasized and its influence on Reliability is capped.")
        st.markdown("<div class='section'>Precision entry / risk plan</div>",unsafe_allow_html=True)
        if bool(ent.get('plan_valid',False)) and ca_report.get('data_quality')=='OK':
            z1,z2,z3,z4=st.columns(4);z1.metric("Entry zone",f"{ent['zone_low']:.3f} – {ent['zone_high']:.3f}");z2.metric("Trade trigger",f"> {ent['trigger']:.3f}");z3.metric("Invalidation",f"< {ent['invalidation']:.3f}");z4.metric("Targets",f"{ent['target1']:.3f} / {ent['target2']:.3f}");st.caption(f"Entry status: {ent.get('status','—')} • Quant is supporting evidence, not a standalone entry gate.")
        else:st.warning("Trade plan suppressed: "+str(ent.get('plan_reason','data-quality validation failed')))
        st.markdown("<div class='section'>Dynamic Calibration — current ticker</div>",unsafe_allow_html=True);st.caption(f"Prediction Score = {dyn.get('quant_weight',0)*100:.0f}% Dynamic Quant + {dyn.get('early_weight',0)*100:.0f}% Dynamic Early. Small samples cannot take over the model.")
        dc1,dc2=st.columns(2)
        with dc1:
            st.markdown("#### Early dynamic weights");et=dyn.get('early_calibration',{}).get('table',pd.DataFrame()).copy()
            if not et.empty:st.dataframe(et,use_container_width=True,hide_index=True)
        with dc2:
            st.markdown("#### Quant dynamic weights");qt=dyn.get('quant_calibration',{}).get('table',pd.DataFrame()).copy()
            if not qt.empty:st.dataframe(qt,use_container_width=True,hide_index=True)
        combos=dyn.get('combinations',pd.DataFrame())
        if isinstance(combos,pd.DataFrame) and not combos.empty:st.markdown("#### Strong Early + Quant combinations");st.dataframe(combos.head(8),use_container_width=True,hide_index=True)
        left,right=st.columns(2)
        with left:st.markdown("#### Quant components");st.dataframe(comp,use_container_width=True,hide_index=True)
        with right:st.markdown("#### Early Prediction components");st.dataframe(ec,use_container_width=True,hide_index=True)
        st.markdown("<div class='section'>Static vs Dynamic holdout</div>",unsafe_allow_html=True);st.dataframe(compare_df,use_container_width=True,hide_index=True);st.caption(f"Calibration uses earlier {cmp.get('train_rows',0)} rows; holdout compares on later {cmp.get('test_rows',0)} eligible rows. Tiny samples do not prove Dynamic superiority.")
        st.markdown("<div class='section'>Early Prediction event study</div>",unsafe_allow_html=True)
        if ev is None or ev.empty:st.info(f"No qualifying +{target_run}% single-day events in this history window.")
        else:
            evshow=ev.copy();evshow['EventDate']=pd.to_datetime(evshow['EventDate']).dt.strftime('%Y-%m-%d');st.dataframe(evshow,use_container_width=True,hide_index=True)
            if 'EventQuality' in evshow and (evshow['EventQuality']=='OUTLIER REVIEW').any():st.warning("Extreme one-day moves are flagged OUTLIER REVIEW and are excluded from dynamic calibration to reduce corporate-action/anomaly contamination.")
        st.markdown("#### Component calibration")
        cc1,cc2=st.columns(2)
        with cc1:st.caption("Early components");st.dataframe(early_cal,use_container_width=True,hide_index=True) if early_cal is not None and not early_cal.empty else st.info("Insufficient Early evidence")
        with cc2:st.caption("Quant components");st.dataframe(quant_cal,use_container_width=True,hide_index=True) if quant_cal is not None and not quant_cal.empty else st.info("Insufficient Quant evidence")
        if pay.get('excel'):st.download_button("⬇️ Download Analyze to Excel",data=pay['excel'],file_name=f"AI_Stock_Hunter_V{APP_VERSION}_Analyze_{t}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="an603_dl")
        st.markdown("<div class='section'>📊 Price chart</div>",unsafe_allow_html=True);chart_period=st.radio("Range",["5D","1M","3M","6M","1Y","MAX"],horizontal=True,index=2,key=f"simple_period_{t}");chart_tf="1D" if chart_period in ("3M","6M","1Y","MAX") else "1H";chart_layers=["EMA20","EMA50","Volume"];chart_rsi=False;chart_macd=False
        with st.expander("Advanced chart",expanded=False):
            chart_tf=st.selectbox("Timeframe",["15m","1H","1D","1W"],2,key=f"adv_tf_{t}");chart_layers=st.multiselect("Layers",["EMA9","EMA20","EMA50","VWAP","Volume"],default=["EMA20","EMA50","Volume"],key=f"adv_layers_{t}");ac1,ac2=st.columns(2);chart_rsi=ac1.checkbox("RSI",False,key=f"adv_rsi_{t}");chart_macd=ac2.checkbox("MACD",False,key=f"adv_macd_{t}")
        chart_interval,chart_fetch_period,chart_capped=chart_request(chart_tf,chart_period);cd=fetch_ohlcv(t,chart_fetch_period,chart_interval)
        if cd is not None and len(cd)>0:
            cf=compute_features(cd,intraday=chart_interval in ("5m","15m","30m","1h"));st.plotly_chart(chart(cf,f"{t} • {chart_tf} • {chart_period}",chart_layers,chart_rsi,chart_macd,trade_plan=ent if ca_report.get('data_quality')=='OK' else None,current_price=latest_live.get('price')),use_container_width=True,config=CHART_CONFIG,key=f"main_chart_{t}_{chart_tf}_{chart_period}")
            if chart_capped:st.caption("Intraday display history is provider-capped. This affects the chart only, not model calculations.")

with tab2:
    st.markdown("<div class='section'>Multi-stock opportunity scanner</div>",unsafe_allow_html=True)
    universe_mode=st.radio("Market filter",["ALL 150","NASDAQ 50","HONG KONG 50","TEL AVIV 50","Custom"],horizontal=True)
    if universe_mode == "ALL 150": default_universe=VALIDATION_150
    elif universe_mode == "NASDAQ 50": default_universe=NASDAQ_50
    elif universe_mode == "HONG KONG 50": default_universe=HK_50
    elif universe_mode == "TEL AVIV 50": default_universe=TASE_50
    else: default_universe=DEFAULT_TICKERS
    tickers=st.text_area("Tickers",default_universe,disabled=universe_mode!="Custom",height=120)
    c1,c2,c3=st.columns(3); sh=c1.selectbox("History",["3mo","6mo","1y"],1,key="sh"); ho=c2.selectbox("Forecast days",[3,5,7,10],1,key="ho"); ta=c3.selectbox("Target %",[3,4,5,6,8,10],3,key="ta")
    with st.expander("Advanced scanner settings",expanded=False):
        st.caption("Fixed market views still scan all 150 so Global Rank is genuinely global. The selected market only changes what is displayed.")
        st.caption("Historical Quant thresholds are research-only and are not exposed as a live Scanner control.")
    historical_quant_threshold=66
    scan_universe=VALIDATION_150 if universe_mode!="Custom" else tickers
    prefilter_top=150 if universe_mode!="Custom" else min(150,max(10,len([x for x in tickers.split(',') if x.strip()])))
    show_mode=st.selectbox("Show",["ALL","TOP OPPORTUNITIES","ACTIONABLE NOW","WATCHLIST"],index=0)
    scanner_status=_scanner_status_v601()
    scanner_busy=scanner_status in ('running','stopping')
    b1,b2=st.columns([2,1])
    with b1:
        if st.button("▶ Start Scan",key="scanner_start_v601",use_container_width=True,disabled=scanner_busy):
            ts=[x.strip().upper() for x in scan_universe.split(',') if x.strip()]
            config={'tickers':ts,'history':sh,'horizon':int(ho),'target':float(ta)/100,'threshold':int(historical_quant_threshold),'prefilter_top':int(prefilter_top),'universe_mode':universe_mode}
            ok,msg=_start_scanner_job_v599(config)
            if ok:
                st.success("Scan started server-side. Global Rank will be calculated across the complete 150-stock universe.")
                st.rerun()
            else:st.warning(msg)
    with b2:
        if st.button("■ Stop Scan",key="scanner_stop_v601",use_container_width=True,disabled=not scanner_busy or scanner_status=='stopping'):
            ok,msg=_request_scanner_stop_v601()
            if ok:st.warning(msg)
            else:st.info(msg)
            st.rerun()
    # Auto-refresh only while RUNNING/STOPPING. Terminal states render once, statically.
    if _scanner_status_v601() in ('running','stopping'):
        _scanner_live_fragment_v599(show_mode,universe_mode)
    else:
        _render_scanner_results_v599(show_mode,universe_mode)
with tab3:
    st.markdown("<div class='section'>Historical Quant Threshold Backtest Lab</div>",unsafe_allow_html=True)
    st.caption("Research only — this tests historical Quant thresholds. It is NOT Top Score, NOT Trade Trigger, and NOT a live buy threshold.")
    bt_t=st.text_input("Ticker for threshold test","QCOM",key="bt603_t"); bt_h=st.selectbox("History",["6mo","1y"],1,key="bth"); bt_days=st.selectbox("Forecast days",[3,5,7,10],1,key="btd"); bt_target=st.selectbox("Target %",[3,4,5,6,8,10],3,key="btt")
    a,_=_lab_snapshot_v603('backtest');busy=bool(a and a.get('status') in ('running','stopping'))
    c1,c2=st.columns([2,1])
    with c1:
        if st.button("▶ Start Backtest",key="bt603_start",use_container_width=True,disabled=busy):
            cfg={'ticker':bt_t.strip().upper(),'history':bt_h,'days':int(bt_days),'target':float(bt_target)}
            ok,msg=_start_lab_v603('backtest',_backtest_worker_v603,cfg,total=9)
            if ok:st.success("Backtest started server-side. You can switch apps and return later.");st.rerun()
            else:st.warning(msg)
    with c2:
        if st.button("■ Stop Backtest",key="bt603_stop",use_container_width=True,disabled=not busy or (a and a.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('backtest');st.warning(msg) if ok else st.info(msg);st.rerun()
    if busy:_lab_live_fragment_v603('backtest')
    else:_render_lab_status_v603('backtest')
    a,last=_lab_snapshot_v603('backtest');snap=a if a and a.get('payload') else last
    if snap and snap.get('payload'):
        pay=snap['payload'];df=pay.get('table',pd.DataFrame())
        if not df.empty:st.dataframe(df,use_container_width=True,hide_index=True)
        st.caption("For samples below 12 signals, Hit Rate is intentionally hidden/de-emphasized. Compare evidence size, return and worst drawdown — not only hit rate.")
        if pay.get('excel'):st.download_button("⬇️ Download Backtest to Excel",data=pay['excel'],file_name=f"AI_Stock_Hunter_V{APP_VERSION}_Backtest_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="bt603_dl")
st.caption("Research prototype. Scores and entry zones are quantitative estimates, not guarantees or personalized investment advice.")


with tab4:
    st.markdown(f"<div class='section'>V{APP_VERSION} Walk-Forward Validation Lab</div>",unsafe_allow_html=True)
    st.caption("Four chronological unseen folds. Runs server-side with Stop; live model weights are NOT changed automatically.")
    universe_text=st.text_area("Validation universe",VALIDATION_50,height=145,key="v603_universe")
    vc1,vc2,vc3=st.columns(3);vhist=vc1.selectbox("Validation history",["1y","2y","3y","5y"],1,key="v_hist");vtarget=vc2.selectbox("Validation target %",[3,4,5,6,8],0,key="v_target");min_events=vc3.selectbox("Minimum train events / fold",[2,3,5,8],1,key="v_min_events")
    st.caption("Recommended: 50 stocks • 2Y • +3% target • minimum 3 train events/fold.")
    tickers=[]
    for raw in universe_text.replace("\n",",").split(","):
        t=raw.strip().upper()
        if t and t not in tickers:tickers.append(t)
    tickers=tickers[:50]
    a,_=_lab_snapshot_v603('validate');busy=bool(a and a.get('status') in ('running','stopping'));c1,c2=st.columns([2,1])
    with c1:
        if st.button(f"▶ Start V{APP_VERSION} Validation",key="v603_start",use_container_width=True,disabled=busy):
            if len(tickers)<3:st.error("Enter at least 3 tickers for cross-stock validation.")
            else:
                cfg={'tickers':tickers,'history':vhist,'target':float(vtarget),'min_events':int(min_events)};ok,msg=_start_lab_v603('validate',_validate_worker_v603,cfg,total=len(tickers))
                if ok:st.success("Validation started server-side. You can switch apps and return later.");st.rerun()
                else:st.warning(msg)
    with c2:
        if st.button("■ Stop Validation",key="v603_stop",use_container_width=True,disabled=not busy or (a and a.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('validate');st.warning(msg) if ok else st.info(msg);st.rerun()
    if busy:_lab_live_fragment_v603('validate')
    else:_render_lab_status_v603('validate')
    a,last=_lab_snapshot_v603('validate');snap=a if a and a.get('payload') else last
    if snap and snap.get('payload'):
        pay=snap['payload'];ea=pay.get('early',pd.DataFrame());qa=pay.get('quant',pd.DataFrame())
        m1,m2,m3=st.columns(3);m1.metric("Stocks validated",len(pay.get('audit',pd.DataFrame())));m2.metric("Skipped",len(pay.get('skipped',pd.DataFrame())));m3.metric("Status","PARTIAL" if pay.get('partial') else "COMPLETED")
        for title,z in [("Early — walk-forward validation",ea),("Quant — walk-forward validation",qa)]:
            st.markdown(f"#### {title}")
            if z is None or z.empty:st.info("Not enough evidence in this section.")
            else:
                show=z.copy()
                for c in ['Train Median Lift','WF Median Lift','WF Mean Lift','WF Coverage %','Positive stocks %','Positive folds %','WF Stability %']:
                    if c in show:show[c]=pd.to_numeric(show[c],errors='coerce').round(2)
                st.dataframe(show,use_container_width=True,hide_index=True)
        ov=pay.get('overlaps',pd.DataFrame())
        if ov is not None and not ov.empty:
            st.markdown("#### Highest component overlaps");st.dataframe(ov,use_container_width=True,hide_index=True)
            if (pd.to_numeric(ov['Abs correlation'],errors='coerce')>=.70).any():st.warning("Possible double-counting risk: one or more component correlations are ≥ 0.70.")
        audit=pay.get('audit',pd.DataFrame());sk=pay.get('skipped',pd.DataFrame())
        if audit is not None and not audit.empty:st.markdown("#### Stock / fold audit");st.dataframe(audit,use_container_width=True,hide_index=True)
        if sk is not None and not sk.empty:
            with st.expander(f"Skipped stocks ({len(sk)})"):st.dataframe(sk,use_container_width=True,hide_index=True)
        st.info(f"V{APP_VERSION} gate: do not change live weights from a tiny sample. Components must survive multiple unseen folds and many stocks.")
        if pay.get('excel'):st.download_button("⬇️ Download Validate to Excel"+(" (partial)" if pay.get('partial') else ""),data=pay['excel'],file_name=f"AI_Stock_Hunter_V{APP_VERSION}_Validate_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="v603_dl")
    st.markdown("<div class='section'>V6.0.3 Liquidity / validation notes</div>",unsafe_allow_html=True)
    st.caption("Liquidity remains relative to the stock's own rolling turnover. Walk-forward evidence, sample size and stability should drive any future weight changes.")

with tab5:
    st.markdown(f"<div class='section'>V{APP_VERSION} Entry Timing Validation — Static vs Dynamic</div>",unsafe_allow_html=True)
    st.caption("Validates whether high Entry Timing scores actually precede better outcomes. Quant supports the score but is NOT a standalone live buy threshold.")
    ec1,ec2,ec3,ec4=st.columns(4);ehist=ec1.selectbox("Entry validation history",["1y","2y","3y","5y"],1,key="entry_v_hist");etarget=ec2.selectbox("Entry target %",[2,3,4,5,6],1,key="entry_v_target");ehorizon=ec3.selectbox("Entry horizon days",[2,3,5,7,10],2,key="entry_v_horizon");emin=ec4.selectbox("Min train events / fold",[2,3,5,8],1,key="entry_v_min_events")
    entry_tickers=[x.strip() for x in VALIDATION_50.split(',') if x.strip()]
    a,_=_lab_snapshot_v603('entry');busy=bool(a and a.get('status') in ('running','stopping'));c1,c2=st.columns([2,1])
    with c1:
        if st.button("▶ Start Entry Validation",key="entry603_start",use_container_width=True,disabled=busy):
            cfg={'tickers':entry_tickers,'history':ehist,'target':float(etarget),'horizon':int(ehorizon),'min_events':int(emin)};ok,msg=_start_lab_v603('entry',_entry_worker_v603,cfg,total=len(entry_tickers))
            if ok:st.success("Entry Validation started server-side. You can switch apps and return later.");st.rerun()
            else:st.warning(msg)
    with c2:
        if st.button("■ Stop Entry Validation",key="entry603_stop",use_container_width=True,disabled=not busy or (a and a.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('entry');st.warning(msg) if ok else st.info(msg);st.rerun()
    if busy:_lab_live_fragment_v603('entry')
    else:_render_lab_status_v603('entry')
    a,last=_lab_snapshot_v603('entry');snap=a if a and a.get('payload') else last
    if snap and snap.get('payload'):
        pay=snap['payload'];summary=pay.get('summary',pd.DataFrame());gate=pay.get('gate',pd.DataFrame());audit=pay.get('audit',pd.DataFrame());sk=pay.get('skipped',pd.DataFrame())
        x1,x2,x3,x4=st.columns(4);x1.metric("Stocks validated",len(audit));x2.metric("Skipped",len(sk));x3.metric("Walk-forward folds","4");x4.metric("Test observations",f"{pay.get('observations',0):,}")
        st.markdown("#### Entry Score buckets")
        if summary is not None and not summary.empty:st.dataframe(summary.round(2),use_container_width=True,hide_index=True)
        st.markdown("#### High Entry-Timing gate — Static vs Dynamic")
        if gate is None or gate.empty:st.info("No Entry Timing ≥72 signals in the validated test blocks.")
        else:st.dataframe(gate.round(2),use_container_width=True,hide_index=True)
        if audit is not None and not audit.empty:st.markdown("#### Stock / fold audit");st.dataframe(audit,use_container_width=True,hide_index=True)
        if sk is not None and not sk.empty:
            with st.expander(f"Skipped stocks ({len(sk)})"):st.dataframe(sk,use_container_width=True,hide_index=True)
        st.caption("This is timing validation, not a buy signal. Intraday history is provider-limited, so multi-year walk-forward uses consistent daily historical features.")
        if pay.get('excel'):st.download_button("⬇️ Download Entry Validation to Excel"+(" (partial)" if pay.get('partial') else ""),data=pay['excel'],file_name=f"AI_Stock_Hunter_V{APP_VERSION}_EntryValidation_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="entry603_dl")

with tab6:
    st.markdown("<div class='section'>⚡ Explosive Move Walk-Forward Lab</div>",unsafe_allow_html=True)
    st.caption("Direction-aware explosive research. Server-side background run with Stop; a high score is never presented as a probability.")
    ex_t=st.text_input("Explosive validation ticker","1196.HK",key="ex_t");ex_hist=st.selectbox("Explosive history",["1y","2y","3y","5y"],1,key="ex_hist");ex_th=st.slider("Explosive research threshold",50,90,68,key="ex_th")
    a,_=_lab_snapshot_v603('explosive');busy=bool(a and a.get('status') in ('running','stopping'));c1,c2=st.columns([2,1])
    with c1:
        if st.button("▶ Start Explosive Walk-Forward",key="ex603_start",use_container_width=True,disabled=busy):
            cfg={'ticker':ex_t.strip().upper(),'history':ex_hist,'threshold':int(ex_th)};ok,msg=_start_lab_v603('explosive',_explosive_worker_v603,cfg,total=3)
            if ok:st.success("Explosive research started server-side. You can switch apps and return later.");st.rerun()
            else:st.warning(msg)
    with c2:
        if st.button("■ Stop Explosive",key="ex603_stop",use_container_width=True,disabled=not busy or (a and a.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('explosive');st.warning(msg) if ok else st.info(msg);st.rerun()
    if busy:_lab_live_fragment_v603('explosive')
    else:_render_lab_status_v603('explosive')
    a,last=_lab_snapshot_v603('explosive');snap=a if a and a.get('payload') else last
    if snap and snap.get('payload'):
        pay=snap['payload'];ewf=pay.get('table',pd.DataFrame())
        if ewf is not None and not ewf.empty:
            st.dataframe(ewf,use_container_width=True,hide_index=True);focus=ewf[(ewf.Target=='+15%') & (ewf.Horizon=='5D')] if {'Target','Horizon'}.issubset(ewf.columns) else pd.DataFrame()
            if not focus.empty:
                r=focus.iloc[0];st.metric("+15% / 5D median lift",f"{r['Median Lift']:.2f}x" if np.isfinite(r['Median Lift']) else '—',delta=f"Positive folds {r['Positive Folds']}")
        if pay.get('excel'):st.download_button("⬇️ Download Explosive Lab to Excel",data=pay['excel'],file_name=f"AI_Stock_Hunter_V{APP_VERSION}_ExplosiveLab_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="ex603_dl")

with tab7:
    st.markdown("<div class='section'>🧪 Adaptive 150-Stock Research</div>",unsafe_allow_html=True)
    st.caption("Runs causal V6 research across the selected multi-market universe, including directional volume, Exit Pressure, score acceleration, trajectory consistency, Reliability and Top-K validation.")
    r_market=st.radio("Research market",["ALL 150","NASDAQ 50","HONG KONG 50","TEL AVIV 50"],horizontal=True,key="r_market")
    r_hist=st.selectbox("Research history",["2y","3y","5y"],2,key="r60_hist")
    r_min=st.number_input("Minimum signals for Best Setup",10,100,20,5,key="r60_min")

    research_status=_research_status_v602()
    research_busy=research_status in ('running','stopping')
    rb1,rb2=st.columns([2,1])
    with rb1:
        if st.button("▶ Start Research",key="run_602_research",use_container_width=True,disabled=research_busy):
            if not all(callable(x) for x in [historical_signal_timeline,threshold_optimization,adaptive_target_horizon_v2,atr_target_validation,pre_move_study,topk_daily_validation]):
                st.error(f"V{APP_VERSION} research functions are missing from quant_engine.py. Upload the matching files.")
            else:
                _ru={'ALL 150':VALIDATION_150,'NASDAQ 50':NASDAQ_50,'HONG KONG 50':HK_50,'TEL AVIV 50':TASE_50}[r_market]
                rts=[x.strip() for x in _ru.split(',') if x.strip()]
                config={'tickers':rts,'market':r_market,'history':r_hist,'minimum_signals':int(r_min)}
                ok,msg=_start_research_job_v602(config)
                if ok:
                    st.success("Research started server-side. You can leave this page and return later.")
                    st.rerun()
                else:
                    st.warning(msg)
    with rb2:
        if st.button("■ Stop Research",key="stop_602_research",use_container_width=True,disabled=not research_busy or research_status=='stopping'):
            ok,msg=_request_research_stop_v602()
            if ok: st.warning(msg)
            else: st.info(msg)
            st.rerun()

    st.caption("Server-side background mode: switching to another phone app/browser tab does not cancel the Research job. A Streamlit server restart/sleep can still end an in-memory job.")
    if _research_status_v602() in ('running','stopping'):
        _research_live_fragment_v602()
    else:
        _render_research_status_v602()


with tab8:
    st.markdown("<div class='section'>↺ Feedback / Outcome Tracker</div>",unsafe_allow_html=True)
    st.caption("Every completed live scan is snapshotted. Due outcomes are checked at 1D / 3D / 5D. Small samples never auto-retrain the production model.")
    a,_=_lab_snapshot_v603('feedback');busy=bool(a and a.get('status') in ('running','stopping'));c1,c2=st.columns([2,1])
    with c1:
        if st.button("▶ Refresh due outcomes",key="feedback603_start",use_container_width=True,disabled=busy):
            ok,msg=_start_lab_v603('feedback',_feedback_worker_v603,{'max_snapshots':80},total=1)
            if ok:st.success("Feedback refresh started server-side. You can switch apps and return later.");st.rerun()
            else:st.warning(msg)
    with c2:
        if st.button("■ Stop Feedback refresh",key="feedback603_stop",use_container_width=True,disabled=not busy or (a and a.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('feedback');st.warning(msg) if ok else st.info(msg);st.rerun()
    if busy:_lab_live_fragment_v603('feedback')
    else:_render_lab_status_v603('feedback')
    a,last=_lab_snapshot_v603('feedback');snap=a if a and a.get('payload') else last
    if snap and snap.get('payload') and 'evaluated' in snap['payload']:st.success(f"Evaluated {snap['payload']['evaluated']} due outcome windows in the last refresh.")
    sn,oc=_feedback_frames_v600()
    done={(int(r.snapshot_id),int(r.horizon)) for _,r in oc.iterrows()} if not oc.empty else set()
    pending={h:0 for h in (1,3,5)}
    next_dates=[]
    if not sn.empty:
        for _,r in sn.iterrows():
            try:base=pd.Timestamp(str(r.ts_utc))
            except Exception:continue
            for h in (1,3,5):
                if (int(r.id),h) not in done:
                    pending[h]+=1;next_dates.append(base+pd.Timedelta(days=h))
    f1,f2,f3,f4,f5=st.columns(5);f1.metric("Snapshots",len(sn));f2.metric("Evaluated windows",len(oc));f3.metric("Pending 1D",pending[1]);f4.metric("Pending 3D",pending[3]);f5.metric("Pending 5D",pending[5])
    if next_dates:
        future=[d for d in next_dates if d>=pd.Timestamp.now(tz=next_dates[0].tz) if getattr(d,'tzinfo',None)] if getattr(next_dates[0],'tzinfo',None) else [d for d in next_dates if d>=pd.Timestamp.now()]
        nd=min(future) if future else min(next_dates)
        st.caption(f"Next scheduled evaluation window: approximately {pd.Timestamp(nd).strftime('%Y-%m-%d %H:%M')} • DB: {_feedback_db_path_v600().name}")
    else:st.caption(f"DB: {_feedback_db_path_v600().name}")
    if sn.empty:
        st.info("No live scan snapshots yet. Run Scanner once; the completed scan will be recorded automatically.")
    elif oc.empty:
        st.info("Snapshots are being collected. 1D/3D/5D outcome rows will appear when enough future market data exists.")
        st.dataframe(sn.head(30),use_container_width=True,hide_index=True)
    else:
        merged=oc.merge(sn,left_on='snapshot_id',right_on='id',how='left');merged['End Return %']=100*pd.to_numeric(merged.end_return,errors='coerce');merged['MFE %']=100*pd.to_numeric(merged.max_favorable,errors='coerce');merged['MAE %']=100*pd.to_numeric(merged.max_adverse,errors='coerce')
        st.markdown("#### Live-signal audit")
        stage=merged.groupby(['horizon','trade_stage'],dropna=False).agg(Signals=('snapshot_id','count'),Avg_End_Return=('End Return %','mean'),Avg_MFE=('MFE %','mean'),Avg_MAE=('MAE %','mean'),Target1_Hit=('target1_hit','mean'),Invalidation_Hit=('invalidation_hit','mean')).reset_index();stage['Target1 Hit %']=100*stage.pop('Target1_Hit');stage['Invalidation Hit %']=100*stage.pop('Invalidation_Hit')
        for c in ['Avg_End_Return','Avg_MFE','Avg_MAE','Target1 Hit %','Invalidation Hit %']:stage[c]=pd.to_numeric(stage[c],errors='coerce').round(2)
        st.dataframe(stage,use_container_width=True,hide_index=True);st.markdown("#### Recent evaluated snapshots");showcols=['ticker','market','horizon','trade_stage','movement_stage','top_score','opportunity','entry_score','hourly','exit_pressure','global_rank','End Return %','MFE %','MAE %','first_event'];st.dataframe(merged[[c for c in showcols if c in merged]].head(100),use_container_width=True,hide_index=True)
        excel_feedback=workbook_bytes({'Snapshots':sn,'Outcomes':oc,'Stage Summary':stage},{'Tab':'Feedback','Version':APP_VERSION})
        st.download_button('⬇️ Download Feedback audit to Excel',data=excel_feedback,file_name=f"AI_Stock_Hunter_V{APP_VERSION}_Feedback_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True,key='feedback603_dl')
    st.caption("Persistence note: the included SQLite tracker persists on the running Streamlit host. A redeploy/host reset may clear local storage; use an external database later for permanent multi-deploy history.")

