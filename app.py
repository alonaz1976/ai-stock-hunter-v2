import streamlit as st
import pandas as pd
import numpy as np
import math
import threading
import sqlite3
import json
import os
import base64
import gzip
import tempfile
import urllib.request as urllib_request
import urllib.error as urllib_error
import urllib.parse as urllib_parse
import time as time_module
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
import importlib.util
from pathlib import Path
from datetime import datetime, time, timedelta, timezone
from io import BytesIO
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
from plotly.subplots import make_subplots

APP_VERSION = "6.3.3"
APP_BUILD_ID = "V633-COMBINATION-DISCOVERY-WALKFORWARD-20260919-A"

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
pre_move_indicator_lift = getattr(qe, "pre_move_indicator_lift", None)
hourly_lift_study = getattr(qe, "hourly_lift_study", None)
topk_daily_validation = getattr(qe, "topk_daily_validation", None)
atr_target_validation = getattr(qe, "atr_target_validation", None)
hourly_confirmation = getattr(qe, "hourly_confirmation", None)
signal_timing_latest = getattr(qe, "signal_timing_latest", None)
acceleration_validation = getattr(qe, "acceleration_validation", None)
confirmed_intraday_bars = getattr(qe, "confirmed_intraday_bars", lambda x: x)
normalize_cross_timeframes = getattr(qe, "normalize_cross_timeframes", lambda d,h=None,m=None,anchor_price=None,split_ratio=None: (d,h,m,{"split_adjusted":False,"split_detected":False,"data_quality":"OK","details":[]}))
fetch_live_intraday_snapshot = getattr(qe, "fetch_live_intraday_snapshot", lambda ticker,daily=None: {"price":np.nan,"prev_close":np.nan,"change_pct":np.nan,"timestamp_label":"—","source":"unavailable","fresh":False,"display_current":False,"trade_fresh":False,"anchor_eligible":False,"quote_status":"UNAVAILABLE","same_session_date":False,"age_minutes":np.nan,"split_ratio":np.nan,"split_date":None,"split_detected":False})
frame_price_snapshot = getattr(qe, "frame_price_snapshot", lambda ticker,frame,max_age_minutes=60.0: {"price":np.nan,"timestamp_label":"—","fresh":False,"same_session_date":False,"age_minutes":np.nan,"source":"unavailable"})
resolve_current_market_snapshot = getattr(qe, "resolve_current_market_snapshot", lambda ticker,daily=None,hourly=None,m15=None,primary=None,market_open=False,market_phase=None,market_date=None: dict(primary or {}))
directional_volume_row = getattr(qe, "directional_volume_row", lambda r: {"magnitude":0.0,"bullish":0.0,"bearish":0.0,"label":"N/A","rvol":np.nan})
institutional_flow_row = getattr(qe, "institutional_flow_row", lambda r: {"score":0.0,"label":"NEUTRAL","components":[]})
exit_pressure_row = getattr(qe, "exit_pressure_row", lambda r: (0.0,[],"CLEAR"))
entry_score_row = getattr(qe, "entry_score_row", None)
setup_origin_validation_v619 = getattr(qe, "setup_origin_validation_v619", lambda m15_feat, target_pct=.02, stop_pct=.015, max_bars=16: pd.DataFrame())
setup_origin_validation_summary_v619 = getattr(qe, "setup_origin_validation_summary_v619", lambda events: pd.DataFrame())
setup_origin_validation_summary_v620 = getattr(qe, "setup_origin_validation_summary_v620", setup_origin_validation_summary_v619)
setup_origin_robustness_v620 = getattr(qe, "setup_origin_robustness_v620", lambda m15_feat: pd.DataFrame())
continuation_base_validation_v620 = getattr(qe, "continuation_base_validation_v620", lambda m15_feat, breakout_lookahead=8, target_pct=.02, stop_pct=.015, outcome_bars=16: pd.DataFrame())
continuation_base_validation_summary_v620 = getattr(qe, "continuation_base_validation_summary_v620", lambda events: pd.DataFrame())
continuation_base_validation_v621 = getattr(qe, "continuation_base_validation_v621", continuation_base_validation_v620)
continuation_base_validation_summary_v621 = getattr(qe, "continuation_base_validation_summary_v621", continuation_base_validation_summary_v620)
setup_origin_matched_baseline_v622 = getattr(qe, "setup_origin_matched_baseline_v622", lambda m15_feat, target_pct=.02, stop_pct=.015, max_bars=16: pd.DataFrame())
research_evidence_summary_v622 = getattr(qe, "research_evidence_summary_v622", lambda origin_summary, matched_baseline, robustness, continuation_summary: pd.DataFrame())
setup_origin_matched_confidence_v623 = getattr(qe, "setup_origin_matched_confidence_v623", lambda matched_baseline: pd.DataFrame())
setup_origin_session_pairs_v624 = getattr(qe, "setup_origin_session_pairs_v624", lambda m15_feat, target_pct=.02, stop_pct=.015, max_bars=16: pd.DataFrame())
cluster_bootstrap_matched_edge_v624 = getattr(qe, "cluster_bootstrap_matched_edge_v624", lambda pairs, n_boot=1200, seed=624: pd.DataFrame())
pre_move_stock_oos_v625 = getattr(qe, "pre_move_stock_oos_v625", lambda feat, target_pct=.05, horizon_days=3, discovery_fraction=.70: pd.DataFrame())
aggregate_pre_move_oos_v625 = getattr(qe, "aggregate_pre_move_oos_v625", lambda rows, min_discovery_signals=25, min_validation_signals=12, min_discovery_lift=1.20: pd.DataFrame())


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


def _v544_scan_universe_dynamic(tickers,daily_period='6mo',use_hourly=True,hourly_period='1mo',horizon=5,target_pct=.03,min_turnover=0,buy_threshold=66,prefilter_top=30,progress_callback=None,optimizer_model=None):
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
            opt_pre=np.nan
            if optimizer_model:
                rr=f.dropna(subset=['Close']).iloc[-1]; q0=float(ds.get('dynamic_quant',ds.get('static_quant',50))); e0=_entry_score_from_row(rr,q0,float(ds.get('dynamic_early',50))); rf=_entry_research_features_v612(rr,q0,e0)
                inst=institutional_flow_row(rr); tmp={'Ticker':ticker,'DailySetupCheck':rf.get('DailySetup'),'FreshSignalCheck':rf.get('FreshSignal'),'VolumeFlowCheck':rf.get('VolumeFlow'),'NoChaseCheck':rf.get('NoChase'),'EntryScore':e0,'DynamicQuant':q0,'ExitPressure':rf.get('ExitPressureAtSignal',50),'InstitutionalFlowScore':inst.get('score',0),'DailyRobustRVOL':rr.get('robust_volume_ratio',np.nan),'ADX14':rr.get('adx14',np.nan),'VolumeAccel':rr.get('vol_accel',np.nan),'FreshTransitionCount':rr.get('fresh_transition_count',0)}
                opt_pre,_,_=_optimized_score_from_row_v612(tmp,optimizer_model,ticker)
                if np.isfinite(opt_pre):pre=.82*opt_pre+.18*float(ds['final_prediction'])
                else:pre=-1e6  # no eligible OOS model for this market/horizon/target -> do not consume optimized deep-analysis slots
            stage.append((pre,ticker,f,ds,opt_pre))
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
    for deep_i,(pre,ticker,f,ds,opt_pre) in enumerate(stage,1):
        if progress_callback:
            progress_callback('stage2',deep_i,len(stage),ticker)
        try:
            hfeat=m15feat=None; h=m15=None; hq=he=np.nan
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
            market_regime=_market_regime_v610(ticker)
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
            phase_scan=_market_phase(_market_for_ticker_v612(ticker))
            ps15=frame_price_snapshot(ticker,m15,45.0);ps1h=frame_price_snapshot(ticker,h,110.0)
            ps=ps15 if ps15.get('fresh') else (ps1h if ps1h.get('fresh') else None)
            liveq=None
            # Keep the full 151-stock scan light: only invoke the richer current-quote
            # fallback for a deep-analysis finalist when 15m/1H cannot supply today's price.
            if phase_scan=='OPEN' and ps is None:
                try:liveq=fetch_live_intraday_snapshot(ticker,f)
                except Exception:liveq=None
            if liveq and liveq.get('display_current') and np.isfinite(float(liveq.get('price',np.nan))):
                intraday_price=float(liveq.get('price'));display_price=intraday_price
                live_price_fresh=bool(liveq.get('trade_fresh'))
                price_source=str(liveq.get('source','current/delayed fallback'))
                price_timestamp=str(liveq.get('timestamp_label','—'))
            else:
                live_price_fresh=bool(ps is not None) if phase_scan=='OPEN' else True
                intraday_price=float(ps.get('price',np.nan)) if ps is not None and np.isfinite(float(ps.get('price',np.nan))) else np.nan
                display_price=intraday_price if np.isfinite(intraday_price) else float(lr['Close'])
                price_source=(('15m current-session confirmed bar' if ps is ps15 else '1H current-session confirmed bar') if ps is not None else 'Daily reference / live unavailable')
                price_timestamp=ps.get('timestamp_label','—') if ps is not None else '—'
            ent=entry_timing(f,dq,de,hourly_feat=hfeat,m15_feat=m15feat,current_price=display_price,market_regime=market_regime,market_phase=phase_scan,market_date=_market_status_detail_v612(_market_for_ticker_v612(ticker)).get('local_date'))
            if str(ca_report.get('data_quality','OK'))!='OK':
                ent=dict(ent);ent.update({'plan_valid':False,'plan_reason':'Blocked by cross-timeframe data-quality gate','trigger_state':'WAIT','status':'WAIT','zone_low':np.nan,'zone_high':np.nan,'trigger':np.nan,'invalidation':np.nan,'target1':np.nan,'target2':np.nan})
            ex=explosive_latest(live_f,hfeat) if callable(explosive_latest) else {}
            timing=signal_timing_latest(live_f,hfeat) if callable(signal_timing_latest) else {}
            latest_live=score_latest(live_f,0); latest_live['price']=display_price
            hopt_score,hopt_match,hopt_status,hopt_horizon=_hourly_score_live_v613(ticker,hfeat,optimizer_model) if optimizer_model else (np.nan,np.nan,'NO ELIGIBLE HOURLY MODEL','—')
            rows.append({'Ticker':ticker,'Prediction':round(pred,1),'DynamicQuant':round(dq,1),'DynamicEarly':round(de,1),'StaticQuant':round(ds['static_quant'],1),'StaticEarly':round(ds['static_early'],1),'EntryScore':ent['entry_score'],'LiveActionabilityScore':ent.get('live_actionability_score',ent.get('entry_score',0)),'SetupEntryScore':ent.get('setup_entry_score_pre_chase',ent.get('entry_score',0)),'EntryStatus':ent['status'],'EntryTriggerState':ent.get('trigger_state',ent.get('status','WAIT')),'EntryConfirmationPct':ent.get('confirmation_pct',0),'EntryConfirmedConditions':ent.get('confirmed_conditions',0),'EntryTotalConditions':ent.get('total_conditions',6),'DailySetupCheck':ent.get('daily_setup',False),'FreshSignalCheck':ent.get('fresh_signal',False),'HourlyEntryCheck':ent.get('hourly_entry_ok',False),'VolumeFlowCheck':ent.get('volume_flow_ok',False),'NoChaseCheck':ent.get('no_chase',False),'ExtensionGuardCheck':ent.get('extension_guard_ok',True),'ChaseRiskScore':ent.get('chase_risk_score',0),'ChaseRiskLabel':ent.get('chase_risk_label','LOW'),'SessionMovePct':ent.get('session_move_pct',np.nan),'MoveBeforeTriggerPct':ent.get('move_before_trigger_pct',np.nan),'SessionMoveATR':ent.get('session_move_atr',np.nan),'SessionMovePercentile':ent.get('session_move_percentile',np.nan),'SinceTriggerPct':ent.get('since_trigger_pct',np.nan),'GapPct':ent.get('gap_pct',np.nan),'VWAPDistanceATR':ent.get('vwap_distance_atr',np.nan),'EMA9DistanceATR':ent.get('ema9_distance_atr',np.nan),'EMA20DistanceATR':ent.get('ema20_distance_atr',np.nan),'Target1ProgressPct':ent.get('target1_progress_pct',np.nan),'LiveRR_T1':ent.get('live_rr_t1',np.nan),'LiveRR_T2':ent.get('live_rr_t2',np.nan),'LiveRRGuardOK':ent.get('live_rr_guard_ok',True),'CarryoverExtension':ent.get('carryover_extension',False),'CarryoverHardVeto':ent.get('carryover_hard_veto',False),'PriorSessionMovePct':ent.get('prior_session_move_pct',np.nan),'CarryoverRetentionPct':ent.get('carryover_retention_pct',np.nan),'NextSessionCarryoverCandidate':ent.get('next_session_carryover_candidate',False),'NextSessionCarryoverHardCandidate':ent.get('next_session_carryover_hard_candidate',False),'NextSessionCarryoverReason':ent.get('next_session_carryover_reason',''),'OriginToTriggerPct':ent.get('origin_to_trigger_pct',np.nan),'TriggerLagMinutes':ent.get('trigger_lag_minutes',np.nan),'TriggerLagATR':ent.get('trigger_lag_atr',np.nan),'MoveConsumedBeforeTriggerPct':ent.get('move_consumed_before_trigger_pct',np.nan),'TriggerEfficiencyLabel':ent.get('trigger_efficiency_label','RESEARCH • NO DATA'),'VolumeTrend':ent.get('volume_trend','NO DATA'),'VolumeTrend15m':ent.get('volume_trend_15m','NO DATA'),'VolumeTrend1H':ent.get('volume_trend_1h','NO DATA'),'MomentumState':ent.get('momentum_state','NO DATA'),'MomentumState15m':ent.get('momentum_state_15m','NO DATA'),'MomentumState1H':ent.get('momentum_state_1h','NO DATA'),'PostSpikeState':ent.get('post_spike_state','NO DATA'),'PostSpikeDistributionRisk':ent.get('post_spike_distribution_risk','NO DATA'),'ContinuationBaseCandidate':ent.get('continuation_base_candidate',False),'ContinuationBaseStatus':ent.get('continuation_base_status','RESEARCH • NO BASE'),'ContinuationBaseQuality':ent.get('continuation_base_quality','NO DATA'),'ContinuationSessionPeak':ent.get('continuation_session_peak',np.nan),'ContinuationBreakoutTrigger':ent.get('continuation_breakout_trigger',np.nan),'ContinuationBreakoutReference':ent.get('continuation_breakout_reference','—'),'SetupOriginPrice':ent.get('setup_origin_price',np.nan),'SetupOriginTime':ent.get('setup_origin_time','—'),'MoveBeforeSetupOriginPct':ent.get('move_before_setup_origin_pct',np.nan),'SinceSetupOriginPct':ent.get('since_setup_origin_pct',np.nan),'TriggerAnchorPrice':ent.get('trigger_anchor_price',np.nan),'TriggerAnchorTime':ent.get('trigger_anchor_time','—'),'TriggerAnchorBarStartTime':ent.get('trigger_anchor_bar_start_time','—'),'TriggerAnchorTimeframe':ent.get('trigger_anchor_timeframe','—'),'TriggerAnchorQuality':ent.get('trigger_anchor_quality','NONE'),'TriggerAnchorAgeBars':ent.get('trigger_anchor_age_bars',np.nan),'RetestZoneLow':ent.get('retest_zone_low',np.nan),'RetestZoneHigh':ent.get('retest_zone_high',np.nan),'PullbackNeededPct':ent.get('pullback_needed_pct',np.nan),'RetestStatus':ent.get('retest_status','—'),'RecommendedAction':ent.get('recommended_action',''),'MarketRegime':ent.get('market_regime','NEUTRAL'),'MarketRegimeCheck':ent.get('market_regime_ok',True),'EntryWhyNow':ent.get('why_now',''),'EntryMissingChecks':ent.get('missing_checks',''),'EntryLow':round(float(ent.get('zone_low',np.nan)),4) if np.isfinite(float(ent.get('zone_low',np.nan))) else np.nan,'EntryHigh':round(float(ent.get('zone_high',np.nan)),4) if np.isfinite(float(ent.get('zone_high',np.nan))) else np.nan,'BreakoutTrigger':round(float(ent.get('trigger',np.nan)),4) if np.isfinite(float(ent.get('trigger',np.nan))) else np.nan,'Invalidation':round(float(ent.get('invalidation',np.nan)),4) if np.isfinite(float(ent.get('invalidation',np.nan))) else np.nan,'Target1':round(float(ent.get('target1',np.nan)),4) if np.isfinite(float(ent.get('target1',np.nan))) else np.nan,'Target2':round(float(ent.get('target2',np.nan)),4) if np.isfinite(float(ent.get('target2',np.nan))) else np.nan,'ExplosiveScore':ex.get('score',np.nan),'ExplosiveStage':ex.get('stage','—'),'MoveScore':timing.get('move_score',np.nan),'Accel1D':timing.get('accel_1d',np.nan),'Accel2D':timing.get('accel_2d',np.nan),'Accel3D':timing.get('accel_3d',np.nan),'Rising3D':timing.get('rising_3d',False),'TimingStage':timing.get('timing_stage','—'),'HourlyConfirm':ex.get('hourly_confirmation',np.nan),'P5_5D':ex.get('p5_5d',np.nan),'P10_5D':ex.get('p10_5d',np.nan),'P15_5D':ex.get('p15_5d',np.nan),'P15_5D_N':ex.get('p15_5d_n',0),'RobustRVOL':ex.get('robust_volume_ratio',np.nan),'Retention':ex.get('post_impulse_retention',np.nan),'DryUp':ex.get('volume_dryup',np.nan),'ReExpansion':ex.get('volume_reexpansion',np.nan),'SignalLift':round(cmp.get('signal_lift_dynamic',np.nan),2) if np.isfinite(cmp.get('signal_lift_dynamic',np.nan)) else np.nan,'CalibrationConfidence':round(conf,1),'BacktestN':int(db.get('n',0) or 0),'EmpiricalHitRate':round(float(db.get('hit_rate'))*100,1) if db.get('n',0) and np.isfinite(db.get('hit_rate',np.nan)) else np.nan,'Price':round(float(display_price),4),'LivePriceFresh':live_price_fresh,'PriceSource':price_source,'PriceTimestamp':price_timestamp,'VolumeRatio':round(float(lr.get('volume_ratio',np.nan)),2) if np.isfinite(float(lr.get('volume_ratio',np.nan))) else np.nan,'LiveIntradayRVOL':round(float(hfeat.dropna(subset=['Close']).iloc[-1].get('time_adjusted_rvol',np.nan)),2) if hfeat is not None and len(hfeat) and np.isfinite(float(hfeat.dropna(subset=['Close']).iloc[-1].get('time_adjusted_rvol',np.nan))) else np.nan,'DailyRobustRVOL':round(float(daily_lr.get('robust_volume_ratio',np.nan)),2) if np.isfinite(float(daily_lr.get('robust_volume_ratio',np.nan))) else np.nan,'TimeAdjustedRVOL':round(float((hfeat.dropna(subset=['Close']).iloc[-1].get('time_adjusted_rvol',np.nan) if hfeat is not None and len(hfeat) else daily_lr.get('robust_volume_ratio',np.nan))),2) if np.isfinite(float((hfeat.dropna(subset=['Close']).iloc[-1].get('time_adjusted_rvol',np.nan) if hfeat is not None and len(hfeat) else daily_lr.get('robust_volume_ratio',np.nan)))) else np.nan,'VolumeContext':latest_live.get('volume_context','N/A'),'BullishVolumeEvidence':latest_live.get('bullish_volume_evidence',np.nan),'BearishVolumeEvidence':latest_live.get('bearish_volume_evidence',np.nan),'ExitPressure':timing.get('exit_pressure',latest_live.get('exit_pressure',np.nan)),'ExitStage':timing.get('exit_stage',latest_live.get('exit_stage','CLEAR')),'PlanValid':bool(ent.get('plan_valid',False)),'PlanReason':ent.get('plan_reason',''),'SplitAdjusted':bool(ca_report.get('split_adjusted',False)),'DataQuality':str(ca_report.get('data_quality','OK')),'RSI14':round(float(lr.get('rsi14',np.nan)),1) if np.isfinite(float(lr.get('rsi14',np.nan))) else np.nan,'ADX14':round(float(lr.get('adx14',np.nan)),1) if np.isfinite(float(lr.get('adx14',np.nan))) else np.nan,'VolumeAccel':round(float(lr.get('vol_accel',np.nan)),3) if np.isfinite(float(lr.get('vol_accel',np.nan))) else np.nan,'FreshTransitionCount':float(lr.get('fresh_transition_count',0) or 0),'InstitutionalFlowScore':latest_live.get('institutional_flow_score',np.nan),'InstitutionalFlowLabel':latest_live.get('institutional_flow_label','NEUTRAL'),'HourlyOptimizedScore':hopt_score,'HourlyOptimizedMatchPct':hopt_match,'HourlyOptimizedStatus':hopt_status,'HourlyOptimizedHorizon':hopt_horizon,'OptimizedPrefilterScore':opt_pre})
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
st.markdown(f"""<div class='hero'><span class='badge'>V{APP_VERSION} • PERSISTENT FEEDBACK • HISTORICAL REPLAY • LARGE UNIVERSE</span><div class='hero-title'>📈 AI Stock Hunter<br>V{APP_VERSION}</div><div class='hero-sub'>Adaptive Entry Intelligence • 350-stock universe • Research Radar → Live Entry → Persistent Outcome Learning</div></div>""",unsafe_allow_html=True)

DEFAULT_TICKERS="1196.HK,NVDA,NVMI,MU,AMD,AVGO,AMZN,META,GOOGL,MSFT,AAPL,TSLA,PLTR,CRWV,NBIS,GILD,ORCL,SMCI,ARM,TSM,QCOM,NFLX,UBER,COIN,HOOD,TTWO"
NASDAQ_50="NVDA,AMD,MU,AVGO,NVMI,QCOM,ARM,INTC,AMAT,MSFT,GOOGL,META,AMZN,AAPL,ORCL,ADBE,PLTR,CSCO,NFLX,COST,PEP,MDLZ,AMGN,GILD,REGN,VRTX,ISRG,MRNA,BIIB,TSLA,TTWO,EA,RBLX,ABNB,BKNG,DASH,CRWD,PANW,FTNT,DDOG,ZS,MRVL,ADI,MCHP,ON,LRCX,KLAC,CDNS,SNPS,INTU"
NASDAQ_100="NVDA,AMD,MU,AVGO,NVMI,QCOM,ARM,INTC,AMAT,MSFT,GOOGL,META,AMZN,AAPL,ORCL,ADBE,PLTR,CSCO,NFLX,COST,PEP,MDLZ,AMGN,GILD,REGN,VRTX,ISRG,MRNA,BIIB,TSLA,TTWO,EA,RBLX,ABNB,BKNG,DASH,CRWD,PANW,FTNT,DDOG,ZS,MRVL,ADI,MCHP,ON,LRCX,KLAC,CDNS,SNPS,INTU,GOOG,TXN,ADP,MELI,PYPL,MAR,ORLY,CEG,CTAS,NXPI,PCAR,AEP,MNST,KDP,ROST,PAYX,FAST,ODFL,CSX,EXC,VRSK,BKR,XEL,WBD,GEHC,APP,MSTR,HOOD,COIN,SMCI,CRWV,NBIS,MDB,NET,TTD,SHOP,PDD,JD,BIDU,NTES,BILI,TCOM,TME,FUTU,LI,RIVN,LCID,SOFI,AFRM,UPST"
NASDAQ_200="NVDA,AMD,MU,AVGO,NVMI,QCOM,ARM,INTC,AMAT,MSFT,GOOGL,META,AMZN,AAPL,ORCL,ADBE,PLTR,CSCO,NFLX,COST,PEP,MDLZ,AMGN,GILD,REGN,VRTX,ISRG,MRNA,BIIB,TSLA,TTWO,EA,RBLX,ABNB,BKNG,DASH,CRWD,PANW,FTNT,DDOG,ZS,MRVL,ADI,MCHP,ON,LRCX,KLAC,CDNS,SNPS,INTU,GOOG,TXN,ADP,MELI,PYPL,MAR,ORLY,CEG,CTAS,NXPI,PCAR,AEP,MNST,KDP,ROST,PAYX,FAST,ODFL,CSX,EXC,VRSK,BKR,XEL,WBD,GEHC,APP,MSTR,HOOD,COIN,SMCI,CRWV,NBIS,MDB,NET,TTD,SHOP,PDD,JD,BIDU,NTES,BILI,TCOM,TME,FUTU,LI,RIVN,LCID,SOFI,AFRM,UPST,TROW,FITB,HBAN,NDAQ,IBKR,LULU,ULTA,CELH,DUOL,CART,ETSY,WING,FOXA,FOX,CHTR,SIRI,WMG,WDAY,DOCU,ZM,OKTA,GTLB,CFLT,DBX,BILL,PCOR,MNDY,FIVN,NICE,CYBR,CHKP,GEN,AKAM,FFIV,JKHY,MPWR,LSCC,SWKS,QRVO,ALGM,ACLS,SITM,CRDO,MTSI,CAMT,TSEM,ASML,AMKR,COHU,FORM,ICHR,TER,SYNA,SMTC,POWI,RMBS,ALNY,INCY,BMRN,SRPT,NBIX,CRSP,NTLA,BEAM,EDIT,RXRX,EXAS,ILMN,DXCM,PODD,HOLX,MASI,INSP,TECH,MEDP,RARE,IONS,CYTK,PCVX,RVMD,ACLX,TMDX,VCEL,GH,NTRA,TEM,AXON,CPRT,MANH,PCTY,FSLR,ENPH,RUN,CSIQ,ARRY,NXT,ASTS,RKLB,LUNR,RGTI"
BROAD_200=NASDAQ_200  # compatibility alias; V6.2.9 expanded research/scan universe
US_51=NASDAQ_50+",ITT"
US_201=NASDAQ_200+",ITT"
HK_50="1196.HK,1570.HK,0700.HK,9988.HK,3690.HK,9618.HK,1810.HK,9999.HK,1024.HK,9888.HK,0005.HK,0939.HK,1398.HK,3988.HK,1299.HK,2318.HK,0388.HK,0883.HK,0857.HK,0386.HK,0941.HK,0762.HK,0728.HK,0002.HK,0003.HK,0006.HK,0011.HK,0016.HK,0012.HK,0823.HK,1109.HK,1997.HK,2020.HK,2331.HK,2313.HK,1928.HK,0291.HK,9633.HK,1211.HK,0175.HK,9866.HK,2015.HK,6690.HK,2269.HK,6160.HK,1177.HK,3750.HK,2899.HK,2600.HK,0669.HK"
HK_100="1196.HK,1570.HK,0700.HK,9988.HK,3690.HK,9618.HK,1810.HK,9999.HK,1024.HK,9888.HK,0005.HK,0939.HK,1398.HK,3988.HK,1299.HK,2318.HK,0388.HK,0883.HK,0857.HK,0386.HK,0941.HK,0762.HK,0728.HK,0002.HK,0003.HK,0006.HK,0011.HK,0016.HK,0012.HK,0823.HK,1109.HK,1997.HK,2020.HK,2331.HK,2313.HK,1928.HK,0291.HK,9633.HK,1211.HK,0175.HK,9866.HK,2015.HK,6690.HK,2269.HK,6160.HK,1177.HK,3750.HK,2899.HK,2600.HK,0669.HK,0017.HK,0027.HK,0066.HK,0083.HK,0101.HK,0151.HK,0267.HK,0288.HK,0322.HK,0384.HK,0688.HK,0763.HK,0968.HK,1038.HK,1044.HK,1066.HK,1093.HK,1113.HK,1209.HK,1288.HK,1336.HK,1378.HK,1658.HK,1876.HK,1919.HK,1929.HK,2007.HK,2202.HK,2238.HK,2382.HK,2388.HK,2628.HK,3328.HK,3968.HK,6098.HK,6618.HK,6862.HK,9616.HK,9626.HK,9698.HK,0981.HK,0992.HK,1801.HK,1800.HK,1880.HK,2688.HK,2689.HK,3311.HK,3888.HK,9992.HK"
TASE_50="TEVA.TA,NICE.TA,LUMI.TA,POLI.TA,MZTF.TA,FIBI.TA,DSCT.TA,ESLT.TA,ICL.TA,CAMT.TA,NVMI.TA,TSEM.TA,ENLT.TA,OPCE.TA,DORL.TA,ORL.TA,DELG.TA,FTAL.TA,FOX.TA,RMLI.TA,SHUF.TA,STRA.TA,ILCO.TA,PTNR.TA,CEL.TA,BEZQ.TA,AZRG.TA,MLSR.TA,AMOT.TA,GCT.TA,ALHE.TA,MGDL.TA,CLIS.TA,PHOE.TA,HAREL.TA,MMHD.TA,ONE.TA,MTRX.TA,HIPR.TA,AURA.TA,DLEKG.TA,NWMD.TA,ISRA.TA,ELAL.TA,FORTY.TA,SPNS.TA,AQAR.TA,ARGO.TA,KRNT.TA,PERI.TA"
VALIDATION_50=NASDAQ_50
VALIDATION_51=US_51
VALIDATION_151=US_51+","+HK_50+","+TASE_50
VALIDATION_350=NASDAQ_200+","+HK_100+","+TASE_50
VALIDATION_351=US_201+","+HK_100+","+TASE_50
VALIDATION_150=VALIDATION_151  # compatibility alias for older helpers
DISCOVERY_UNIVERSE=','.join(dict.fromkeys(VALIDATION_351.split(',')))
DISCOVERY_COUNT=len([x for x in DISCOVERY_UNIVERSE.split(',') if x])
MARKET_MAP={**{t:'NASDAQ' for t in NASDAQ_200.split(',')},'ITT':'NYSE',**{t:'HONG KONG' for t in HK_100.split(',')},**{t:'TEL AVIV' for t in TASE_50.split(',')}}
SECTOR_MAP={}
for t in NASDAQ_200.split(','): SECTOR_MAP[t]='Diversified NASDAQ / US Growth'
SECTOR_MAP['ITT']='Industrials'
for t in HK_100.split(','): SECTOR_MAP[t]='Diversified HK'
for t in TASE_50.split(','): SECTOR_MAP[t]='Diversified TASE'
# Explicit anchors/case-study names are always included in the large universes.
SECTOR_MAP.update({'1196.HK':'Conglomerate / Digital','1570.HK':'Industrial / Property','0700.HK':'Technology','0005.HK':'Banking','0883.HK':'Energy','1211.HK':'EV','2269.HK':'Healthcare','0823.HK':'REIT','3750.HK':'Battery','2899.HK':'Materials'})

def _market_for_ticker_v612(ticker):
    t=str(ticker).upper()
    if t in MARKET_MAP:return MARKET_MAP[t]
    if t.endswith('.HK'):return 'HONG KONG'
    if t.endswith('.TA'):return 'TEL AVIV'
    return 'US'
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


# Exchange-session display metadata. Keep phase strings stable because they are
# used throughout Scanner/Analyze decision logic.
_MARKET_CLOSURES_V612 = {
    'NASDAQ': {
        '2026-01-01': "New Year's Day", '2026-01-19': 'MLK Day',
        '2026-02-16': "Presidents Day", '2026-04-03': 'Good Friday',
        '2026-05-25': 'Memorial Day', '2026-06-19': 'Juneteenth',
        '2026-07-03': 'Independence Day observed', '2026-09-07': 'Labor Day',
        '2026-11-26': 'Thanksgiving', '2026-12-25': 'Christmas Day',
    },
    'NYSE': {
        '2026-01-01': "New Year's Day", '2026-01-19': 'MLK Day',
        '2026-02-16': "Presidents Day", '2026-04-03': 'Good Friday',
        '2026-05-25': 'Memorial Day', '2026-06-19': 'Juneteenth',
        '2026-07-03': 'Independence Day observed', '2026-09-07': 'Labor Day',
        '2026-11-26': 'Thanksgiving', '2026-12-25': 'Christmas Day',
    },
    'US': {
        '2026-01-01': "New Year's Day", '2026-01-19': 'MLK Day',
        '2026-02-16': "Presidents Day", '2026-04-03': 'Good Friday',
        '2026-05-25': 'Memorial Day', '2026-06-19': 'Juneteenth',
        '2026-07-03': 'Independence Day observed', '2026-09-07': 'Labor Day',
        '2026-11-26': 'Thanksgiving', '2026-12-25': 'Christmas Day',
    },
    'HONG KONG': {
        '2026-01-01': 'New Year holiday', '2026-02-17': 'Lunar New Year',
        '2026-02-18': 'Lunar New Year', '2026-02-19': 'Lunar New Year',
        '2026-04-03': 'Good Friday', '2026-04-06': 'Ching Ming holiday',
        '2026-04-07': 'Easter holiday', '2026-05-01': 'Labour Day',
        '2026-05-25': 'Buddha Birthday holiday', '2026-06-19': 'Tuen Ng Festival',
        '2026-07-01': 'HKSAR Establishment Day', '2026-10-01': 'National Day',
        '2026-10-19': 'Chung Yeung holiday', '2026-12-25': 'Christmas Day',
    },
    # Current known TASE 2026 special closures. Explicit dates avoid guessing
    # Jewish-holiday dates; regular Friday shortening is handled separately below.
    'TEL AVIV': {
        '2026-09-18': 'Yom Kippur schedule',
        '2026-09-21': 'Yom Kippur',
        '2026-09-25': 'Sukkot',
        '2026-10-02': 'Simchat Torah',
    },
}

_MARKET_EARLY_CLOSES_V612 = {
    # U.S. cash equities close at 13:00 ET on these 2026 dates.
    'NASDAQ': {'2026-11-27': time(13,0), '2026-12-24': time(13,0)},
    'NYSE': {'2026-11-27': time(13,0), '2026-12-24': time(13,0)},
    'US': {'2026-11-27': time(13,0), '2026-12-24': time(13,0)},
    # HKEX half-day securities sessions around major holiday eves.
    'HONG KONG': {'2026-02-16': time(12,10), '2026-12-24': time(12,10), '2026-12-31': time(12,10)},
}

def _market_status_detail_v612(market):
    cfg={
        'NASDAQ':('America/New_York',time(4,0),time(9,30),time(16,0),time(20,0)),
        'NYSE':('America/New_York',time(4,0),time(9,30),time(16,0),time(20,0)),
        'US':('America/New_York',time(4,0),time(9,30),time(16,0),time(20,0)),
        'HONG KONG':('Asia/Hong_Kong',time(9,0),time(9,30),time(16,10),None),
        # TASE moved to Monday-Friday in 2026. Friday is a shortened session.
        'TEL AVIV':('Asia/Jerusalem',time(9,25),time(9,59),time(17,30),None),
    }
    if market not in cfg:
        return {'phase':'UNKNOWN','reason':'','local_time':'—','market':market}
    tz,pre,op,cl,after=cfg[market]
    now=datetime.now(ZoneInfo(tz)); t=now.time().replace(tzinfo=None)
    dkey=now.date().isoformat(); reason=_MARKET_CLOSURES_V612.get(market,{}).get(dkey,'')
    early_close=_MARKET_EARLY_CLOSES_V612.get(market,{}).get(dkey)
    if reason:
        phase='CLOSED'
    elif market=='TEL AVIV':
        # Since 2026: Saturday/Sunday closed; Friday closes at 13:50 local time.
        if now.weekday() in (5,6):
            phase='CLOSED'
        else:
            close_today=time(13,50) if now.weekday()==4 else cl
            if pre<=t<op:
                phase='PRE-OPEN'
            elif op<=t<close_today:
                phase='OPEN'
            else:
                phase='CLOSED'
    else:
        if now.weekday()>=5:
            phase='CLOSED'
        else:
            close_today=early_close or cl
            if pre<=t<op:
                phase='PRE-MARKET' if market in ('NASDAQ','NYSE','US') else 'PRE-OPEN'
            elif op<=t<close_today:
                phase='OPEN'
            elif after is not None and close_today<=t<after:
                phase='AFTER-MARKET'
            else:
                phase='CLOSED'
    return {
        'phase':phase,
        'reason':reason,
        'local_time':now.strftime('%H:%M'),
        'local_date':now.strftime('%Y-%m-%d'),
        'market':market,
    }

def _feedback_market_key_v612(market, ticker=''):
    """Normalize stored market labels for feedback calendar/session logic."""
    m=str(market or '').upper().strip()
    if m in ('NASDAQ','NYSE','US','HONG KONG','TEL AVIV'):
        return m
    return _market_for_ticker_v612(ticker)

def _market_timezone_v612(market):
    m=_feedback_market_key_v612(market)
    return {
        'NASDAQ':'America/New_York','NYSE':'America/New_York','US':'America/New_York',
        'HONG KONG':'Asia/Hong_Kong','TEL AVIV':'Asia/Jerusalem',
    }.get(m,'UTC')

def _market_close_for_date_v612(market, d):
    """Regular-session close used only for feedback maturity timing."""
    m=_feedback_market_key_v612(market)
    early=_MARKET_EARLY_CLOSES_V612.get(m,{}).get(d.isoformat())
    if early is not None:return early
    if m=='TEL AVIV':
        return time(13,50) if d.weekday()==4 else time(17,30)
    if m=='HONG KONG':return time(16,10)
    return time(16,0)

def _is_trading_date_v612(market, d):
    """Calendar estimate for UI scheduling only. Actual outcome maturity is bar-count based."""
    m=_feedback_market_key_v612(market)
    if d.weekday()>=5:return False
    return d.isoformat() not in _MARKET_CLOSURES_V612.get(m,{})

def _nth_future_trading_date_v612(market, after_date, n):
    n=max(1,int(n)); cur=after_date; seen=0
    for _ in range(40):
        cur=cur+timedelta(days=1)
        if _is_trading_date_v612(market,cur):
            seen+=1
            if seen>=n:return cur
    return cur

def _snapshot_market_date_v612(ts_utc, market, ticker=''):
    """Convert the UTC snapshot timestamp to the exchange's local trade date."""
    try:
        z=pd.to_datetime(ts_utc,utc=True)
        return z.tz_convert(ZoneInfo(_market_timezone_v612(_feedback_market_key_v612(market,ticker)))).date()
    except Exception:
        try:return pd.Timestamp(ts_utc).date()
        except Exception:return datetime.utcnow().date()

def _feedback_due_at_v612(ts_utc, market, horizon, ticker=''):
    """Approximate UTC time when H future regular sessions should be complete.
    Actual evaluation still requires H provider daily bars, so holidays/provider gaps cannot
    cause an outcome to mature early.
    """
    m=_feedback_market_key_v612(market,ticker); tz=ZoneInfo(_market_timezone_v612(m))
    start=_snapshot_market_date_v612(ts_utc,m,ticker)
    d=_nth_future_trading_date_v612(m,start,int(horizon))
    close_t=_market_close_for_date_v612(m,d)
    local_dt=datetime.combine(d,close_t).replace(tzinfo=tz)+timedelta(minutes=30)
    return pd.Timestamp(local_dt.astimezone(timezone.utc))

def _completed_future_daily_bars_v612(frame, scan_date, market, horizon=None):
    """Return completed provider daily bars strictly after the snapshot's LOCAL market date.
    This is the source of truth for 1D/2D/3D/5D maturity: weekends/holidays never count.
    Current still-open sessions are excluded even if the provider exposes a partial daily bar.
    """
    if frame is None or frame.empty:return frame
    z=frame.copy(); idx_dates=np.array(pd.to_datetime(z.index).date)
    z=z.loc[idx_dates>scan_date]
    if z.empty:return z
    m=_feedback_market_key_v612(market); now_utc=datetime.now(timezone.utc); keep=[]
    for idx in z.index:
        d=pd.Timestamp(idx).date()
        if not _is_trading_date_v612(m,d):
            keep.append(False);continue
        tz=ZoneInfo(_market_timezone_v612(m)); close_t=_market_close_for_date_v612(m,d)
        complete_at=datetime.combine(d,close_t).replace(tzinfo=tz)+timedelta(minutes=20)
        keep.append(now_utc>=complete_at.astimezone(timezone.utc))
    z=z.loc[np.array(keep,dtype=bool)]
    return z.head(int(horizon)) if horizon is not None else z

def _market_phase(market):
    return _market_status_detail_v612(market).get('phase','UNKNOWN')

def _market_phase_icon_v612(phase):
    return {
        'OPEN':'🟢','PRE-MARKET':'🟡','PRE-OPEN':'🟡','AFTER-MARKET':'🟠',
        'CLOSED':'⚫','UNKNOWN':'⚪'
    }.get(str(phase),'⚪')

def _render_market_status_badges_v612():
    markets=[('US','NASDAQ'),('Hong Kong','HONG KONG'),('Tel Aviv','TEL AVIV')]
    cols=st.columns(3)
    for col,(label,key) in zip(cols,markets):
        d=_market_status_detail_v612(key); phase=d.get('phase','UNKNOWN'); icon=_market_phase_icon_v612(phase)
        reason=f"<div style='font-size:.72rem;color:#ffcf66;margin-top:3px'>{d.get('reason')}</div>" if d.get('reason') else ''
        col.markdown(
            f"<div style='border:1px solid #2a3851;border-radius:14px;padding:10px 12px;background:#111722'>"
            f"<div style='font-size:.78rem;color:#8f9bad'>{label}</div>"
            f"<div style='font-weight:850;font-size:1.02rem'>{icon} {phase}</div>"
            f"<div style='font-size:.72rem;color:#8f9bad'>Local {d.get('local_time','—')}</div>{reason}</div>",
            unsafe_allow_html=True,
        )



_MARKET_REGIME_CACHE_V610={}
def _market_regime_v610(ticker):
    """Lightweight broad-market gate, cached per benchmark for the process."""
    t=str(ticker).upper()
    bench='^HSI' if t.endswith('.HK') else ('^TA125.TA' if t.endswith('.TA') else 'SPY')
    if not bench:return 'NEUTRAL'
    cached=_MARKET_REGIME_CACHE_V610.get(bench)
    if cached and time_module.time()-cached[0] < 1800:return cached[1]
    regime='NEUTRAL'
    try:
        d=fetch_ohlcv(bench,'6mo','1d')
        if d is not None and len(d)>=55:
            f=compute_features(d);r=f.dropna(subset=['Close']).iloc[-1]
            c=float(r.get('Close',np.nan));e20=float(r.get('ema20',np.nan));e50=float(r.get('ema50',np.nan));m5=float(r.get('mom5',np.nan))
            if np.isfinite(c) and np.isfinite(e20) and np.isfinite(e50):
                if c<e20 and e20<e50 and np.isfinite(m5) and m5<-0.02:regime='RISK-OFF'
                elif c>=e20 and e20>=e50:regime='SUPPORTIVE'
    except Exception:pass
    _MARKET_REGIME_CACHE_V610[bench]=(time_module.time(),regime)
    return regime


def _trade_stage_label(stage):
    stg=str(stage)
    return 'CONFIRMED ENTRY' if stg in ('TRIGGER','TRADE TRIGGER','LIVE TRIGGERED') else stg


def _movement_stage_label(stage):
    return 'MOVEMENT TRIGGER' if str(stage)=='TRIGGER' else str(stage)


def _why_not_trade_trigger(r):
    missing=str(r.get('EntryMissingChecks','') or '').strip()
    if missing and missing.lower()!='none':return missing
    if str(r.get('EntryTriggerState',''))=='EXTENDED — DO NOT CHASE':return 'Chase/Extension Guard blocked entry — wait for retest'
    if str(r.get('EntryTriggerState',''))=='TOO LATE / CHASE':return 'No-Chase gate failed — price already extended'
    if str(r.get('EntryTriggerState',''))=='INVALIDATED':return 'Trade plan invalidated / exit-risk gate'
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


def _evidence_gate_v615(row):
    """Classify out-of-sample evidence without overreacting to tiny samples.

    UNPROVEN is informational only. A hard guard is used only when there are
    enough signals to make persistently poor lift meaningful.
    """
    try: n=int(float(row.get('BacktestN',0) or 0))
    except Exception: n=0
    try: lift=float(row.get('SignalLift',np.nan))
    except Exception: lift=np.nan
    try: rel=float(row.get('Reliability',0) or 0)
    except Exception: rel=0.0
    if n < 8 or not np.isfinite(lift):
        return 'UNPROVEN', True
    if n >= 12 and lift < 0.75:
        return 'WEAK — GUARD', False
    if lift < 0.90:
        return 'WEAK', True
    if n >= 20 and lift >= 1.20 and rel >= 50:
        return 'STRONG', True
    if n >= 12 and lift >= 1.05:
        return 'SUPPORTIVE', True
    return 'MIXED', True


def add_market_and_opportunity(df):
    z=df.copy()
    z['Market']=z['Ticker'].map(lambda x:_market_for_ticker_v612(x))
    z['Sector']=z['Ticker'].map(SECTOR_MAP).fillna('Discovery / Other')
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
    _eg=z.apply(_evidence_gate_v615,axis=1,result_type='expand'); _eg.columns=['EvidenceState','EvidenceGuardOK']; z[['EvidenceState','EvidenceGuardOK']]=_eg
    if 'EntryTriggerState' in z.columns:
        z['TradeStage']=z['EntryTriggerState'].fillna('WAIT').astype(str)
    else:
        z['TradeStage']=z['OpportunityStage'].map(_trade_stage_label)
    z['MovementStage']=z.get('TimingStage',pd.Series(['—']*len(z),index=z.index)).map(_movement_stage_label)
    z['WhyNotTradeTrigger']=z.apply(_why_not_trade_trigger,axis=1)
    z['MarketPhase']=z['Market'].map(_market_phase)
    z['PreviousSessionTrigger']=z['TradeStage'].eq('CONFIRMED ENTRY')

    z['PMPrice']=np.nan; z['PMChangePct']=np.nan; z['PMVolume']=np.nan; z['PMVolumeStrength']=np.nan; z['PMData']='N/A'; z['PMConfirmation']='N/A'
    nas_pm=z[(z['Market'].isin(['NASDAQ','NYSE','US'])) & (z['MarketPhase'].eq('PRE-MARKET'))]['Ticker'].tolist()
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

    z['AHPrice']=np.nan; z['RegularClose']=np.nan; z['AHChangePct']=np.nan; z['AHVolume']=np.nan; z['AHVolumeStrength']=np.nan; z['AHData']='N/A'; z['AHLastTime']='—'; z['AHAgeMinutes']=np.nan; z['AHFresh']=False; z['AHConfirmation']='N/A'
    nas_ah=z[(z['Market'].isin(['NASDAQ','NYSE','US'])) & (z['MarketPhase'].eq('AFTER-MARKET'))]['Ticker'].tolist()
    ah=fetch_aftermarket_snapshots(nas_ah) if nas_ah else {}
    for i,r in z.iterrows():
        snap=ah.get(str(r['Ticker']).upper())
        if snap:
            for k in ['AHPrice','RegularClose','AHChangePct','AHVolume','AHVolumeStrength','AHAgeMinutes']: z.at[i,k]=snap.get(k,np.nan)
            z.at[i,'AHData']=snap.get('AHData','N/A'); z.at[i,'AHLastTime']=snap.get('AHLastTime','—'); z.at[i,'AHFresh']=bool(snap.get('AHFresh',False))
            ch=float(snap.get('AHChangePct',np.nan)); vr=float(snap.get('AHVolumeStrength',np.nan))
            if np.isfinite(ch):
                if ch>=0.6 and np.isfinite(vr) and vr>=0.8: c='CONFIRMED'
                elif ch>=0.6 and not np.isfinite(vr): c='PRICE CONFIRMED • VOLUME UNAVAILABLE'
                elif ch<=-1.5 and np.isfinite(vr) and vr>=1.0: c='STRONGLY WEAKENED'
                elif ch<=-0.5: c='WEAKENED'
                else: c='NEUTRAL'
                z.at[i,'AHConfirmation']=c

    z['LiveStage']=z['TradeStage']
    _live_price_ok=z['LivePriceFresh'].fillna(True).astype(bool) if 'LivePriceFresh' in z else pd.Series(True,index=z.index)
    _live_data_ok=z['DataQuality'].eq('OK') if 'DataQuality' in z else pd.Series(True,index=z.index)
    _live_plan_ok=z['PlanValid'].astype(bool) if 'PlanValid' in z else pd.Series(True,index=z.index)
    live_ok=z['TradeStage'].eq('CONFIRMED ENTRY') & z['MarketPhase'].eq('OPEN') & (pd.to_numeric(z['ExitPressure'],errors='coerce').fillna(0)<55) & _live_price_ok & _live_data_ok & _live_plan_ok
    z.loc[live_ok,'LiveStage']='CONFIRMED ENTRY — LIVE'
    z.loc[z['PreviousSessionTrigger'] & z['MarketPhase'].eq('OPEN') & (~_live_price_ok),'LiveStage']='LIVE DATA STALE'
    z.loc[z['PreviousSessionTrigger'] & z['MarketPhase'].eq('OPEN') & (~_live_data_ok),'LiveStage']='DATA CHECK — TRIGGER BLOCKED'
    pm_trigger=z['PreviousSessionTrigger'] & z['MarketPhase'].eq('PRE-MARKET')
    z.loc[pm_trigger,'LiveStage']='PRE-MARKET SETUP'; z.loc[pm_trigger & z['PMConfirmation'].eq('CONFIRMED'),'LiveStage']='PRE-MARKET CONFIRMED'; z.loc[pm_trigger & z['PMConfirmation'].isin(['WEAKENED','STRONGLY WEAKENED']),'LiveStage']='PRE-MARKET WEAKENED'
    ah_trigger=z['PreviousSessionTrigger'] & z['MarketPhase'].eq('AFTER-MARKET')
    z.loc[ah_trigger,'LiveStage']='AFTER-MARKET SETUP'; z.loc[ah_trigger & z['AHConfirmation'].eq('CONFIRMED'),'LiveStage']='AFTER-MARKET CONFIRMED'; z.loc[ah_trigger & z['AHConfirmation'].isin(['WEAKENED','STRONGLY WEAKENED']),'LiveStage']='AFTER-MARKET WEAKENED'
    z.loc[z['PreviousSessionTrigger'] & z['MarketPhase'].eq('CLOSED'),'LiveStage']='PREVIOUS SESSION CONFIRMED ENTRY'
    # Keep the underlying regular-session stage visible, but expose a separate session-aware state.
    if 'RegularSessionEntryState' not in z.columns:z['RegularSessionEntryState']=z['TradeStage']
    else:z['RegularSessionEntryState']=z['RegularSessionEntryState'].fillna(z['TradeStage'])
    if 'SessionEntryState' not in z.columns:z['SessionEntryState']=z['TradeStage']
    else:z['SessionEntryState']=z['SessionEntryState'].fillna(z['TradeStage'])
    _ahmask=z['MarketPhase'].eq('AFTER-MARKET')
    z.loc[_ahmask & z['TradeStage'].eq('CONFIRMED ENTRY'),'SessionEntryState']='AFTER-MARKET SETUP — RECONFIRM NEXT SESSION'
    z.loc[_ahmask & z['TradeStage'].eq('EXTENDED — DO NOT CHASE'),'SessionEntryState']='EXTENDED — DO NOT CHASE'
    z.loc[_ahmask & (~z['TradeStage'].isin(['CONFIRMED ENTRY','EXTENDED — DO NOT CHASE'])),'SessionEntryState']='AFTER-MARKET REVIEW — '+z.loc[_ahmask & (~z['TradeStage'].isin(['CONFIRMED ENTRY','EXTENDED — DO NOT CHASE'])),'TradeStage'].astype(str)
    _tot=pd.to_numeric(z.get('SessionMovePct',np.nan),errors='coerce'); _ahm=pd.to_numeric(z.get('AHChangePct',np.nan),errors='coerce')
    if 'TotalMoveIncludingAHPct' not in z.columns:z['TotalMoveIncludingAHPct']=np.where(_ahmask,_tot,np.nan)
    if 'AfterHoursMovePct' not in z.columns:z['AfterHoursMovePct']=np.where(_ahmask,_ahm,np.nan)
    if 'AfterHoursPrice' not in z.columns:z['AfterHoursPrice']=np.where(_ahmask,pd.to_numeric(z.get('AHPrice',np.nan),errors='coerce'),np.nan)
    if 'AfterHoursVolumeStrength' not in z.columns:z['AfterHoursVolumeStrength']=np.where(_ahmask,pd.to_numeric(z.get('AHVolumeStrength',np.nan),errors='coerce'),np.nan)
    if 'RegularSessionMovePct' not in z.columns:
        _den=1.0+_ahm/100.0
        z['RegularSessionMovePct']=np.where(_ahmask & _tot.notna() & _ahm.notna() & (_den>0),100.0*((1.0+_tot/100.0)/_den-1.0),np.where(~_ahmask,_tot,np.nan))

    def session_status(r):
        phase=str(r.get('MarketPhase','UNKNOWN')); stage=str(r.get('TradeStage','WAIT')); live=str(r.get('LiveStage',stage))
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
        stg=str(r.get('TradeStage','WAIT')); pred=float(r.get('Prediction',0) or 0); xp=float(r.get('ExitPressure',0) or 0)
        if xp>=72:return 'EXIT TRIGGER'
        if xp>=55:return 'EXIT ARMED'
        if stg=='CONFIRMED ENTRY':return 'CONFIRMED ENTRY'
        if stg=='EXTENDED — DO NOT CHASE':return 'EXTENDED — DO NOT CHASE'
        if stg=='TOO LATE / CHASE':return 'TOO LATE / CHASE'
        if stg=='INVALIDATED':return 'INVALIDATED'
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
    z['_RankScore']=pd.to_numeric(z['TopScore'],errors='coerce').fillna(0)
    z['MarketRank']=z.groupby('Market')['_RankScore'].rank(method='first',ascending=False).astype(int)
    z['SectorRank']=z.groupby(['Market','Sector'])['_RankScore'].rank(method='first',ascending=False).astype(int)
    priority={'CONFIRMED ENTRY':7,'ARMED':6,'WATCH':5,'WAIT':4,'EXTENDED — DO NOT CHASE':3,'TOO LATE / CHASE':2,'INVALIDATED':1}
    z['_StagePriority']=z['TradeStage'].map(priority).fillna(1)
    z['_ExitPenalty']=(pd.to_numeric(z['ExitPressure'],errors='coerce').fillna(0)>=55).astype(int)
    order=z.sort_values(['_ExitPenalty','_StagePriority','TopScore'],ascending=[True,False,False]).index.tolist()
    pr={idx:i+1 for i,idx in enumerate(order)}; z['TradePriorityRank']=[pr[i] for i in z.index]
    _plan_ok=z['PlanValid'].astype(bool) if 'PlanValid' in z else True
    _data_ok=z['DataQuality'].eq('OK') if 'DataQuality' in z else True
    _price_fresh=z['LivePriceFresh'].fillna(True).astype(bool) if 'LivePriceFresh' in z else True
    # V6.1.4 AH-aware: after-hours confirmation is context only, not ActionableNow.
    # Hourly/15m Entry indicators are regular-session features, so an AH print must be
    # reconfirmed in the next regular session before becoming a trade-grade live entry.
    _evidence_ok=z['EvidenceGuardOK'].fillna(True).astype(bool) if 'EvidenceGuardOK' in z else True
    z['ActionableNow']=(((z['MarketPhase'].eq('OPEN')) & z['LiveStage'].eq('CONFIRMED ENTRY — LIVE')) | ((z['MarketPhase'].eq('PRE-MARKET')) & z['PMConfirmation'].eq('CONFIRMED') & z['TradeStage'].eq('CONFIRMED ENTRY'))) & (pd.to_numeric(z['ExitPressure'],errors='coerce').fillna(0)<55) & _plan_ok & _data_ok & _price_fresh & _evidence_ok
    return z.drop(columns=['_StagePriority','_ExitPenalty','_RankScore'],errors='ignore')


def safe(x,d=2):
    try:return "—" if pd.isna(x) else f"{float(x):.{d}f}"
    except:return "—"
def cls(s):
    s=str(s).upper()
    # Order matters: previous-session/closed labels must never turn green just because they contain “TRIGGER”.
    if any(x in s for x in ["WEAKENED","AVOID","COLD","EXIT TRIGGER","EXIT ARMED","DISTRIBUTION","DATA CHECK"]): return "bad"
    if any(x in s for x in ["CLOSED","PREVIOUS SESSION","PRE-OPEN","WATCH","WAIT","ARMED","SETUP","NEUTRAL","MOVEMENT TRIGGER"]): return "warn"
    if any(x in s for x in ["PRE-MARKET CONFIRMED","AFTER-MARKET CONFIRMED","CONFIRMED ENTRY","ENTER"]): return "good"
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
    hit=np.full(n,np.nan); ret=np.full(n,np.nan); mae=np.full(n,np.nan); mfe=np.full(n,np.nan); days=np.full(n,np.nan)
    for i in range(n-int(horizon)):
        p=closes[i]; fh=highs[i+1:i+1+int(horizon)]; fl=lows[i+1:i+1+int(horizon)]
        if not np.isfinite(p) or p<=0 or len(fh)==0 or len(fl)==0:continue
        target=p*(1+float(target_pct)); reached=np.where(fh>=target)[0]
        hit[i]=1.0 if len(reached) else 0.0
        days[i]=float(reached[0]+1) if len(reached) else np.nan
        ret[i]=closes[i+int(horizon)]/p-1.0
        mfe[i]=np.nanmax(fh)/p-1.0
        mae[i]=np.nanmin(fl)/p-1.0
    return hit,ret,mfe,mae,days


def _entry_bucket(score):
    if score>=80:return '80–100'
    if score>=70:return '70–79'
    if score>=60:return '60–69'
    return '<60'



def _entry_research_gate_v610(r,quant_score,entry_score):
    return _entry_research_features_v612(r,quant_score,entry_score)



SHADOW_MODEL_PATH_V612=Path(__file__).resolve().with_name('entry_shadow_model_v612.json')
MODEL_REGISTRY_PATH_V613=Path(__file__).resolve().with_name('entry_model_registry_v613.json')


def _load_shadow_model_v612():
    """Legacy latest-model loader kept for backward compatibility."""
    try:
        if SHADOW_MODEL_PATH_V612.exists():
            obj=json.loads(SHADOW_MODEL_PATH_V612.read_text())
            return obj if isinstance(obj,dict) else None
    except Exception:pass
    return None


def _save_shadow_model_v612(model):
    try:
        if model and model.get('scopes'):SHADOW_MODEL_PATH_V612.write_text(json.dumps(model,indent=2,sort_keys=True))
    except Exception:pass


def _load_model_registry_v613():
    try:
        if MODEL_REGISTRY_PATH_V613.exists():
            obj=json.loads(MODEL_REGISTRY_PATH_V613.read_text())
            if isinstance(obj,dict) and isinstance(obj.get('models'),list):return obj
    except Exception:pass
    return {'version':APP_VERSION,'updated':None,'models':[]}


def _save_model_registry_v613(reg):
    try:
        if isinstance(reg,dict):
            reg['version']=APP_VERSION;reg['updated']=datetime.now().isoformat(timespec='seconds')
            MODEL_REGISTRY_PATH_V613.write_text(json.dumps(reg,indent=2,sort_keys=True))
    except Exception:pass


def _model_id_v613(model,cfg):
    created=str(model.get('created') or datetime.now().isoformat(timespec='seconds')).replace(':','').replace('-','')
    return f"{created}_{str(cfg.get('market','ALL')).replace(' ','_')}_{int(cfg.get('horizon',3))}D_{float(cfg.get('target',3)):g}P"


def _register_model_v613(model,cfg,hourly_model=None):
    """Append one optimizer run to the persistent registry; never overwrite older evidence."""
    if not isinstance(model,dict) or not model.get('scopes'):return _load_model_registry_v613()
    reg=_load_model_registry_v613(); mid=_model_id_v613(model,cfg)
    rec={
        'model_id':mid,'version':APP_VERSION,'created':model.get('created',datetime.now().isoformat(timespec='seconds')),
        'source_universe':cfg.get('market','CUSTOM'),'history':cfg.get('history','2y'),
        'horizon_days':int(cfg.get('horizon',3)),'target_pct':float(cfg.get('target',3)),
        'hourly_target_pct':float(cfg.get('hourly_target',3)),'hourly_bars':[int(x) for x in cfg.get('hourly_bars',(1,2,4))],
        'scopes':model.get('scopes',{}),'hourly_scopes':(hourly_model or {}).get('scopes',{}) if isinstance(hourly_model,dict) else {},
    }
    models=[x for x in reg.get('models',[]) if x.get('model_id')!=mid];models.append(rec)
    # Keep a bounded registry while preserving enough history to compare repeated optimizations.
    models=sorted(models,key=lambda x:str(x.get('created','')))[-80:]
    reg['models']=models;_save_model_registry_v613(reg)
    # Keep legacy latest file too so an older deployment can still read something.
    legacy=dict(model);legacy.update({'source_universe':rec['source_universe'],'history':rec['history'],'horizon_days':rec['horizon_days'],'target_pct':rec['target_pct'],'model_id':mid,'hourly_scopes':rec['hourly_scopes']})
    _save_shadow_model_v612(legacy)
    return reg



def _import_optimizer_workbook_v613(file_obj):
    """Import a V6.1.2/V6.1.3/V6.1.4 Optimizer workbook into the registry.

    This lets existing expensive optimizer runs be reused after upgrading instead of
    forcing the user to rerun the entire 151-stock study just to populate the registry.
    """
    try:
        xls=pd.ExcelFile(file_obj)
        about=pd.read_excel(xls,'About') if 'About' in xls.sheet_names else pd.DataFrame()
        meta={str(r['Field']):r['Value'] for _,r in about.iterrows()} if set(['Field','Value']).issubset(about.columns) else {}
        opt_name='Daily OOS Optimizer' if 'Daily OOS Optimizer' in xls.sheet_names else ('Entry Optimizer Shadow' if 'Entry Optimizer Shadow' in xls.sheet_names else None)
        wt_name='Daily OOS Weights' if 'Daily OOS Weights' in xls.sheet_names else ('Optimizer Weights' if 'Optimizer Weights' in xls.sheet_names else None)
        if not opt_name or not wt_name:return False,'Missing optimizer/weights sheets.'
        opt=pd.read_excel(xls,opt_name);wt=pd.read_excel(xls,wt_name)
        scopes={}
        for _,r in opt.iterrows():
            scope=str(r.get('Scope','')).strip()
            if not scope:continue
            wg=wt[wt['Scope'].astype(str)==scope] if 'Scope' in wt else pd.DataFrame()
            weights={str(x.get('Feature')):float(x.get('Learned weight %'))/100.0 for _,x in wg.iterrows() if pd.notna(x.get('Feature')) and pd.notna(x.get('Learned weight %'))}
            if not weights:continue
            scopes[scope]={'weights':weights,'threshold':float(r.get('Shadow threshold',wg['Shadow threshold'].iloc[0] if not wg.empty and 'Shadow threshold' in wg else .65)),'status':str(r.get('Status','RESEARCH ONLY')),'inner_median_lift':float(r.get('Inner median OOS lift',np.nan)) if pd.notna(r.get('Inner median OOS lift',np.nan)) else None,'inner_worst_lift':float(r.get('Inner worst OOS lift',np.nan)) if pd.notna(r.get('Inner worst OOS lift',np.nan)) else None,'fold4_lift':float(r.get('Final Fold4 OOS lift',np.nan)) if pd.notna(r.get('Final Fold4 OOS lift',np.nan)) else None,'fold4_signals':int(r.get('Final Fold4 signals',0) or 0)}
        if not scopes:return False,'No learned scopes found.'
        model={'version':str(meta.get('Version','6.1.2')),'created':str(meta.get('Generated',datetime.now().isoformat(timespec='seconds'))),'scopes':scopes}
        cfg={'market':meta.get('Market','IMPORTED'),'history':meta.get('History','2y'),'target':float(meta.get('TargetPct',3)),'horizon':int(float(meta.get('HorizonDays',3))),'hourly_target':float(meta.get('HourlyTargetPct',3)),'hourly_bars':(1,2,4)}
        reg=_register_model_v613(model,cfg,None)
        return True,f"Imported {len(scopes)} scope(s) for {cfg['horizon']}D / +{cfg['target']:g}% into registry ({len(reg.get('models',[]))} runs saved)."
    except Exception as e:
        return False,f'{type(e).__name__}: {str(e)[:180]}'


def _scope_quality_v613(scope):
    try:
        f=float(scope.get('fold4_lift') or 0);m=float(scope.get('inner_median_lift') or 0);n=float(scope.get('fold4_signals') or 0)
        return f+.12*m+min(n,250)/5000.0
    except Exception:return -999.0


def _candidate_scope_v613(rec,market):
    scopes=rec.get('scopes',{}) if isinstance(rec,dict) else {};source=str(rec.get('source_universe','ALL 151')).upper()
    # An "ALL" scope inside a US-only/HK-only/TASE-only run is local to that universe,
    # not a license to apply those weights to another exchange.
    source_ok=(source.startswith('ALL') or source in ('CUSTOM','IMPORTED')) or (source.startswith('US') and market in ('NASDAQ','NYSE','US')) or ('HONG KONG' in source and market=='HONG KONG') or ('TEL AVIV' in source and market=='TEL AVIV')
    order=[]
    if market in scopes:order.append((3,market,scopes[market]))
    if market in ('NASDAQ','NYSE','US') and 'US' in scopes:order.append((2,'US',scopes['US']))
    if source_ok and 'ALL' in scopes:order.append((1,'ALL',scopes['ALL']))
    return order


def _candidate_hourly_scope_v613(rec,market,horizon_label):
    scopes=rec.get('hourly_scopes',{}) if isinstance(rec,dict) else {};source=str(rec.get('source_universe','ALL 151')).upper()
    source_ok=(source.startswith('ALL') or source in ('CUSTOM','IMPORTED')) or (source.startswith('US') and market in ('NASDAQ','NYSE','US')) or ('HONG KONG' in source and market=='HONG KONG') or ('TEL AVIV' in source and market=='TEL AVIV')
    out=[]
    for pri,key in ((3,market),(2,'US' if market in ('NASDAQ','NYSE','US') else None),(1,'ALL' if source_ok else None)):
        if not key or key not in scopes:continue
        hobj=(scopes.get(key) or {}).get(horizon_label)
        if hobj:out.append((pri,key,hobj))
    return out


def _select_active_model_v613(registry,horizon_days,target_pct):
    """Select the best *eligible* registry model separately for each market.

    horizon_days=None means AUTO BEST OOS: each market may use a different daily horizon.
    The latest run never wins automatically. Exact-market evidence outranks US/ALL
    fallbacks; within the same specificity tier the strongest final OOS model wins.
    """
    models=[] if not isinstance(registry,dict) else list(registry.get('models',[]))
    candidates=[m for m in models if (horizon_days is None or int(m.get('horizon_days',-1))==int(horizon_days)) and abs(float(m.get('target_pct',-999))-float(target_pct))<1e-9]
    active={'version':APP_VERSION,'created':datetime.now().isoformat(timespec='seconds'),'horizon_days':'AUTO' if horizon_days is None else int(horizon_days),'target_pct':float(target_pct),'scopes':{},'hourly_scopes':{},'selected_models':{}}
    for market in ('NASDAQ','NYSE','HONG KONG','TEL AVIV'):
        opts=[]
        for rec in candidates:
            for pri,skey,scope in _candidate_scope_v613(rec,market):
                if str(scope.get('status',''))!='SHADOW ELIGIBLE':continue
                opts.append((pri,_scope_quality_v613(scope),str(rec.get('created','')),rec,skey,scope))
        if not opts:continue
        pri,qual,created,rec,skey,scope=max(opts,key=lambda x:(x[0],x[1],x[2]))
        chosen=dict(scope);chosen.update({'registry_model_id':rec.get('model_id'),'registry_scope':skey,'registry_source':rec.get('source_universe'),'registry_created':rec.get('created'),'horizon_days':rec.get('horizon_days'),'target_pct':rec.get('target_pct')})
        active['scopes'][market]=chosen
        active['selected_models'][market]={'model_id':rec.get('model_id'),'scope':skey,'horizon_days':rec.get('horizon_days'),'target_pct':rec.get('target_pct'),'fold4_lift':scope.get('fold4_lift'),'fold4_signals':scope.get('fold4_signals'),'source_universe':rec.get('source_universe'),'created':rec.get('created')}
        # Select the best eligible hourly timing model from the same daily run first.
        hchoices=[]
        for hlabel in ('1h','2h','4h'):
            for hpri,hkey,hscope in _candidate_hourly_scope_v613(rec,market,hlabel):
                if str(hscope.get('status',''))!='SHADOW ELIGIBLE':continue
                hchoices.append((hpri,_scope_quality_v613(hscope),hlabel,hkey,hscope))
        if hchoices:
            hpri,hqual,hlabel,hkey,hscope=max(hchoices,key=lambda x:(x[0],x[1]))
            active['hourly_scopes'][market]={hlabel:{**hscope,'registry_model_id':rec.get('model_id'),'registry_scope':hkey}}
    active['source_universe']='MODEL REGISTRY'
    return active


def _registry_selection_frame_v613(active):
    rows=[]
    for market,meta in (active or {}).get('selected_models',{}).items():
        hs=(active.get('hourly_scopes',{}).get(market,{}) or {})
        hlabel=next(iter(hs.keys()),'—')
        hscope=hs.get(hlabel,{}) if hlabel!='—' else {}
        rows.append({'Market':market,'Daily Horizon':f"{meta.get('horizon_days','—')}D",'Daily Target %':meta.get('target_pct'),'Daily Model ID':meta.get('model_id'),'Daily Scope':meta.get('scope'),'Daily Fold4 OOS Lift':meta.get('fold4_lift'),'Daily Fold4 Signals':meta.get('fold4_signals'),'Hourly Model':hlabel,'Hourly Fold4 OOS Lift':hscope.get('fold4_lift'),'Source':meta.get('source_universe'),'Created':meta.get('created')})
    return pd.DataFrame(rows)


def _model_scope_for_ticker_v612(model,ticker):
    if not model:return None
    market=_market_for_ticker_v612(ticker)
    scopes=model.get('scopes',{})
    if market in scopes:return scopes[market]
    if market in ('NASDAQ','NYSE','US') and 'US' in scopes:return scopes['US']
    return scopes.get('ALL')


def _optimized_feature_values_v612(row):
    def n(key,default=0):
        try:
            v=float(row.get(key,default));return v if np.isfinite(v) else default
        except:return default
    return {
        'DailySetup':1.0 if bool(row.get('DailySetupCheck',row.get('DailySetup',False))) else 0.0,
        'FreshSignal':1.0 if bool(row.get('FreshSignalCheck',row.get('FreshSignal',False))) else 0.0,
        'VolumeFlow':1.0 if bool(row.get('VolumeFlowCheck',row.get('VolumeFlow',False))) else 0.0,
        'NoChase':1.0 if bool(row.get('NoChaseCheck',row.get('NoChase',False))) else 0.0,
        'EntryNorm':np.clip(n('EntryScore')/100.0,0,1),'QuantNorm':np.clip(n('DynamicQuant',n('QuantScore'))/100.0,0,1),
        'ExitSafety':np.clip((100-n('ExitPressure',n('ExitPressureAtSignal',50)))/100.0,0,1),'InstitutionalFlow':np.clip(n('InstitutionalFlowScore')/100.0,0,1),
        'RVOLNorm':np.clip((n('DailyRobustRVOL',n('RobustRVOL',1))-0.8)/1.7,0,1),'ADXNorm':np.clip((n('ADX14',15)-15)/30,0,1),
        'VolAccelNorm':np.clip((n('VolumeAccel',0.85)-0.85)/0.75,0,1),'FreshTransitionNorm':np.clip(n('FreshTransitionCount')/3.0,0,1),
    }


def _live_hourly_features_v613(hourly_feat):
    """Features used by the separately learned intraday timing model."""
    names=['HourlyFreshEMA','HourlyRVOLNorm','HourlyBullVolume','HourlyVolAccelNorm','HourlyMACDCross','HourlyVWAPReclaim','HourlyMACDStrength','HourlyInstitutionalFlow','HourlyADXNorm']
    if hourly_feat is None or not isinstance(hourly_feat,pd.DataFrame) or hourly_feat.empty:return {k:np.nan for k in names}
    h=hourly_feat.dropna(subset=['Close']).tail(3)
    if h.empty:return {k:np.nan for k in names}
    last=h.iloc[-1]
    def mx(col,default=0):
        try:
            v=pd.to_numeric(h[col],errors='coerce') if col in h else pd.Series(dtype=float)
            return float(np.nanmax(v)) if len(v) and np.isfinite(np.nanmax(v)) else default
        except:return default
    rr=float(last.get('time_adjusted_rvol',last.get('robust_volume_ratio',np.nan)))
    va=float(last.get('vol_accel',np.nan));adx=float(last.get('adx14',np.nan));ms=float(last.get('macd_hist_slope',np.nan));mh=float(last.get('macd_hist',np.nan))
    dv=directional_volume_row(last);inst=institutional_flow_row(last)
    return {
        'HourlyFreshEMA':1.0 if mx('ema9_cross_up',0)>0 else 0.0,
        'HourlyRVOLNorm':float(np.clip((rr-.8)/1.7,0,1)) if np.isfinite(rr) else np.nan,
        'HourlyBullVolume':float(np.clip(dv.get('bullish',0),0,1)),
        'HourlyVolAccelNorm':float(np.clip((va-.85)/.75,0,1)) if np.isfinite(va) else np.nan,
        'HourlyMACDCross':1.0 if mx('macd_cross_up',0)>0 else 0.0,
        'HourlyVWAPReclaim':1.0 if mx('vwap_cross_up',0)>0 else 0.0,
        'HourlyMACDStrength':1.0 if np.isfinite(ms) and ms>0 and np.isfinite(mh) and mh>0 else 0.0,
        'HourlyInstitutionalFlow':float(np.clip(float(inst.get('score',0))/100.0,0,1)),
        'HourlyADXNorm':float(np.clip((adx-15)/30,0,1)) if np.isfinite(adx) else np.nan,
    }


def _hourly_model_for_ticker_v613(model,ticker):
    if not model:return None,None
    market=_market_for_ticker_v612(ticker);hs=(model.get('hourly_scopes',{}) or {}).get(market,{})
    if not hs:return None,None
    hlabel=next(iter(hs.keys()),None)
    return (hs.get(hlabel),hlabel) if hlabel else (None,None)


def _hourly_score_live_v613(ticker,hourly_feat,model):
    scope,hlabel=_hourly_model_for_ticker_v613(model,ticker)
    if not scope:return np.nan,np.nan,'NO ELIGIBLE HOURLY MODEL','—'
    vals=_live_hourly_features_v613(hourly_feat);weights=scope.get('weights',{})
    present=[k for k in weights if np.isfinite(float(vals.get(k,np.nan)))]
    wsum=sum(float(weights.get(k,0)) for k in present)
    if wsum<=0:return np.nan,np.nan,str(scope.get('status','RESEARCH ONLY')),hlabel
    score=sum(float(weights.get(k,0))*float(vals[k]) for k in present)/wsum
    th=float(scope.get('threshold',.5));match=float(np.clip(100*score/max(th,1e-9),0,100))
    return float(100*score),match,str(scope.get('status','RESEARCH ONLY')),hlabel


def _optimized_score_from_row_v612(row,model,ticker=None):
    scope=_model_scope_for_ticker_v612(model,ticker or row.get('Ticker',''))
    if not scope:return np.nan,np.nan,'NO ELIGIBLE MODEL'
    vals=_optimized_feature_values_v612(row); w=scope.get('weights',{})
    score=sum(float(w.get(k,0))*float(vals.get(k,0)) for k in w)
    th=float(scope.get('threshold',0.65)); status=str(scope.get('status','RESEARCH ONLY'))
    return float(100*score),float(np.clip(100*score/max(th,1e-9),0,100)),status


def _apply_optimized_model_v612(df,model):
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:return df
    z=df.copy(); vals=z.apply(lambda r:_optimized_score_from_row_v612(r,model,r.get('Ticker','')),axis=1)
    z['OptimizedScore']=[x[0] for x in vals];z['OptimizedMatchPct']=[x[1] for x in vals];z['OptimizedModelStatus']=[x[2] for x in vals]
    def model_meta(ticker):
        s=_model_scope_for_ticker_v612(model,ticker)
        return (s or {}).get('registry_model_id','—'),(s or {}).get('registry_scope','—'),(s or {}).get('fold4_lift',np.nan),(s or {}).get('horizon_days',np.nan)
    metas=[model_meta(t) for t in z.get('Ticker',pd.Series('',index=z.index))]
    z['OptimizedModelID']=[x[0] for x in metas];z['OptimizedModelScope']=[x[1] for x in metas];z['OptimizedModelOOSLift']=[x[2] for x in metas];z['OptimizedModelHorizon']=[x[3] for x in metas]
    # Live hourly OOS score is computed during deep analysis and placed on the row.
    def ost(r):
        match=float(r.get('OptimizedMatchPct',0) or 0); hmatch=float(r.get('HourlyOptimizedMatchPct',np.nan));regime=bool(r.get('MarketRegimeCheck',True));xp=float(r.get('ExitPressure',0) or 0)
        hourly_ok=(np.isfinite(hmatch) and hmatch>=100) if pd.notna(r.get('HourlyOptimizedMatchPct',np.nan)) else bool(r.get('HourlyEntryCheck',False))
        ext_ok=bool(r.get('ExtensionGuardCheck',True)) and str(r.get('ChaseRiskLabel','LOW')).upper()!='HIGH'
        if not ext_ok:return 'OPTIMIZED WAIT — EXTENDED'
        if match>=100 and hourly_ok and regime and xp<55:return 'OPTIMIZED CONFIRMED'
        if match>=100 and regime and xp<65:return 'OPTIMIZED ARMED'
        if match>=85:return 'OPTIMIZED WATCH'
        return 'OPTIMIZED WAIT'
    z['OptimizedStage']=z.apply(ost,axis=1);z['OptimizedDelta']=pd.to_numeric(z['OptimizedScore'],errors='coerce')-pd.to_numeric(z.get('TopScore',0),errors='coerce')
    return z

def _aggregate_lift_rows_v611(df, keys, baseline_col):
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:return pd.DataFrame()
    x=df.copy();x['Signals']=pd.to_numeric(x['Signals'],errors='coerce').fillna(0)
    out=[]
    for kvals,g in x.groupby(keys,dropna=False):
        if not isinstance(kvals,tuple):kvals=(kvals,)
        n=float(g.Signals.sum())
        if n<=0:continue
        hits=float((g.Signals*pd.to_numeric(g['Hit Rate %'],errors='coerce').fillna(0)/100).sum())
        bases=float((g.Signals*pd.to_numeric(g[baseline_col],errors='coerce').fillna(0)/100).sum())
        rec={k:v for k,v in zip(keys,kvals)};rec.update({'Signals':int(n),'Hit Rate %':100*hits/n,'Baseline %':100*bases/n,'Lift x':hits/bases if bases>0 else np.nan,'Avg MFE %':float(np.average(pd.to_numeric(g['Avg MFE %'],errors='coerce').fillna(0),weights=g.Signals)),'Avg MAE %':float(np.average(pd.to_numeric(g['Avg MAE %'],errors='coerce').fillna(0),weights=g.Signals)),'Tickers':int(g['Ticker'].nunique()) if 'Ticker' in g else np.nan})
        out.append(rec)
    z=pd.DataFrame(out)
    return z.sort_values(['Lift x','Signals'],ascending=[False,False]).reset_index(drop=True) if not z.empty else z

def _entry_optimizer_v611(rows, min_signals=60, seed=612):
    """V6.1.2 nested OOS optimizer.

    Candidate weights are selected only from rolling validation folds 2-3.
    Fold 4 stays untouched until the final OOS report. Correlated features are
    penalized to reduce double-counting (especially closely related volume signals).
    """
    z=pd.DataFrame(rows)
    if z.empty:return pd.DataFrame(),pd.DataFrame(),{}
    z=z[z.get('Mode','').astype(str).eq('Dynamic')].copy() if 'Mode' in z else z.copy()
    features=['DailySetup','FreshSignal','VolumeFlow','NoChase','EntryNorm','QuantNorm','ExitSafety','InstitutionalFlow','RVOLNorm','ADXNorm','VolAccelNorm','FreshTransitionNorm']
    z['EntryNorm']=pd.to_numeric(z['EntryScore'],errors='coerce').fillna(0).clip(0,100)/100.0
    z['QuantNorm']=pd.to_numeric(z['QuantScore'],errors='coerce').fillna(0).clip(0,100)/100.0
    z['ExitSafety']=(100-pd.to_numeric(z['ExitPressureAtSignal'],errors='coerce').fillna(50).clip(0,100))/100.0
    for c in ['DailySetup','FreshSignal','VolumeFlow','NoChase']:z[c]=z[c].astype(bool).astype(float)
    for c in ['InstitutionalFlow','RVOLNorm','ADXNorm','VolAccelNorm','FreshTransitionNorm']:
        if c not in z:z[c]=0.0
        z[c]=pd.to_numeric(z[c],errors='coerce').fillna(0).clip(0,1)
    rng=np.random.default_rng(seed)
    anchors=[np.array([.10,.13,.14,.02,.09,.07,.07,.12,.10,.06,.06,.04]),np.array([.08,.14,.15,.01,.08,.06,.06,.14,.12,.06,.06,.04]),np.array([.11,.12,.14,.00,.10,.07,.07,.12,.11,.06,.06,.04])]
    alpha=np.array([1.5,2.1,2.2,.45,1.4,1.1,1.1,2.0,1.8,1.0,1.3,1.0])
    candidates=anchors+list(rng.dirichlet(alpha,size=720)); thresholds=np.arange(.48,.84,.025)
    scopes=[('ALL',z)]
    if 'Market' in z:
        us=z[z.Market.astype(str).isin(['NASDAQ','NYSE','US'])].copy()
        if len(us)>=250:scopes.append(('US',us))
        for m,g in z.groupby('Market'):
            if len(g)>=250:scopes.append((str(m),g.copy()))
    best_rows=[];weight_rows=[];model={'version':APP_VERSION,'created':datetime.now().isoformat(timespec='seconds'),'scopes':{}}
    for scope,g in scopes:
        final_test=g[g.Fold.astype(int)==4].copy(); inner=g[g.Fold.astype(int).isin([1,2,3])].copy()
        if len(inner)<240 or len(final_test)<40:continue
        corr=inner[features].corr().abs().fillna(0)
        pairs=[(i,j,float(corr.loc[i,j])) for ix,i in enumerate(features) for j in features[ix+1:] if float(corr.loc[i,j])>=.85]
        best=None
        for w in candidates:
            fold_metrics=[]; total_signals=0
            for vf in (2,3):
                train=g[g.Fold.astype(int)<vf]; val=g[g.Fold.astype(int)==vf]
                if len(train)<80 or len(val)<30:continue
                Xv=val[features].to_numpy(float); base=float(val.Hit.mean())
                sv=Xv@w
                # threshold chosen on earlier folds only
                Xt=train[features].to_numpy(float); st=Xt@w; btr=float(train.Hit.mean())
                best_th=None;best_train=-9
                for th in thresholds:
                    m=st>=th; ns=int(m.sum())
                    if ns<max(25,int(min_signals*.6)):continue
                    hr=float(train.loc[m,'Hit'].mean()); lift=hr/btr if btr>0 else np.nan
                    if np.isfinite(lift) and lift>best_train:best_train=lift;best_th=float(th)
                if best_th is None:continue
                vm=sv>=best_th;ns=int(vm.sum())
                if ns<15:continue
                hr=float(val.loc[vm,'Hit'].mean());lift=hr/base if base>0 else np.nan
                mfe=float(val.loc[vm,'MFE'].mean());mae=float(val.loc[vm,'MAE'].mean())
                fold_metrics.append((lift,ns,hr,mfe,mae,best_th));total_signals+=ns
            if len(fold_metrics)<2:continue
            lifts=np.array([x[0] for x in fold_metrics if np.isfinite(x[0])]);
            if len(lifts)<2:continue
            med=float(np.median(lifts)); worst=float(np.min(lifts)); pos=float(np.mean(lifts>1.0)); stability=max(0.0,1.0-float(np.std(lifts)))
            corr_pen=sum(min(float(w[features.index(i)]),float(w[features.index(j)]))*max(0,c-.85)/.15 for i,j,c in pairs)
            mfe=float(np.mean([x[3] for x in fold_metrics]));mae=float(np.mean([x[4] for x in fold_metrics])); sample=min(1.0,np.sqrt(total_signals/max(min_signals*2,1)))
            objective=(med-1)*2.2+(worst-1)*.9+(pos-.5)*.5+stability*.12+(mfe+mae)*.12+sample*.06-corr_pen*.35
            avg_th=float(np.median([x[5] for x in fold_metrics]))
            rec=(objective,med,worst,pos,total_signals,avg_th,w,stability,corr_pen)
            if best is None or rec[0]>best[0]:best=rec
        if best is None:continue
        objective,med,worst,pos,ns,th,w,stability,corr_pen=best
        base_test=float(final_test.Hit.mean());score=final_test[features].to_numpy(float)@w;mask=score>=th;tn=int(mask.sum())
        thr=float(final_test.loc[mask,'Hit'].mean()) if tn else np.nan;tl=thr/base_test if tn and base_test>0 else np.nan
        status='SHADOW ELIGIBLE' if tn>=25 and med>=1.03 and worst>=.98 and np.isfinite(tl) and tl>=1.03 else 'RESEARCH ONLY'
        best_rows.append({'Scope':scope,'Inner validation signals':ns,'Inner median OOS lift':med,'Inner worst OOS lift':worst,'Inner positive folds %':100*pos,'Stability':stability,'Correlation penalty':corr_pen,'Shadow threshold':th,'Final Fold4 signals':tn,'Final Fold4 hit rate %':100*thr if np.isfinite(thr) else np.nan,'Final Fold4 baseline %':100*base_test,'Final Fold4 OOS lift':tl,'Status':status})
        weights={name:float(val) for name,val in zip(features,w)}
        model['scopes'][scope]={'weights':weights,'threshold':float(th),'status':status,'inner_median_lift':med,'inner_worst_lift':worst,'fold4_lift':float(tl) if np.isfinite(tl) else None,'fold4_signals':tn}
        for name,val in weights.items():weight_rows.append({'Scope':scope,'Feature':name,'Learned weight %':100*val,'Shadow threshold':th,'Status':status})
    return pd.DataFrame(best_rows),pd.DataFrame(weight_rows),model



def _hourly_optimizer_observations_v613(hourly_feat,ticker,target_pct=.03,horizon_bars=(1,2,4)):
    """Create causal intraday observations for a separate OOS timing optimizer."""
    if hourly_feat is None or not isinstance(hourly_feat,pd.DataFrame) or len(hourly_feat)<120:return []
    f=hourly_feat.dropna(subset=['Close','High','Low']).copy()
    if not isinstance(f.index,pd.DatetimeIndex):
        try:f.index=pd.to_datetime(f.index)
        except Exception:return []
    n=len(f);cl=f['Close'].to_numpy(float);hi=f['High'].to_numpy(float);lo=f['Low'].to_numpy(float);out=[]
    for i,(ts,r) in enumerate(f.iterrows()):
        frac=(i+1)/max(n,1);fold=min(4,max(1,int(np.ceil(frac*4))))
        rr=float(r.get('time_adjusted_rvol',r.get('robust_volume_ratio',np.nan)));va=float(r.get('vol_accel',np.nan));adx=float(r.get('adx14',np.nan));ms=float(r.get('macd_hist_slope',np.nan));mh=float(r.get('macd_hist',np.nan));dv=directional_volume_row(r);inst=institutional_flow_row(r)
        vals={
            'HourlyFreshEMA':1.0 if float(r.get('ema9_cross_up',0) or 0)>0 else 0.0,
            'HourlyRVOLNorm':float(np.clip((rr-.8)/1.7,0,1)) if np.isfinite(rr) else 0.0,
            'HourlyBullVolume':float(np.clip(dv.get('bullish',0),0,1)),
            'HourlyVolAccelNorm':float(np.clip((va-.85)/.75,0,1)) if np.isfinite(va) else 0.0,
            'HourlyMACDCross':1.0 if float(r.get('macd_cross_up',0) or 0)>0 else 0.0,
            'HourlyVWAPReclaim':1.0 if float(r.get('vwap_cross_up',0) or 0)>0 else 0.0,
            'HourlyMACDStrength':1.0 if np.isfinite(ms) and ms>0 and np.isfinite(mh) and mh>0 else 0.0,
            'HourlyInstitutionalFlow':float(np.clip(float(inst.get('score',0))/100.0,0,1)),
            'HourlyADXNorm':float(np.clip((adx-15)/30,0,1)) if np.isfinite(adx) else 0.0,
        }
        for hb in horizon_bars:
            hb=int(hb)
            if i+hb>=n or not np.isfinite(cl[i]) or cl[i]<=0:continue
            fh=hi[i+1:i+1+hb];fl=lo[i+1:i+1+hb]
            mfe=float(np.nanmax(fh)/cl[i]-1.0);mae=float(np.nanmin(fl)/cl[i]-1.0)
            out.append({'Ticker':ticker,'Market':_market_for_ticker_v612(ticker),'Fold':fold,'Hour':int(ts.hour),'HorizonBars':hb,'Hit':float(mfe>=float(target_pct)),'MFE':mfe,'MAE':mae,**vals})
    return out


def _hourly_matched_lift_v613(g,mask):
    if g is None or g.empty:return np.nan,0,np.nan,np.nan,np.nan
    m=np.asarray(mask,dtype=bool)
    if len(m)!=len(g) or not m.any():return np.nan,0,np.nan,np.nan,np.nan
    base_by_hour=g.groupby('Hour')['Hit'].mean().to_dict()
    sel=g.loc[m]
    mb=float(np.mean([base_by_hour.get(int(h),np.nan) for h in sel.Hour])) if len(sel) else np.nan
    hr=float(sel.Hit.mean()) if len(sel) else np.nan
    lift=hr/mb if np.isfinite(hr) and np.isfinite(mb) and mb>0 else np.nan
    return lift,len(sel),hr,float(sel.MFE.mean()),float(sel.MAE.mean())


def _hourly_optimizer_v613(rows,min_signals=80,seed=613):
    """Nested OOS optimizer for intraday timing signals using same-hour baselines."""
    z=pd.DataFrame(rows)
    if z.empty:return pd.DataFrame(),pd.DataFrame(),{'scopes':{}}
    feats=['HourlyFreshEMA','HourlyRVOLNorm','HourlyBullVolume','HourlyVolAccelNorm','HourlyMACDCross','HourlyVWAPReclaim','HourlyMACDStrength','HourlyInstitutionalFlow','HourlyADXNorm']
    for c in feats:z[c]=pd.to_numeric(z.get(c,0),errors='coerce').fillna(0).clip(0,1)
    rng=np.random.default_rng(seed)
    anchors=[np.array([.18,.18,.16,.10,.10,.06,.08,.08,.06]),np.array([.22,.20,.18,.09,.09,.04,.07,.06,.05])]
    alpha=np.array([2.2,2.2,2.0,1.3,1.5,.8,1.1,1.2,1.0]);candidates=anchors+list(rng.dirichlet(alpha,size=360));thresholds=np.arange(.30,.81,.03)
    scope_sets=[('ALL',z)]
    us=z[z.Market.astype(str).isin(['NASDAQ','NYSE','US'])].copy()
    if len(us)>=800:scope_sets.append(('US',us))
    for m,g in z.groupby('Market'):
        if len(g)>=800:scope_sets.append((str(m),g.copy()))
    rows_out=[];weights_out=[];model={'scopes':{}}
    for hb in sorted(set(int(x) for x in z.HorizonBars.unique())):
      zh=z[z.HorizonBars.astype(int)==hb]
      for scope,base_scope in scope_sets:
        g=base_scope[base_scope.HorizonBars.astype(int)==hb].copy()
        if len(g)<500:continue
        final=g[g.Fold.astype(int)==4].copy();inner=g[g.Fold.astype(int).isin([1,2,3])]
        if len(final)<100 or len(inner)<300:continue
        corr=inner[feats].corr().abs().fillna(0);pairs=[(i,j,float(corr.loc[i,j])) for ix,i in enumerate(feats) for j in feats[ix+1:] if float(corr.loc[i,j])>=.85]
        best=None
        for w in candidates:
            mets=[];total=0
            for vf in (2,3):
                tr=g[g.Fold.astype(int)<vf];va=g[g.Fold.astype(int)==vf]
                if len(tr)<150 or len(va)<80:continue
                st=tr[feats].to_numpy(float)@w;sv=va[feats].to_numpy(float)@w
                bth=None;bobj=-999
                for th in thresholds:
                    lift,ns,hr,mfe,mae=_hourly_matched_lift_v613(tr,st>=th)
                    if ns<max(40,int(min_signals*.6)) or not np.isfinite(lift):continue
                    obj=(lift-1)*2.0+min(ns,300)/3000.0+(mfe+mae)*.08
                    if obj>bobj:bobj=obj;bth=float(th)
                if bth is None:continue
                lift,ns,hr,mfe,mae=_hourly_matched_lift_v613(va,sv>=bth)
                if ns<25 or not np.isfinite(lift):continue
                mets.append((lift,ns,hr,mfe,mae,bth));total+=ns
            if len(mets)<2:continue
            lifts=np.array([x[0] for x in mets]);med=float(np.median(lifts));worst=float(np.min(lifts));pos=float(np.mean(lifts>1));stability=max(0,1-float(np.std(lifts)))
            corr_pen=sum(min(float(w[feats.index(i)]),float(w[feats.index(j)]))*max(0,c-.85)/.15 for i,j,c in pairs)
            th=float(np.median([x[5] for x in mets]));objective=(med-1)*2.3+(worst-1)*1.0+(pos-.5)*.45+stability*.1+min(total,300)/5000-corr_pen*.3
            rec=(objective,med,worst,pos,total,th,w,stability,corr_pen)
            if best is None or rec[0]>best[0]:best=rec
        if best is None:continue
        objective,med,worst,pos,total,th,w,stability,corr_pen=best;score=final[feats].to_numpy(float)@w
        tl,tn,thr,mfe,mae=_hourly_matched_lift_v613(final,score>=th)
        status='SHADOW ELIGIBLE' if tn>=35 and med>=1.08 and worst>=1.00 and np.isfinite(tl) and tl>=1.08 else 'RESEARCH ONLY'
        hlabel=f'{hb}h';rows_out.append({'Scope':scope,'Hourly Horizon':hlabel,'Inner signals':total,'Inner median OOS lift':med,'Inner worst OOS lift':worst,'Positive folds %':100*pos,'Stability':stability,'Correlation penalty':corr_pen,'Threshold':th,'Fold4 signals':tn,'Fold4 hit rate %':100*thr if np.isfinite(thr) else np.nan,'Fold4 matched OOS lift':tl,'Status':status})
        weights={k:float(v) for k,v in zip(feats,w)};model['scopes'].setdefault(scope,{})[hlabel]={'weights':weights,'threshold':th,'status':status,'inner_median_lift':med,'inner_worst_lift':worst,'fold4_lift':float(tl) if np.isfinite(tl) else None,'fold4_signals':tn}
        for k,v in weights.items():weights_out.append({'Scope':scope,'Hourly Horizon':hlabel,'Feature':k,'Learned weight %':100*v,'Status':status,'Fold4 OOS lift':tl})
    return pd.DataFrame(rows_out),pd.DataFrame(weights_out),model

def _aggregate_entry_validation(rows):
    z=pd.DataFrame(rows)
    if z.empty:return pd.DataFrame(),pd.DataFrame(),pd.DataFrame()
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
                'Avg MFE %':100*float(g['MFE'].mean()),
                'Avg MAE %':100*float(g['MAE'].mean()),
                'Avg Drawdown %':100*float(g['Drawdown'].mean()),
                'Median Days to Target':float(g.loc[g['Hit']>0,'DaysToTarget'].median()) if (g['Hit']>0).any() else np.nan,
                'Positive stocks %':100*float((stock_rates>base).mean()) if len(stock_rates) and np.isfinite(base) else np.nan,
            })
    summary=pd.DataFrame(out)
    # V6.1.1 daily causal proxy for Entry Trigger V3. Hourly confirmation is
    # validated live/short-horizon separately because provider intraday history is limited.
    gates=[]
    for mode in ['Static','Dynamic']:
        if 'TriggerEligible' in z.columns:g=z[(z.Mode==mode)&(z.TriggerEligible.astype(bool))]
        else:g=z[(z.Mode==mode)&(z.EntryScore>=72)]
        if g.empty:continue
        gates.append({'Mode':mode,'Signals':len(g),'Hit Rate %':100*float(g.Hit.mean()),
                      'Lift vs baseline':float(g.Hit.mean()/base) if np.isfinite(base) and base>0 else np.nan,
                      'Avg Forward Return %':100*float(g.ForwardReturn.mean()),
                      'Avg MFE %':100*float(g.MFE.mean()),
                      'Avg MAE %':100*float(g.MAE.mean()),
                      'Avg Drawdown %':100*float(g.Drawdown.mean()),
                      'Median Days to Target':float(g.loc[g.Hit>0,'DaysToTarget'].median()) if (g.Hit>0).any() else np.nan})
    market_rows=[]
    if 'Market' in z.columns:
        for market in sorted(z['Market'].dropna().astype(str).unique()):
            zm=z[z.Market.astype(str)==market]
            for mode in ['Static','Dynamic']:
                all_m=zm[zm.Mode==mode]
                if all_m.empty:continue
                market_base=float(all_m.Hit.mean())
                g=all_m[all_m.TriggerEligible.astype(bool)] if 'TriggerEligible' in all_m.columns else all_m[all_m.EntryScore>=72]
                if g.empty:continue
                fold_rates=g.groupby('Fold')['Hit'].mean(); positive_folds=int((fold_rates>market_base).sum()) if len(fold_rates) else 0
                market_rows.append({
                    'Market':market,'Mode':mode,'Signals':len(g),'Stocks':int(g.Ticker.nunique()),
                    'Baseline Hit Rate %':100*market_base,'Trigger Hit Rate %':100*float(g.Hit.mean()),
                    'Lift vs market baseline':float(g.Hit.mean()/market_base) if market_base>0 else np.nan,
                    'Avg Forward Return %':100*float(g.ForwardReturn.mean()),'Avg MFE %':100*float(g.MFE.mean()),'Avg MAE %':100*float(g.MAE.mean()),
                    'Positive folds':f"{positive_folds}/{len(fold_rates)}",
                    'Median Days to Target':float(g.loc[g.Hit>0,'DaysToTarget'].median()) if (g.Hit>0).any() else np.nan,
                })
    return summary,pd.DataFrame(gates),pd.DataFrame(market_rows)

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



def _excel_safe_df(obj):
    """Return a copy that Excel/openpyxl can serialize safely.

    Excel does not support timezone-aware datetimes. Intraday 15m/1H
    frames intentionally keep exchange-aware timestamps for calculations,
    so exports must strip only the timezone metadata (preserving the local
    wall-clock time shown to the user). Object columns are handled too
    because mixed audit tables can contain pandas/Python datetime objects.
    """
    if obj is None:
        return pd.DataFrame()
    if not isinstance(obj, pd.DataFrame):
        try:
            obj = pd.DataFrame(obj)
        except Exception:
            return pd.DataFrame()
    out = obj.copy()

    # Index is normally exported with index=False, but sanitize it as well
    # so this helper is safe for future callers.
    try:
        if isinstance(out.index, pd.DatetimeIndex) and out.index.tz is not None:
            out.index = out.index.tz_localize(None)
    except Exception:
        pass

    def _strip_tz_value(v):
        try:
            if isinstance(v, pd.Timestamp):
                return v.tz_localize(None) if v.tzinfo is not None else v
            if isinstance(v, datetime):
                return v.replace(tzinfo=None) if v.tzinfo is not None else v
        except Exception:
            return v
        return v

    for col in out.columns:
        ser = out[col]
        try:
            if isinstance(ser.dtype, pd.DatetimeTZDtype):
                out[col] = ser.dt.tz_localize(None)
                continue
        except Exception:
            pass
        if ser.dtype == 'object':
            # Apply only when at least one tz-aware datetime is present.
            try:
                sample = ser.dropna().head(200)
                has_tz = any(
                    (isinstance(v, pd.Timestamp) and v.tzinfo is not None) or
                    (isinstance(v, datetime) and v.tzinfo is not None)
                    for v in sample
                )
                if has_tz:
                    out[col] = ser.map(_strip_tz_value)
            except Exception:
                pass
    return out

def scanner_excel_bytes(df,scan_meta=None):
    bio=BytesIO()
    out_df=df.copy()
    if 'BacktestN' in out_df:
        out_df['BacktestQuality']=np.where(pd.to_numeric(out_df['BacktestN'],errors='coerce').fillna(0)>=12,'EVIDENCE OK',np.where(pd.to_numeric(out_df['BacktestN'],errors='coerce').fillna(0)>0,'LOW SAMPLE','NO SAMPLE'))
        if 'EmpiricalHitRate' in out_df:out_df.loc[pd.to_numeric(out_df['BacktestN'],errors='coerce').fillna(0)<12,'EmpiricalHitRate']=np.nan
    with pd.ExcelWriter(bio,engine="openpyxl") as writer:
        _excel_safe_df(out_df).to_excel(writer,index=False,sheet_name="Scanner Results")
        exp_cols=[c for c in ["Rank","Ticker","Signal","TradeStage","MovementStage","ExitPressure","ExitStage","VolumeContext","LiveIntradayRVOL","DailyRobustRVOL","TimeAdjustedRVOL","ExplosiveScore","ExplosiveStage","HourlyConfirm","P5_5D","P10_5D","P15_5D","P15_5D_N","EntryScore","Prediction","EvidenceQuality","BacktestQuality"] if c in out_df.columns]
        _excel_safe_df(out_df[exp_cols]).to_excel(writer,index=False,sheet_name="Explosive Move")
        hk=out_df[out_df["Ticker"].astype(str).str.endswith(".HK")].copy() if "Ticker" in out_df else pd.DataFrame()
        _excel_safe_df(hk).to_excel(writer,index=False,sheet_name="Hong Kong Universe")
        sm=scan_meta or {}
        skipped=sm.get('skipped') or []
        meta=pd.DataFrame({"Field":["Version","Generated","Rows in export","Requested","Daily success","Deep success","Skipped/errors"],"Value":[APP_VERSION,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),len(df),sm.get('requested','—'),sm.get('daily_success','—'),sm.get('deep_success','—'),len(skipped)]})
        meta.to_excel(writer,index=False,sheet_name="About")
        if skipped:_excel_safe_df(pd.DataFrame(skipped)).to_excel(writer,index=False,sheet_name="Skipped")
    return bio.getvalue()


def _auto_backtest_threshold(feat,horizon,target_pct):
    rows=[]
    for th in [60,62,64,66,68,70,72,75]:
        b=normalize_backtest_confidence(backtest_signal(feat,int(horizon),float(target_pct),th,0))
        n=int(b.get('n',0) or 0); hr=float(b.get('hit_rate',np.nan)); ar=float(b.get('avg_return',np.nan))
        # Reward evidence first; tiny samples cannot win only because of 100% hit rate.
        evidence=min(1.0,math.sqrt(n/20.0)) if n else 0.0
        quality=(100*hr if np.isfinite(hr) else 0)*evidence + 10*max(-.1,min(.2,ar if np.isfinite(ar) else 0))*evidence + min(15,n/2)
        rows.append({'Threshold':th,'Signals':n,'Observed Hit Rate %':100*hr if n and np.isfinite(hr) else np.nan,'Hit Rate %':100*hr if n>=12 and np.isfinite(hr) else np.nan,'Avg Return %':100*ar if n and np.isfinite(ar) else np.nan,'Evidence':round(100*evidence,1),'Quality':quality})
    tb=pd.DataFrame(rows)
    qualified=tb[tb.Signals>=12]
    pick=int((qualified if not qualified.empty else tb).sort_values(['Quality','Signals'],ascending=False).iloc[0].Threshold)
    return pick,tb


_FEEDBACK_REMOTE_STATE_V630={'attempted_pull':False,'last_pull':None,'last_push':None,'last_error':None}
_FEEDBACK_REMOTE_LOCK_V630=threading.RLock()

def _feedback_db_path_v600():
    # Keep the historic filename so an in-place V6.2.x -> V6.3.0 upgrade reuses
    # every snapshot already present on the current host. V6.3.0 adds portable
    # backup/restore and optional GitHub persistence around this same DB.
    base=Path.home()/'.ai_stock_hunter'
    try:base.mkdir(parents=True,exist_ok=True)
    except Exception:base=Path('/tmp')
    return base/'feedback_v600.sqlite3'

def _feedback_persistence_cfg_v630():
    """Optional durable GitHub store configured only through Streamlit secrets.

    Example .streamlit/secrets.toml:
      [feedback_persistence]
      github_token = "github_pat_..."
      repo = "alonaz1976/ai-stock-hunter-v2"
      branch = "main"
      path = "data/feedback_v630.sqlite3.gz"

    The token is never rendered or exported. Without it the app still supports
    one-click DB download + restore, so the user can keep portable backups.
    """
    try:
        sec=st.secrets.get('feedback_persistence',{})
        token=str(sec.get('github_token','')).strip()
        repo=str(sec.get('repo','alonaz1976/ai-stock-hunter-v2')).strip()
        branch=str(sec.get('branch','main')).strip() or 'main'
        path=str(sec.get('path','data/feedback_v630.sqlite3.gz')).strip() or 'data/feedback_v630.sqlite3.gz'
        enabled=bool(token and repo and '/' in repo and path)
        return {'enabled':enabled,'token':token,'repo':repo,'branch':branch,'path':path}
    except Exception:
        return {'enabled':False,'token':'','repo':'','branch':'main','path':'data/feedback_v630.sqlite3.gz'}

def _feedback_checkpoint_v630():
    try:
        path=_feedback_db_path_v600()
        if not path.exists():return
        con=sqlite3.connect(str(path),timeout=30)
        try:con.execute('PRAGMA wal_checkpoint(FULL)')
        finally:con.close()
    except Exception:pass

def _feedback_db_bytes_v630():
    try:
        _feedback_checkpoint_v630();p=_feedback_db_path_v600()
        return p.read_bytes() if p.exists() else b''
    except Exception:return b''

def _feedback_validate_db_file_v630(path):
    con=None
    try:
        con=sqlite3.connect(str(path),timeout=10)
        ok=con.execute('PRAGMA integrity_check').fetchone()[0]
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        return str(ok).lower()=='ok' and 'snapshots' in tables and 'outcomes' in tables
    except Exception:return False
    finally:
        try:
            if con is not None:con.close()
        except Exception:pass

def _feedback_restore_bytes_v630(data, push_remote=False):
    if not data:return False,'Backup file is empty.'
    target=_feedback_db_path_v600();tmp=target.with_suffix('.restore.tmp')
    try:
        tmp.write_bytes(bytes(data))
        if not _feedback_validate_db_file_v630(tmp):
            try:tmp.unlink()
            except Exception:pass
            return False,'The uploaded file is not a valid AI Stock Hunter Feedback database.'
        # Remove stale WAL/SHM before atomically replacing the database.
        for ext in ('-wal','-shm'):
            try:Path(str(target)+ext).unlink()
            except Exception:pass
        os.replace(tmp,target)
        _FEEDBACK_REMOTE_STATE_V630['attempted_pull']=True
        if push_remote:_feedback_schedule_remote_push_v630()
        return True,'Feedback database restored successfully.'
    except Exception as e:
        try:tmp.unlink()
        except Exception:pass
        return False,f'{type(e).__name__}: {e}'

def _feedback_github_request_v630(method,url,token,payload=None):
    headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'AI-Stock-Hunter-V630'}
    if token:headers['Authorization']=f'Bearer {token}'
    body=json.dumps(payload).encode('utf-8') if payload is not None else None
    req=urllib_request.Request(url,data=body,headers=headers,method=method)
    with urllib_request.urlopen(req,timeout=45) as resp:
        raw=resp.read()
        return json.loads(raw.decode('utf-8')) if raw else {}

def _feedback_remote_pull_v630(force=False):
    cfg=_feedback_persistence_cfg_v630()
    if not cfg['enabled']:return False,'GitHub persistence is not configured.'
    with _FEEDBACK_REMOTE_LOCK_V630:
        if _FEEDBACK_REMOTE_STATE_V630['attempted_pull'] and not force:return False,'Already checked this session.'
        _FEEDBACK_REMOTE_STATE_V630['attempted_pull']=True
    qpath=urllib_parse.quote(cfg['path'],safe='/')
    url=f"https://api.github.com/repos/{cfg['repo']}/contents/{qpath}?ref={urllib_parse.quote(cfg['branch'])}"
    try:
        obj=_feedback_github_request_v630('GET',url,cfg['token'])
        raw_content=str(obj.get('content','') or '').replace('\n','')
        if raw_content:
            content=base64.b64decode(raw_content)
        elif obj.get('git_url'):
            blob=_feedback_github_request_v630('GET',str(obj.get('git_url')),cfg['token'])
            content=base64.b64decode(str(blob.get('content','') or '').replace('\n',''))
        elif obj.get('download_url'):
            headers={'Authorization':f"Bearer {cfg['token']}",'User-Agent':'AI-Stock-Hunter-V630'}
            req=urllib_request.Request(str(obj.get('download_url')),headers=headers,method='GET')
            with urllib_request.urlopen(req,timeout=60) as resp:content=resp.read()
        else:
            return False,'Remote Feedback backup has no downloadable content.'
        if str(cfg.get('path','')).lower().endswith('.gz'):
            content=gzip.decompress(content)
        ok,msg=_feedback_restore_bytes_v630(content,push_remote=False)
        if ok:_FEEDBACK_REMOTE_STATE_V630.update({'last_pull':datetime.utcnow().isoformat()+'Z','last_error':None})
        else:_FEEDBACK_REMOTE_STATE_V630['last_error']=msg
        return ok,msg
    except urllib_error.HTTPError as e:
        if e.code==404:return False,'No remote Feedback backup exists yet.'
        msg=f'GitHub pull HTTP {e.code}'
        _FEEDBACK_REMOTE_STATE_V630['last_error']=msg;return False,msg
    except Exception as e:
        msg=f'{type(e).__name__}: {e}';_FEEDBACK_REMOTE_STATE_V630['last_error']=msg;return False,msg

def _feedback_remote_push_v630():
    cfg=_feedback_persistence_cfg_v630()
    if not cfg['enabled']:return False,'GitHub persistence is not configured.'
    data=_feedback_db_bytes_v630()
    if not data:return False,'Feedback database is empty.'
    upload_data=gzip.compress(data,compresslevel=6) if str(cfg.get('path','')).lower().endswith('.gz') else data
    qpath=urllib_parse.quote(cfg['path'],safe='/')
    url=f"https://api.github.com/repos/{cfg['repo']}/contents/{qpath}"
    sha=None
    try:
        cur=_feedback_github_request_v630('GET',url+f"?ref={urllib_parse.quote(cfg['branch'])}",cfg['token']);sha=cur.get('sha')
    except urllib_error.HTTPError as e:
        if e.code!=404:
            msg=f'GitHub lookup HTTP {e.code}';_FEEDBACK_REMOTE_STATE_V630['last_error']=msg;return False,msg
    except Exception as e:
        msg=f'{type(e).__name__}: {e}';_FEEDBACK_REMOTE_STATE_V630['last_error']=msg;return False,msg
    payload={'message':f'Feedback DB sync V{APP_VERSION} {datetime.utcnow().replace(microsecond=0).isoformat()}Z','content':base64.b64encode(upload_data).decode('ascii'),'branch':cfg['branch']}
    if sha:payload['sha']=sha
    try:
        _feedback_github_request_v630('PUT',url,cfg['token'],payload)
        _FEEDBACK_REMOTE_STATE_V630.update({'last_push':datetime.utcnow().isoformat()+'Z','last_error':None});return True,'Remote Feedback backup updated.'
    except Exception as e:
        msg=f'{type(e).__name__}: {e}';_FEEDBACK_REMOTE_STATE_V630['last_error']=msg;return False,msg

def _feedback_schedule_remote_push_v630():
    if not _feedback_persistence_cfg_v630().get('enabled'):return
    def run():
        try:_feedback_remote_push_v630()
        except Exception:pass
    threading.Thread(target=run,daemon=True,name='feedback-persistence-v630').start()

def _feedback_auto_restore_v630():
    path=_feedback_db_path_v600()
    if path.exists() and path.stat().st_size>0:
        _FEEDBACK_REMOTE_STATE_V630['attempted_pull']=True;return
    if _feedback_persistence_cfg_v630().get('enabled'):
        _feedback_remote_pull_v630(force=False)

def _feedback_conn_v600():
    _feedback_auto_restore_v630()
    con=sqlite3.connect(str(_feedback_db_path_v600()),timeout=30)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=30000')
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
    con.execute("""CREATE TABLE IF NOT EXISTS replay_runs(
        run_id TEXT PRIMARY KEY, created_at TEXT, scope TEXT, history TEXT, target_pct REAL, horizon_days INTEGER,
        sample_every INTEGER, requested_tickers INTEGER, successful_tickers INTEGER, event_rows INTEGER, clean_rows INTEGER)""")
    con.execute("""CREATE TABLE IF NOT EXISTS replay_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, ticker TEXT, market TEXT, signal_date TEXT, price REAL,
        quant_score REAL, early_score REAL, entry_score REAL, atr_pct REAL, target1 REAL, invalidation REAL,
        end_return REAL, max_favorable REAL, max_adverse REAL, first_event TEXT, clean_outcome TEXT, indicators TEXT, candidate INTEGER,
        UNIQUE(run_id,ticker,signal_date))""")
    con.execute("""CREATE TABLE IF NOT EXISTS replay_combinations(
        run_id TEXT, combination TEXT, combo_size INTEGER, families TEXT, discovery_rank INTEGER, discovery_score REAL,
        discovery_n INTEGER, discovery_wins INTEGER, discovery_success REAL, discovery_baseline REAL, discovery_lift REAL, discovery_delta REAL, discovery_stocks INTEGER,
        validation_n INTEGER, validation_wins INTEGER, validation_success REAL, validation_baseline REAL, validation_lift REAL, validation_delta REAL, validation_stocks INTEGER,
        positive_folds INTEGER, usable_folds INTEGER, stability_gap REAL, research_tier TEXT, oos_status TEXT,
        PRIMARY KEY(run_id,combination))""")
    con.execute("""CREATE TABLE IF NOT EXISTS replay_combo_folds(
        run_id TEXT, combination TEXT, fold INTEGER, resolved INTEGER, wins INTEGER, success_rate REAL, baseline_rate REAL, lift REAL, delta_pp REAL, stocks INTEGER,
        PRIMARY KEY(run_id,combination,fold))""")
    # V6.1.1 migration: persist live gate evidence so Feedback can learn which
    # confirmations are adding lift in the CURRENT market. Existing DBs are upgraded in place.
    existing={r[1] for r in con.execute('PRAGMA table_info(snapshots)').fetchall()}
    for col,typ in [('entry_state','TEXT'),('confirmation_pct','REAL'),('daily_setup','INTEGER'),('fresh_signal','INTEGER'),('hourly_entry','INTEGER'),('volume_flow','INTEGER'),('no_chase','INTEGER'),('extension_guard','INTEGER'),('chase_risk_score','REAL'),('chase_risk_label','TEXT'),('session_move_pct','REAL'),('since_trigger_pct','REAL'),('volume_trend','TEXT'),('trigger_anchor_price','REAL'),('market_regime','TEXT'),('market_regime_ok','INTEGER'),('optimized_stage','TEXT'),('optimized_score','REAL'),('optimized_match','REAL'),('optimized_model_status','TEXT'),('optimized_model_id','TEXT'),('optimized_model_scope','TEXT'),('optimized_model_horizon','REAL'),('optimized_oos_lift','REAL'),('optimized_hourly_match','REAL'),('optimized_hourly_horizon','TEXT'),('model_disagreement','TEXT'),('scan_mode','TEXT'),('pre_move_stage','TEXT'),('pre_move_score','REAL'),('pre_move_probability','REAL'),('pre_move_families','TEXT'),('pre_move_features','TEXT'),('pre_move_best_lift','REAL'),('pre_move_freshness','TEXT')]:
        if col not in existing:
            try:con.execute(f'ALTER TABLE snapshots ADD COLUMN {col} {typ}')
            except Exception:pass
    replay_existing={r[1] for r in con.execute('PRAGMA table_info(replay_events)').fetchall()}
    replay_cols=[
        ('candidate','INTEGER'),('legacy_candidate','INTEGER'),('candidate_v2','INTEGER'),('high_confidence','INTEGER'),
        ('family_signature','TEXT'),('family_count','INTEGER'),('freshness_state','TEXT'),('move_consumed_pct','REAL'),
        ('extension_atr','REAL'),('distribution_risk','INTEGER'),('setup_score_v2','REAL'),('meta_probability','REAL'),
        ('meta_sample','INTEGER'),('meta_lift','REAL'),('r_multiple','REAL'),('recent_2d_return','REAL'),
        ('core_momentum','INTEGER'),('core_volume_flow','INTEGER'),('candidate_rule_version','TEXT'),
        ('combo_phase','TEXT'),('combo_candidate_v3','INTEGER'),('combo_high_confidence_v3','INTEGER'),('combo_70_research','INTEGER'),
        ('combo_match_count','INTEGER'),('combo_best_signature','TEXT'),('combo_best_discovery_rate','REAL'),('combo_best_discovery_lift','REAL')
    ]
    for col,typ in replay_cols:
        if col not in replay_existing:
            try:con.execute(f'ALTER TABLE replay_events ADD COLUMN {col} {typ}')
            except Exception:pass
    con.commit()
    return con


def _feedback_store_scan_v600(scan_id,df,config):
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:return
    try:
        # V6.2.9: persist the research-radar layer together with the live scan so
        # Feedback can learn which Pre-Move families/features actually matured.
        try: df=_attach_pre_move_overlay_v628(df)
        except Exception: df=df.copy()
        con=_feedback_conn_v600(); ts=datetime.utcnow().replace(microsecond=0).isoformat()+'Z'
        def num(v):
            try:return float(v) if pd.notna(v) and np.isfinite(float(v)) else None
            except:return None
        def bit(v):
            try:return int(bool(v))
            except:return None
        for _,r in df.iterrows():
            prod=str(r.get('EntryTriggerState',r.get('EntryStatus','')))
            opt=str(r.get('OptimizedStage',''))
            pconf=prod=='CONFIRMED ENTRY';oconf=opt=='OPTIMIZED CONFIRMED'
            disagreement='BOTH CONFIRMED' if pconf and oconf else ('OPTIMIZED ONLY' if oconf else ('PRODUCTION ONLY' if pconf else 'NEITHER'))
            rec={
                'scan_id':scan_id,'ts_utc':ts,'ticker':str(r.get('Ticker','')),'market':str(r.get('Market','')),'price':num(r.get('Price')),
                'top_score':num(r.get('TopScore')),'opportunity':num(r.get('OpportunityScore')),'trade_stage':str(r.get('TradeStage','')),'movement_stage':str(r.get('MovementStage','')),
                'prediction':num(r.get('Prediction')),'move_score':num(r.get('MoveScore')),'explosive':num(r.get('ExplosiveScore')),'entry_score':num(r.get('EntryScore')),
                'hourly':num(r.get('HourlyConfirm')),'exit_pressure':num(r.get('ExitPressure')),'global_rank':int(r.get('GlobalRank')) if pd.notna(r.get('GlobalRank')) else None,
                'market_rank':int(r.get('MarketRank')) if pd.notna(r.get('MarketRank')) else None,'session_status':str(r.get('SessionStatus','')),
                'entry_low':num(r.get('EntryLow')),'entry_high':num(r.get('EntryHigh')),'trigger':num(r.get('BreakoutTrigger')),'invalidation':num(r.get('Invalidation')),
                'target1':num(r.get('Target1')),'target2':num(r.get('Target2')),'horizon_days':int(config.get('horizon',5)),'entry_state':prod,
                'confirmation_pct':num(r.get('EntryConfirmationPct')),'daily_setup':bit(r.get('DailySetupCheck')),'fresh_signal':bit(r.get('FreshSignalCheck')),
                'hourly_entry':bit(r.get('HourlyEntryCheck')),'volume_flow':bit(r.get('VolumeFlowCheck')),'no_chase':bit(r.get('NoChaseCheck')),
                'extension_guard':bit(r.get('ExtensionGuardCheck')),'chase_risk_score':num(r.get('ChaseRiskScore')),'chase_risk_label':str(r.get('ChaseRiskLabel','LOW')),'session_move_pct':num(r.get('SessionMovePct')),'since_trigger_pct':num(r.get('SinceTriggerPct')),'volume_trend':str(r.get('VolumeTrend','NO DATA')),'trigger_anchor_price':num(r.get('TriggerAnchorPrice')),
                'market_regime':str(r.get('MarketRegime','NEUTRAL')),'market_regime_ok':bit(r.get('MarketRegimeCheck')),
                'optimized_stage':opt,'optimized_score':num(r.get('OptimizedScore')),'optimized_match':num(r.get('OptimizedMatchPct')),
                'optimized_model_status':str(r.get('OptimizedModelStatus','')),'optimized_model_id':str(r.get('OptimizedModelID','')),
                'optimized_model_scope':str(r.get('OptimizedModelScope','')),'optimized_model_horizon':num(r.get('OptimizedModelHorizon')),'optimized_oos_lift':num(r.get('OptimizedModelOOSLift')),
                'optimized_hourly_match':num(r.get('HourlyOptimizedMatchPct')),'optimized_hourly_horizon':str(r.get('HourlyOptimizedHorizon','')),
                'model_disagreement':disagreement,'scan_mode':str(config.get('scan_mode','Production 151')),
                'pre_move_stage':str(r.get('PreMoveStage','')),'pre_move_score':num(r.get('PreMoveScore')),
                'pre_move_probability':num(r.get('PreMoveProbabilityPct')),'pre_move_families':str(r.get('PreMoveIndependentFamilies','')),
                'pre_move_features':str(r.get('PreMoveStrongestFeatures','')),'pre_move_best_lift':num(r.get('PreMoveBestOOSLiftX')),
                'pre_move_freshness':str(r.get('PreMoveFreshness','')),
            }
            cols=list(rec.keys());vals=[rec[c] for c in cols];ph=','.join(['?']*len(cols))
            con.execute(f"INSERT OR REPLACE INTO snapshots({','.join(cols)}) VALUES({ph})",vals)
        con.commit();con.close();_feedback_schedule_remote_push_v630()
    except Exception:
        pass


def _resolve_first_event_intraday_v610(ticker,event_date,target1,invalidation):
    """Resolve target-vs-invalidation order inside an ambiguous daily candle.
    Prefer 15m; fall back to 1h. If both levels occur in one intraday bar, remain ambiguous.
    """
    for interval in ('15m','1h'):
        try:
            q=confirmed_intraday_bars(fetch_ohlcv(str(ticker),'1mo',interval))
            if q is None or q.empty:continue
            idx=pd.DatetimeIndex(q.index)
            mask=np.array([x.date()==event_date for x in idx])
            day=q.loc[mask]
            if day.empty:continue
            for _,bar in day.iterrows():
                ht=bool(np.isfinite(target1) and float(bar.High)>=target1)
                hi=bool(np.isfinite(invalidation) and float(bar.Low)<=invalidation)
                if ht and hi:return f'AMBIGUOUS SAME {interval.upper()} BAR'
                if hi:return f'INVALIDATION FIRST ({interval})'
                if ht:return f'TARGET1 FIRST ({interval})'
        except Exception:
            continue
    return 'AMBIGUOUS SAME DAY — INTRADAY UNAVAILABLE'


def _feedback_evaluate_due_v600(max_snapshots=30):
    """Evaluate due 1D/2D/3D/5D outcomes. Runs safely in the background after scans."""
    try:
        con=_feedback_conn_v600(); snap=pd.read_sql_query("SELECT s.* FROM snapshots s LEFT JOIN outcomes o ON o.snapshot_id=s.id GROUP BY s.id HAVING COUNT(DISTINCT o.horizon)<4 ORDER BY s.id ASC LIMIT 50000",con)
        # V6.1.1 migration: revisit old daily-ambiguous outcomes and resolve event order
        # with 15m/1h bars when those bars are still available from the provider.
        try:
            amb=pd.read_sql_query("SELECT o.snapshot_id,o.horizon,o.first_event,s.ticker,s.target1,s.invalidation,s.ts_utc FROM outcomes o JOIN snapshots s ON s.id=o.snapshot_id WHERE o.first_event LIKE 'AMBIGUOUS SAME DAY%' ORDER BY o.evaluated_at DESC LIMIT 120",con)
            for _,ar in amb.iterrows():
                try:
                    market0=_market_for_ticker_v612(str(ar.ticker)); scan_date=_snapshot_market_date_v612(ar.ts_utc,market0,str(ar.ticker)); d0=fetch_ohlcv(str(ar.ticker),'1mo','1d')
                    if d0 is None or d0.empty:continue
                    z0=d0.copy(); future0=_completed_future_daily_bars_v612(z0,scan_date,market0,int(ar.horizon))
                    t1=float(ar.target1) if pd.notna(ar.target1) else np.nan; inv=float(ar.invalidation) if pd.notna(ar.invalidation) else np.nan
                    for _,bar0 in future0.iterrows():
                        ht=bool(np.isfinite(t1) and float(bar0.High)>=t1); hi=bool(np.isfinite(inv) and float(bar0.Low)<=inv)
                        if ht and hi:
                            resolved=_resolve_first_event_intraday_v610(str(ar.ticker),pd.Timestamp(bar0.name).date(),t1,inv)
                            con.execute('UPDATE outcomes SET first_event=? WHERE snapshot_id=? AND horizon=?',(resolved,int(ar.snapshot_id),int(ar.horizon)));break
                        if hi:
                            con.execute('UPDATE outcomes SET first_event=? WHERE snapshot_id=? AND horizon=?',('INVALIDATION FIRST (daily)',int(ar.snapshot_id),int(ar.horizon)));break
                        if ht:
                            con.execute('UPDATE outcomes SET first_event=? WHERE snapshot_id=? AND horizon=?',('TARGET1 FIRST (daily)',int(ar.snapshot_id),int(ar.horizon)));break
                except Exception:continue
            con.commit()
        except Exception:pass
        done=pd.read_sql_query('SELECT snapshot_id,horizon FROM outcomes',con)
        done_set=set(zip(done.snapshot_id.astype(int),done.horizon.astype(int))) if not done.empty else set()
        evaluated=0
        for _,r in snap.iterrows():
            if evaluated>=max_snapshots:break
            market=_feedback_market_key_v612(r.get('market',''),str(r.ticker))
            scan_date=_snapshot_market_date_v612(r.ts_utc,market,str(r.ticker))
            pending_h=[h for h in (1,2,3,5) if (int(r.id),h) not in done_set]
            if not pending_h:continue
            # Source of truth is the number of COMPLETE future exchange daily bars, not
            # elapsed calendar days. This prevents Saturday/Sunday/holidays from maturing 1D.
            d=fetch_ohlcv(str(r.ticker),'1mo','1d')
            if d is None or d.empty:continue
            z=d.copy(); completed=_completed_future_daily_bars_v612(z,scan_date,market)
            if completed is None or completed.empty:continue
            due=[h for h in pending_h if len(completed)>=h]
            if not due:continue
            for h in due:
                future=completed.head(h)
                if len(future)<h:continue
                base=float(r.price) if pd.notna(r.price) else np.nan
                if not np.isfinite(base) or base<=0:continue
                endret=float(future.Close.iloc[-1]/base-1); mfe=float(future.High.max()/base-1); mae=float(future.Low.min()/base-1)
                t1=float(r.target1) if pd.notna(r.target1) else np.nan; t2=float(r.target2) if pd.notna(r.target2) else np.nan; inv=float(r.invalidation) if pd.notna(r.invalidation) else np.nan
                t1h=bool(np.isfinite(t1) and (future.High>=t1).any()); t2h=bool(np.isfinite(t2) and (future.High>=t2).any()); invh=bool(np.isfinite(inv) and (future.Low<=inv).any())
                first='NONE'
                for _,bar in future.iterrows():
                    hit_t=bool(np.isfinite(t1) and float(bar.High)>=t1); hit_i=bool(np.isfinite(inv) and float(bar.Low)<=inv)
                    if hit_t and hit_i:first=_resolve_first_event_intraday_v610(str(r.ticker),pd.Timestamp(bar.name).date(),t1,inv); break
                    if hit_i:first='INVALIDATION FIRST (daily)'; break
                    if hit_t:first='TARGET1 FIRST (daily)'; break
                con.execute('INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?,?,?,?,?,?,?)',(int(r.id),h,datetime.utcnow().replace(microsecond=0).isoformat()+'Z',endret,mfe,mae,int(t1h),int(t2h),int(invh),first))
                con.commit(); evaluated+=1; done_set.add((int(r.id),h))
                if evaluated>=max_snapshots:break
        con.close()
        if evaluated:_feedback_schedule_remote_push_v630()
        return evaluated
    except Exception:return 0


def _feedback_frames_v600():
    try:
        con=_feedback_conn_v600(); sn=pd.read_sql_query('SELECT * FROM snapshots ORDER BY id DESC',con); oc=pd.read_sql_query('SELECT * FROM outcomes ORDER BY evaluated_at DESC',con); con.close(); return sn,oc
    except Exception:return pd.DataFrame(),pd.DataFrame()


def _feedback_replay_active_indicators_v630(r):
    """Causal DAILY indicator states used by Historical Replay.

    V6.3.1 keeps each state observable at the historical signal close.  These are
    research features only; unavailable historical 15m/1h confirmations are never
    fabricated.
    """
    def fin(k,default=np.nan):
        try:
            x=float(r.get(k,default));return x if np.isfinite(x) else default
        except Exception:return default
    p=fin('Close');e9=fin('ema9');e20=fin('ema20');vw=fin('vwap');mh=fin('macd_hist');ms=fin('macd_hist_slope')
    rv=fin('time_adjusted_rvol',fin('robust_volume_ratio'));va=fin('vol_accel');cmf=fin('cmf20');obv=fin('obv_slope5');ad=fin('ad_slope5');rs=fin('rs20');rsi=fin('rsi14');cl=fin('close_location');adx=fin('adx14');br=fin('breakout20_pct');ft=fin('fresh_transition_count',0)
    try:dv=directional_volume_row(r) or {}
    except Exception:dv={}
    bull=float(dv.get('bullish',0) or 0);bear=float(dv.get('bearish',0) or 0)
    states=[
        ('EMA9/20 bullish cross',fin('ema9_cross_up',0)>0),
        ('MACD bullish cross',fin('macd_cross_up',0)>0),
        ('MACD histogram turn positive',fin('macd_hist_turn_pos',0)>0),
        ('VWAP reclaim',fin('vwap_cross_up',0)>0),
        ('EMA9 > EMA20',np.isfinite(e9) and np.isfinite(e20) and e9>e20),
        ('Price > EMA20',np.isfinite(p) and np.isfinite(e20) and p>e20),
        ('Price > VWAP',np.isfinite(p) and np.isfinite(vw) and p>vw),
        ('MACD histogram positive',np.isfinite(mh) and mh>0),
        ('MACD strengthening',np.isfinite(ms) and ms>0),
        ('RSI 50-70',np.isfinite(rsi) and 50<=rsi<=70),
        ('RVOL >= 1.20',np.isfinite(rv) and rv>=1.20),
        ('Volume acceleration',np.isfinite(va) and va>=1.08),
        ('Directional bullish volume',bull>=.22 and bull>bear),
        ('CMF > 0',np.isfinite(cmf) and cmf>0),
        ('OBV accumulating',np.isfinite(obv) and obv>0),
        ('A/D accumulating',np.isfinite(ad) and ad>0),
        ('Relative strength positive',np.isfinite(rs) and rs>0),
        ('Near 20D breakout',np.isfinite(br) and -3.0<=br<=2.0),
        ('Strong close location',np.isfinite(cl) and cl>=.70),
        ('ADX >= 25',np.isfinite(adx) and adx>=25),
        ('Squeeze release',bool(fin('squeeze_release',0)>0)),
        ('Fresh transitions >= 2',ft>=2),
    ]
    return [name for name,on in states if bool(on)]


def _feedback_replay_setup_v631(r, target_pct, recent_2d_return=np.nan):
    """Daily-only proxy of the live two-layer logic, with correlated signals de-duped.

    No future bar is consulted.  It approximates Independent Families + Freshness +
    Already-Moved/Extension + directional distribution using only the signal close.
    """
    def fin(k,default=np.nan):
        try:
            x=float(r.get(k,default));return x if np.isfinite(x) else default
        except Exception:return default
    active=_feedback_replay_active_indicators_v630(r); aset=set(active)
    try:dv=directional_volume_row(r) or {}
    except Exception:dv={}
    bull=float(dv.get('bullish',0) or 0);bear=float(dv.get('bearish',0) or 0)
    p=fin('Close');e9=fin('ema9');e20=fin('ema20');vw=fin('vwap');atrp=fin('atr_pct');ret1=fin('ret1',0);rv=fin('time_adjusted_rvol',fin('robust_volume_ratio'));cl=fin('close_location',.5);cmf=fin('cmf20',0);obv=fin('obv_slope5',0);ad=fin('ad_slope5',0);ft=fin('fresh_transition_count',0)
    momentum=bool({'MACD bullish cross','MACD histogram turn positive','MACD strengthening','MACD histogram positive'} & aset)
    volume=bool({'RVOL >= 1.20','Volume acceleration'} & aset)
    flow=bool('Directional bullish volume' in aset or sum(x in aset for x in ('CMF > 0','OBV accumulating','A/D accumulating'))>=2)
    relative=bool('Relative strength positive' in aset)
    trend=bool(('EMA9 > EMA20' in aset and 'Price > EMA20' in aset) or 'ADX >= 25' in aset)
    structure=bool({'VWAP reclaim','Price > VWAP','Near 20D breakout','Strong close location','Squeeze release'} & aset)
    transition=bool(ft>=2 or {'EMA9/20 bullish cross','MACD bullish cross','MACD histogram turn positive','VWAP reclaim'} & aset)
    fam={'MOMENTUM':momentum,'VOLUME':volume,'FLOW':flow,'RELATIVE_STRENGTH':relative,'TREND':trend,'STRUCTURE':structure,'TRANSITION_BREADTH':transition}
    families=[k for k,v in fam.items() if v];family_count=len(families)
    target=max(float(target_pct),1e-6)
    recent2=float(recent_2d_return) if np.isfinite(recent_2d_return) else 0.0
    consumed=100.0*max(0.0,ret1,recent2)/target
    atr_abs=p*atrp/100.0 if np.isfinite(p) and np.isfinite(atrp) and atrp>0 else np.nan
    ext=[]
    if np.isfinite(atr_abs) and atr_abs>0:
        for ref in (e9,e20,vw):
            if np.isfinite(ref):ext.append(max(0.0,(p-ref)/atr_abs))
    extension=max(ext) if ext else np.nan
    if consumed>=100 or (np.isfinite(extension) and extension>=1.80):fresh='ALREADY MOVED'
    elif consumed>=60 or (np.isfinite(extension) and extension>=1.10):fresh='LATE'
    elif transition or 'Squeeze release' in aset:fresh='FRESH'
    else:fresh='DEVELOPING'
    distribution=bool((bear>=.22 and bear>bull) or ((ret1<0 and np.isfinite(rv) and rv>=1.20 and cl<.45) and (cmf<0 or obv<0 or ad<0)))
    core_momentum=momentum
    core_volume_flow=bool(volume or flow)
    score=12.0*family_count
    score+=8 if core_momentum else 0
    score+=8 if core_volume_flow else 0
    score+=8 if transition else 0
    score+=5 if relative else 0
    score+=5 if structure else 0
    if fresh=='FRESH':score+=8
    elif fresh=='LATE':score-=22
    elif fresh=='ALREADY MOVED':score-=38
    if distribution:score-=28
    score=float(np.clip(score,0,100))
    candidate_v2=bool(score>=62 and family_count>=3 and core_momentum and core_volume_flow and fresh in ('FRESH','DEVELOPING') and not distribution and consumed<60 and (not np.isfinite(extension) or extension<1.10))
    return {'active':active,'families':families,'family_signature':' + '.join(families),'family_count':family_count,'freshness_state':fresh,'move_consumed_pct':consumed,'extension_atr':extension,'distribution_risk':distribution,'setup_score_v2':score,'candidate_v2':candidate_v2,'core_momentum':core_momentum,'core_volume_flow':core_volume_flow}



def _feedback_replay_indicator_family_v633(name):
    """Map correlated DAILY indicators to one independent research family."""
    m={
        'MACD bullish cross':'MOMENTUM','MACD histogram turn positive':'MOMENTUM','MACD histogram positive':'MOMENTUM','MACD strengthening':'MOMENTUM','RSI 50-70':'MOMENTUM',
        'RVOL >= 1.20':'VOLUME','Volume acceleration':'VOLUME',
        'Directional bullish volume':'FLOW','CMF > 0':'FLOW','OBV accumulating':'FLOW','A/D accumulating':'FLOW',
        'Relative strength positive':'RELATIVE_STRENGTH',
        'EMA9 > EMA20':'TREND','Price > EMA20':'TREND','ADX >= 25':'TREND',
        'VWAP reclaim':'STRUCTURE','Price > VWAP':'STRUCTURE','Near 20D breakout':'STRUCTURE','Strong close location':'STRUCTURE','Squeeze release':'STRUCTURE',
        'EMA9/20 bullish cross':'TRANSITION_BREADTH','Fresh transitions >= 2':'TRANSITION_BREADTH',
    }
    return m.get(str(name),'OTHER')


def _feedback_replay_combination_discovery_v633(events, discovery_fraction=.70, max_discovered=250):
    """Discovery-only combination search + untouched chronological OOS validation.

    Candidate combinations are selected only from the first 70% of signal dates.
    The final 30% is never used for selection and is split into three chronological
    validation folds. Correlated indicators from the same family cannot coexist in
    one combination. This is research-only and never changes Production Entry.
    """
    e=events.copy() if isinstance(events,pd.DataFrame) else pd.DataFrame()
    empty=(pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),e)
    if e.empty:return empty
    ren={'CleanOutcome':'clean_outcome','Indicators':'indicators','Ticker':'ticker','SignalDate':'signal_date','CandidateV2':'candidate_v2','RMultiple':'r_multiple',
         'FreshnessState':'freshness_state','MoveConsumedPct':'move_consumed_pct','ExtensionATR':'extension_atr','DistributionRisk':'distribution_risk'}
    for a,b in ren.items():
        if a in e and b not in e:e[b]=e[a]
    e['_date']=pd.to_datetime(e.get('signal_date'),errors='coerce')
    e['_win']=e.get('clean_outcome',pd.Series('',index=e.index)).astype(str).map({'WIN':1.0,'LOSS':0.0})
    dates=sorted(pd.Series(e.loc[e['_date'].notna(),'_date'].dt.normalize().unique()).dropna().tolist())
    if len(dates)<8:return empty
    split=max(1,min(len(dates)-1,int(math.floor(len(dates)*float(discovery_fraction)))))
    cutoff=pd.Timestamp(dates[split-1]);val_dates=[pd.Timestamp(x) for x in dates[split:]]
    e['ComboPhase']=np.where(e['_date'].dt.normalize()<=cutoff,'DISCOVERY','OOS VALIDATION')
    fresh=e.get('freshness_state',pd.Series('',index=e.index)).fillna('').astype(str).isin(['FRESH','DEVELOPING'])
    consumed=pd.to_numeric(e.get('move_consumed_pct',np.nan),errors='coerce')
    ext=pd.to_numeric(e.get('extension_atr',np.nan),errors='coerce')
    dist=pd.to_numeric(e.get('distribution_risk',0),errors='coerce').fillna(0).eq(1)
    clean=np.isfinite(pd.to_numeric(e['_win'],errors='coerce'))
    eligible=clean & fresh & (~dist) & ((~np.isfinite(consumed)) | (consumed<60)) & ((~np.isfinite(ext)) | (ext<1.10))
    disc=eligible & e['ComboPhase'].eq('DISCOVERY'); val=eligible & e['ComboPhase'].eq('OOS VALIDATION')
    dn=int(disc.sum());vn=int(val.sum())
    if dn<100 or vn<40:return empty
    dbase=float(e.loc[disc,'_win'].mean());vbase=float(e.loc[val,'_win'].mean())

    def split_ind(txt):return [x.strip() for x in str(txt or '').split(' | ') if x.strip() and x.strip().lower()!='nan']
    ind_sets=[set(split_ind(x)) for x in e.get('indicators',pd.Series('',index=e.index)).fillna('').astype(str)]
    disc_idx=np.where(disc.to_numpy())[0];val_idx=np.where(val.to_numpy())[0]
    names=sorted({x for i in disc_idx for x in ind_sets[i] if _feedback_replay_indicator_family_v633(x)!='OTHER'})
    arrays={name:np.fromiter((name in ss for ss in ind_sets),dtype=bool,count=len(e)) for name in names}
    # Discovery-only pool reduction: sufficient occurrence, then at most the three
    # strongest univariate representatives per independent family. Validation is
    # never consulted while building this pool.
    uni=[]
    for name in names:
        m=disc.to_numpy() & arrays[name];n=int(m.sum())
        if n<35:continue
        rate=float(e.loc[m,'_win'].mean());delta=rate-dbase
        uni.append((name,_feedback_replay_indicator_family_v633(name),n,rate,delta,float(delta*math.log1p(n))))
    pool=[]
    for fam in sorted({x[1] for x in uni}):
        cand=sorted([x for x in uni if x[1]==fam],key=lambda x:(x[5],x[2]),reverse=True)[:3]
        pool.extend([x[0] for x in cand])
    pool=sorted(set(pool))
    if len(pool)<2:return empty

    min_disc=max(40,int(.0025*dn)); discovered=[]
    disc_np=disc.to_numpy();val_np=val.to_numpy();wins=e['_win'].to_numpy(float)
    tick=e.get('ticker',pd.Series('',index=e.index)).fillna('').astype(str).to_numpy()
    for k in (2,3,4):
        for combo in combinations(pool,k):
            fams=[_feedback_replay_indicator_family_v633(x) for x in combo]
            if len(set(fams))<k:continue
            m=disc_np.copy()
            for name in combo:m &= arrays[name]
            n=int(m.sum())
            if n<min_disc:continue
            rate=float(np.nanmean(wins[m]));lift=rate/dbase if dbase>0 else np.nan;delta=rate-dbase
            stocks=len(set(tick[m]))
            if stocks<8 or not np.isfinite(lift) or lift<1.08 or delta<.04:continue
            score=float((100*delta)*math.log1p(n)*(1+.08*(k-2)))
            discovered.append({'combo':combo,'families':fams,'n':n,'wins':int(np.nansum(wins[m])),'rate':rate,'lift':lift,'delta':delta,'stocks':stocks,'score':score})
    discovered=sorted(discovered,key=lambda x:(x['score'],x['n']),reverse=True)[:int(max_discovered)]
    if not discovered:return (pd.DataFrame(),pd.DataFrame(),pd.DataFrame([{'Gate':'OOS ELIGIBLE BASELINE','Resolved':vn,'Wins':int(np.nansum(wins[val_np])),'Losses':vn-int(np.nansum(wins[val_np])),'Success Rate %':100*vbase,'Lift vs OOS baseline x':1.0,'Expectancy R':pd.to_numeric(e.loc[val,'r_multiple'],errors='coerce').mean(),'Meaning':'Fresh/not-extended/no-distribution OOS rows'}]),e.drop(columns=['_date','_win'],errors='ignore'))

    # Three untouched chronological OOS folds.
    fold_groups=[list(x) for x in np.array_split(np.array(val_dates,dtype='datetime64[ns]'),3) if len(x)]
    combo_rows=[];fold_rows=[]
    top_candidate=discovered[:25]
    hc_discovery=[x for x in discovered if x['n']>=60 and x['rate']>=max(.60,dbase+.08) and x['lift']>=1.15 and x['stocks']>=10]
    tier70=[x for x in discovered if x['n']>=40 and x['rate']>=.70 and x['lift']>=1.25 and x['stocks']>=8]
    row_match=np.zeros(len(e),dtype=int);row_hc=np.zeros(len(e),dtype=bool);row_70=np.zeros(len(e),dtype=bool)
    best_rate=np.full(len(e),np.nan);best_lift=np.full(len(e),np.nan);best_sig=np.array(['']*len(e),dtype=object)

    def cmask(combo,base_mask=None):
        m=np.ones(len(e),dtype=bool) if base_mask is None else base_mask.copy()
        for name in combo:m &= arrays[name]
        return m
    top_set={x['combo'] for x in top_candidate};hc_set={x['combo'] for x in hc_discovery};tier70_set={x['combo'] for x in tier70}
    for rank,x in enumerate(discovered,1):
        m_all=cmask(x['combo']);mv=val_np & m_all;n=int(mv.sum());wr=int(np.nansum(wins[mv])) if n else 0;rate=float(np.nanmean(wins[mv])) if n else np.nan
        lift=rate/vbase if n and vbase>0 else np.nan;delta=rate-vbase if n else np.nan;vstocks=len(set(tick[mv])) if n else 0
        pos=0;usable=0
        sig=' + '.join(x['combo'])
        for fi,fd in enumerate(fold_groups,1):
            fd_norm={pd.Timestamp(q).normalize() for q in fd}
            fm=val_np & e['_date'].dt.normalize().isin(fd_norm).to_numpy();fbn=int(fm.sum());fb=float(np.nanmean(wins[fm])) if fbn else np.nan
            mm=fm & m_all;fn=int(mm.sum());fw=int(np.nansum(wins[mm])) if fn else 0;fr=float(np.nanmean(wins[mm])) if fn else np.nan;fl=fr/fb if fn and np.isfinite(fb) and fb>0 else np.nan;dd=fr-fb if fn and np.isfinite(fb) else np.nan
            if fn>=10:
                usable+=1
                if np.isfinite(fl) and fl>=1.03 and np.isfinite(dd) and dd>0:pos+=1
            fold_rows.append({'Combination':sig,'Fold':fi,'Resolved':fn,'Wins':fw,'Success Rate %':100*fr if np.isfinite(fr) else np.nan,'Fold Baseline %':100*fb if np.isfinite(fb) else np.nan,'Lift x':fl,'Delta pp':100*dd if np.isfinite(dd) else np.nan,'Stocks':len(set(tick[mm])) if fn else 0})
        gap=100*abs(rate-x['rate']) if n and np.isfinite(rate) else np.nan
        if n<25:status='LOW SAMPLE'
        elif np.isfinite(lift) and lift>=1.15 and delta>=.05 and pos>=2:status='OOS STRONG'
        elif np.isfinite(lift) and lift>=1.08 and delta>=.03 and pos>=2:status='OOS POSITIVE'
        elif np.isfinite(lift) and (lift<=.95 or delta<=-.02):status='FAILED'
        else:status='OOS MIXED'
        tier='70% DISCOVERY TIER' if x['combo'] in tier70_set else ('HIGH-CONFIDENCE DISCOVERY' if x['combo'] in hc_set else 'DISCOVERED')
        combo_rows.append({'Discovery Rank':rank,'Combination':sig,'Size':len(x['combo']),'Families':' + '.join(x['families']),'Discovery N':x['n'],'Discovery Wins':x['wins'],'Discovery Success %':100*x['rate'],'Discovery Baseline %':100*dbase,'Discovery Lift x':x['lift'],'Discovery Delta pp':100*x['delta'],'Discovery Stocks':x['stocks'],'Discovery Score':x['score'],'Validation N':n,'Validation Wins':wr,'Validation Success %':100*rate if np.isfinite(rate) else np.nan,'Validation Baseline %':100*vbase,'Validation Lift x':lift,'Validation Delta pp':100*delta if np.isfinite(delta) else np.nan,'Validation Stocks':vstocks,'Positive Validation Folds':pos,'Usable Validation Folds':usable,'Stability Gap pp':gap,'Research Tier':tier,'OOS Status':status})
        if x['combo'] in top_set:
            match=val_np & m_all;row_match[match]+=1
            better=match & ((~np.isfinite(best_rate)) | (100*x['rate']>best_rate))
            best_rate[better]=100*x['rate'];best_lift[better]=x['lift'];best_sig[better]=sig
        if x['combo'] in hc_set:row_hc |= (val_np & m_all)
        if x['combo'] in tier70_set:row_70 |= (val_np & m_all)

    e['ComboCandidateV3']=val_np & (row_match>0);e['ComboHighConfidenceV3']=row_hc;e['Combo70Research']=row_70;e['ComboMatchCount']=row_match;e['ComboBestSignature']=best_sig;e['ComboBestDiscoveryRate']=best_rate;e['ComboBestDiscoveryLift']=best_lift
    # OOS gate comparison uses only the untouched validation section.
    def gate(label,mask,meaning):
        m=val_np & mask;n=int(m.sum());w=int(np.nansum(wins[m])) if n else 0;rate=float(np.nanmean(wins[m])) if n else np.nan
        rr=pd.to_numeric(e.loc[m,'r_multiple'],errors='coerce').mean() if n else np.nan
        return {'Gate':label,'Resolved':n,'Wins':w,'Losses':n-w,'Success Rate %':100*rate if np.isfinite(rate) else np.nan,'Lift vs OOS baseline x':rate/vbase if np.isfinite(rate) and vbase>0 else np.nan,'Delta vs OOS baseline pp':100*(rate-vbase) if np.isfinite(rate) else np.nan,'Expectancy R':rr,'Meaning':meaning}
    v2=pd.to_numeric(e.get('candidate_v2',0),errors='coerce').fillna(0).eq(1).to_numpy()
    gate_rows=[gate('OOS ELIGIBLE BASELINE',np.ones(len(e),bool),'Fresh/not-extended/no-distribution rows in untouched final 30%'),gate('OOS V2 CANDIDATE',v2,'Existing V2 gate, evaluated only in untouched final 30%'),gate('OOS COMBO V3',row_match>0,'Top 25 combinations selected only in Discovery'),gate('OOS COMBO HIGH CONFIDENCE',row_hc,'Discovery-only >=60% / lift >=1.15 / sample+breadth gate'),gate('OOS 70% RESEARCH TIER',row_70,'Combinations that reached >=70% in Discovery; OOS result is not used to select them')]
    combo_df=pd.DataFrame(combo_rows)
    if not combo_df.empty:
        order={'OOS STRONG':0,'OOS POSITIVE':1,'OOS MIXED':2,'FAILED':3,'LOW SAMPLE':4};combo_df['_o']=combo_df['OOS Status'].map(order).fillna(9);combo_df=combo_df.sort_values(['_o','Validation Lift x','Validation N','Discovery Rank'],ascending=[True,False,False,True]).drop(columns=['_o']).reset_index(drop=True)
    return combo_df,pd.DataFrame(fold_rows),pd.DataFrame(gate_rows),e.drop(columns=['_date','_win'],errors='ignore')

def _feedback_replay_apply_meta_v631(df):
    """Strict-date rolling empirical-Bayes meta probability.

    V6.3.2 keeps the V6.3.1 mathematics but replaces the quadratic replay
    implementation with cumulative sufficient statistics.  Every probability
    for date D still uses clean outcomes from dates strictly before D, so
    same-day cross-sectional outcomes cannot leak into one another.
    """
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:return df
    z=df.copy();z['_date']=pd.to_datetime(z['SignalDate'],errors='coerce');z=z.sort_values(['_date','Ticker']).reset_index(drop=True)
    for c,v in [('MetaProbability',np.nan),('MetaSample',0),('MetaLift',np.nan),('HighConfidence',False)]:z[c]=v

    # Pre-compute the exact keys used by V6.3.1.  We then maintain cumulative
    # (count, wins) dictionaries and update them only after a complete signal
    # date has been scored.  This is O(N) instead of repeatedly rebuilding and
    # filtering the entire prior history for every replay row.
    z['_meta_family_signature']=z.get('FamilySignature',pd.Series('',index=z.index)).fillna('').astype(str)
    z['_meta_freshness']=z.get('FreshnessState',pd.Series('',index=z.index)).fillna('').astype(str)
    z['_meta_score_bucket']=(pd.to_numeric(z.get('SetupScoreV2',0),errors='coerce').fillna(0)//10).astype(int)
    cm=z.get('CoreMomentum',pd.Series(False,index=z.index)).fillna(False).astype(bool)
    cv=z.get('CoreVolumeFlow',pd.Series(False,index=z.index)).fillna(False).astype(bool)
    z['_meta_core_pattern']=cm.astype(int).astype(str)+cv.astype(int).astype(str)

    # V6.3.1 attempted to include a 'FamilyCount' meta feature, but the replay
    # frame exposes 'IndependentFamilyCount'; therefore that feature was never
    # active in the published V6.3.1 probabilities.  Keep it out here so this
    # hotfix is performance-only and reproduces prior results exactly.
    key_cols=('_meta_family_signature','_meta_freshness','_meta_score_bucket','_meta_core_pattern')
    stats={c:{} for c in key_cols}
    global_n=0;global_wins=0.0

    for _,idxs in z.groupby('_date',sort=True,dropna=False).groups.items():
        idxs=list(idxs)
        n=int(global_n)
        if n:
            gw=float(global_wins/n);global_p=float((global_wins+8*.50)/(n+8))
        else:
            gw=np.nan;global_p=.50

        for idx in idxs:
            r=z.loc[idx];estimates=[];supports=[]
            if n:
                for col in key_cols:
                    key=r.get(col)
                    nn,wwins=stats[col].get(key,(0,0.0))
                    if nn:
                        pp=float((wwins+12*global_p)/(nn+12));estimates.append(pp);supports.append(int(nn))
            if estimates:
                weights=np.asarray([min(80,max(5,x)) for x in supports],float)
                p=float((np.dot(weights,np.asarray(estimates,float))+20*global_p)/(weights.sum()+20))
                support=int(max(supports))
            else:
                p=float(global_p);support=int(n)
            z.at[idx,'MetaProbability']=100*p;z.at[idx,'MetaSample']=support;z.at[idx,'MetaLift']=p/gw if np.isfinite(gw) and gw>0 else np.nan
            hc=bool(r.get('CandidateV2',False) and float(r.get('SetupScoreV2',0))>=72 and int(r.get('IndependentFamilyCount',0) or 0)>=4 and str(r.get('FreshnessState',''))=='FRESH' and float(r.get('MoveConsumedPct',999))<45 and not bool(r.get('DistributionRisk',False)) and support>=50 and p>=.65)
            z.at[idx,'HighConfidence']=hc

        # Strict-date causality: today's outcomes become available only after every
        # row on this date has received its probability.
        for idx in idxs:
            outcome=str(z.at[idx,'CleanOutcome'])
            if outcome not in ('WIN','LOSS'):continue
            win=1.0 if outcome=='WIN' else 0.0
            global_n+=1;global_wins+=win
            for col in key_cols:
                key=z.at[idx,col];nn,wwins=stats[col].get(key,(0,0.0));stats[col][key]=(nn+1,wwins+win)

    return z.drop(columns=['_date',*key_cols],errors='ignore')


def _feedback_store_replay_v630(run_id,rows,cfg,successful_tickers,combinations_df=None,combo_folds_df=None):
    con=_feedback_conn_v600()
    try:
        con.execute('DELETE FROM replay_events WHERE run_id=?',(str(run_id),))
        cols=['run_id','ticker','market','signal_date','price','quant_score','early_score','entry_score','atr_pct','target1','invalidation','end_return','max_favorable','max_adverse','first_event','clean_outcome','indicators','candidate','legacy_candidate','candidate_v2','high_confidence','family_signature','family_count','freshness_state','move_consumed_pct','extension_atr','distribution_risk','setup_score_v2','meta_probability','meta_sample','meta_lift','r_multiple','recent_2d_return','core_momentum','core_volume_flow','candidate_rule_version','combo_phase','combo_candidate_v3','combo_high_confidence_v3','combo_70_research','combo_match_count','combo_best_signature','combo_best_discovery_rate','combo_best_discovery_lift']
        vals=[]
        for r in rows:
            vals.append((str(run_id),str(r.get('Ticker','')),str(r.get('Market','')),str(r.get('SignalDate','')),r.get('Price'),r.get('QuantScore'),r.get('EarlyScore'),r.get('EntryScore'),r.get('ATRPct'),r.get('Target1'),r.get('Invalidation'),r.get('EndReturn'),r.get('MFE'),r.get('MAE'),str(r.get('FirstEvent','')),str(r.get('CleanOutcome','')),str(r.get('Indicators','')),int(bool(r.get('CandidateV2',r.get('Candidate',False)))),int(bool(r.get('LegacyCandidate',False))),int(bool(r.get('CandidateV2',False))),int(bool(r.get('HighConfidence',False))),str(r.get('FamilySignature','')),int(r.get('IndependentFamilyCount',0) or 0),str(r.get('FreshnessState','')),r.get('MoveConsumedPct'),r.get('ExtensionATR'),int(bool(r.get('DistributionRisk',False))),r.get('SetupScoreV2'),r.get('MetaProbability'),int(r.get('MetaSample',0) or 0),r.get('MetaLift'),r.get('RMultiple'),r.get('Recent2DReturn'),int(bool(r.get('CoreMomentum',False))),int(bool(r.get('CoreVolumeFlow',False))),str(r.get('CandidateRuleVersion','V6.3.3')),str(r.get('ComboPhase','')),int(bool(r.get('ComboCandidateV3',False))),int(bool(r.get('ComboHighConfidenceV3',False))),int(bool(r.get('Combo70Research',False))),int(r.get('ComboMatchCount',0) or 0),str(r.get('ComboBestSignature','')),r.get('ComboBestDiscoveryRate'),r.get('ComboBestDiscoveryLift')))
        if vals:
            q=','.join(['?']*len(cols));con.executemany(f"INSERT OR REPLACE INTO replay_events({','.join(cols)}) VALUES({q})",vals)
        con.execute('DELETE FROM replay_combinations WHERE run_id=?',(str(run_id),))
        con.execute('DELETE FROM replay_combo_folds WHERE run_id=?',(str(run_id),))
        if isinstance(combinations_df,pd.DataFrame) and not combinations_df.empty:
            for _,r in combinations_df.iterrows():
                con.execute("INSERT OR REPLACE INTO replay_combinations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                    str(run_id),str(r.get('Combination','')),int(r.get('Size',0) or 0),str(r.get('Families','')),int(r.get('Discovery Rank',0) or 0),float(r.get('Discovery Score',np.nan)) if pd.notna(r.get('Discovery Score')) else None,
                    int(r.get('Discovery N',0) or 0),int(r.get('Discovery Wins',0) or 0),float(r.get('Discovery Success %',np.nan)) if pd.notna(r.get('Discovery Success %')) else None,float(r.get('Discovery Baseline %',np.nan)) if pd.notna(r.get('Discovery Baseline %')) else None,float(r.get('Discovery Lift x',np.nan)) if pd.notna(r.get('Discovery Lift x')) else None,float(r.get('Discovery Delta pp',np.nan)) if pd.notna(r.get('Discovery Delta pp')) else None,int(r.get('Discovery Stocks',0) or 0),
                    int(r.get('Validation N',0) or 0),int(r.get('Validation Wins',0) or 0),float(r.get('Validation Success %',np.nan)) if pd.notna(r.get('Validation Success %')) else None,float(r.get('Validation Baseline %',np.nan)) if pd.notna(r.get('Validation Baseline %')) else None,float(r.get('Validation Lift x',np.nan)) if pd.notna(r.get('Validation Lift x')) else None,float(r.get('Validation Delta pp',np.nan)) if pd.notna(r.get('Validation Delta pp')) else None,int(r.get('Validation Stocks',0) or 0),
                    int(r.get('Positive Validation Folds',0) or 0),int(r.get('Usable Validation Folds',0) or 0),float(r.get('Stability Gap pp',np.nan)) if pd.notna(r.get('Stability Gap pp')) else None,str(r.get('Research Tier','')),str(r.get('OOS Status',''))))
        if isinstance(combo_folds_df,pd.DataFrame) and not combo_folds_df.empty:
            for _,r in combo_folds_df.iterrows():
                con.execute("INSERT OR REPLACE INTO replay_combo_folds VALUES(?,?,?,?,?,?,?,?,?,?)",(
                    str(run_id),str(r.get('Combination','')),int(r.get('Fold',0) or 0),int(r.get('Resolved',0) or 0),int(r.get('Wins',0) or 0),float(r.get('Success Rate %',np.nan)) if pd.notna(r.get('Success Rate %')) else None,float(r.get('Fold Baseline %',np.nan)) if pd.notna(r.get('Fold Baseline %')) else None,float(r.get('Lift x',np.nan)) if pd.notna(r.get('Lift x')) else None,float(r.get('Delta pp',np.nan)) if pd.notna(r.get('Delta pp')) else None,int(r.get('Stocks',0) or 0)))
        clean=sum(1 for r in rows if str(r.get('CleanOutcome')) in ('WIN','LOSS'))
        con.execute('INSERT OR REPLACE INTO replay_runs(run_id,created_at,scope,history,target_pct,horizon_days,sample_every,requested_tickers,successful_tickers,event_rows,clean_rows) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (str(run_id),datetime.utcnow().replace(microsecond=0).isoformat()+'Z',str(cfg.get('scope','')),str(cfg.get('history','')),float(cfg.get('target_pct',.05)),int(cfg.get('horizon_days',3)),int(cfg.get('sample_every',5)),len(cfg.get('tickers',[])),int(successful_tickers),len(rows),clean))
        old_runs=[x[0] for x in con.execute('SELECT run_id FROM replay_runs ORDER BY created_at DESC LIMIT -1 OFFSET 5').fetchall()]
        for old_id in old_runs:
            con.execute('DELETE FROM replay_events WHERE run_id=?',(str(old_id),));con.execute('DELETE FROM replay_combinations WHERE run_id=?',(str(old_id),));con.execute('DELETE FROM replay_combo_folds WHERE run_id=?',(str(old_id),));con.execute('DELETE FROM replay_runs WHERE run_id=?',(str(old_id),))
        con.commit()
    finally:con.close()
    _feedback_schedule_remote_push_v630()


def _feedback_replay_frames_v630(latest_only=True):
    try:
        con=_feedback_conn_v600();runs=pd.read_sql_query('SELECT * FROM replay_runs ORDER BY created_at DESC',con)
        if latest_only and not runs.empty:
            rid=str(runs.iloc[0]['run_id']);ev=pd.read_sql_query('SELECT * FROM replay_events WHERE run_id=? ORDER BY signal_date DESC,ticker',con,params=(rid,))
        else:ev=pd.read_sql_query('SELECT * FROM replay_events ORDER BY signal_date DESC,ticker',con)
        con.close();return runs,ev
    except Exception:return pd.DataFrame(),pd.DataFrame()



def _feedback_replay_combo_frames_v633(latest_only=True):
    try:
        con=_feedback_conn_v600();runs=pd.read_sql_query('SELECT * FROM replay_runs ORDER BY created_at DESC',con)
        if latest_only and not runs.empty:
            rid=str(runs.iloc[0]['run_id']);c=pd.read_sql_query('SELECT * FROM replay_combinations WHERE run_id=? ORDER BY discovery_rank',con,params=(rid,));f=pd.read_sql_query('SELECT * FROM replay_combo_folds WHERE run_id=? ORDER BY combination,fold',con,params=(rid,))
        else:
            c=pd.read_sql_query('SELECT * FROM replay_combinations ORDER BY run_id,discovery_rank',con);f=pd.read_sql_query('SELECT * FROM replay_combo_folds ORDER BY run_id,combination,fold',con)
        con.close()
        ren={'combination':'Combination','combo_size':'Size','families':'Families','discovery_rank':'Discovery Rank','discovery_score':'Discovery Score','discovery_n':'Discovery N','discovery_wins':'Discovery Wins','discovery_success':'Discovery Success %','discovery_baseline':'Discovery Baseline %','discovery_lift':'Discovery Lift x','discovery_delta':'Discovery Delta pp','discovery_stocks':'Discovery Stocks','validation_n':'Validation N','validation_wins':'Validation Wins','validation_success':'Validation Success %','validation_baseline':'Validation Baseline %','validation_lift':'Validation Lift x','validation_delta':'Validation Delta pp','validation_stocks':'Validation Stocks','positive_folds':'Positive Validation Folds','usable_folds':'Usable Validation Folds','stability_gap':'Stability Gap pp','research_tier':'Research Tier','oos_status':'OOS Status'}
        if not c.empty:c=c.rename(columns=ren)
        fren={'combination':'Combination','fold':'Fold','resolved':'Resolved','wins':'Wins','success_rate':'Success Rate %','baseline_rate':'Fold Baseline %','lift':'Lift x','delta_pp':'Delta pp','stocks':'Stocks'}
        if not f.empty:f=f.rename(columns=fren)
        return c,f
    except Exception:return pd.DataFrame(),pd.DataFrame()

def _feedback_replay_scorecards_v631(events):
    """V6.3.1: baseline, V2 gate, High Confidence, indicators, stocks, calibration."""
    e=events.copy() if isinstance(events,pd.DataFrame) else pd.DataFrame()
    if e.empty:return (pd.DataFrame(),)*5
    # Normalize either live worker column names or SQLite snake_case names.
    ren={'CleanOutcome':'clean_outcome','Indicators':'indicators','Ticker':'ticker','MFE':'max_favorable','MAE':'max_adverse','EndReturn':'end_return','CandidateV2':'candidate_v2','LegacyCandidate':'legacy_candidate','HighConfidence':'high_confidence','RMultiple':'r_multiple','MetaProbability':'meta_probability','MetaSample':'meta_sample','FamilySignature':'family_signature','IndependentFamilyCount':'family_count','FreshnessState':'freshness_state','SetupScoreV2':'setup_score_v2'}
    for a,b in ren.items():
        if a in e and b not in e:e[b]=e[a]
    clean=e[e.get('clean_outcome',pd.Series('',index=e.index)).astype(str).isin(['WIN','LOSS'])].copy();clean['Win']=clean['clean_outcome'].eq('WIN').astype(float) if not clean.empty else np.nan
    def bitcol(name):return pd.to_numeric(e.get(name,0),errors='coerce').fillna(0).eq(1)
    all_clean=clean
    legacy=clean[pd.to_numeric(clean.get('legacy_candidate',0),errors='coerce').fillna(0).eq(1)] if not clean.empty else clean
    cand=clean[pd.to_numeric(clean.get('candidate_v2',clean.get('candidate',0)),errors='coerce').fillna(0).eq(1)] if not clean.empty else clean
    high=clean[pd.to_numeric(clean.get('high_confidence',0),errors='coerce').fillna(0).eq(1)] if not clean.empty else clean
    def stats(g):
        n=len(g);w=int(g['Win'].sum()) if n else 0;rate=100*w/n if n else np.nan;er=float(pd.to_numeric(g.get('r_multiple'),errors='coerce').mean()) if n and 'r_multiple' in g else np.nan
        return n,w,n-w,rate,er
    bn,bw,bl,br,be=stats(all_clean);ln,lw,ll,lr,le=stats(legacy);cn,cw,cl,cr,ce=stats(cand);hn,hw,hl,hr,he=stats(high)
    headline=pd.DataFrame([{
        'All Clean Baseline %':br,'All Clean N':bn,
        'Legacy Candidate %':lr,'Legacy Resolved':ln,'Legacy Lift x':lr/br if np.isfinite(lr) and np.isfinite(br) and br>0 else np.nan,
        'V2 Candidate Success %':cr,'V2 Candidate Resolved':cn,'V2 Wins':cw,'V2 Losses':cl,'V2 Lift x':cr/br if np.isfinite(cr) and np.isfinite(br) and br>0 else np.nan,'V2 Delta pp':cr-br if np.isfinite(cr) and np.isfinite(br) else np.nan,'V2 Expectancy R':ce,
        'High Confidence Success %':hr,'High Confidence Resolved':hn,'HC Wins':hw,'HC Losses':hl,'HC Lift x':hr/br if np.isfinite(hr) and np.isfinite(br) and br>0 else np.nan,'HC Delta pp':hr-br if np.isfinite(hr) and np.isfinite(br) else np.nan,'HC Expectancy R':he,
        'Definition':'Causal DAILY replay V2. High Confidence requires independent families + fresh/not-extended + no distribution + >=65% causal meta probability with >=50 prior matching observations.'
    }])
    gates=pd.DataFrame([
        {'Gate':'ALL CLEAN BASELINE','Resolved':bn,'Wins':bw,'Losses':bl,'Success Rate %':br,'Lift vs All x':1.0 if bn else np.nan,'Expectancy R':be,'Meaning':'All sampled historical rows'},
        {'Gate':'LEGACY V6.3.0','Resolved':ln,'Wins':lw,'Losses':ll,'Success Rate %':lr,'Lift vs All x':lr/br if np.isfinite(lr) and np.isfinite(br) and br>0 else np.nan,'Expectancy R':le,'Meaning':'Old score-only candidate rule for audit'},
        {'Gate':'V2 CANDIDATE','Resolved':cn,'Wins':cw,'Losses':cl,'Success Rate %':cr,'Lift vs All x':cr/br if np.isfinite(cr) and np.isfinite(br) and br>0 else np.nan,'Expectancy R':ce,'Meaning':'Independent families + freshness + extension/distribution guards'},
        {'Gate':'HIGH CONFIDENCE','Resolved':hn,'Wins':hw,'Losses':hl,'Success Rate %':hr,'Lift vs All x':hr/br if np.isfinite(hr) and np.isfinite(br) and br>0 else np.nan,'Expectancy R':he,'Meaning':'V2 + strictly-prior causal Meta Probability >=65%; quality over quantity'},
    ])
    indicators=[];base=float(all_clean['Win'].mean()) if not all_clean.empty else np.nan
    if not all_clean.empty and 'indicators' in all_clean:
        def split_ind(txt):return [x.strip() for x in str(txt or '').split(' | ') if x.strip() and x.strip().lower()!='nan']
        names=sorted({z for txt in all_clean['indicators'].fillna('').astype(str) for z in split_ind(txt)})
        for name in names:
            mask=all_clean['indicators'].fillna('').astype(str).apply(lambda txt:name in split_ind(txt));g=all_clean[mask];n=len(g)
            if n<5:continue
            rate=float(g['Win'].mean());lift=rate/base if np.isfinite(base) and base>0 else np.nan;delta=100*(rate-base) if np.isfinite(base) else np.nan
            status='LOW SAMPLE' if n<20 else ('WORKED' if np.isfinite(lift) and lift>=1.05 and delta>=2 else ('FAILED' if np.isfinite(lift) and lift<=.95 and delta<=-2 else 'MIXED'))
            indicators.append({'Type':'Indicator','Indicator / Family':name,'Resolved':n,'Success Rate %':100*rate,'All-row Baseline %':100*base if np.isfinite(base) else np.nan,'Lift x':lift,'Delta pp':delta,'Status':status})
    if not all_clean.empty and 'family_signature' in all_clean:
        fam_names=['MOMENTUM','VOLUME','FLOW','RELATIVE_STRENGTH','TREND','STRUCTURE','TRANSITION_BREADTH']
        fs=all_clean['family_signature'].fillna('').astype(str)
        for fam in fam_names:
            g=all_clean[fs.str.contains(fam,regex=False)];n=len(g)
            if n<5:continue
            rate=float(g['Win'].mean());lift=rate/base if np.isfinite(base) and base>0 else np.nan;delta=100*(rate-base) if np.isfinite(base) else np.nan
            status='LOW SAMPLE' if n<20 else ('WORKED' if np.isfinite(lift) and lift>=1.05 and delta>=2 else ('FAILED' if np.isfinite(lift) and lift<=.95 and delta<=-2 else 'MIXED'))
            indicators.append({'Type':'Independent Family','Indicator / Family':fam,'Resolved':n,'Success Rate %':100*rate,'All-row Baseline %':100*base if np.isfinite(base) else np.nan,'Lift x':lift,'Delta pp':delta,'Status':status})
    ind=pd.DataFrame(indicators)
    if not ind.empty:
        order={'WORKED':0,'MIXED':1,'FAILED':2,'LOW SAMPLE':3};ind['_o']=ind.Status.map(order).fillna(9);ind=ind.sort_values(['_o','Lift x','Resolved'],ascending=[True,False,False]).drop(columns=['_o']).reset_index(drop=True)
    stocks=[]
    cand_all=e[pd.to_numeric(e.get('candidate_v2',e.get('candidate',0)),errors='coerce').fillna(0).eq(1)].copy()
    if not cand_all.empty:
        for t,g in cand_all.groupby('ticker'):
            gc=g[g['clean_outcome'].isin(['WIN','LOSS'])].copy();n=len(gc);w=int((gc['clean_outcome']=='WIN').sum());rate=100*w/n if n else np.nan
            status='LOW SAMPLE / WAITING' if n<5 else ('SUCCESS' if rate>=55 else ('FAILURE' if rate<=45 else 'MIXED'))
            stocks.append({'Ticker':str(t),'V2 Candidate Rows':len(g),'Resolved':n,'Wins':w,'Losses':n-w,'Success Rate %':rate,'High Confidence Rows':int(pd.to_numeric(g.get('high_confidence',0),errors='coerce').fillna(0).eq(1).sum()),'Avg Meta Probability %':pd.to_numeric(g.get('meta_probability'),errors='coerce').mean(),'Avg MFE %':100*pd.to_numeric(g.get('max_favorable'),errors='coerce').mean(),'Avg MAE %':100*pd.to_numeric(g.get('max_adverse'),errors='coerce').mean(),'Model Status':status})
    stocks=pd.DataFrame(stocks)
    cal=[]
    if not clean.empty and 'meta_probability' in clean:
        mp=pd.to_numeric(clean['meta_probability'],errors='coerce');ms=pd.to_numeric(clean.get('meta_sample',0),errors='coerce').fillna(0)
        valid=clean[np.isfinite(mp) & (ms>=20)].copy();valid['_p']=pd.to_numeric(valid['meta_probability'],errors='coerce')
        for lo,hi in [(0,50),(50,55),(55,60),(60,65),(65,70),(70,80),(80,101)]:
            g=valid[(valid['_p']>=lo)&(valid['_p']<hi)];n=len(g)
            if not n:continue
            cal.append({'Meta Probability Bucket':f'{lo}-{hi if hi<=100 else 100}%','Resolved':n,'Predicted Avg %':float(g['_p'].mean()),'Actual Success %':100*float(g['Win'].mean()),'Calibration Error pp':100*float(g['Win'].mean())-float(g['_p'].mean()),'Avg Prior Support':pd.to_numeric(g.get('meta_sample'),errors='coerce').mean()})
    return headline,ind,stocks,gates,pd.DataFrame(cal)


def _feedback_replay_scorecards_v630(events):
    # Compatibility wrapper for older callers; V6.3.1 callers use the extended function.
    h,i,s,_,_=_feedback_replay_scorecards_v631(events);return h,i,s


def _feedback_learning_v611(merged, half_life_days=60):
    """Recency-weighted live feedback. Recent resolved observations matter more,
    but low-sample rows are explicitly marked and never auto-promote production."""
    if merged is None or merged.empty:return pd.DataFrame(),pd.DataFrame()
    x=merged.copy();x['ts_dt']=pd.to_datetime(x.get('ts_utc'),errors='coerce',utc=True)
    now=pd.Timestamp.now(tz='UTC');age=(now-x['ts_dt']).dt.total_seconds()/86400.0
    x['RecencyWeight']=np.exp(-np.log(2)*age.clip(lower=0)/max(float(half_life_days),1.0))
    x['ResolvedWin']=x.get('first_event','').astype(str).map(lambda v:1.0 if v.startswith('TARGET1 FIRST') else (0.0 if v.startswith('INVALIDATION FIRST') else np.nan))
    clean=x[np.isfinite(pd.to_numeric(x['ResolvedWin'],errors='coerce'))].copy()
    if 'optimized_stage' in clean:clean['optimized_confirmed']=clean['optimized_stage'].astype(str).eq('OPTIMIZED CONFIRMED').astype(int)
    if 'entry_state' in clean:clean['production_confirmed']=clean['entry_state'].astype(str).eq('CONFIRMED ENTRY').astype(int)
    if clean.empty:return pd.DataFrame(),pd.DataFrame()
    def wmean(g,col):
        v=pd.to_numeric(g[col],errors='coerce');w=pd.to_numeric(g['RecencyWeight'],errors='coerce');m=np.isfinite(v)&np.isfinite(w)&(w>0)
        return float(np.average(v[m],weights=w[m])) if m.any() else np.nan
    summaries=[]
    for keys,g in clean.groupby(['market','horizon'],dropna=False):
        wr=wmean(g,'ResolvedWin'); summaries.append({'Market':keys[0],'Horizon':keys[1],'Resolved':len(g),'Effective recent N':float(g.RecencyWeight.sum()),'Raw win rate %':100*float(g.ResolvedWin.mean()),'Recency-weighted win rate %':100*wr})
    feature_rows=[]
    feature_map={'daily_setup':'Daily Setup','fresh_signal':'Fresh Signal','hourly_entry':'Hourly / 15m','volume_flow':'Volume / Flow','no_chase':'No-Chase','market_regime_ok':'Market Regime','production_confirmed':'Production Confirmed','optimized_confirmed':'Optimized Confirmed'}
    for (market,horizon),g in clean.groupby(['market','horizon'],dropna=False):
        base=wmean(g,'ResolvedWin')
        for col,label in feature_map.items():
            if col not in g:continue
            gg=g[pd.to_numeric(g[col],errors='coerce')==1]
            if len(gg)<3:continue
            hr=wmean(gg,'ResolvedWin'); feature_rows.append({'Market':market,'Horizon':horizon,'Feature':label,'Resolved signals':len(gg),'Effective recent N':float(gg.RecencyWeight.sum()),'Weighted win rate %':100*hr if np.isfinite(hr) else np.nan,'Weighted baseline %':100*base if np.isfinite(base) else np.nan,'Recent Lift x':hr/base if np.isfinite(hr) and np.isfinite(base) and base>0 else np.nan,'Evidence':'OK' if float(gg.RecencyWeight.sum())>=12 else 'LOW SAMPLE'})
    return pd.DataFrame(summaries),pd.DataFrame(feature_rows).sort_values(['Recent Lift x','Effective recent N'],ascending=[False,False]) if feature_rows else pd.DataFrame()


def _feedback_primary_rows_v629(merged):
    """One primary outcome row per snapshot, avoiding 1D/2D/3D/5D double-counting.

    If a scan used 7D/10D, Feedback currently evaluates up to 5D, so the nearest
    supported horizon (5D) is used and exposed in the table.
    """
    if merged is None or not isinstance(merged,pd.DataFrame) or merged.empty:return pd.DataFrame()
    x=merged.copy();allowed=(1,2,3,5)
    cfg=pd.to_numeric(x.get('horizon_days',5),errors='coerce').fillna(5)
    x['Primary Feedback Horizon']=cfg.map(lambda v:min(allowed,key=lambda h:abs(float(v)-h)))
    hh=pd.to_numeric(x.get('horizon'),errors='coerce')
    return x[hh==pd.to_numeric(x['Primary Feedback Horizon'],errors='coerce')].copy()


def _feedback_scorecards_v629(sn, primary):
    """Simple Hebrew-friendly success, indicator and stock scorecards.

    Success = Target1 was reached before invalidation among clean resolved primary
    outcomes. OPEN / ambiguous rows are shown separately and never hidden inside
    the percentage.
    """
    p=primary.copy() if isinstance(primary,pd.DataFrame) else pd.DataFrame()
    if not p.empty and 'Clean Outcome' not in p:
        p['Clean Outcome']=p.get('first_event','').astype(str).map(lambda x:'WIN' if x.startswith('TARGET1 FIRST') else ('LOSS' if x.startswith('INVALIDATION FIRST') else ('AMBIGUOUS' if x.startswith('AMBIGUOUS') else 'OPEN/NONE')))
    clean=p[p.get('Clean Outcome',pd.Series('',index=p.index)).isin(['WIN','LOSS'])].copy() if not p.empty else pd.DataFrame()
    if not clean.empty:clean['Clean Win']=clean['Clean Outcome'].eq('WIN').astype(float)
    wins=int((clean.get('Clean Outcome',pd.Series(dtype=str))=='WIN').sum()) if not clean.empty else 0
    losses=int((clean.get('Clean Outcome',pd.Series(dtype=str))=='LOSS').sum()) if not clean.empty else 0
    resolved=wins+losses; evaluated=len(p)
    amb=int((p.get('Clean Outcome',pd.Series(dtype=str))=='AMBIGUOUS').sum()) if not p.empty else 0
    opened=int((p.get('Clean Outcome',pd.Series(dtype=str))=='OPEN/NONE').sum()) if not p.empty else 0
    success=100*wins/resolved if resolved else np.nan
    coverage=100*resolved/evaluated if evaluated else np.nan
    headline=pd.DataFrame([{
        'אחוז הצלחה':success,'הצלחות':wins,'כשלונות':losses,'מקרים נקיים שהוכרעו':resolved,
        'נבדקו בפועל':evaluated,'לא הוכרעו / פתוחים':opened,'דו-משמעיים':amb,'כיסוי הכרעה %':coverage,
        'הגדרה':'Target 1 לפני Invalidation, רק באופק הראשי של כל סריקה'
    }])

    base=float(clean['Clean Win'].mean()) if not clean.empty else np.nan
    indicator_rows=[]
    feature_map={
        'daily_setup':'Daily Setup','fresh_signal':'Fresh Signal / Transition','hourly_entry':'Hourly / 15m confirmation',
        'volume_flow':'Volume / Flow','no_chase':'No-Chase','extension_guard':'Extension Guard OK',
        'market_regime_ok':'Market Regime OK'
    }
    def add_indicator(label,mask,kind='Live gate'):
        if clean.empty:return
        try:g=clean.loc[mask.reindex(clean.index,fill_value=False)]
        except Exception:return
        n=len(g)
        if n==0:return
        hr=float(g['Clean Win'].mean());lift=hr/base if np.isfinite(base) and base>0 else np.nan
        delta=100*(hr-base) if np.isfinite(base) else np.nan
        if n<5:status='LOW SAMPLE'
        elif np.isfinite(lift) and lift>=1.05 and delta>=2:status='WORKED'
        elif np.isfinite(lift) and lift<=.95 and delta<=-2:status='FAILED'
        else:status='MIXED'
        indicator_rows.append({'סוג':kind,'אינדיקטור / תנאי':label,'מקרים שהוכרעו':n,'אחוז הצלחה %':100*hr,'בסיס כללי %':100*base if np.isfinite(base) else np.nan,'Lift x':lift,'פער מול בסיס (נק׳ %)':delta,'סטטוס':status})
    for col,label in feature_map.items():
        if col in clean:add_indicator(label,pd.to_numeric(clean[col],errors='coerce').fillna(0).eq(1))
    if 'pre_move_stage' in clean:
        add_indicator('Pre-Move Candidate',clean['pre_move_stage'].astype(str).isin(['PRE-MOVE CANDIDATE','STRONG PRE-MOVE CANDIDATE']),'Research radar')
    fams=['MOMENTUM','VOLUME','FLOW','RELATIVE_STRENGTH','TREND','STRUCTURE','TRANSITION_BREADTH']
    if 'pre_move_families' in clean:
        fs=clean['pre_move_families'].fillna('').astype(str)
        for fam in fams:add_indicator('Pre-Move family: '+fam,fs.str.contains(fam,regex=False),'Pre-Move family')
    # Exact strongest Pre-Move combinations are also tracked; require >=3 clean outcomes.
    if 'pre_move_features' in clean:
        rows=[]
        for idx,r in clean[['pre_move_features','Clean Win']].iterrows():
            for sig in [x.strip() for x in str(r.get('pre_move_features','')).split(' | ') if x.strip() and x.strip().lower()!='nan']:
                rows.append((sig,float(r['Clean Win'])))
        if rows:
            tmp=pd.DataFrame(rows,columns=['Signal','Win'])
            for sig,g in tmp.groupby('Signal'):
                if len(g)<3:continue
                hr=float(g.Win.mean());lift=hr/base if np.isfinite(base) and base>0 else np.nan;delta=100*(hr-base) if np.isfinite(base) else np.nan
                status='LOW SAMPLE' if len(g)<5 else ('WORKED' if np.isfinite(lift) and lift>=1.05 and delta>=2 else ('FAILED' if np.isfinite(lift) and lift<=.95 and delta<=-2 else 'MIXED'))
                indicator_rows.append({'סוג':'Pre-Move signal','אינדיקטור / תנאי':sig,'מקרים שהוכרעו':len(g),'אחוז הצלחה %':100*hr,'בסיס כללי %':100*base if np.isfinite(base) else np.nan,'Lift x':lift,'פער מול בסיס (נק׳ %)':delta,'סטטוס':status})
    indicators=pd.DataFrame(indicator_rows)
    if not indicators.empty:
        order={'WORKED':0,'MIXED':1,'FAILED':2,'LOW SAMPLE':3}
        indicators['_o']=indicators['סטטוס'].map(order).fillna(9);indicators=indicators.sort_values(['_o','Lift x','מקרים שהוכרעו'],ascending=[True,False,False]).drop(columns=['_o']).reset_index(drop=True)

    # All tickers that have ever been snapshotted are shown, even before outcomes mature.
    stock_base=pd.DataFrame({'Ticker':sorted(set(sn.get('ticker',pd.Series(dtype=str)).dropna().astype(str)))}) if isinstance(sn,pd.DataFrame) and not sn.empty else pd.DataFrame(columns=['Ticker'])
    if not p.empty:
        stock_stats=[]
        for ticker,g in p.groupby('ticker',dropna=False):
            gc=g[g['Clean Outcome'].isin(['WIN','LOSS'])].copy();w=int((gc['Clean Outcome']=='WIN').sum());l=int((gc['Clean Outcome']=='LOSS').sum());n=w+l
            hr=100*w/n if n else np.nan
            avg=float(pd.to_numeric(g.get('End Return %'),errors='coerce').mean()) if 'End Return %' in g else np.nan
            mfe=float(pd.to_numeric(g.get('MFE %'),errors='coerce').mean()) if 'MFE %' in g else np.nan
            mae=float(pd.to_numeric(g.get('MAE %'),errors='coerce').mean()) if 'MAE %' in g else np.nan
            if n<3:status='LOW SAMPLE / WAITING'
            elif hr>=55:status='SUCCESS'
            elif hr<=45:status='FAILURE'
            else:status='MIXED'
            stock_stats.append({'Ticker':str(ticker),'Resolved':n,'Wins':w,'Losses':l,'Success Rate %':hr,'Avg End Return %':avg,'Avg MFE %':mfe,'Avg MAE %':mae,'Model Status':status})
        ss=pd.DataFrame(stock_stats);stocks=stock_base.merge(ss,on='Ticker',how='left')
    else:stocks=stock_base.copy()
    if not stocks.empty:
        stocks['Snapshots']=stocks['Ticker'].map(sn.groupby('ticker').size() if isinstance(sn,pd.DataFrame) and not sn.empty else {}).fillna(0).astype(int)
        for c in ['Resolved','Wins','Losses']:
            if c not in stocks:stocks[c]=0
            stocks[c]=pd.to_numeric(stocks[c],errors='coerce').fillna(0).astype(int)
        stocks['Model Status']=stocks.get('Model Status',pd.Series(index=stocks.index,dtype=object)).fillna('WAITING FOR OUTCOME')
        order={'SUCCESS':0,'MIXED':1,'FAILURE':2,'LOW SAMPLE / WAITING':3,'WAITING FOR OUTCOME':4}
        stocks['_o']=stocks['Model Status'].map(order).fillna(9);stocks=stocks.sort_values(['_o','Success Rate %','Resolved'],ascending=[True,False,False]).drop(columns=['_o']).reset_index(drop=True)
    return headline,indicators,stocks


def _feedback_color_table_v629(df,status_col):
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:return df
    def row_style(row):
        v=str(row.get(status_col,''))
        if v in ('WORKED','SUCCESS'):style='background-color: rgba(53,212,154,.20); color: #b7f7dd; font-weight: 700'
        elif v in ('FAILED','FAILURE'):style='background-color: rgba(255,100,124,.20); color: #ffc0ca; font-weight: 700'
        elif v=='MIXED':style='background-color: rgba(246,200,95,.16); color: #ffe7a8'
        else:style='color: #9aa7bb'
        return [style]*len(row)
    try:return df.style.apply(row_style,axis=1)
    except Exception:return df


def _feedback_workbook_v629(sheets,meta=None):
    """Feedback Excel with the same green/red scorecard semantics as the UI."""
    raw=workbook_bytes(sheets,meta)
    try:
        from openpyxl import load_workbook
        from openpyxl.styles import PatternFill, Font
        bio=BytesIO(raw);wb=load_workbook(bio)
        colors={'WORKED':'C6EFCE','SUCCESS':'C6EFCE','OOS STRONG':'C6EFCE','OOS POSITIVE':'C6EFCE','FAILED':'FFC7CE','FAILURE':'FFC7CE','MIXED':'FFEB9C','OOS MIXED':'FFEB9C'}
        for sheet,status_header in [('Indicator Summary','סטטוס'),('Stock Summary','Model Status'),('Replay Indicators','Status'),('Replay Stocks','Model Status'),('Combination Discovery','OOS Status')]:
            if sheet not in wb.sheetnames:continue
            ws=wb[sheet];headers={c.value:i for i,c in enumerate(ws[1],1)};ci=headers.get(status_header)
            if not ci:continue
            for r in range(2,ws.max_row+1):
                status=str(ws.cell(r,ci).value or '')
                color=colors.get(status)
                if not color:continue
                fill=PatternFill('solid',fgColor=color)
                for c in range(1,ws.max_column+1):ws.cell(r,c).fill=fill
        out=BytesIO();wb.save(out);return out.getvalue()
    except Exception:return raw

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
            _excel_safe_df(obj).to_excel(writer,index=False,sheet_name=name)
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
            job['market']=_market_for_ticker_v612(ticker_name)
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
            config['threshold'],config['prefilter_top'],progress_callback=progress,optimizer_model=config.get('optimizer_model'))
        # A stop can be requested while the final network/data call is still in flight.
        # Re-check before publishing/storing a completed result.
        with runtime['lock']:
            job=runtime.get('active')
            if (not job or job.get('id')!=job_id or job.get('cancel_requested') or job.get('status') in ('stopping','stopped')):
                raise _ScannerCancelled()
        meta=dict(getattr(res,'attrs',{}).get('scan_meta',{})) if isinstance(res,pd.DataFrame) else {}
        if isinstance(res,pd.DataFrame) and not res.empty:
            res=add_market_and_opportunity(res);res=_apply_optimized_model_v612(res,config.get('optimizer_model'))
            try: res=_attach_pre_move_overlay_v628(res)
            except Exception: pass
            if config.get('scan_mode') in ('Optimized 151','Discovery') and 'OptimizedScore' in res:
                res=res.sort_values(['OptimizedScore','TopScore','EntryScore'],ascending=False).reset_index(drop=True);res['GlobalRank']=np.arange(1,len(res)+1);res['MarketRank']=res.groupby('Market')['OptimizedScore'].rank(method='first',ascending=False).astype(int)
            else:res=res.sort_values(['TopScore','OpportunityScore','ExplosiveScore','EntryScore'],ascending=False).reset_index(drop=True)
        finished=time_module.time()
        try:
            _feedback_store_scan_v600(job_id,res,config)
            threading.Thread(target=_feedback_evaluate_due_v600,kwargs={'max_snapshots':80},daemon=True).start()
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

def _filter_scanner_results_v599(df,show_mode,market_filter="ALL 151"):
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:
        return pd.DataFrame()
    z=df.copy()
    market_name={'HONG KONG 50':'HONG KONG','TEL AVIV 50':'TEL AVIV'}.get(market_filter)
    if market_filter=='US 51' and 'Ticker' in z:z=z[z.Ticker.astype(str).isin(set(US_51.split(',')))]
    elif market_filter=='US ALL' and 'Market' in z:z=z[z.Market.astype(str).isin(['NASDAQ','NYSE','US'])]
    elif market_name and 'Market' in z:z=z[z.Market.eq(market_name)]
    if show_mode=='STRONG PRE-MOVE CANDIDATE':
        z=z[z.get('PreMoveStage',pd.Series('',index=z.index)).eq('STRONG PRE-MOVE CANDIDATE')]
    elif show_mode=='PRE-MOVE CANDIDATE':
        z=z[z.get('PreMoveStage',pd.Series('',index=z.index)).isin(['STRONG PRE-MOVE CANDIDATE','PRE-MOVE CANDIDATE'])]
    elif show_mode=='CONFIRMED ENTRY':
        z=z[z.get('EntryTriggerState',pd.Series('',index=z.index)).eq('CONFIRMED ENTRY')]
    elif show_mode=='OPTIMIZED CONFIRMED':
        z=z[z.get('OptimizedStage',pd.Series('',index=z.index)).eq('OPTIMIZED CONFIRMED')]
    elif show_mode=='OPTIMIZED ARMED':
        z=z[z.get('OptimizedStage',pd.Series('',index=z.index)).eq('OPTIMIZED ARMED')]
    elif show_mode=='ARMED':
        z=z[z.get('EntryTriggerState',pd.Series('',index=z.index)).eq('ARMED')]
    elif show_mode=='EXTENDED / RETEST':
        z=z[z.get('EntryTriggerState',pd.Series('',index=z.index)).eq('EXTENDED — DO NOT CHASE')]
    elif show_mode=='TOP OPPORTUNITIES':
        z=z[(z.TopScore>=68) | (z.OpportunityScore>=72)]
    elif show_mode=='ACTIONABLE NOW':
        if 'ActionableNow' in z: z=z[z.ActionableNow.astype(bool)]
    elif show_mode=='WATCHLIST':
        z=z[z.get('EntryTriggerState',z.OpportunityStage).isin(['WATCH','ARMED','EXTENDED — DO NOT CHASE'])]
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
        c='good' if live=='CONFIRMED ENTRY — LIVE' else ('bad' if 'WEAKENED' in live else 'warn')
        return f"<span class='{c}'>OPEN: {live}</span>"
    if phase=='PRE-OPEN': return f"<span class='warn'>PRE-OPEN • Previous session: {stage}</span>"
    if phase=='CLOSED': return f"<span class='warn'>CLOSED • Previous session: {stage}</span>"
    return f"<span class='warn'>{phase}: {stage}</span>"

def _live_levels_html_v599(r):
    if str(r.get('MarketPhase',''))!='OPEN' or str(r.get('LiveStage',''))!='CONFIRMED ENTRY — LIVE':
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
            "**WAIT** → **WATCH** → **ARMED** → **CONFIRMED ENTRY** • hard override: **EXTENDED — DO NOT CHASE / WAIT FOR RETEST** • then **TOO LATE / CHASE** or **INVALIDATED**"
        )
        st.caption(
            "WAIT = conditions are not ready • WATCH = setup is developing • ARMED = setup is strong but still missing confirmation • "
            "CONFIRMED ENTRY = Daily Setup + fresh transition + intraday timing + volume/flow + No-Chase + market-regime gates are aligned."
        )
        st.caption(
            "EXTENDED — DO NOT CHASE = the six setup gates may still be 6/6, but the independent Chase/Extension Guard blocks a late entry after an outsized move and waits for a retest • TOO LATE / CHASE = the legacy No-Chase gate failed • "
            "INVALIDATED = the trade plan or exit-risk gate failed. A previous-session confirmation must remain valid in the current session."
        )

def _render_scanner_results_v599(show_mode,market_filter="ALL 151"):
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
    full=_attach_pre_move_overlay_v628(last.get('result'))
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
                pm_stage=str(r.get('PreMoveStage','NO CURRENT PRE-MOVE CANDIDATE'))
                live_entry=str(r.get('EntryTriggerState',r.get('TradeStage','—')))
                if pm_stage!='NO CURRENT PRE-MOVE CANDIDATE':
                    st.markdown(f"**Research radar:** **{pm_stage}**  •  **Live entry:** **{live_entry}**")
                    st.caption(f"Pre-Move score {safe(r.get('PreMoveScore'),1)} • OOS empirical hit {safe(r.get('PreMoveProbabilityPct'),1)}% • Best lift {safe(r.get('PreMoveBestOOSLiftX'),2)}x • Freshness {r.get('PreMoveFreshness','—')} • Families {int(r.get('PreMoveIndependentFamilyCount',0) or 0)} • Research only")
                else:
                    st.caption(f"Research radar: no current Pre-Move candidate • Live entry: {live_entry}")
                st.markdown(f"**Trade:** :{'green' if str(r.get('TradeStage'))=='CONFIRMED ENTRY' else 'orange'}[**{r.get('TradeStage','—')}**]  •  **Movement:** {r.get('MovementStage','—')}  •  **Exit:** :{'red' if float(r.get('ExitPressure',0) or 0)>=55 else 'orange' if float(r.get('ExitPressure',0) or 0)>=35 else 'green'}[**{r.get('ExitStage','CLEAR')} {safe(r.get('ExitPressure'),0)}**]")
                st.caption(f"Entry gates {int(r.get('EntryConfirmedConditions',0) or 0)}/{int(r.get('EntryTotalConditions',6) or 6)} ({float(r.get('EntryConfirmationPct',0) or 0):.0f}%) • Why now: {r.get('EntryWhyNow','—')}")
                _cr=float(r.get('ChaseRiskScore',0) or 0); _sm=pd.to_numeric(pd.Series([r.get('SessionMovePct',np.nan)]),errors='coerce').iloc[0]; _st=pd.to_numeric(pd.Series([r.get('SinceTriggerPct',np.nan)]),errors='coerce').iloc[0]
                if str(r.get('ChaseRiskLabel','LOW'))!='LOW' or not bool(r.get('ExtensionGuardCheck',True)):
                    st.warning(f"Chase risk {r.get('ChaseRiskLabel','LOW')} ({_cr:.0f}/100) • Session {f'{_sm:+.1f}%' if np.isfinite(_sm) else '—'} • Since original trigger {f'{_st:+.1f}%' if np.isfinite(_st) else '—'} • {r.get('RecommendedAction','WAIT FOR RETEST')}")
                if np.isfinite(float(r.get('OptimizedScore',np.nan))):st.caption(f"{r.get('OptimizedStage','OPTIMIZED WAIT')} • Optimized {float(r.get('OptimizedScore')):.1f} • Match {float(r.get('OptimizedMatchPct',np.nan)):.0f}% • Δ vs TOP {float(r.get('OptimizedDelta',np.nan)):+.1f} • Institutional Flow {float(r.get('InstitutionalFlowScore',np.nan)):.0f} ({r.get('InstitutionalFlowLabel','—')})")
                if str(r.get('EntryMissingChecks','')) not in ('','None'):st.caption("Still missing: "+str(r.get('EntryMissingChecks')))
                m1,m2,m3,m4=st.columns(4)
                m1.metric("Prediction Score",safe(r.get('Prediction'),1)); m2.metric("Evidence",str(r.get('EvidenceQuality','LOW'))); m3.metric("Live entry",safe(r.get('LiveActionabilityScore',r.get('EntryScore')),1),delta=f"Timing {safe(r.get('EntryScore'),1)} • Setup {safe(r.get('SetupEntryScore'),1)}"); m4.metric("Hourly",safe(r.get('HourlyConfirm'),1))
                st.caption(f"Move {safe(r.get('MoveScore'),1)} • Explosive {safe(r.get('ExplosiveScore'),1)} • Volume {r.get('VolumeContext','N/A')} • Live RVOL {safe(r.get('LiveIntradayRVOL',r.get('TimeAdjustedRVOL')))}x • Daily RVOL {safe(r.get('DailyRobustRVOL'))}x • Global #{int(r.get('GlobalRank',0) or 0)} • {r.get('Market','—')} #{int(r.get('MarketRank',0) or 0)} • Sector #{int(r.get('SectorRank',0) or 0)}")
                n=int(r.get('BacktestN',0) or 0)
                bt_txt=f"{safe(r.get('EmpiricalHitRate'),1)}% ({n} signals)" if n>=12 else f"LOW SAMPLE — {n} signals"
                st.caption(f"Evidence {r.get('EvidenceQuality','LOW')} • Reliability {safe(r.get('Reliability'),1)} • Backtest {bt_txt} • Lift {safe(r.get('SignalLift'))}x • RSI {safe(r.get('RSI14'),1)} • Data quality {r.get('DataQuality','OK')}{' • Split adjusted' if bool(r.get('SplitAdjusted',False)) else ''}")
                if bool(r.get('PlanValid',False)) and str(r.get('MarketPhase',''))=='OPEN' and str(r.get('LiveStage',''))=='CONFIRMED ENTRY — LIVE':
                    vals={k:pd.to_numeric(pd.Series([r.get(k,np.nan)]),errors='coerce').iloc[0] for k in ['EntryLow','EntryHigh','Invalidation','Target1','Target2']}
                    if all(np.isfinite(vals[k]) for k in vals):
                        e1,e2,e3,e4=st.columns(4); e1.metric("Entry zone",f"{vals['EntryLow']:.3f}–{vals['EntryHigh']:.3f}"); e2.metric("Invalidation",f"{vals['Invalidation']:.3f}"); e3.metric("Target 1",f"{vals['Target1']:.3f}"); e4.metric("Target 2",f"{vals['Target2']:.3f}")
        _scanner_stage_guide_v599()
        # Clear ranking table:
        # Rank = position inside the CURRENT selected view/filter.
        # GlobalRank = position among the full scan result set.
        # MarketRank = position only inside the stock's exchange (NASDAQ / NYSE / Hong Kong / Tel Aviv).
        cols=['Ticker','Rank','PreMoveStage','PreMoveScore','PreMoveProbabilityPct','PreMoveFreshness','PreMoveMoveConsumedPct','PreMoveIndependentFamilyCount','PreMovePositiveOOSFamilyCount','PreMoveCoreConfirmed','PreMoveBestOOSLiftX','PreMoveStrongestFeatures','PreMoveTargetHorizon','PreMoveRunCompleted','PreMoveRunAgeHours','TradePriorityRank','OptimizedStage','OptimizedScore','OptimizedMatchPct','OptimizedDelta','OptimizedModelStatus','OptimizedModelID','OptimizedModelScope','OptimizedModelHorizon','OptimizedModelOOSLift','HourlyOptimizedScore','HourlyOptimizedMatchPct','HourlyOptimizedStatus','HourlyOptimizedHorizon','InstitutionalFlowScore','InstitutionalFlowLabel','GlobalRank','MarketRank','SectorRank','Market','Sector','MarketPhase','SessionStatus','LiveStage','ActionableNow','TradeStage','EntryTriggerState','SessionEntryState','RegularSessionEntryState','EntryConfirmationPct','DailySetupCheck','FreshSignalCheck','HourlyEntryCheck','VolumeFlowCheck','NoChaseCheck','ExtensionGuardCheck','ChaseRiskScore','ChaseRiskLabel','SessionMovePct','MoveBeforeTriggerPct','RegularSessionMovePct','AfterHoursMovePct','AfterHoursPrice','AfterHoursPriceSource','AfterHoursVolumeStrength','TotalMoveIncludingAHPct','SessionMoveATR','SessionMovePercentile','SinceTriggerPct','GapPct','VWAPDistanceATR','Target1ProgressPct','VolumeTrend','VolumeTrend15m','VolumeTrend1H','MomentumState','MomentumState15m','MomentumState1H','PostSpikeState','PostSpikeDistributionRisk','ContinuationBaseCandidate','ContinuationBaseStatus','ContinuationBaseQuality','ContinuationSessionPeak','ContinuationBreakoutTrigger','ContinuationBreakoutReference','TriggerAnchorPrice','TriggerAnchorTimeframe','TriggerAnchorQuality','TriggerAnchorAgeBars','RetestZoneLow','RetestZoneHigh','PullbackNeededPct','RetestStatus','RecommendedAction','MarketRegime','EntryWhyNow','EntryMissingChecks','MovementStage','WhyNotTradeTrigger','TopScore','OpportunityScore','Reliability','EvidenceQuality','EvidenceState','EvidenceGuardOK','ExitPressure','ExitStage','VolumeContext','BullishVolumeEvidence','BearishVolumeEvidence','LiveIntradayRVOL','DailyRobustRVOL','TimeAdjustedRVOL','MoveScore','ExplosiveScore','EntryScore','LiveActionabilityScore','SetupEntryScore','PlanValid','PlanReason','EntryLow','EntryHigh','BreakoutTrigger','Invalidation','Target1','Target2','Accel1D','Accel2D','Accel3D','HourlyConfirm','Signal','Prediction','DynamicQuant','DynamicEarly','EntryStatus','ExplosiveStage','P5_5D','P10_5D','P15_5D','P15_5D_N','SignalLift','CalibrationConfidence','Price','LivePriceFresh','PriceSource','PriceTimestamp','RSI14','EmpiricalHitRate','BacktestN','SplitAdjusted','DataQuality','PMConfirmation','PMChangePct','PMVolumeStrength','AHConfirmation','AHChangePct','AHVolumeStrength']
        table=res[[c for c in cols if c in res]].copy()
        table=table.rename(columns={
            'Rank':'View Rank',
            'GlobalRank':'Global Rank',
            'MarketRank':'Market Rank','SectorRank':'Sector Rank','TradePriorityRank':'Trade Priority',
        })
        if 'BacktestN' in table:
            table['Backtest Quality']=np.where(pd.to_numeric(table['BacktestN'],errors='coerce').fillna(0)>=12,'EVIDENCE OK',np.where(pd.to_numeric(table['BacktestN'],errors='coerce').fillna(0)>0,'LOW SAMPLE','NO SAMPLE'))
            if 'EmpiricalHitRate' in table:table.loc[pd.to_numeric(table['BacktestN'],errors='coerce').fillna(0)<12,'EmpiricalHitRate']=np.nan
        if set(res.get('Market',pd.Series(dtype=str)).astype(str).unique()).isdisjoint({'NASDAQ','NYSE'}):
            table=table.drop(columns=[c for c in table.columns if c.startswith('PM') or c.startswith('AH')],errors='ignore')
        st.caption("Ranking: Trade Priority = stage first, then TOP Score • Global Rank = rank across the full successfully analyzed requested universe • Market Rank = exchange rank • Sector Rank = sector rank inside that market.")
        st.dataframe(table,use_container_width=True,hide_index=True)
    if skipped:
        with st.expander(f"Skipped / error details ({len(skipped)})"):
            st.dataframe(pd.DataFrame(skipped),use_container_width=True,hide_index=True)

if hasattr(st,'fragment'):
    @st.fragment(run_every="1s")
    def _scanner_live_fragment_v599(show_mode,market_filter="ALL 151"):
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
    def _scanner_live_fragment_v599(show_mode,market_filter="ALL 151"):
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
        job['market'] = _market_for_ticker_v612(ticker) if ticker not in (None, '—') else '—'
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
        'Tab': 'Research 151',
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
                            'Market': _market_for_ticker_v612(tkr),
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
        suffix = 'PARTIAL' if partial else 'Research151'
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
def _lab_runtimes_v603(build_id):
    # Key the in-memory Lab runtime by build so hot-reloads cannot reuse payloads
    # created by an older app structure. This prevents stale-object AttributeErrors
    # after deploys while preserving server-side background jobs within the same build.
    names=('analyze','backtest','validate','entry','explosive','feedback','research_validator','pre_move','historical_replay')
    return {name:{'lock':threading.RLock(),'executor':None,'active':None,'last_completed':None} for name in names}


def _lab_runtime_v603(name):
    # V6.2.6: tolerate newly-added Lab names even if a future UI block is added
    # before the static registry tuple is updated. This prevents a page-level
    # KeyError such as the V6.2.5 Pre-Move runtime crash.
    runtimes=_lab_runtimes_v603(APP_BUILD_ID)
    if name not in runtimes:
        runtimes[name]={'lock':threading.RLock(),'executor':None,'active':None,'last_completed':None}
    return runtimes[name]


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

        _lab_update_v603(runtime,jid,1,8,t,'Current-session 1m/5m price + corporate action check')
        live_snapshot=fetch_live_intraday_snapshot(t,d);_lab_check_v603(runtime,jid)

        _lab_update_v603(runtime,jid,2,8,t,'Confirmed 1H / 15m + split normalization')
        h=confirmed_intraday_bars(fetch_ohlcv(t,'1mo','1h'));m15=confirmed_intraday_bars(fetch_ohlcv(t,'60d','15m'))
        # V6.0.5 hard gate: a stale/prior-session quote is NEVER a normalization anchor.
        safe_anchor=live_snapshot.get('price',np.nan) if bool(live_snapshot.get('anchor_eligible')) and not bool(live_snapshot.get('scale_suspect')) else np.nan
        d,h,m15,ca_report=normalize_cross_timeframes(
            d,h,m15,
            anchor_price=safe_anchor,
            split_ratio=live_snapshot.get('split_ratio',np.nan),
        );_lab_check_v603(runtime,jid)
        if live_snapshot.get('split_detected'):
            ca_report=dict(ca_report);ca_report['split_detected']=True
            ca_report['split_ratio']=live_snapshot.get('split_ratio',np.nan);ca_report['split_date']=live_snapshot.get('split_date')
        _phase_detail=_market_status_detail_v612(_market_for_ticker_v612(t))
        phase_now=_phase_detail.get('phase','UNKNOWN')
        _market_date=_phase_detail.get('local_date')
        live_snapshot=resolve_current_market_snapshot(t,d,h,m15,live_snapshot,market_open=(phase_now=='OPEN'),market_phase=phase_now,market_date=_market_date)
        # V6.1.4 AH-aware: keep extended-hours price/volume separate from regular-session
        # indicators. The AH snapshot can affect chase/extension risk, but it cannot by
        # itself turn regular-session technicals into an ActionableNow entry.
        ah_snapshot={}
        if phase_now=='AFTER-MARKET' and _market_for_ticker_v612(t) in ('NASDAQ','NYSE','US'):
            try: ah_snapshot=fetch_aftermarket_snapshots([t]).get(str(t).upper(),{}) or {}
            except Exception: ah_snapshot={}
            # Yahoo's 5m prepost endpoint occasionally omits AH rows even when the
            # fresher 1m/current-session quote is valid. In that case use the live
            # quote only for AH price/change context; volume strength stays unavailable.
            if not np.isfinite(float(ah_snapshot.get('AHPrice',np.nan))):
                try:
                    _lp=float(live_snapshot.get('price',np.nan)); _rc=float(live_snapshot.get('fallback_price',np.nan))
                except Exception:
                    _lp=_rc=np.nan
                if bool(live_snapshot.get('display_current')) and bool(live_snapshot.get('trade_fresh')) and np.isfinite(_lp) and np.isfinite(_rc) and _rc>0:
                    ah_snapshot={
                        'AHPrice':_lp,'RegularClose':_rc,'AHChangePct':(_lp/_rc-1.0)*100.0,
                        'AHVolume':np.nan,'AHVolumeStrength':np.nan,'AHData':'LIVE QUOTE FALLBACK',
                        'AHLastTime':live_snapshot.get('timestamp_label','—'),'AHAgeMinutes':live_snapshot.get('age_minutes',np.nan),
                        'AHFresh':True,'AHPriceSource':str(live_snapshot.get('source','live quote fallback'))
                    }
            elif ah_snapshot:
                ah_snapshot['AHPriceSource']=ah_snapshot.get('AHData','REAL 5M')

        _lab_update_v603(runtime,jid,3,8,t,'Quant + Early features on normalized data')
        f=compute_features(d);latest=score_latest(f,0);dyn=dynamic_scores(f,target/100,0);_lab_check_v603(runtime,jid)
        hfeat=compute_features(h,True) if h is not None and len(h)>=30 else None;m15feat=compute_features(m15,True) if m15 is not None and len(m15)>=30 else None
        hs=he=np.nan
        if hfeat is not None:
            hl=score_latest(hfeat,0);hs=hl['score'];he=hl['early_score']
        qscore=latest['score'] if not np.isfinite(hs) else .78*latest['score']+.22*hs;escore=latest['early_score'] if not np.isfinite(he) else .70*latest['early_score']+.30*he

        _lab_update_v603(runtime,jid,4,8,t,'Historical evidence')
        auto_threshold,auto_table=_auto_backtest_threshold(f,horizon,target/100);buy_threshold=int(auto_threshold);bt=normalize_backtest_confidence(backtest_signal(f,horizon,target/100,buy_threshold,0));cmp=compare_static_dynamic_backtest(f,horizon,target/100,buy_threshold,0);sb,db=cmp.get('static',{}),cmp.get('dynamic',{});analysis_conf=float(dyn.get('early_calibration',{}).get('confidence',0)+dyn.get('quant_calibration',{}).get('confidence',0))/2.0;_lab_check_v603(runtime,jid)

        _lab_update_v603(runtime,jid,5,8,t,'Entry + live timing')
        _ah_price=float(ah_snapshot.get('AHPrice',np.nan)) if np.isfinite(float(ah_snapshot.get('AHPrice',np.nan))) else np.nan
        _live_price=float(live_snapshot.get('price',np.nan)) if bool(live_snapshot.get('display_current')) and np.isfinite(float(live_snapshot.get('price',np.nan))) else np.nan
        current_entry_price=_ah_price if phase_now=='AFTER-MARKET' and np.isfinite(_ah_price) else _live_price
        _regular_close=float(ah_snapshot.get('RegularClose',np.nan)) if np.isfinite(float(ah_snapshot.get('RegularClose',np.nan))) else float(live_snapshot.get('fallback_price',np.nan)) if np.isfinite(float(live_snapshot.get('fallback_price',np.nan))) else np.nan
        regular_ent=None
        if phase_now=='AFTER-MARKET' and np.isfinite(_regular_close):
            regular_ent=entry_timing(f,qscore,escore,hourly_feat=hfeat,m15_feat=m15feat,current_price=_regular_close,market_regime=_market_regime_v610(t),previous_close=live_snapshot.get('prev_close',np.nan),market_phase=phase_now,market_date=_market_date)
        ent=entry_timing(f,qscore,escore,hourly_feat=hfeat,m15_feat=m15feat,current_price=current_entry_price,market_regime=_market_regime_v610(t),previous_close=live_snapshot.get('prev_close',np.nan),market_phase=phase_now,market_date=_market_date)
        ent=dict(ent)
        _prev_close=float(live_snapshot.get('prev_close',np.nan)) if np.isfinite(float(live_snapshot.get('prev_close',np.nan))) else np.nan
        _ah_change=float(ah_snapshot.get('AHChangePct',np.nan)) if np.isfinite(float(ah_snapshot.get('AHChangePct',np.nan))) else np.nan
        _regular_move=((_regular_close/_prev_close)-1.0)*100.0 if np.isfinite(_regular_close) and np.isfinite(_prev_close) and _prev_close>0 else np.nan
        _total_extended=((current_entry_price/_prev_close)-1.0)*100.0 if phase_now=='AFTER-MARKET' and np.isfinite(current_entry_price) and np.isfinite(_prev_close) and _prev_close>0 else np.nan
        ent['market_phase']=phase_now; ent['regular_session_close']=_regular_close; ent['regular_session_move_pct']=_regular_move
        ent['after_hours_price']=_ah_price; ent['after_hours_move_pct']=_ah_change; ent['after_hours_volume_strength']=ah_snapshot.get('AHVolumeStrength',np.nan); ent['after_hours_fresh']=bool(ah_snapshot.get('AHFresh',False)); ent['after_hours_price_source']=ah_snapshot.get('AHPriceSource',ah_snapshot.get('AHData','N/A')); ent['total_move_including_ah_pct']=_total_extended
        ent['regular_session_entry_state']=(regular_ent or {}).get('trigger_state',(regular_ent or {}).get('status',ent.get('trigger_state',ent.get('status','WAIT'))))
        ent['regular_session_entry_score']=(regular_ent or {}).get('entry_score',ent.get('entry_score',np.nan))
        ent['regular_session_chase_risk_score']=(regular_ent or {}).get('chase_risk_score',ent.get('chase_risk_score',np.nan))
        if phase_now=='AFTER-MARKET':
            if not bool(ent.get('extension_guard_ok',True)) or ent.get('trigger_state')=='EXTENDED — DO NOT CHASE':
                ent['session_entry_state']='EXTENDED — DO NOT CHASE'
                ent['recommended_action']='WAIT FOR RETEST • RECONFIRM NEXT REGULAR SESSION'
            elif ent.get('trigger_state')=='CONFIRMED ENTRY':
                ent['session_entry_state']='AFTER-MARKET SETUP — RECONFIRM NEXT SESSION'
                ent['recommended_action']='AFTER-MARKET REVIEW • RECONFIRM IN REGULAR SESSION'
            else:
                ent['session_entry_state']='AFTER-MARKET REVIEW — '+str(ent.get('trigger_state',ent.get('status','WAIT')))
                if not ent.get('recommended_action'): ent['recommended_action']='RECONFIRM IN NEXT REGULAR SESSION'
        else:
            ent['session_entry_state']=ent.get('trigger_state',ent.get('status','WAIT'))
        if str(ca_report.get('data_quality','OK'))!='OK':
            ent=dict(ent);ent.update({'plan_valid':False,'plan_reason':'Blocked by cross-timeframe data-quality gate','zone_low':np.nan,'zone_high':np.nan,'trigger':np.nan,'invalidation':np.nan,'target1':np.nan,'target2':np.nan})
        daily_lr=f.dropna(subset=['Close']).iloc[-1];live_f=f.copy()
        if hfeat is not None and len(hfeat):
            try:
                rv=float(hfeat.iloc[-1].get('time_adjusted_rvol',np.nan))
                if np.isfinite(rv):live_f.loc[live_f.index[-1],'robust_volume_ratio']=rv;live_f.loc[live_f.index[-1],'volume_ratio']=rv
            except Exception:pass
        latest_live=score_latest(live_f,0)
        # V6.0.7: display the best current/delayed quote found by the fallback chain,
        # while keeping LIVE confirmation gated by the stricter trade_fresh flag.
        lp=float(live_snapshot.get('price',np.nan)) if bool(live_snapshot.get('display_current')) and np.isfinite(float(live_snapshot.get('price',np.nan))) else np.nan
        fallback_lp=float(live_snapshot.get('fallback_price',np.nan)) if np.isfinite(float(live_snapshot.get('fallback_price',np.nan))) else float(daily_lr.get('Close',np.nan))
        if phase_now=='AFTER-MARKET' and np.isfinite(_ah_price): latest_live['price']=_ah_price
        elif np.isfinite(lp): latest_live['price']=lp
        elif np.isfinite(fallback_lp): latest_live['price']=fallback_lp
        fresh_change=bool(live_snapshot.get('display_current')) or phase_now!='OPEN'
        if phase_now=='AFTER-MARKET' and np.isfinite(_total_extended):
            latest_live['daily_change_pct']=_total_extended
        elif fresh_change and np.isfinite(float(live_snapshot.get('change_pct',np.nan))):
            latest_live['daily_change_pct']=float(live_snapshot.get('change_pct'))
        elif phase_now=='OPEN':
            latest_live['daily_change_pct']=np.nan
        ex=explosive_latest(live_f,hfeat) if callable(explosive_latest) else {};timing=signal_timing_latest(live_f,hfeat) if callable(signal_timing_latest) else {}
        active_model=_select_active_model_v613(_load_model_registry_v613(),horizon,target)
        hopt_score,hopt_match,hopt_status,hopt_horizon=_hourly_score_live_v613(t,hfeat,active_model) if active_model.get('scopes') else (np.nan,np.nan,'NO ELIGIBLE HOURLY MODEL','—')
        row=pd.DataFrame([{'Ticker':t,'Prediction':dyn.get('final_prediction',0),'EntryScore':ent.get('entry_score',0),'SetupEntryScore':ent.get('setup_entry_score_pre_chase',ent.get('entry_score',0)),'EntryStatus':ent.get('status','WAIT'),'EntryTriggerState':ent.get('trigger_state',ent.get('status','WAIT')),'SessionEntryState':ent.get('session_entry_state',ent.get('trigger_state',ent.get('status','WAIT'))),'RegularSessionEntryState':ent.get('regular_session_entry_state',ent.get('trigger_state',ent.get('status','WAIT'))),'RegularSessionClose':ent.get('regular_session_close',np.nan),'RegularSessionMovePct':ent.get('regular_session_move_pct',np.nan),'AfterHoursPrice':ent.get('after_hours_price',np.nan),'AfterHoursMovePct':ent.get('after_hours_move_pct',np.nan),'AfterHoursVolumeStrength':ent.get('after_hours_volume_strength',np.nan),'AfterHoursFresh':ent.get('after_hours_fresh',False),'TotalMoveIncludingAHPct':ent.get('total_move_including_ah_pct',np.nan),'EntryConfirmationPct':ent.get('confirmation_pct',0),'DailySetupCheck':ent.get('daily_setup',False),'FreshSignalCheck':ent.get('fresh_signal',False),'HourlyEntryCheck':ent.get('hourly_entry_ok',False),'VolumeFlowCheck':ent.get('volume_flow_ok',False),'NoChaseCheck':ent.get('no_chase',False),'ExtensionGuardCheck':ent.get('extension_guard_ok',True),'ChaseRiskScore':ent.get('chase_risk_score',0),'ChaseRiskLabel':ent.get('chase_risk_label','LOW'),'SessionMovePct':ent.get('session_move_pct',np.nan),'SessionMoveATR':ent.get('session_move_atr',np.nan),'SessionMovePercentile':ent.get('session_move_percentile',np.nan),'SinceTriggerPct':ent.get('since_trigger_pct',np.nan),'GapPct':ent.get('gap_pct',np.nan),'VWAPDistanceATR':ent.get('vwap_distance_atr',np.nan),'EMA9DistanceATR':ent.get('ema9_distance_atr',np.nan),'EMA20DistanceATR':ent.get('ema20_distance_atr',np.nan),'Target1ProgressPct':ent.get('target1_progress_pct',np.nan),'LiveRR_T1':ent.get('live_rr_t1',np.nan),'LiveRR_T2':ent.get('live_rr_t2',np.nan),'LiveRRGuardOK':ent.get('live_rr_guard_ok',True),'CarryoverExtension':ent.get('carryover_extension',False),'CarryoverHardVeto':ent.get('carryover_hard_veto',False),'PriorSessionMovePct':ent.get('prior_session_move_pct',np.nan),'CarryoverRetentionPct':ent.get('carryover_retention_pct',np.nan),'VolumeTrend':ent.get('volume_trend','NO DATA'),'TriggerAnchorPrice':ent.get('trigger_anchor_price',np.nan),'TriggerAnchorTime':ent.get('trigger_anchor_time','—'),'TriggerAnchorTimeframe':ent.get('trigger_anchor_timeframe','—'),'TriggerAnchorQuality':ent.get('trigger_anchor_quality','NONE'),'TriggerAnchorAgeBars':ent.get('trigger_anchor_age_bars',np.nan),'RetestZoneLow':ent.get('retest_zone_low',np.nan),'RetestZoneHigh':ent.get('retest_zone_high',np.nan),'PullbackNeededPct':ent.get('pullback_needed_pct',np.nan),'RetestStatus':ent.get('retest_status','—'),'RecommendedAction':ent.get('recommended_action',''),'MarketRegime':ent.get('market_regime','NEUTRAL'),'EntryWhyNow':ent.get('why_now',''),'EntryMissingChecks':ent.get('missing_checks',''),'MoveScore':timing.get('move_score',0),'ExplosiveScore':ex.get('score',0),'Accel1D':timing.get('accel_1d',0),'Accel2D':timing.get('accel_2d',0),'Accel3D':timing.get('accel_3d',0),'HourlyConfirm':timing.get('hourly_confirmation',ex.get('hourly_confirmation',0)),'CalibrationConfidence':analysis_conf,'BacktestN':int(db.get('n',0) or 0),'EmpiricalHitRate':(round(float(db.get('hit_rate'))*100,1) if db.get('n',0) and np.isfinite(float(db.get('hit_rate',np.nan))) else np.nan),'SignalLift':(float(cmp.get('signal_lift_dynamic')) if np.isfinite(float(cmp.get('signal_lift_dynamic',np.nan))) else 1.0),'ExitPressure':timing.get('exit_pressure',latest_live.get('exit_pressure',0)),'ExitStage':timing.get('exit_stage',latest_live.get('exit_stage','CLEAR')),'TimingStage':timing.get('timing_stage','—'),'PlanValid':ent.get('plan_valid',False),'EntryLow':ent.get('zone_low'),'EntryHigh':ent.get('zone_high'),'BreakoutTrigger':ent.get('trigger'),'Invalidation':ent.get('invalidation'),'Target1':ent.get('target1'),'Target2':ent.get('target2'),'Price':latest_live.get('price'),'VolumeContext':latest_live.get('volume_context','N/A'),'InstitutionalFlowScore':latest_live.get('institutional_flow_score',np.nan),'InstitutionalFlowLabel':latest_live.get('institutional_flow_label','NEUTRAL'),'HourlyOptimizedScore':hopt_score,'HourlyOptimizedMatchPct':hopt_match,'HourlyOptimizedStatus':hopt_status,'HourlyOptimizedHorizon':hopt_horizon,'LiveIntradayRVOL':(hfeat.iloc[-1].get('time_adjusted_rvol',np.nan) if hfeat is not None and len(hfeat) else np.nan),'DailyRobustRVOL':daily_lr.get('robust_volume_ratio',np.nan),'TimeAdjustedRVOL':(hfeat.iloc[-1].get('time_adjusted_rvol',np.nan) if hfeat is not None and len(hfeat) else daily_lr.get('robust_volume_ratio',np.nan)),'RSI14':latest_live.get('rsi14',np.nan),'SplitAdjusted':ca_report.get('split_adjusted',False),'DataQuality':ca_report.get('data_quality','OK'),'LivePriceFresh':bool(live_snapshot.get('trade_fresh')) if phase_now in ('OPEN','AFTER-MARKET') else True}]);decision_df=add_market_and_opportunity(row);decision_df=_apply_optimized_model_v612(decision_df,active_model);decision=decision_df.iloc[0].to_dict(); ent['evidence_state']=decision.get('EvidenceState','UNPROVEN'); ent['evidence_guard_ok']=bool(decision.get('EvidenceGuardOK',True)); _lab_check_v603(runtime,jid)

        _lab_update_v603(runtime,jid,6,8,t,'Walk-forward diagnostics + event study')
        comp=pd.DataFrame(latest['components'],columns=['Component','Points','Max']);comp['Strength %']=(100*comp.Points/comp.Max).round();ec=pd.DataFrame(latest['early_components'],columns=['Component','Points','Max']);ec['Strength %']=(100*ec.Points/ec.Max).round();
        def pct(v):return f'{v*100:.1f}%' if v is not None and np.isfinite(v) else '—'
        def num(v):return f'{v:.2f}x' if v is not None and np.isfinite(v) else '—'
        compare_df=pd.DataFrame([{'Model':'Static','Signals':sb.get('n',0),'Hit Rate':pct(sb.get('hit_rate',np.nan)),'Signal Lift':num(cmp.get('signal_lift_static',np.nan)),'Avg Fwd Return':pct(sb.get('avg_return',np.nan)),'Max Drawdown':pct(sb.get('max_drawdown',np.nan)),'Sample Reliability %':round(sb.get('sample_reliability',0),1)},{'Model':'Dynamic','Signals':db.get('n',0),'Hit Rate':pct(db.get('hit_rate',np.nan)),'Signal Lift':num(cmp.get('signal_lift_dynamic',np.nan)),'Avg Fwd Return':pct(db.get('avg_return',np.nan)),'Max Drawdown':pct(db.get('max_drawdown',np.nan)),'Sample Reliability %':round(db.get('sample_reliability',0),1)}])
        ev=early_event_backtest(f,target/100,(1,2,3),0);early_cal,quant_cal,cal_events=component_calibration(f,target/100,(1,2,3),0);_lab_check_v603(runtime,jid)

        _lab_update_v603(runtime,jid,7,8,t,'Building Analyze workbook')
        summary=pd.DataFrame([{'Ticker':t,'Version':APP_VERSION,'History':hist,'ForecastDays':horizon,'TargetPct':target,'HistoricalQuantThreshold':buy_threshold,'ThresholdMode':'AUTO-RESEARCH','Price':latest_live.get('price'),'LivePrice':live_snapshot.get('price',np.nan),'FallbackOfficialClose':live_snapshot.get('fallback_price',np.nan),'DayChangePct':latest_live.get('daily_change_pct',np.nan),'PriceSource':live_snapshot.get('source'),'PriceTimestamp':live_snapshot.get('timestamp_label'),'PriceFresh':live_snapshot.get('fresh'),'DisplayCurrent':live_snapshot.get('display_current'),'TradeFresh':live_snapshot.get('trade_fresh'),'QuoteStatus':live_snapshot.get('quote_status'),'ProviderTimestampVerified':live_snapshot.get('provider_timestamp_verified'),'StaleProviderPrice':live_snapshot.get('stale_price',np.nan),'StaleProviderTimestamp':live_snapshot.get('stale_timestamp_label','—'),'PreviousOfficialClose':live_snapshot.get('prev_close'),'AnalysisSessionDate':live_snapshot.get('analysis_session_date'),'PreviousSessionDate':live_snapshot.get('previous_session_date'),'SessionContext':live_snapshot.get('session_context'),'TopScore':decision.get('TopScore'),'OpportunityScore':decision.get('OpportunityScore'),'TradeStage':decision.get('TradeStage'),'MovementStage':decision.get('MovementStage'),'ExitPressure':decision.get('ExitPressure'),'ExitStage':decision.get('ExitStage'),'VolumeContext':latest_live.get('volume_context'),'LiveIntradayRVOL':decision.get('LiveIntradayRVOL'),'DailyRobustRVOL':decision.get('DailyRobustRVOL'),'EvidenceQuality':decision.get('EvidenceQuality'),'EvidenceState':decision.get('EvidenceState'),'EvidenceGuardOK':decision.get('EvidenceGuardOK'),'Reliability':decision.get('Reliability'),'DynamicHoldoutSignals':int(db.get('n',0) or 0),'DynamicHoldoutHitRate':db.get('hit_rate',np.nan),'DynamicHoldoutLift':cmp.get('signal_lift_dynamic',np.nan),'WhyNotTradeTrigger':decision.get('WhyNotTradeTrigger'),'SplitDetected':ca_report.get('split_detected'),'SplitRatio':ca_report.get('split_ratio'),'SplitDate':ca_report.get('split_date'),'SplitAdjusted':ca_report.get('split_adjusted'),'DataQuality':ca_report.get('data_quality'),'DataQualityDetails':' | '.join(ca_report.get('details',[])),'DynamicQuant':dyn.get('dynamic_quant'),'DynamicEarly':dyn.get('dynamic_early'),'PredictionScore':dyn.get('final_prediction'),'EntryScore':ent.get('entry_score'),'LiveActionabilityScore':ent.get('live_actionability_score'),'SetupEntryScore':ent.get('setup_entry_score_pre_chase'),'EntryStatus':ent.get('status'),'SessionEntryState':ent.get('session_entry_state'),'RegularSessionEntryState':ent.get('regular_session_entry_state'),'RegularSessionEntryScore':ent.get('regular_session_entry_score'),'MarketPhase':phase_now,'RegularSessionClose':ent.get('regular_session_close'),'RegularSessionMovePct':ent.get('regular_session_move_pct'),'AfterHoursPrice':ent.get('after_hours_price'),'AfterHoursPriceSource':ent.get('after_hours_price_source'),'AfterHoursMovePct':ent.get('after_hours_move_pct'),'AfterHoursVolumeStrength':ent.get('after_hours_volume_strength'),'AfterHoursFresh':ent.get('after_hours_fresh'),'TotalMoveIncludingAHPct':ent.get('total_move_including_ah_pct'),'ChaseRiskScore':ent.get('chase_risk_score'),'ChaseRiskLabel':ent.get('chase_risk_label'),'ExtensionGuardOK':ent.get('extension_guard_ok'),'SessionMovePct':ent.get('session_move_pct'),'SessionMoveATR':ent.get('session_move_atr'),'SessionMovePercentile':ent.get('session_move_percentile'),'MoveBeforeTriggerPct':ent.get('move_before_trigger_pct'),'SinceOriginalTriggerPct':ent.get('since_trigger_pct'),'GapPct':ent.get('gap_pct'),'VWAPDistanceATR':ent.get('vwap_distance_atr'),'Target1ProgressPct':ent.get('target1_progress_pct'),'LiveRR_T1':ent.get('live_rr_t1'),'LiveRR_T2':ent.get('live_rr_t2'),'LiveRRGuardOK':ent.get('live_rr_guard_ok'),'CarryoverExtension':ent.get('carryover_extension'),'CarryoverHardVeto':ent.get('carryover_hard_veto'),'PriorSessionMovePct':ent.get('prior_session_move_pct'),'PriorSessionMoveATR':ent.get('prior_session_move_atr'),'CarryoverRetentionPct':ent.get('carryover_retention_pct'),'CarryoverSourceSessionDate':ent.get('carryover_source_session_date'),'NextSessionCarryoverCandidate':ent.get('next_session_carryover_candidate'),'NextSessionCarryoverHardCandidate':ent.get('next_session_carryover_hard_candidate'),'NextSessionCarryoverReason':ent.get('next_session_carryover_reason'),'OriginToTriggerPct':ent.get('origin_to_trigger_pct'),'TriggerLagMinutes':ent.get('trigger_lag_minutes'),'TriggerLagATR':ent.get('trigger_lag_atr'),'MoveConsumedBeforeTriggerPct':ent.get('move_consumed_before_trigger_pct'),'MoveConsumedBeforeSetupOriginPct':ent.get('move_consumed_before_setup_origin_pct'),'TriggerEfficiencyLabel':ent.get('trigger_efficiency_label'),'VolumeTrend':ent.get('volume_trend'),'VolumeTrend15m':ent.get('volume_trend_15m'),'VolumeTrend1H':ent.get('volume_trend_1h'),'TriggerAnchorPrice':ent.get('trigger_anchor_price'),'TriggerAnchorTime':ent.get('trigger_anchor_time'),'TriggerAnchorBarStartTime':ent.get('trigger_anchor_bar_start_time'),'TriggerAnchorTimeframe':ent.get('trigger_anchor_timeframe'),'TriggerAnchorQuality':ent.get('trigger_anchor_quality'),'TriggerAnchorAgeBars':ent.get('trigger_anchor_age_bars'),'SetupOriginPrice':ent.get('setup_origin_price'),'SetupOriginTime':ent.get('setup_origin_time'),'SetupOriginBarStartTime':ent.get('setup_origin_bar_start_time'),'SetupOriginQuality':ent.get('setup_origin_quality'),'MoveBeforeSetupOriginPct':ent.get('move_before_setup_origin_pct'),'SinceSetupOriginPct':ent.get('since_setup_origin_pct'),'MomentumState':ent.get('momentum_state'),'MomentumState15m':ent.get('momentum_state_15m'),'MomentumState1H':ent.get('momentum_state_1h'),'PostSpikeState':ent.get('post_spike_state'),'SessionPeakPrice':ent.get('session_peak_price'),'SessionPeakMovePct':ent.get('session_peak_move_pct'),'HighGivebackPct':ent.get('high_giveback_pct'),'MoveRetentionFromHighPct':ent.get('move_retention_from_high_pct'),'PostSpikeStructureOK':ent.get('post_spike_structure_ok'),'PostSpikeDistributionRisk':ent.get('post_spike_distribution_risk'),'PostSpikeStructurePrice':ent.get('post_spike_structure_price'),'PostSpikeStructureReference':ent.get('post_spike_structure_reference'),'PostSpikeBearishConfirmBars':ent.get('post_spike_bearish_confirm_bars'),'PostSpikeDistributionScore':ent.get('post_spike_distribution_score'),'ContinuationBaseCandidate':ent.get('continuation_base_candidate'),'ContinuationBaseRawCandidate':ent.get('continuation_base_raw_candidate'),'ContinuationResearchEligible':ent.get('continuation_research_eligible'),'ContinuationInvalidationReason':ent.get('continuation_invalidation_reason'),'ContinuationBaseStatus':ent.get('continuation_base_status'),'ContinuationBaseBars':ent.get('continuation_base_bars'),'ContinuationBaseLow':ent.get('continuation_base_low'),'ContinuationBaseHigh':ent.get('continuation_base_high'),'ContinuationBaseRangePct':ent.get('continuation_base_range_pct'),'ContinuationBaseRangeATR':ent.get('continuation_base_range_atr'),'ContinuationVolumeDryupRatio':ent.get('continuation_volume_dryup_ratio'),'ContinuationBreakoutTrigger':ent.get('continuation_breakout_trigger'),'ContinuationBaseQuality':ent.get('continuation_base_quality'),'ContinuationSessionPeak':ent.get('continuation_session_peak'),'ContinuationBreakoutReference':ent.get('continuation_breakout_reference'),'ContinuationHoldOK':ent.get('continuation_hold_ok'),'RetestZoneLow':ent.get('retest_zone_low'),'RetestZoneHigh':ent.get('retest_zone_high'),'PullbackNeededPct':ent.get('pullback_needed_pct'),'RetestStatus':ent.get('retest_status'),'RecommendedAction':ent.get('recommended_action'),'EntryZoneLow':ent.get('zone_low'),'EntryZoneHigh':ent.get('zone_high'),'BreakoutTrigger':ent.get('trigger'),'Invalidation':ent.get('invalidation'),'Target1':ent.get('target1'),'Target2':ent.get('target2'),'ExplosiveScore':ex.get('score',np.nan),'MoveScore':timing.get('move_score',np.nan),'HourlyConfirmation':timing.get('hourly_confirmation',np.nan),'BacktestSignals':bt.get('n',0),'BacktestHitRate':bt.get('hit_rate',np.nan),'BacktestAvgReturn':bt.get('avg_return',np.nan),'BacktestWorstDrawdown':bt.get('max_drawdown',np.nan)}])
        origin_validation=setup_origin_validation_v619(m15feat,target_pct=.02,stop_pct=.015,max_bars=16) if m15feat is not None else pd.DataFrame()
        origin_validation_summary=setup_origin_validation_summary_v620(origin_validation)
        origin_robustness=setup_origin_robustness_v620(m15feat) if m15feat is not None else pd.DataFrame()
        continuation_validation=continuation_base_validation_v621(m15feat,breakout_lookahead=8,target_pct=.02,stop_pct=.015,outcome_bars=16) if m15feat is not None else pd.DataFrame()
        continuation_validation_summary=continuation_base_validation_summary_v621(continuation_validation)
        origin_matched_baseline=setup_origin_matched_baseline_v622(m15feat,target_pct=.02,stop_pct=.015,max_bars=16) if m15feat is not None else pd.DataFrame()
        origin_matched_confidence=setup_origin_matched_confidence_v623(origin_matched_baseline)
        research_evidence_summary=research_evidence_summary_v622(origin_validation_summary,origin_matched_baseline,origin_robustness,continuation_validation_summary)
        entry_audit=pd.DataFrame([{'Ticker':t,'EntryScoreLive':ent.get('entry_score'),'LiveActionabilityScore':ent.get('live_actionability_score'),'SetupEntryScorePreChase':ent.get('setup_entry_score_pre_chase'),'EntryStatus':ent.get('status'),'SessionEntryState':ent.get('session_entry_state'),'RegularSessionEntryState':ent.get('regular_session_entry_state'),'RegularSessionEntryScore':ent.get('regular_session_entry_score'),'MarketPhase':phase_now,'RegularSessionMovePct':ent.get('regular_session_move_pct'),'AfterHoursPrice':ent.get('after_hours_price'),'AfterHoursPriceSource':ent.get('after_hours_price_source'),'AfterHoursMovePct':ent.get('after_hours_move_pct'),'AfterHoursVolumeStrength':ent.get('after_hours_volume_strength'),'TotalMoveIncludingAHPct':ent.get('total_move_including_ah_pct'),'ChaseRiskScore':ent.get('chase_risk_score'),'ChaseRiskLabel':ent.get('chase_risk_label'),'SessionMovePct':ent.get('session_move_pct'),'SessionMoveATR':ent.get('session_move_atr'),'SessionMovePercentile':ent.get('session_move_percentile'),'MoveBeforeTriggerPct':ent.get('move_before_trigger_pct'),'SinceOriginalTriggerPct':ent.get('since_trigger_pct'),'GapPct':ent.get('gap_pct'),'TriggerAnchorPrice':ent.get('trigger_anchor_price'),'TriggerAnchorTime':ent.get('trigger_anchor_time'),'TriggerAnchorBarStartTime':ent.get('trigger_anchor_bar_start_time'),'TriggerAnchorTimeframe':ent.get('trigger_anchor_timeframe'),'TriggerAnchorQuality':ent.get('trigger_anchor_quality'),'TriggerAnchorAgeBars':ent.get('trigger_anchor_age_bars'),'TriggerAnchorSelection':ent.get('trigger_anchor_selection'),'TriggerAnchorSignals':ent.get('trigger_anchor_signals'),'SetupOriginPrice':ent.get('setup_origin_price'),'SetupOriginTime':ent.get('setup_origin_time'),'SetupOriginBarStartTime':ent.get('setup_origin_bar_start_time'),'SetupOriginSignals':ent.get('setup_origin_signals'),'SetupOriginQuality':ent.get('setup_origin_quality'),'MoveBeforeSetupOriginPct':ent.get('move_before_setup_origin_pct'),'SinceSetupOriginPct':ent.get('since_setup_origin_pct'),'MomentumState':ent.get('momentum_state'),'MomentumState15m':ent.get('momentum_state_15m'),'MomentumState1H':ent.get('momentum_state_1h'),'PostSpikeState':ent.get('post_spike_state'),'SessionPeakPrice':ent.get('session_peak_price'),'SessionPeakMovePct':ent.get('session_peak_move_pct'),'HighGivebackPct':ent.get('high_giveback_pct'),'MoveRetentionFromHighPct':ent.get('move_retention_from_high_pct'),'PostSpikeStructureOK':ent.get('post_spike_structure_ok'),'PostSpikeDistributionRisk':ent.get('post_spike_distribution_risk'),'PostSpikeStructurePrice':ent.get('post_spike_structure_price'),'PostSpikeStructureReference':ent.get('post_spike_structure_reference'),'PostSpikeBearishConfirmBars':ent.get('post_spike_bearish_confirm_bars'),'PostSpikeDistributionScore':ent.get('post_spike_distribution_score'),'ContinuationBaseCandidate':ent.get('continuation_base_candidate'),'ContinuationBaseRawCandidate':ent.get('continuation_base_raw_candidate'),'ContinuationResearchEligible':ent.get('continuation_research_eligible'),'ContinuationInvalidationReason':ent.get('continuation_invalidation_reason'),'ContinuationBaseStatus':ent.get('continuation_base_status'),'ContinuationBaseBars':ent.get('continuation_base_bars'),'ContinuationBaseLow':ent.get('continuation_base_low'),'ContinuationBaseHigh':ent.get('continuation_base_high'),'ContinuationBaseRangePct':ent.get('continuation_base_range_pct'),'ContinuationBaseRangeATR':ent.get('continuation_base_range_atr'),'ContinuationVolumeDryupRatio':ent.get('continuation_volume_dryup_ratio'),'ContinuationBreakoutTrigger':ent.get('continuation_breakout_trigger'),'ContinuationBaseQuality':ent.get('continuation_base_quality'),'ContinuationSessionPeak':ent.get('continuation_session_peak'),'ContinuationBreakoutReference':ent.get('continuation_breakout_reference'),'ContinuationHoldOK':ent.get('continuation_hold_ok'),'RetestConfirmationNeeded':ent.get('retest_confirmation_needed'),'VWAPDistanceATR':ent.get('vwap_distance_atr'),'EMA9DistanceATR':ent.get('ema9_distance_atr'),'EMA20DistanceATR':ent.get('ema20_distance_atr'),'Target1ProgressPct':ent.get('target1_progress_pct'),'LiveRR_T1':ent.get('live_rr_t1'),'LiveRR_T2':ent.get('live_rr_t2'),'LiveRRGuardOK':ent.get('live_rr_guard_ok'),'CarryoverExtension':ent.get('carryover_extension'),'CarryoverHardVeto':ent.get('carryover_hard_veto'),'PriorSessionMovePct':ent.get('prior_session_move_pct'),'PriorSessionMoveATR':ent.get('prior_session_move_atr'),'CarryoverRetentionPct':ent.get('carryover_retention_pct'),'NextSessionCarryoverCandidate':ent.get('next_session_carryover_candidate'),'NextSessionCarryoverHardCandidate':ent.get('next_session_carryover_hard_candidate'),'NextSessionCarryoverReason':ent.get('next_session_carryover_reason'),'OriginToTriggerPct':ent.get('origin_to_trigger_pct'),'TriggerLagMinutes':ent.get('trigger_lag_minutes'),'TriggerLagATR':ent.get('trigger_lag_atr'),'MoveConsumedBeforeTriggerPct':ent.get('move_consumed_before_trigger_pct'),'MoveConsumedBeforeSetupOriginPct':ent.get('move_consumed_before_setup_origin_pct'),'TriggerEfficiencyLabel':ent.get('trigger_efficiency_label'),'RetestZoneLow':ent.get('retest_zone_low'),'RetestZoneHigh':ent.get('retest_zone_high'),'PullbackNeededPct':ent.get('pullback_needed_pct'),'RetestReference':ent.get('retest_reference'),'RetestReferenceLabel':ent.get('retest_reference_label'),'RetestStatus':ent.get('retest_status'),'VolumeTrend':ent.get('volume_trend'),'VolumeTrend15m':ent.get('volume_trend_15m'),'VolumeTrend1H':ent.get('volume_trend_1h'),'EvidenceState':decision.get('EvidenceState'),'EvidenceGuardOK':decision.get('EvidenceGuardOK'),'RecommendedAction':ent.get('recommended_action'),'BacktestSignals':bt.get('n',0),'BacktestConfidence':bt.get('confidence',0),'DynamicHoldoutLift':cmp.get('signal_lift_dynamic',np.nan)}]);sheets={'Summary':summary,'Entry Audit':entry_audit,'Historical Quant Threshold Evidence':auto_table,'Quant Components':comp,'Early Components':ec,'Static vs Dynamic':compare_df,'Daily Features':f.reset_index(),'Event Study':ev,'Early Calibration':early_cal,'Quant Calibration':quant_cal,'Setup Origin Validation Summary':origin_validation_summary,'Setup Origin Validation':origin_validation,'Setup Origin Robustness':origin_robustness,'Setup Origin Matched Baseline':origin_matched_baseline,'Setup Origin Matched Confidence':origin_matched_confidence,'Research Evidence Summary':research_evidence_summary,'Continuation Validation Summary':continuation_validation_summary,'Continuation Validation':continuation_validation};
        if hfeat is not None and len(hfeat):sheets['Hourly Features']=hfeat.tail(260).reset_index()
        if m15feat is not None and len(m15feat):sheets['15m Features']=m15feat.tail(1100).reset_index()
        if callable(historical_signal_timeline):
            atl=historical_signal_timeline(f);sheets['Signal Timeline']=atl
            if callable(acceleration_validation):sheets['Acceleration Validation']=acceleration_validation(atl)
        if isinstance(dyn.get('early_calibration',{}).get('table'),pd.DataFrame):sheets['Dynamic Early Calibration']=dyn['early_calibration']['table']
        if isinstance(dyn.get('quant_calibration',{}).get('table'),pd.DataFrame):sheets['Dynamic Quant Calibration']=dyn['quant_calibration']['table']
        combos=dyn.get('combinations',pd.DataFrame())
        if isinstance(combos,pd.DataFrame) and not combos.empty:sheets['Combinations']=combos
        excel=None; excel_error=None
        try:
            excel=workbook_bytes(sheets,{'Tab':'Analyze','Ticker':t,'Version':APP_VERSION})
        except Exception as _excel_exc:
            # Excel export must never invalidate an otherwise completed market analysis.
            excel_error=f'{type(_excel_exc).__name__}: {_excel_exc}'
        payload={'ticker':t,'history':hist,'horizon':horizon,'target':target,'f':f,'latest':latest,'dyn':dyn,'hfeat':hfeat,'ent':ent,'latest_live':latest_live,'live_snapshot':live_snapshot,'ah_snapshot':ah_snapshot,'ex':ex,'timing':timing,'decision':decision,'ca_report':ca_report,'bt':bt,'buy_threshold':buy_threshold,'auto_table':auto_table,'comp':comp,'ec':ec,'cmp':cmp,'compare_df':compare_df,'ev':ev,'early_cal':early_cal,'quant_cal':quant_cal,'cal_events':cal_events,'origin_validation_summary':origin_validation_summary,'origin_robustness':origin_robustness,'origin_matched_baseline':origin_matched_baseline,'origin_matched_confidence':origin_matched_confidence,'research_evidence_summary':research_evidence_summary,'continuation_validation_summary':continuation_validation_summary,'continuation_validation':continuation_validation,'excel':excel,'excel_error':excel_error}
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


def _entry_payload_v603(rows,audit,skipped,cfg,partial=False,premove_rows=None,hourly_rows=None,hourly_obs_rows=None):
    summary,gate,market_gate=_aggregate_entry_validation(rows)
    opt,opt_weights,shadow_model=_entry_optimizer_v611(rows)
    shadow_model['source_universe']=cfg.get('market','CUSTOM') if isinstance(shadow_model,dict) else 'CUSTOM'
    hop,hweights,hmodel=_hourly_optimizer_v613(hourly_obs_rows or [],min_signals=max(60,int(cfg.get('min_events',25))*2))
    registry=_load_model_registry_v613()
    if not partial and isinstance(shadow_model,dict) and shadow_model.get('scopes'):
        registry=_register_model_v613(shadow_model,cfg,hmodel)
    pm=pd.DataFrame(premove_rows or []);hl=pd.DataFrame(hourly_rows or [])
    pm_summary=_aggregate_lift_rows_v611(pm,['Indicator','Days Before','Target','Horizon'],'Baseline %') if not pm.empty else pd.DataFrame()
    pm_market=_aggregate_lift_rows_v611(pm,['Market','Indicator','Days Before','Target','Horizon'],'Baseline %') if not pm.empty else pd.DataFrame()
    hl_summary=_aggregate_lift_rows_v611(hl,['Signal','Target','Horizon'],'Matched Baseline %') if not hl.empty else pd.DataFrame()
    hl_market=_aggregate_lift_rows_v611(hl,['Market','Signal','Target','Horizon'],'Matched Baseline %') if not hl.empty else pd.DataFrame()
    active=_select_active_model_v613(registry,int(cfg.get('horizon',3)),float(cfg.get('target',3)))
    regsel=_registry_selection_frame_v613(active)
    sheets={'Entry Summary':summary,'Entry Trigger V4 Gate':gate,'Entry Gate by Market':market_gate,'Daily OOS Optimizer':opt,'Daily OOS Weights':opt_weights,'Hourly OOS Optimizer':hop,'Hourly OOS Weights':hweights,'Registry Selection':regsel,'Pre-Move Lift Summary':pm_summary,'Pre-Move by Market':pm_market,'Pre-Move Indicator Lift':pm,'Hourly Lift Summary':hl_summary,'Hourly Lift by Market':hl_market,'Hourly Matched Lift':hl,'Raw Observations':pd.DataFrame(rows),'Stock Audit':pd.DataFrame(audit)}
    if skipped:sheets['Skipped']=pd.DataFrame(skipped,columns=['Ticker','Reason'])
    excel=workbook_bytes(sheets,{'Tab':'Adaptive Entry Optimizer','Market':cfg.get('market','CUSTOM'),'History':cfg['history'],'TargetPct':cfg['target'],'HorizonDays':cfg['horizon'],'HourlyTargetPct':cfg.get('hourly_target',3),'HourlyHorizons':','.join(f'{int(x)}h' for x in cfg.get('hourly_bars',(1,2,4))),'MinTrainEvents':cfg['min_events'],'Status':'PARTIAL / STOPPED' if partial else 'COMPLETED','RegistryModels':len(registry.get('models',[])),'Note':'V6.1.4 keeps the persistent model registry and adds Trigger Anchor V2 / Chase audit. Optimized Scanner selects the best SHADOW ELIGIBLE OOS model by market/horizon/target instead of the latest run. Hourly timing has its own OOS optimizer.'})
    return {'summary':summary,'gate':gate,'market_gate':market_gate,'optimizer':opt,'optimizer_weights':opt_weights,'hourly_optimizer':hop,'hourly_optimizer_weights':hweights,'shadow_model':shadow_model,'model_registry':registry,'registry_selection':regsel,'premove':pm,'premove_summary':pm_summary,'premove_market':pm_market,'hourly_lift':hl,'hourly_summary':hl_summary,'hourly_market':hl_market,'audit':pd.DataFrame(audit),'skipped':pd.DataFrame(skipped,columns=['Ticker','Reason']) if skipped else pd.DataFrame(),'excel':excel,'partial':partial,'observations':len(rows)//2,'hourly_observations':len(hourly_obs_rows or [])}


def _entry_worker_v603(runtime,jid,cfg):
    rows=[];audit=[];skipped=[];premove_rows=[];hourly_rows=[];hourly_obs_rows=[];completed=0;folds=[(.40,.55),(.55,.70),(.70,.85),(.85,1.00)];total=len(cfg['tickers'])
    try:
        for idx,t in enumerate(cfg['tickers'],1):
            _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,completed,total,t,'Entry + hourly OOS walk-forward')
            try:
                stock_rows=[];d=fetch_ohlcv(t,cfg['history'],'1d');_lab_check_v603(runtime,jid)
                if d is None:skipped.append((t,'no price data returned'));completed=idx;continue
                if len(d)<180:skipped.append((t,f'only {len(d)} daily rows; need at least 180'));completed=idx;continue
                f=compute_features(d).dropna(subset=['Close']).copy();usable=0;tested=0;hourly_n=0
                try:
                    if callable(pre_move_indicator_lift):
                        pm=pre_move_indicator_lift(f,targets=tuple(sorted(set((int(cfg['target']),5,10)))),horizons=(int(cfg['horizon']),),lags=(1,2,3),min_signals=10)
                        if pm is not None and not pm.empty:
                            pm=pm.copy();pm.insert(0,'Market',_market_for_ticker_v612(t));pm.insert(0,'Ticker',t);premove_rows.extend(pm.to_dict('records'))
                except Exception:pass
                try:
                    # Yahoo/yfinance normally supports up to ~730 days for 1h data; request 2y even when daily research is longer.
                    hraw=fetch_ohlcv(t,'2y','1h')
                    if hraw is None or len(hraw)<120:hraw=fetch_ohlcv(t,'6mo','1h')
                    if hraw is not None and len(hraw)>=80:
                        hf=compute_features(hraw,True)
                        if callable(hourly_lift_study):
                            hs=hourly_lift_study(hf,targets=(int(cfg.get('hourly_target',3)),),horizon_bars=tuple(cfg.get('hourly_bars',(1,2,4))),min_signals=10)
                            if hs is not None and not hs.empty:
                                hs=hs.copy();hs.insert(0,'Market',_market_for_ticker_v612(t));hs.insert(0,'Ticker',t);hourly_rows.extend(hs.to_dict('records'))
                        obs=_hourly_optimizer_observations_v613(hf,t,float(cfg.get('hourly_target',3))/100.0,tuple(cfg.get('hourly_bars',(1,2,4))))
                        hourly_obs_rows.extend(obs);hourly_n=len(obs)
                except Exception:pass
                for fold,(train_end,test_end) in enumerate(folds,1):
                    _lab_check_v603(runtime,jid);i1=max(80,int(len(f)*train_end));i2=min(len(f),int(len(f)*test_end))
                    if i2-i1<max(25,int(cfg['horizon'])+5):continue
                    train=f.iloc[:i1].copy();test=f.iloc[i1:i2].copy();ec=_v544_calibrate_components(train,'early',float(cfg['target'])/100,(1,2,3),0);qc=_v544_calibrate_components(train,'quant',float(cfg['target'])/100,(1,2,3),0);train_events=min(int(ec.get('events',0) or 0),int(qc.get('events',0) or 0))
                    if train_events<int(cfg['min_events']):continue
                    hit,ret,mfe,mae,days=_entry_forward_metrics(test,int(cfg['horizon']),float(cfg['target'])/100);fold_rows=0
                    for j in range(len(test)):
                        if not np.isfinite(hit[j]):continue
                        r=test.iloc[j];sq=float(score_row(r,0)[0]);se=float(early_score_row(r)[0]);dq,_=_v544_dynamic_score_row(r,qc,'quant',0);de,_=_v544_dynamic_score_row(r,ec,'early',0);static_entry=_entry_score_from_row(r,sq,se);dynamic_entry=_entry_score_from_row(r,dq,de);common={'Ticker':t,'Market':_market_for_ticker_v612(t),'Fold':fold,'Hit':float(hit[j]),'ForwardReturn':float(ret[j]),'Drawdown':float(mae[j]),'MFE':float(mfe[j]),'MAE':float(mae[j]),'DaysToTarget':float(days[j]) if np.isfinite(days[j]) else np.nan};sg=_entry_research_gate_v610(r,sq,static_entry);dg=_entry_research_gate_v610(r,dq,dynamic_entry);stock_rows.append({**common,'Mode':'Static','EntryScore':static_entry,'QuantScore':sq,'EarlyScore':se,'Bucket':_entry_bucket(static_entry),**sg});stock_rows.append({**common,'Mode':'Dynamic','EntryScore':dynamic_entry,'QuantScore':dq,'EarlyScore':de,'Bucket':_entry_bucket(dynamic_entry),**dg});fold_rows+=1
                    if fold_rows:usable+=1;tested+=fold_rows
                if usable<2:skipped.append((t,f'only {usable} usable walk-forward folds'));completed=idx;continue
                rows.extend(stock_rows);audit.append({'Ticker':t,'Rows':len(f),'Usable folds':usable,'Test rows':tested,'Hourly OOS observations':hourly_n})
            except _LabCancelled:raise
            except Exception as e:skipped.append((t,f'calculation/data error: {type(e).__name__}'))
            completed=idx;_lab_update_v603(runtime,jid,completed,total,t,'Ticker complete')
        _lab_check_v603(runtime,jid);_lab_publish_v603(runtime,jid,_entry_payload_v603(rows,audit,skipped,cfg,False,premove_rows,hourly_rows,hourly_obs_rows))
    except _LabCancelled:
        try:payload=_entry_payload_v603(rows,audit,skipped,cfg,True,premove_rows,hourly_rows,hourly_obs_rows)
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
        _lab_update_v603(runtime,jid,0,1,'Outcomes','Evaluating due 1D / 2D / 3D / 5D windows');_lab_check_v603(runtime,jid);n=_feedback_evaluate_due_v600(max_snapshots=int(cfg.get('max_snapshots',80)));_lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,1,1,'Outcomes','Completed');_lab_publish_v603(runtime,jid,{'evaluated':n})
    except _LabCancelled:_lab_publish_v603(runtime,jid,None,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)


def _historical_replay_worker_v630(runtime,jid,cfg):
    """V6.3.3 causal daily replay with V2 audit plus combination Discovery/OOS research."""
    try:
        tickers=list(cfg.get('tickers') or []);total=len(tickers);history=str(cfg.get('history','1y'));target=float(cfg.get('target_pct',.05));h=int(cfg.get('horizon_days',3));step=max(1,int(cfg.get('sample_every',5)))
        final_steps=5;work_total=max(1,total+final_steps)
        rows=[];skipped=[];successful=0
        for n,t in enumerate(tickers,1):
            _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,n-1,work_total,t,'Historical Replay V3 • causal daily evidence')
            try:
                d=fetch_ohlcv(t,history,'1d')
                if d is None or len(d)<100:raise ValueError('Need at least 100 daily bars')
                f=compute_features(d).dropna(subset=['Close']).copy()
                if len(f)>1:f=f.iloc[:-1].copy()
                if len(f)<90+h:raise ValueError('Insufficient completed daily history after feature warm-up')
                successful+=1;start_i=70;last=len(f)-h
                for i in range(start_i,last,step):
                    r=f.iloc[i];p0=float(r.get('Close',np.nan))
                    if not np.isfinite(p0) or p0<=0:continue
                    q=float(score_row(r,0)[0]) if callable(score_row) else np.nan;es=float(early_score_row(r)[0]) if callable(early_score_row) else np.nan;ent=float(_entry_score_from_row(r,q,es))
                    atrp=float(r.get('atr_pct',np.nan)) if pd.notna(r.get('atr_pct',np.nan)) else np.nan;stop_pct=float(np.clip(1.20*(atrp/100.0),.02,.06)) if np.isfinite(atrp) else .03
                    t1=p0*(1+target);inv=p0*(1-stop_pct);future=f.iloc[i+1:i+1+h]
                    if len(future)<h:continue
                    first='NONE'
                    for _,bar in future.iterrows():
                        ht=bool(float(bar.High)>=t1);hi=bool(float(bar.Low)<=inv)
                        if ht and hi:first='AMBIGUOUS SAME DAILY BAR';break
                        if hi:first='INVALIDATION FIRST (daily replay)';break
                        if ht:first='TARGET1 FIRST (daily replay)';break
                    outcome='WIN' if first.startswith('TARGET1 FIRST') else ('LOSS' if first.startswith('INVALIDATION FIRST') else ('AMBIGUOUS' if first.startswith('AMBIGUOUS') else 'OPEN/NONE'))
                    endret=float(future.Close.iloc[-1]/p0-1);mfe=float(future.High.max()/p0-1);mae=float(future.Low.min()/p0-1)
                    recent2=float(p0/float(f.iloc[i-2].Close)-1) if i>=2 and float(f.iloc[i-2].Close)>0 else np.nan
                    setup=_feedback_replay_setup_v631(r,target,recent2)
                    legacy=bool(ent>=55 and (es>=50 or q>=60));r_mult=(target/stop_pct if outcome=='WIN' else (-1.0 if outcome=='LOSS' else np.nan))
                    try:sigdate=str(pd.Timestamp(f.index[i]).date())
                    except Exception:sigdate=str(f.index[i])
                    rows.append({'Ticker':str(t),'Market':_feedback_market_key_v612('',str(t)),'SignalDate':sigdate,'Price':p0,'QuantScore':q,'EarlyScore':es,'EntryScore':ent,'ATRPct':atrp,'Target1':t1,'Invalidation':inv,'EndReturn':endret,'MFE':mfe,'MAE':mae,'FirstEvent':first,'CleanOutcome':outcome,'Indicators':' | '.join(setup['active']),'Candidate':setup['candidate_v2'],'LegacyCandidate':legacy,'CandidateV2':setup['candidate_v2'],'HighConfidence':False,'FamilySignature':setup['family_signature'],'IndependentFamilyCount':setup['family_count'],'FreshnessState':setup['freshness_state'],'MoveConsumedPct':setup['move_consumed_pct'],'ExtensionATR':setup['extension_atr'],'DistributionRisk':setup['distribution_risk'],'SetupScoreV2':setup['setup_score_v2'],'MetaProbability':np.nan,'MetaSample':0,'MetaLift':np.nan,'RMultiple':r_mult,'Recent2DReturn':recent2,'CoreMomentum':setup['core_momentum'],'CoreVolumeFlow':setup['core_volume_flow'],'CandidateRuleVersion':'V6.3.3 DAILY-V2+COMBO-OOS'})
            except Exception as e:skipped.append({'Ticker':str(t),'Reason':f'{type(e).__name__}: {e}'})
            _lab_update_v603(runtime,jid,n,work_total,t,'Historical Replay V3 • ticker complete')
        _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,total,work_total,'Meta model','Finalizing • causal meta probabilities')
        df=_feedback_replay_apply_meta_v631(pd.DataFrame(rows)) if rows else pd.DataFrame()
        _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,total+1,work_total,'Combination Discovery','70% discovery • independent-family combinations • untouched 30% OOS')
        combos,combo_folds,combo_gates,df=_feedback_replay_combination_discovery_v633(df)
        rows=df.to_dict('records') if not df.empty else []
        _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,total+2,work_total,'Replay database','Finalizing • saving replay + combination evidence')
        _feedback_store_replay_v630(jid,rows,cfg,successful,combos,combo_folds)
        _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,total+3,work_total,'Scorecards','Finalizing • success / lift / walk-forward validation')
        head,inds,stocks,gates,cal=_feedback_replay_scorecards_v631(df)
        _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,total+4,work_total,'Excel','Finalizing • building workbook')
        excel=_feedback_workbook_v629({'Replay Success':head,'Replay Gate Comparison':gates,'V3 OOS Gate Comparison':combo_gates,'Combination Discovery':combos,'WalkForward Folds':combo_folds,'Replay Meta Calibration':cal,'Replay Indicators':inds,'Replay Stocks':stocks,'Replay Events':df,'Skipped':pd.DataFrame(skipped)},{'Tab':'Historical Replay V3','Version':APP_VERSION,'Scope':cfg.get('scope'),'History':history,'TargetPct':100*target,'HorizonDays':h,'SampleEverySessions':step,'RequestedStocks':total,'SuccessfulStocks':successful,'DiscoveryValidation':'70% chronological discovery / 30% untouched OOS validation; 3 chronological OOS folds','ResearchOnly':'YES — combination discovery is research-only; no Production Entry rules changed'})
        _lab_publish_v603(runtime,jid,{'events':df,'headline':head,'indicators':inds,'stocks':stocks,'gates':gates,'calibration':cal,'combinations':combos,'combo_folds':combo_folds,'combo_gates':combo_gates,'skipped':pd.DataFrame(skipped),'excel':excel,'successful':successful})
    except _LabCancelled:_lab_publish_v603(runtime,jid,None,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)


def _research_validator_universe_v624(scope, max_tickers):
    """Deterministic expanded research universe selection (V6.2.9)."""
    def arr(txt): return [x.strip().upper() for x in str(txt).split(',') if x.strip()]
    max_tickers=max(1,int(max_tickers))
    if scope=='NASDAQ': return arr(NASDAQ_200)[:max_tickers]
    if scope=='US': return arr(US_201)[:max_tickers]
    if scope=='HONG KONG': return arr(HK_100)[:max_tickers]
    if scope=='TEL AVIV': return arr(TASE_50)[:max_tickers]
    groups=[arr(NASDAQ_200),arr(HK_100),arr(TASE_50)]; out=[]; k=0
    while len(out)<max_tickers and any(k<len(g) for g in groups):
        for g in groups:
            if k<len(g) and len(out)<max_tickers: out.append(g[k])
        k+=1
    return out


def _research_validator_worker_v624(runtime,jid,cfg):
    """Cross-stock fixed-rule research validator; no production weights change."""
    try:
        tickers=list(cfg.get('tickers') or []); target=float(cfg.get('target_pct',.02)); stop=float(cfg.get('stop_pct',.015)); horizon=int(cfg.get('horizon_bars',16))
        stock_rows=[]; pair_frames=[]; cont_frames=[]; skipped=[]
        total=max(1,len(tickers))
        for i,t in enumerate(tickers,1):
            _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,i-1,total,t,'Downloading 60d 15m research history')
            try:
                m15=confirmed_intraday_bars(fetch_ohlcv(t,'60d','15m'))
                if m15 is None or len(m15)<30: raise ValueError('Not enough 15m history')
                f15=compute_features(m15,True)
                pairs=setup_origin_session_pairs_v624(f15,target_pct=target,stop_pct=stop,max_bars=horizon)
                cont=continuation_base_validation_v621(f15,breakout_lookahead=8,target_pct=target,stop_pct=stop,outcome_bars=horizon)
                base=setup_origin_matched_baseline_v622(f15,target_pct=target,stop_pct=stop,max_bars=horizon)
                robust=setup_origin_robustness_v620(f15)
                market=_market_for_ticker_v612(t)
                if pairs is not None and not pairs.empty:
                    pairs=pairs.copy();pairs.insert(0,'Market',market);pairs.insert(0,'Ticker',t);pair_frames.append(pairs)
                if cont is not None and not cont.empty:
                    cont=cont.copy();cont.insert(0,'Market',market);cont.insert(0,'Ticker',t);cont_frames.append(cont)
                clean_pairs=pairs[np.isfinite(pd.to_numeric(pairs.get('SignalWin'),errors='coerce')) & np.isfinite(pd.to_numeric(pairs.get('BaselineHitRatePctLOO'),errors='coerce'))] if isinstance(pairs,pd.DataFrame) and not pairs.empty else pd.DataFrame()
                _sig_hr=100*pd.to_numeric(clean_pairs.get('SignalWin'),errors='coerce').mean() if len(clean_pairs) else np.nan
                _base_hr=pd.to_numeric(clean_pairs.get('BaselineHitRatePctLOO'),errors='coerce').mean() if len(clean_pairs) else np.nan
                _lift=(_sig_hr/_base_hr) if np.isfinite(_sig_hr) and np.isfinite(_base_hr) and _base_hr>0 else np.nan
                _exp_delta=pd.to_numeric(clean_pairs.get('ExpectancyEdgePct'),errors='coerce').mean() if len(clean_pairs) else np.nan
                rvals=pd.to_numeric(robust.get('GrossExpectancyPct'),errors='coerce').dropna() if isinstance(robust,pd.DataFrame) and not robust.empty else pd.Series(dtype=float)
                stock_rows.append({'Ticker':t,'Market':market,'15mBars':len(f15),'MatchedSignals':len(pairs) if isinstance(pairs,pd.DataFrame) else 0,
                                   'CleanMatchedSignals':len(clean_pairs),'SignalHitRatePct':_sig_hr,
                                   'MatchedBaselineHitRatePct':_base_hr,
                                   'MatchedHitRateLiftX':_lift,
                                   'MatchedExpectancyDeltaPct':_exp_delta,
                                   'RobustnessPositiveScenarios':int((rvals>0).sum()) if len(rvals) else 0,'RobustnessScenarios':int(len(rvals)),
                                   'ContinuationCandidates':len(cont) if isinstance(cont,pd.DataFrame) else 0,
                                   'ContinuationClean':int(cont['PostBreakoutOutcome'].isin(['TARGET','STOP']).sum()) if isinstance(cont,pd.DataFrame) and not cont.empty else 0,
                                   'ContinuationTargets':int((cont['PostBreakoutOutcome']=='TARGET').sum()) if isinstance(cont,pd.DataFrame) and not cont.empty else 0})
            except Exception as e:
                skipped.append({'Ticker':t,'Reason':f'{type(e).__name__}: {e}'})
            _lab_update_v603(runtime,jid,i,total,t,'Cross-stock research validation')
        pairs_all=pd.concat(pair_frames,ignore_index=True) if pair_frames else pd.DataFrame()
        cont_all=pd.concat(cont_frames,ignore_index=True) if cont_frames else pd.DataFrame()
        summary_rows=[]
        scopes=['ALL']+sorted(pairs_all['Market'].dropna().astype(str).unique().tolist()) if not pairs_all.empty else ['ALL']
        for scope in scopes:
            sub=pairs_all if scope=='ALL' else pairs_all[pairs_all['Market'].astype(str)==scope]
            boot=cluster_bootstrap_matched_edge_v624(sub,n_boot=int(cfg.get('bootstrap_runs',1200)),seed=624)
            bm=dict(zip(boot['Metric'].astype(str),boot['Value'])) if isinstance(boot,pd.DataFrame) and not boot.empty else {}
            cc=cont_all if scope=='ALL' else (cont_all[cont_all['Market'].astype(str)==scope] if not cont_all.empty else pd.DataFrame())
            clean_cont=cc[cc['PostBreakoutOutcome'].isin(['TARGET','STOP'])] if not cc.empty else pd.DataFrame()
            summary_rows.append({'Scope':scope,'Stocks':int(sub['Ticker'].nunique()) if not sub.empty else 0,'CleanMatchedSignals':bm.get('Clean matched signal N',0),
                                 'ClusteredSessionDates':bm.get('Unique clustered session dates',0),'SignalHitRatePct':bm.get('Signal hit rate %',np.nan),
                                 'MatchedBaselineHitRatePct':bm.get('Mean LOO matched baseline hit rate %',np.nan),'HitRateEdgePP':bm.get('Observed matched hit-rate edge pp',np.nan),
                                 'Bootstrap95LowPP':bm.get('Session-cluster bootstrap 95% low pp',np.nan),'Bootstrap95HighPP':bm.get('Session-cluster bootstrap 95% high pp',np.nan),
                                 'BootstrapPValue':bm.get('Bootstrap two-sided p-value',np.nan),'ExpectancyEdgePct':bm.get('Observed expectancy edge % / signal',np.nan),
                                 'ExpectancyBootstrapLowPct':bm.get('Expectancy edge bootstrap 95% low %',np.nan),'ExpectancyBootstrapHighPct':bm.get('Expectancy edge bootstrap 95% high %',np.nan),
                                 'SetupOriginResearchState':bm.get('Research state','NO SAMPLE'),'ContinuationCleanN':len(clean_cont),
                                 'ContinuationTargets':int((clean_cont['PostBreakoutOutcome']=='TARGET').sum()) if len(clean_cont) else 0,
                                 'ContinuationHitRatePct':100*float((clean_cont['PostBreakoutOutcome']=='TARGET').mean()) if len(clean_cont) else np.nan,
                                 'ProductionImpact':'NONE — RESEARCH ONLY'})
        summary=pd.DataFrame(summary_rows); stocks=pd.DataFrame(stock_rows); skipped_df=pd.DataFrame(skipped)
        sheets={'Cross-Stock Summary':summary,'Stock Evidence':stocks,'Setup Origin Session Pairs':pairs_all,'Continuation Events':cont_all,'Skipped':skipped_df}
        excel=workbook_bytes(sheets,{'Tab':'Cross-Stock Research Validator','Version':APP_VERSION,'Scope':cfg.get('scope'),'RequestedStocks':len(tickers),'SuccessfulStocks':len(stock_rows),'TargetPct':100*target,'StopPct':100*stop,'HorizonBars':horizon,'BootstrapRuns':int(cfg.get('bootstrap_runs',1200)),'ProductionImpact':'NONE'})
        _lab_publish_v603(runtime,jid,{'summary':summary,'stocks':stocks,'pairs':pairs_all,'continuation':cont_all,'skipped':skipped_df,'excel':excel})
    except _LabCancelled:_lab_publish_v603(runtime,jid,None,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)



def _pre_move_signal_families_v627(signal):
    """Map a discovered signal/pair into independent evidence families.

    The goal is candidate ranking, not feature deletion. Correlated variants such
    as MACD cross / MACD histogram turn-positive belong to one MOMENTUM family,
    so they cannot inflate the live Early Signal Score by being counted repeatedly.
    """
    parts=[x.strip() for x in str(signal).split(' + ') if x.strip()]
    fam=[]
    for part in parts:
        u=part.upper()
        if ('MACD' in u) or ('ROC ' in u) or u.startswith('RSI'):
            f='MOMENTUM'
        elif ('RVOL' in u) or ('VOLUME ACCELERATION' in u) or ('DIRECTIONAL BULLISH VOLUME' in u):
            f='VOLUME'
        elif ('OBV ' in u) or ('A/D ' in u) or ('CMF ' in u):
            f='FLOW'
        elif ('RELATIVE STRENGTH' in u):
            f='RELATIVE_STRENGTH'
        elif ('EMA' in u) or ('ADX' in u) or ('PRICE ABOVE EMA20' in u):
            f='TREND'
        elif ('VWAP' in u) or ('BREAKOUT' in u) or ('SQUEEZE' in u) or ('STRONG CLOSE' in u):
            f='STRUCTURE'
        elif ('FRESH TRANSITIONS' in u):
            f='TRANSITION_BREADTH'
        else:
            f='OTHER'
        if f not in fam:fam.append(f)
    return tuple(sorted(fam))


def _pre_move_evidence_signature_v627(a):
    """Compact signature used to collapse materially duplicated OOS evidence."""
    def q(k,nd=3):
        try:
            v=float(a.get(k,np.nan));return round(v,nd) if np.isfinite(v) else None
        except Exception:return None
    return (q('ValidationHitRatePct',2),q('ValidationMatchedBaselinePct',2),int(float(a.get('ValidationSignals',0) or 0)),q('ValidationLiftX',3),str(a.get('OOSState','')))


def _pre_move_freshness_v627(feat, target_pct):
    """How much of the requested future-move size has already occurred recently.

    This is intentionally transparent: the larger of the latest 1D and 2D close
    move is divided by the research target. It is a freshness/chase guard only;
    it does not alter historical OOS labels or Production Entry logic.
    """
    out={'CurrentDayMovePct':np.nan,'Recent2DMovePct':np.nan,'MoveAlreadyConsumedPct':np.nan,'FreshnessState':'NO DATA'}
    if feat is None or not isinstance(feat,pd.DataFrame) or len(feat)<3:return out
    c=pd.to_numeric(feat.get('Close'),errors='coerce').dropna()
    if len(c)<3:return out
    p=float(c.iloc[-1]);p1=float(c.iloc[-2]);p2=float(c.iloc[-3])
    r1=100*(p/p1-1.0) if p1>0 else np.nan
    r2=100*(p/p2-1.0) if p2>0 else np.nan
    target=100*float(target_pct)
    already=max(0.0,*[x for x in (r1,r2) if np.isfinite(x)]) if any(np.isfinite(x) for x in (r1,r2)) else np.nan
    consumed=100*already/target if np.isfinite(already) and target>0 else np.nan
    if not np.isfinite(consumed):state='NO DATA'
    elif consumed<35:state='FRESH'
    elif consumed<60:state='DEVELOPING'
    elif consumed<100:state='LATE'
    else:state='ALREADY MOVED'
    out.update({'CurrentDayMovePct':r1,'Recent2DMovePct':r2,'MoveAlreadyConsumedPct':consumed,'FreshnessState':state})
    return out


def _pre_move_representatives_v627(active, evidence_map):
    """Greedy de-duplication of active OOS signals for one live candidate.

    Only one representative can contribute from a family signature, and rows with
    the same rounded OOS evidence signature are counted once. This prevents dozens
    of correlated MACD/volume variants from behaving like independent votes.
    """
    rows=[]
    for _,rr in active.iterrows():
        sig=str(rr.get('Signal',''));a=dict(evidence_map.get(sig,{}) or {})
        try:vl=float(a.get('ValidationLiftX',np.nan));vh=float(a.get('ValidationHitRatePct',np.nan));vn=float(a.get('ValidationSignals',0) or 0)
        except Exception:continue
        if not (np.isfinite(vl) and np.isfinite(vh) and vn>0):continue
        fam=_pre_move_signal_families_v627(sig);fsig='+'.join(fam) if fam else 'OTHER'
        rows.append({'Signal':sig,'Families':fam,'FamilySignature':fsig,'ValidationLiftX':vl,'ValidationHitRatePct':vh,'ValidationSignals':vn,
                     'ValidationBaselinePct':a.get('ValidationMatchedBaselinePct',np.nan),'OOSState':str(a.get('OOSState','OOS MIXED')),
                     'EvidenceSignature':_pre_move_evidence_signature_v627(a)})
    rows.sort(key=lambda x:(1 if x['OOSState']=='OOS POSITIVE' else 0,x['ValidationLiftX'],x['ValidationSignals']),reverse=True)
    reps=[];seen_fsig=set();seen_evidence=set();covered_families=set()
    for r in rows:
        famset=set(r['Families'])
        if r['FamilySignature'] in seen_fsig:continue
        if r['EvidenceSignature'] in seen_evidence:continue
        # Once a stronger representative already covers all of this signal's
        # families, the weaker signal adds no independent vote. Multi-family
        # signals can still be kept when they introduce at least one new family.
        if famset and famset.issubset(covered_families):continue
        reps.append(r);seen_fsig.add(r['FamilySignature']);seen_evidence.add(r['EvidenceSignature']);covered_families.update(famset)
    return reps


def _pre_move_discovery_worker_v625(runtime,jid,cfg):
    """Cross-stock pre-move discovery with V6.2.7 independent-family ranking."""
    try:
        tickers=list(cfg.get('tickers') or []); target=float(cfg.get('target_pct',.05)); horizon=int(cfg.get('horizon_days',3)); history=str(cfg.get('history','3y'))
        stock_frames=[]; skipped=[]; latest_meta=[]; feature_map={}; total=max(1,len(tickers))
        for i,t in enumerate(tickers,1):
            _lab_check_v603(runtime,jid);_lab_update_v603(runtime,jid,i-1,total,t,f'Daily pre-move research • {history}')
            try:
                d=fetch_ohlcv(t,history,'1d')
                if d is None or len(d)<140: raise ValueError(f'Only {0 if d is None else len(d)} daily rows')
                f=compute_features(d).dropna(subset=['Close','High','Low']).copy();feature_map[str(t)]=f
                z=pre_move_stock_oos_v625(f,target_pct=target,horizon_days=horizon,discovery_fraction=.70)
                if z is None or z.empty: raise ValueError('Not enough chronological discovery/OOS sample')
                market=_market_for_ticker_v612(t); z=z.copy();z.insert(0,'Market',market);z.insert(0,'Ticker',t);stock_frames.append(z)
                lr=f.iloc[-1]; fresh=_pre_move_freshness_v627(f,target)
                latest_meta.append({'Ticker':t,'Market':market,'Price':float(lr.get('Close',np.nan)),
                                    'DailyChangePct':fresh.get('CurrentDayMovePct',np.nan),'Recent2DMovePct':fresh.get('Recent2DMovePct',np.nan),
                                    'MoveAlreadyConsumedPct':fresh.get('MoveAlreadyConsumedPct',np.nan),'FreshnessState':fresh.get('FreshnessState','NO DATA')})
            except Exception as e: skipped.append({'Ticker':t,'Reason':f'{type(e).__name__}: {e}'})
            _lab_update_v603(runtime,jid,i,total,t,'Pre-move discovery / OOS validation')
        raw=pd.concat(stock_frames,ignore_index=True) if stock_frames else pd.DataFrame()
        min_d=int(cfg.get('min_discovery_signals',25)); min_v=int(cfg.get('min_validation_signals',12)); min_l=float(cfg.get('min_discovery_lift',1.20))
        global_summary=aggregate_pre_move_oos_v625(raw,min_discovery_signals=min_d,min_validation_signals=min_v,min_discovery_lift=min_l)
        summaries=[]
        if not raw.empty:
            for scope,g in [('ALL',raw)]+[(m,raw[raw['Market'].astype(str)==m]) for m in sorted(raw['Market'].dropna().astype(str).unique())]:
                ssum=aggregate_pre_move_oos_v625(g,min_discovery_signals=max(10,min_d if scope=='ALL' else max(10,min_d//2)),min_validation_signals=max(6,min_v if scope=='ALL' else max(6,min_v//2)),min_discovery_lift=min_l)
                if not ssum.empty:ssum.insert(0,'Scope',scope);summaries.append(ssum)
        evidence=pd.concat(summaries,ignore_index=True) if summaries else global_summary.copy()
        if isinstance(evidence,pd.DataFrame) and not evidence.empty:
            evidence=evidence.copy();evidence['SignalFamilies']=evidence['Signal'].map(lambda x:' + '.join(_pre_move_signal_families_v627(x)))
            evidence['FamilySignature']=evidence['Signal'].map(lambda x:'+'.join(_pre_move_signal_families_v627(x)))
        # Current-candidate ranking uses only discovery-selected signals that did not fail OOS.
        accepted=global_summary[global_summary['OOSState'].isin(['OOS POSITIVE','OOS MIXED'])].copy() if isinstance(global_summary,pd.DataFrame) and not global_summary.empty else pd.DataFrame()
        candidates=[];candidate_audit=[];latest_df=pd.DataFrame(latest_meta)
        if not accepted.empty and not raw.empty:
            amap=accepted.set_index('Signal').to_dict('index')
            accepted_set=set(amap)
            for t,g in raw.groupby('Ticker'):
                active=g[(g['CurrentActive']==True)&g['Signal'].isin(accepted_set)].copy()
                if active.empty:continue
                reps=_pre_move_representatives_v627(active,amap)
                if not reps:continue
                fam_union=sorted(set(f for r in reps for f in r['Families']))
                positive_fam=sorted(set(f for r in reps if r['OOSState']=='OOS POSITIVE' for f in r['Families']))
                positive_reps=[r for r in reps if r['OOSState']=='OOS POSITIVE']
                vals=[]
                for r in reps:
                    factor=1.0 if r['OOSState']=='OOS POSITIVE' else .40
                    w=max(.03,r['ValidationLiftX']-1.0)*max(1.0,math.sqrt(max(1.0,r['ValidationSignals'])))*factor
                    vals.append((r,w))
                wsum=sum(w for _,w in vals);prob=sum(r['ValidationHitRatePct']*w for r,w in vals)/wsum if wsum>0 else np.nan
                best=max(r['ValidationLiftX'] for r in reps); sample=sum(r['ValidationSignals'] for r in reps[:5]); fam_n=len(fam_union);pos_fam_n=len(positive_fam)
                raw_active=int(len(active));rep_n=len(reps);dup_removed=max(0,raw_active-rep_n)
                lift_comp=min(1,max(0,(best-1)/.8));sample_comp=min(1,math.log1p(sample)/math.log1p(160));breadth_comp=min(1,fam_n/4);pos_comp=min(1,pos_fam_n/3)
                raw_score=100*(.35*lift_comp+.20*sample_comp+.30*breadth_comp+.15*pos_comp)
                meta=latest_df[latest_df['Ticker'].astype(str)==str(t)];m=meta.iloc[-1].to_dict() if not meta.empty else {}
                consumed=float(m.get('MoveAlreadyConsumedPct',np.nan)) if np.isfinite(float(m.get('MoveAlreadyConsumedPct',np.nan))) else np.nan
                freshness=str(m.get('FreshnessState','NO DATA'))
                freshness_mult=1.0 if freshness=='FRESH' else (.88 if freshness=='DEVELOPING' else (.55 if freshness=='LATE' else (.30 if freshness=='ALREADY MOVED' else .75)))
                score=float(raw_score*freshness_mult)
                core=bool('MOMENTUM' in fam_union and ('VOLUME' in fam_union or 'FLOW' in fam_union))
                strong_positive=bool(pos_fam_n>=2 and len(positive_reps)>=2)
                if freshness in ('LATE','ALREADY MOVED'):
                    stage='LATE / ALREADY MOVED'
                elif score>=72 and fam_n>=3 and pos_fam_n>=3 and core and best>=1.30:
                    stage='STRONG PRE-MOVE CANDIDATE'
                elif score>=58 and fam_n>=2 and strong_positive and (core or fam_n>=3) and best>=1.20:
                    stage='PRE-MOVE CANDIDATE'
                elif score>=35 and fam_n>=2:
                    stage='BUILDING'
                else:
                    stage='WATCH'
                strongest=' | '.join(r['Signal'] for r in reps[:4])
                candidates.append({'Ticker':t,'Market':m.get('Market',g.iloc[0].get('Market','')),'Price':m.get('Price',np.nan),
                                   'CurrentDayMovePct':m.get('DailyChangePct',np.nan),'Recent2DMovePct':m.get('Recent2DMovePct',np.nan),
                                   'MoveAlreadyConsumedPct':round(consumed,1) if np.isfinite(consumed) else np.nan,'FreshnessState':freshness,
                                   'RawPreMoveScore':round(float(raw_score),1),'PreMoveScore':round(float(score),1),'PreMoveStage':stage,
                                   'RawEarlySignalScore':round(float(raw_score),1),'EarlySignalScore':round(float(score),1),'EarlyStage':stage,
                                   'PreMoveProbabilityPct':round(float(prob),1) if np.isfinite(prob) else np.nan,
                                   'RawActiveValidatedSignals':raw_active,'RepresentativeSignals':rep_n,'DuplicateCorrelatedSignalsRemoved':dup_removed,
                                   'IndependentFamilyCount':fam_n,'PositiveOOSFamilyCount':pos_fam_n,'CoreMomentumVolumeConfirmed':core,
                                   'IndependentFamilies':' | '.join(fam_union),'BestOOSLiftX':round(float(best),2),'OOSValidationSignalNTop5':int(sample),
                                   'StrongestIndependentFeatures':strongest,'TargetHorizon':f'+{100*target:g}% within {horizon}D','ResearchOnly':True})
                for rank,r in enumerate(reps,1):
                    candidate_audit.append({'Ticker':t,'RepresentativeRank':rank,'Signal':r['Signal'],'FamilySignature':r['FamilySignature'],
                                            'Families':' | '.join(r['Families']),'OOSState':r['OOSState'],'ValidationLiftX':r['ValidationLiftX'],
                                            'ValidationHitRatePct':r['ValidationHitRatePct'],'ValidationBaselinePct':r.get('ValidationBaselinePct',np.nan),
                                            'ValidationSignals':r['ValidationSignals'],'UsedInLiveCandidateScore':True})
        cand=pd.DataFrame(candidates)
        if not cand.empty:
            stage_order={'STRONG PRE-MOVE CANDIDATE':0,'PRE-MOVE CANDIDATE':1,'BUILDING':2,'WATCH':3,'LATE / ALREADY MOVED':4}
            cand['_ord']=cand['EarlyStage'].map(stage_order).fillna(9)
            cand=cand.sort_values(['_ord','EarlySignalScore','BestOOSLiftX','IndependentFamilyCount'],ascending=[True,False,False,False]).drop(columns=['_ord']).reset_index(drop=True)
        audit_df=pd.DataFrame(candidate_audit);skipped_df=pd.DataFrame(skipped)
        sheets={'Pre-Move OOS Evidence':evidence,'Current Candidates':cand,'Candidate Family Audit':audit_df,'Per-Stock Signal Audit':raw,'Skipped':skipped_df}
        excel=workbook_bytes(sheets,{'Tab':'Pre-Move OOS Discovery','Version':APP_VERSION,'Scope':cfg.get('scope'),'History':history,'RequestedStocks':len(tickers),'SuccessfulStocks':len(stock_frames),'TargetPct':100*target,'HorizonDays':horizon,'DiscoverySplit':'70%','ValidationSplit':'30%','MinDiscoverySignals':min_d,'MinValidationSignals':min_v,'MinDiscoveryLiftX':min_l,'CandidateRanking':'Independent families + correlated-signal de-dup + recent-move freshness guard + research-stage naming','ProductionImpact':'NONE — RESEARCH ONLY; Scanner/Analyze live entry remains separate'})
        _persist_pre_move_overlay_v628(cand,cfg)
        _lab_publish_v603(runtime,jid,{'evidence':evidence,'global_summary':global_summary,'candidates':cand,'candidate_audit':audit_df,'raw':raw,'skipped':skipped_df,'excel':excel})
    except _LabCancelled:_lab_publish_v603(runtime,jid,None,'stopped')
    except Exception as e:_lab_fail_v603(runtime,jid,e)

# -----------------------------------------------------------------------------
# V6.2.8 Pre-Move -> Scanner two-layer overlay
# The Pre-Move lab is a research radar, never a trade trigger. The latest completed
# candidate table is merged into Scanner at render/export time so the user can see
# "research setup" and "live entry state" side by side without changing Production
# ranking, Entry Trigger, Chase Guard, or Live R:R.
# -----------------------------------------------------------------------------
_PREMOVE_CACHE_PATH_V628 = Path("pre_move_latest_v628.json")


def _persist_pre_move_overlay_v628(candidates, cfg, completed_label=None):
    try:
        c = candidates.copy() if isinstance(candidates, pd.DataFrame) else pd.DataFrame(candidates)
        c = c.replace({np.nan: None})
        payload = {
            'version': APP_VERSION,
            'completed_label': completed_label or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'saved_epoch': time_module.time(),
            'config': dict(cfg or {}),
            'candidates': c.to_dict('records'),
        }
        _PREMOVE_CACHE_PATH_V628.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding='utf-8')
    except Exception:
        pass


def _latest_pre_move_snapshot_v628():
    # Prefer the in-memory completed job because it is guaranteed to match this build.
    try:
        active, last = _lab_snapshot_v603('pre_move')
        snap = last if last and last.get('payload') else (active if active and active.get('payload') and active.get('status') == 'completed' else None)
        if snap and snap.get('payload'):
            cand = snap['payload'].get('candidates')
            cand = cand.copy() if isinstance(cand, pd.DataFrame) else pd.DataFrame(cand)
            cfg = dict(snap.get('config') or {})
            finished = snap.get('finished_at')
            age_h = max(0.0, (time_module.time()-float(finished))/3600.0) if finished else np.nan
            return cand, {
                'source':'LAST COMPLETED PRE-MOVE RUN',
                'completed_label':snap.get('completed_label','—'),
                'age_hours':age_h,
                'scope':cfg.get('scope','—'),
                'target_pct':100*float(cfg.get('target_pct',np.nan)) if cfg.get('target_pct') is not None else np.nan,
                'horizon_days':cfg.get('horizon_days',np.nan),
                'history':cfg.get('history','—'),
            }
    except Exception:
        pass
    # Small best-effort local cache survives normal Streamlit reruns/process refreshes.
    try:
        if _PREMOVE_CACHE_PATH_V628.exists():
            p=json.loads(_PREMOVE_CACHE_PATH_V628.read_text(encoding='utf-8'))
            cand=pd.DataFrame(p.get('candidates') or [])
            cfg=dict(p.get('config') or {})
            saved=float(p.get('saved_epoch',np.nan))
            age_h=max(0.0,(time_module.time()-saved)/3600.0) if np.isfinite(saved) else np.nan
            return cand, {
                'source':'LOCAL PRE-MOVE CACHE',
                'completed_label':p.get('completed_label','—'),
                'age_hours':age_h,
                'scope':cfg.get('scope','—'),
                'target_pct':100*float(cfg.get('target_pct',np.nan)) if cfg.get('target_pct') is not None else np.nan,
                'horizon_days':cfg.get('horizon_days',np.nan),
                'history':cfg.get('history','—'),
            }
    except Exception:
        pass
    return pd.DataFrame(), {}


def _attach_pre_move_overlay_v628(df):
    if df is None or not isinstance(df,pd.DataFrame) or df.empty:
        return df
    z=df.copy()
    # Remove any older overlay columns before attaching the newest research snapshot.
    old=[c for c in z.columns if str(c).startswith('PreMove')]
    if old:z=z.drop(columns=old,errors='ignore')
    cand,meta=_latest_pre_move_snapshot_v628()
    if cand is None or not isinstance(cand,pd.DataFrame) or cand.empty or 'Ticker' not in cand.columns:
        z.attrs['pre_move_meta']=meta
        return z
    rename={
        'PreMoveStage':'PreMoveStage','EarlyStage':'PreMoveStage',
        'PreMoveScore':'PreMoveScore','EarlySignalScore':'PreMoveScore',
        'PreMoveProbabilityPct':'PreMoveProbabilityPct','FreshnessState':'PreMoveFreshness',
        'MoveAlreadyConsumedPct':'PreMoveMoveConsumedPct','IndependentFamilyCount':'PreMoveIndependentFamilyCount',
        'PositiveOOSFamilyCount':'PreMovePositiveOOSFamilyCount','CoreMomentumVolumeConfirmed':'PreMoveCoreConfirmed',
        'IndependentFamilies':'PreMoveIndependentFamilies','BestOOSLiftX':'PreMoveBestOOSLiftX',
        'OOSValidationSignalNTop5':'PreMoveOOSSignalNTop5','StrongestIndependentFeatures':'PreMoveStrongestFeatures',
        'TargetHorizon':'PreMoveTargetHorizon','ResearchOnly':'PreMoveResearchOnly'
    }
    # Prefer the new V6.2.8 names when both legacy and new aliases exist.
    keep=['Ticker']
    for src,dst in rename.items():
        if src in cand.columns and dst not in [rename.get(k) for k in keep]:
            keep.append(src)
    pm=cand[keep].copy()
    # Resolve duplicate source columns that rename to the same destination.
    ordered=['Ticker','PreMoveStage','PreMoveScore','PreMoveProbabilityPct','PreMoveFreshness','PreMoveMoveConsumedPct',
             'PreMoveIndependentFamilyCount','PreMovePositiveOOSFamilyCount','PreMoveCoreConfirmed','PreMoveIndependentFamilies',
             'PreMoveBestOOSLiftX','PreMoveOOSSignalNTop5','PreMoveStrongestFeatures','PreMoveTargetHorizon','PreMoveResearchOnly']
    out=pd.DataFrame({'Ticker':pm['Ticker'].astype(str).str.upper()})
    for dst in ordered[1:]:
        sources=[src for src,d in rename.items() if d==dst and src in pm.columns]
        if sources:
            series=pm[sources[0]]
            for src in sources[1:]:series=series.where(series.notna(),pm[src])
            out[dst]=series.values
    out=out.drop_duplicates('Ticker',keep='first')
    out['PreMoveRunCompleted']=meta.get('completed_label','—')
    out['PreMoveRunAgeHours']=meta.get('age_hours',np.nan)
    out['PreMoveModelScope']=meta.get('scope','—')
    out['PreMoveModelTargetPct']=meta.get('target_pct',np.nan)
    out['PreMoveModelHorizonDays']=meta.get('horizon_days',np.nan)
    out['PreMoveModelHistory']=meta.get('history','—')
    z['Ticker']=z['Ticker'].astype(str).str.upper()
    z=z.merge(out,on='Ticker',how='left')
    if 'PreMoveStage' in z:
        z['PreMoveStage']=z['PreMoveStage'].fillna('NO CURRENT PRE-MOVE CANDIDATE')
    z.attrs['pre_move_meta']=meta
    return z


def _render_pre_move_overlay_status_v628():
    cand,meta=_latest_pre_move_snapshot_v628()
    if cand is None or not isinstance(cand,pd.DataFrame) or cand.empty:
        st.caption('🔭 Pre-Move research radar: no completed candidate run is loaded. Run Optimizer → Pre-Move OOS Discovery to add the research layer to Scanner.')
        return
    tgt=meta.get('target_pct',np.nan); hor=meta.get('horizon_days',np.nan); age=meta.get('age_hours',np.nan)
    tgt_txt=f'+{float(tgt):g}%' if pd.notna(tgt) else '—'; hor_txt=f'{int(hor)}D' if pd.notna(hor) else '—'; age_txt=f'{float(age):.1f}h old' if pd.notna(age) else 'age unknown'
    st.caption(f"🔭 Pre-Move research radar loaded • {meta.get('scope','—')} • {tgt_txt} within {hor_txt} • run {meta.get('completed_label','—')} ({age_txt}). Research radar ≠ live trade trigger.")

def _coerce_dataframe_v608(obj):
    """Normalize cached/legacy payload objects before UI rendering."""
    if isinstance(obj, pd.DataFrame):
        return obj
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.Series):
        return obj.to_frame()
    if isinstance(obj, dict):
        try:
            return pd.DataFrame(obj)
        except ValueError:
            return pd.DataFrame([obj])
    try:
        return pd.DataFrame(obj)
    except Exception:
        return pd.DataFrame()


def _render_dataframe_safe_v608(obj, empty_message):
    """Render a DataFrame without allowing a legacy/cached object to crash Analyze."""
    df = _coerce_dataframe_v608(obj)
    if df.empty:
        st.info(empty_message)
        return
    try:
        st.dataframe(df, use_container_width=True, hide_index=True)
    except AttributeError:
        # Last-resort rendering path for Streamlit/Pandas compatibility edge cases.
        st.markdown(df.to_html(index=False, escape=True), unsafe_allow_html=True)


def _render_scanner_top_excel_v624(slot, show_mode, market_filter):
    runtime=_scanner_runtime_v599()
    with runtime['lock']:
        last=runtime.get('last_completed')
    with slot.container():
        if not last or not isinstance(last.get('result'),pd.DataFrame):
            st.caption('⬇️ Excel download will appear here after the first completed scan.')
            return
        full=_attach_pre_move_overlay_v628(last.get('result'));res=_filter_scanner_results_v599(full,show_mode,market_filter);meta=last.get('meta') or {}
        if res is None or res.empty:
            st.caption('⬇️ Excel: current Scanner filter has no rows to export.')
            return
        st.download_button('⬇️ Download Scanner Excel',data=scanner_excel_bytes(res,meta),file_name=f"AI_Stock_Hunter_V{APP_VERSION}_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True,key='scanner_excel_top_v624')


def _render_optimizer_top_excel_v625(slot):
    _,entry_last=_lab_snapshot_v603('entry');entry_active,_=_lab_snapshot_v603('entry')
    _,rv_last=_lab_snapshot_v603('research_validator');rv_active,_=_lab_snapshot_v603('research_validator')
    _,pm_last=_lab_snapshot_v603('pre_move');pm_active,_=_lab_snapshot_v603('pre_move')
    ep=(entry_active.get('payload') if entry_active and entry_active.get('payload') else (entry_last.get('payload') if entry_last else None))
    rp=(rv_active.get('payload') if rv_active and rv_active.get('payload') else (rv_last.get('payload') if rv_last else None))
    pp=(pm_active.get('payload') if pm_active and pm_active.get('payload') else (pm_last.get('payload') if pm_last else None))
    with slot.container():
        available=[]
        if ep and ep.get('excel'):available.append(('Optimizer',ep.get('excel')))
        if rp and rp.get('excel'):available.append(('Cross-Stock Research',rp.get('excel')))
        if pp and pp.get('excel'):available.append(('Pre-Move Discovery',pp.get('excel')))
        if not available:
            st.caption('⬇️ Excel downloads will appear here after a completed Optimizer, Cross-Stock Research or Pre-Move run.')
            return
        cols=st.columns(len(available))
        for c,(label,data) in zip(cols,available):
            with c:st.download_button(f'⬇️ {label} Excel',data=data,file_name=f"AI_Stock_Hunter_V{APP_VERSION}_{label.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True,key=f"top_opt_{label}_v625")


tab_scan,tab_analyze,tab_optimizer,tab_feedback=st.tabs(['🔎 Scanner','📈 Analyze','🧠 Optimizer','🔄 Feedback'])
with tab_scan:
    st.markdown("<div class='section'>🔎 Scanner — live opportunity discovery</div>",unsafe_allow_html=True)
    scanner_excel_top=st.empty()
    _render_market_status_badges_v612()
    st.caption("Session badges use each exchange's local clock. OPEN/PRE/AFTER status is shown separately from the model's entry signal.")
    _render_pre_move_overlay_status_v628()
    scan_mode=st.radio("Scan mode",["Production 151","Optimized 151","Discovery"],horizontal=True,key="scan_mode_v613",format_func=lambda x:x.replace(" 151",""))
    universe_preset=st.selectbox("Scan universe",["CORE 151","NASDAQ 50","NASDAQ 100","NASDAQ 200","US 201 (NASDAQ 200 + ITT)","HONG KONG 50","HONG KONG 100","TEL AVIV 50","ALL 350","ALL 351 + ITT","Custom"],3,key="scanner_universe_v629")
    universe_mode=st.radio("Display market",["ALL","US","HONG KONG","TEL AVIV"],horizontal=True,key="scanner_market_v613")
    preset_map={"CORE 151":VALIDATION_151,"NASDAQ 50":NASDAQ_50,"NASDAQ 100":NASDAQ_100,"NASDAQ 200":NASDAQ_200,"US 201 (NASDAQ 200 + ITT)":US_201,"HONG KONG 50":HK_50,"HONG KONG 100":HK_100,"TEL AVIV 50":TASE_50,"ALL 350":VALIDATION_350,"ALL 351 + ITT":VALIDATION_351}
    scan_universe=preset_map.get(universe_preset,VALIDATION_151)
    if universe_preset=="Custom":
        custom=st.text_area("Custom tickers",DEFAULT_TICKERS,height=100,key="custom_scanner_v613");scan_universe=custom
    universe_n=len([x for x in scan_universe.split(',') if x.strip()])
    if scan_mode=="Production 151":prefilter_top=universe_n  # full deep scan = maximum Feedback coverage
    elif scan_mode=="Optimized 151":prefilter_top=min(universe_n,max(60,min(140,int(math.ceil(universe_n*.60)))))
    else:prefilter_top=min(universe_n,max(80,min(160,int(math.ceil(universe_n*.55)))))
    st.caption(f"Universe requested: {universe_n} stocks • Production performs full deep analysis for maximum Feedback learning; Optimized/Discovery use a larger two-stage prefilter for speed.")
    c1,c2,c3=st.columns(3);sh=c1.selectbox("History",["3mo","6mo","1y"],1,key="sh_v613");ho=c2.selectbox("Forecast horizon",[1,2,3,5,7,10],2,key="ho_v613");ta=c3.selectbox("Target %",[1,2,3,4,5,6,8,10],2,key="ta_v613")
    model_horizon_choice=st.selectbox("Optimized model horizon",["AUTO BEST OOS BY MARKET","MATCH FORECAST HORIZON"],0,key="optimized_horizon_v613",disabled=scan_mode=="Production 151",help="AUTO can use (for example) a 2D US model and a 3D Hong Kong model in the same scan if those are the strongest eligible OOS models.")
    registry=_load_model_registry_v613();model_horizon=None if model_horizon_choice.startswith('AUTO') else int(ho);model=_select_active_model_v613(registry,model_horizon,float(ta))
    if scan_mode!="Production 151":
        sel=_registry_selection_frame_v613(model);hlabel='AUTO BEST OOS BY MARKET' if model_horizon is None else f'{int(ho)}D'
        if model.get('scopes'):
            st.caption(f"Model Registry: {len(registry.get('models',[]))} saved optimization run(s). Scanner uses only SHADOW ELIGIBLE OOS models for +{float(ta):g}% with horizon {hlabel} — never simply the latest run.")
            if not sel.empty:st.dataframe(sel,use_container_width=True,hide_index=True)
            missing=[m for m in ('NASDAQ','HONG KONG','TEL AVIV') if m not in model.get('scopes',{})]
            if missing:st.warning("No eligible optimized model for: "+", ".join(missing)+". Those markets can still appear for comparison, but receive NO ELIGIBLE MODEL rather than unvalidated weights.")
        else:
            st.error(f"No SHADOW ELIGIBLE OOS model exists in the registry for +{float(ta):g}% with the selected model-horizon rule. Run/import Optimizer evidence; Production 151 remains available.")
    show_mode=st.selectbox("Show",["ALL","STRONG PRE-MOVE CANDIDATE","PRE-MOVE CANDIDATE","CONFIRMED ENTRY","OPTIMIZED CONFIRMED","OPTIMIZED ARMED","ARMED","EXTENDED / RETEST","TOP OPPORTUNITIES","ACTIONABLE NOW","WATCHLIST"],key="show_v613")
    st.caption("Two layers: Pre-Move = research radar from the latest OOS discovery run; Live Entry = current Scanner trade timing. A strong research candidate can still be WAIT/INVALIDATED live.")
    scanner_status=_scanner_status_v601();scanner_busy=scanner_status in ('running','stopping');b1,b2=st.columns([2,1])
    with b1:
        disabled=scanner_busy or (scan_mode!="Production 151" and not model.get('scopes'))
        if st.button("▶ Start Scan",key="scanner_start_v612",use_container_width=True,disabled=disabled):
            ts=[x.strip().upper() for x in scan_universe.split(',') if x.strip()]
            config={'tickers':ts,'history':sh,'horizon':int(ho),'target':float(ta)/100,'threshold':66,'prefilter_top':int(prefilter_top),'universe_mode':universe_mode,'scan_mode':scan_mode,'optimizer_model':model if scan_mode!="Production 151" else None}
            ok,msg=_start_scanner_job_v599(config)
            if ok:st.success(f"{scan_mode} started server-side • universe {len(ts)} • deep-analysis cap {prefilter_top}.");st.rerun()
            else:st.warning(msg)
    with b2:
        if st.button("■ Stop Scan",key="scanner_stop_v612",use_container_width=True,disabled=not scanner_busy or scanner_status=='stopping'):
            ok,msg=_request_scanner_stop_v601();st.warning(msg) if ok else st.info(msg);st.rerun()
    if scan_mode=="Discovery":st.caption(f"Discovery/two-stage universe: {universe_n} symbols selected; the best {prefilter_top} receive hourly/15m deep analysis.")
    market_filter={'ALL':'ALL 151','US':'US ALL','HONG KONG':'HONG KONG 50','TEL AVIV':'TEL AVIV 50'}[universe_mode]
    _render_scanner_top_excel_v624(scanner_excel_top,show_mode,market_filter)
    if _scanner_status_v601() in ('running','stopping'):_scanner_live_fragment_v599(show_mode,market_filter)
    else:_render_scanner_results_v599(show_mode,market_filter)

with tab_analyze:
    st.markdown("<div class='section'>📈 Analyze — single-stock decision cockpit</div>",unsafe_allow_html=True)
    analyze_excel_top=st.empty()
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
    if not (snap and snap.get('payload')):
        with analyze_excel_top.container():st.caption('⬇️ Excel download will appear here after a completed Analyze run.')
    if snap and snap.get('payload'):
        pay=snap['payload'];t=pay['ticker'];f=pay['f'];dyn=pay['dyn'];ent=pay['ent'];latest_live=pay['latest_live'];live_snapshot=pay.get('live_snapshot',{});ah_snapshot=pay.get('ah_snapshot',{});ex=pay['ex'];timing=pay['timing'];decision=pay['decision'];ca_report=pay['ca_report'];bt=pay['bt'];buy_threshold=pay['buy_threshold'];comp=pay['comp'];ec=pay['ec'];cmp=pay['cmp'];compare_df=pay['compare_df'];ev=pay['ev'];early_cal=pay['early_cal'];quant_cal=pay['quant_cal'];target_run=pay['target'];horizon_run=pay['horizon']
        phase=str(decision.get('MarketPhase','UNKNOWN'));ch=latest_live.get('daily_change_pct',np.nan);currency='HKD' if t.endswith('.HK') else ('ILA' if t.endswith('.TA') else 'USD')
        market_name=str(decision.get('Market',_market_for_ticker_v612(t)))
        mdet=_market_status_detail_v612(market_name); mphase=mdet.get('phase',phase); micon=_market_phase_icon_v612(mphase)
        mreason=f" • {mdet.get('reason')}" if mdet.get('reason') else ''
        st.markdown(f"### {t} · {market_name} · {micon} {mphase}")
        st.caption(f"Exchange local time {mdet.get('local_time','—')}{mreason}")
        price_fresh=bool(live_snapshot.get('fresh'));display_current=bool(live_snapshot.get('display_current'));trade_fresh=bool(live_snapshot.get('trade_fresh'));live_px=float(live_snapshot.get('price',np.nan)) if np.isfinite(float(live_snapshot.get('price',np.nan))) else np.nan;fallback_px=float(live_snapshot.get('fallback_price',np.nan)) if np.isfinite(float(live_snapshot.get('fallback_price',np.nan))) else np.nan
        quote_status=str(live_snapshot.get('quote_status','UNAVAILABLE'))
        if phase=='AFTER-MARKET' and np.isfinite(float(ah_snapshot.get('AHPrice',np.nan))):
            cur=float(ah_snapshot.get('AHPrice')); price_label='After-hours price'
        elif display_current and np.isfinite(live_px):cur=live_px;price_label='Current price' if trade_fresh else 'Current / delayed price'
        else:cur=fallback_px if np.isfinite(fallback_px) else latest_live.get('price',np.nan);price_label='Last official close' if np.isfinite(cur) else 'Live price unavailable'
        _metric_delta=float(ah_snapshot.get('AHChangePct',np.nan)) if phase=='AFTER-MARKET' and np.isfinite(float(ah_snapshot.get('AHChangePct',np.nan))) else ch
        st.markdown("<div class='section'>Decision cockpit</div>",unsafe_allow_html=True);p1,p2,p3,p4=st.columns([1.35,1,1,1]);p1.metric(price_label,f"{cur:,.3f} {currency}" if np.isfinite(cur) else 'UNAVAILABLE',delta=f"{_metric_delta:+.2f}%" if np.isfinite(_metric_delta) else None);p2.metric("TOP SCORE",f"{decision.get('TopScore',0):.1f}");p3.metric("Opportunity",f"{decision.get('OpportunityScore',0):.1f}");p4.metric("Exit Pressure",f"{decision.get('ExitPressure',0):.0f}",delta=decision.get('ExitStage','CLEAR'))
        quote_stamp=live_snapshot.get('timestamp_label','—');quote_age=live_snapshot.get('age_minutes',np.nan);age_txt=f" • age {float(quote_age):.0f}m" if np.isfinite(float(quote_age)) else '';quote_source=live_snapshot.get('source','unavailable')
        st.caption(f"{phase} • {decision.get('Market','—')} • {quote_status} • {quote_source} @ {quote_stamp}{age_txt}")
        if phase=='AFTER-MARKET':
            _ahc=float(ah_snapshot.get('AHChangePct',np.nan)); _ahr=float(ent.get('regular_session_move_pct',np.nan)); _aht=float(ent.get('total_move_including_ah_pct',np.nan)); _ahv=float(ah_snapshot.get('AHVolumeStrength',np.nan)); _ahts=ah_snapshot.get('AHLastTime','—'); _ahage=float(ah_snapshot.get('AHAgeMinutes',np.nan));
            st.warning("AFTER-MARKET MODE — regular-session 15m/1H indicators are frozen. After-hours price/volume are used as confirmation and chase-risk context only; Actionable Now is blocked until the next regular session reconfirms the setup.")
            st.caption(f"Regular session move {f'{_ahr:+.2f}%' if np.isfinite(_ahr) else '—'} • After-hours move {f'{_ahc:+.2f}%' if np.isfinite(_ahc) else '—'} • Total vs prior close {f'{_aht:+.2f}%' if np.isfinite(_aht) else '—'} • AH volume strength {f'{_ahv:.2f}x' if np.isfinite(_ahv) else '—'} • AH quote {_ahts} • source {ent.get('after_hours_price_source','N/A')}{f' • age {_ahage:.0f}m' if np.isfinite(_ahage) else ''}")
        if live_snapshot.get('temporary_counter_active'):
            temp=str(live_snapshot.get('temporary_counter','')).replace('.HK','');under=str(live_snapshot.get('underlying_symbol',t)).replace('.HK','')
            st.info(f"HKEX CORPORATE-ACTION COUNTER: current quote is read from temporary counter {temp} for permanent ticker {under}. Historical research remains on {under}.")
        if phase=='OPEN' and not display_current:
            stale_ts=live_snapshot.get('stale_timestamp_label','—');stale_px=live_snapshot.get('stale_price',np.nan);stale_note=f" Last rejected provider bar: {float(stale_px):.3f} @ {stale_ts}." if np.isfinite(float(stale_px)) else ''
            st.error("CURRENT PRICE UNAVAILABLE — no trustworthy current-session quote from the fallback chain. The number above is the last official close only. CONFIRMED ENTRY — LIVE and Actionable Now are blocked."+stale_note)
        elif phase=='OPEN' and display_current and not trade_fresh:
            st.warning("CURRENT/DELAYED PRICE FOUND — shown for price reference, but the feed is not timestamp-fresh enough for CONFIRMED ENTRY — LIVE or Actionable Now.")
        if ca_report.get('split_detected'):
            sr=ca_report.get('split_ratio',np.nan);sd=ca_report.get('split_date') or live_snapshot.get('split_date') or 'recent';ratio_txt=f"1→{float(sr):g} subdivision" if np.isfinite(float(sr)) and float(sr)>=1 else (f"split ratio {float(sr):g}" if np.isfinite(float(sr)) else 'split')
            adj=' • price scales normalized' if ca_report.get('split_adjusted') else ' • provider frames already on a consistent scale'
            st.info(f"Corporate Action detected: {ratio_txt} split/subdivision ({sd}){adj}.")
        elif ca_report.get('split_adjusted'):st.info("Corporate Action / split-like scale difference detected — Daily / 1H / 15m were normalized to the current intraday scale.")
        if ca_report.get('data_quality')!='OK':st.error("DATA QUALITY CHECK: unexplained cross-timeframe price mismatch remains after split normalization. PlanValid is forced FALSE and all Trade Plan levels are suppressed.")
        _display_entry_state=ent.get('session_entry_state',ent.get('trigger_state',ent.get('status','WAIT')))
        st.markdown(f"### Entry: :{'green' if _display_entry_state=='CONFIRMED ENTRY' else 'orange'}[{_display_entry_state}] · Movement: {decision.get('MovementStage','—')}")
        if phase=='AFTER-MARKET': st.caption(f"Regular-session close state: {ent.get('regular_session_entry_state','—')} • regular entry score {float(ent.get('regular_session_entry_score',np.nan)):.1f}" if np.isfinite(float(ent.get('regular_session_entry_score',np.nan))) else f"Regular-session close state: {ent.get('regular_session_entry_state','—')}")
        st.caption(f"Confirmed conditions: {ent.get('confirmed_conditions',0)}/{ent.get('total_conditions',6)} ({ent.get('confirmation_pct',0):.0f}%) • Why now: {ent.get('why_now','—')}")
        _cr=float(ent.get('chase_risk_score',0) or 0);_sm=float(ent.get('session_move_pct',np.nan));_sa=float(ent.get('session_move_atr',np.nan));_sp=float(ent.get('session_move_percentile',np.nan));_pre=float(ent.get('move_before_trigger_pct',np.nan));_st=float(ent.get('since_trigger_pct',np.nan));_va=float(ent.get('vwap_distance_atr',np.nan));_tp=float(ent.get('target1_progress_pct',np.nan))
        _risk_line=f"Chase Risk {ent.get('chase_risk_label','LOW')} ({_cr:.0f}/100) • Session {f'{_sm:+.1f}%' if np.isfinite(_sm) else '—'} / {f'{_sa:.2f} ATR' if np.isfinite(_sa) else '—'} • Session pctile {f'{_sp:.0f}' if np.isfinite(_sp) else '—'} • Before trigger {f'{_pre:+.1f}%' if np.isfinite(_pre) else '—'} • Since trigger {f'{_st:+.1f}%' if np.isfinite(_st) else '—'} • VWAP distance {f'{_va:.2f} ATR' if np.isfinite(_va) else '—'} • Volume {ent.get('volume_trend','NO DATA')}"
        if not bool(ent.get('extension_guard_ok',True)):st.warning(_risk_line+" • WAIT FOR RETEST")
        _rr1=ent.get('live_rr_t1',np.nan);_rr2=ent.get('live_rr_t2',np.nan);_act=ent.get('live_actionability_score',np.nan)
        if np.isfinite(float(_act)) if _act is not None else False:st.caption(f"Live actionability {float(_act):.1f}/100 • R:R T1 {float(_rr1):.2f}x • R:R T2 {float(_rr2):.2f}x" if np.isfinite(float(_rr1)) and np.isfinite(float(_rr2)) else f"Live actionability {float(_act):.1f}/100")
        else:st.caption(_risk_line)
        _ta=ent.get('trigger_anchor_time','—'); _tb=ent.get('trigger_anchor_bar_start_time','—'); _tf=ent.get('trigger_anchor_timeframe','—')
        _so=ent.get('setup_origin_time','—'); _sop=float(ent.get('setup_origin_price',np.nan)); _mbs=float(ent.get('move_before_setup_origin_pct',np.nan)); _sss=float(ent.get('since_setup_origin_pct',np.nan))
        st.caption(f"Causal trigger audit: {_tf} signal confirmed {_ta} (bar start {_tb}) • Momentum {ent.get('momentum_state','NO DATA')} [15m {ent.get('momentum_state_15m','NO DATA')} / 1H {ent.get('momentum_state_1h','NO DATA')}]")
        if np.isfinite(_sop):st.caption(f"Research-only setup origin: {_sop:.3f} confirmed {_so} • move before origin {f'{_mbs:+.1f}%' if np.isfinite(_mbs) else '—'} • since origin {f'{_sss:+.1f}%' if np.isfinite(_sss) else '—'} • not an actionable trigger until OOS validated")
        _otl=float(ent.get('origin_to_trigger_pct',np.nan)); _tlm=float(ent.get('trigger_lag_minutes',np.nan)); _mct=float(ent.get('move_consumed_before_trigger_pct',np.nan))
        if np.isfinite(_otl) or np.isfinite(_tlm) or np.isfinite(_mct):st.caption(f"Trigger efficiency audit: {ent.get('trigger_efficiency_label','RESEARCH • NO DATA')} • origin→trigger {f'{_otl:+.2f}%' if np.isfinite(_otl) else '—'} • lag {f'{_tlm:.0f} min' if np.isfinite(_tlm) else '—'} • {f'{_mct:.0f}% of observed session move occurred before causal trigger' if np.isfinite(_mct) else 'move-consumption —'} • research only")
        if bool(ent.get('next_session_carryover_candidate',False)):st.info('Next-session extension memory candidate: '+str(ent.get('next_session_carryover_reason','today’s move should carry forward'))+'. The next regular session must not reset this setup to fresh just because its day change starts near 0%.')
        if ent.get('missing_checks') and ent.get('missing_checks')!='None':st.caption("Still missing: "+str(ent.get('missing_checks')))
        q1,q2,q3,q4=st.columns(4);q1.metric("Prediction Score",f"{dyn.get('final_prediction',np.nan):.1f}");q2.metric("Evidence",str(decision.get('EvidenceQuality','LOW')));q3.metric("Live Entry",f"{ent.get('live_actionability_score',ent.get('entry_score',0)):.1f}",delta=f"Timing {ent.get('entry_score',0):.1f} • Setup {ent.get('setup_entry_score_pre_chase',ent.get('entry_score',0)):.1f}");q4.metric("Hourly",f"{timing.get('hourly_confirmation',np.nan):.1f}" if np.isfinite(timing.get('hourly_confirmation',np.nan)) else '—')
        r1,r2,r3,r4=st.columns(4);r1.metric("Move",f"{timing.get('move_score',np.nan):.1f}");r2.metric("Explosive",f"{ex.get('score',np.nan):.1f}");r3.metric("Volume context",latest_live.get('volume_context','N/A'));r4.metric("Regular-session RVOL" if phase=='AFTER-MARKET' else "Live Intraday RVOL",f"{decision.get('LiveIntradayRVOL',np.nan):.2f}x" if np.isfinite(decision.get('LiveIntradayRVOL',np.nan)) else '—')
        st.caption(f"Daily Robust RVOL {decision.get('DailyRobustRVOL',np.nan):.2f}x • Reliability {decision.get('Reliability',0):.1f} • Evidence {decision.get('EvidenceState','UNPROVEN')} • Prediction is a 0–100 setup score, not a probability.")
        st.caption((f"Institutional Flow {float(decision.get('InstitutionalFlowScore',np.nan)):.0f} ({decision.get('InstitutionalFlowLabel','—')}) • Daily optimized {float(decision.get('OptimizedScore',np.nan)):.1f} / Match {float(decision.get('OptimizedMatchPct',np.nan)):.0f}% • OOS {float(decision.get('OptimizedModelOOSLift',np.nan)):.3f}x • Hourly optimized {float(decision.get('HourlyOptimizedMatchPct',np.nan)):.0f}% ({decision.get('HourlyOptimizedHorizon','—')}) • {decision.get('OptimizedStage','NO OPTIMIZER')}") if np.isfinite(float(decision.get('InstitutionalFlowScore',np.nan))) else 'Institutional Flow unavailable')
        st.caption(f"Exit engine: {decision.get('ExitStage','CLEAR')} • EXIT WATCH is an early warning, not a sell signal. EXIT ARMED / TRIGGER require persistent distribution / breakdown confirmation.")
        bt_value,bt_sample=backtest_display(bt);b1,b2,b3,b4=st.columns(4);b1.metric("Backtest evidence",bt_value);b2.metric("Sample",f"{int(bt.get('n',0))} signals");b3.metric("Historical Quant threshold",f"{buy_threshold} • research only");b4.metric("Worst historical drawdown",f"{bt.get('max_drawdown',np.nan)*100:.2f}%" if int(bt.get('n',0) or 0) else '—')
        if int(bt.get('n',0) or 0)<12:st.caption("LOW SAMPLE: hit-rate is de-emphasized and its influence on Reliability is capped.")
        st.markdown("<div class='section'>Precision entry / risk plan</div>",unsafe_allow_html=True)
        if bool(ent.get('plan_valid',False)) and ca_report.get('data_quality')=='OK':
            z1,z2,z3,z4=st.columns(4);z1.metric("Entry zone",f"{ent['zone_low']:.3f} – {ent['zone_high']:.3f}");z2.metric("Trade trigger",f"> {ent['trigger']:.3f}");z3.metric("Invalidation",f"< {ent['invalidation']:.3f}");z4.metric("Targets",f"{ent['target1']:.3f} / {ent['target2']:.3f}");st.caption(f"Entry Trigger V4: {ent.get('status','—')} • Anchor {ent.get('trigger_anchor_quality','NONE')} / {ent.get('trigger_anchor_timeframe','—')} @ {ent.get('trigger_anchor_price',np.nan):.3f} • age {ent.get('trigger_anchor_age_bars','—')} bars • Chase/Extension Guard can hard-block a late entry even at 6/6 gates.");
            if not bool(ent.get('extension_guard_ok',True)) and np.isfinite(float(ent.get('retest_zone_low',np.nan))) and np.isfinite(float(ent.get('retest_zone_high',np.nan))):st.info(f"Retest plan: {ent.get('retest_zone_low'):.3f} – {ent.get('retest_zone_high'):.3f} • pullback needed {float(ent.get('pullback_needed_pct',0)):.1f}% • {ent.get('retest_status','WAIT FOR RETEST')} • reference {ent.get('retest_reference_label','—')}")
            st.caption(f"Post-spike: {ent.get('post_spike_state','NO DATA')} • peak {safe(ent.get('session_peak_move_pct'),1)}% • giveback {safe(ent.get('high_giveback_pct'),1)}% • retained {safe(ent.get('move_retention_from_high_pct'),1)}% • distribution risk {ent.get('post_spike_distribution_risk','NO DATA')}")
            if ent.get('continuation_base_candidate',False):st.info(f"Continuation Lab (research only): base {safe(ent.get('continuation_base_low'),2)}–{safe(ent.get('continuation_base_high'),2)} • {int(ent.get('continuation_base_bars',0) or 0)} bars • {ent.get('continuation_base_quality','NO DATA')} compression • range {safe(ent.get('continuation_base_range_pct'),2)}% / {safe(ent.get('continuation_base_range_atr'),2)} ATR • volume dry-up {safe(ent.get('continuation_volume_dryup_ratio'),2)}x • session peak {safe(ent.get('continuation_session_peak'),2)} • peak-safe breakout audit {safe(ent.get('continuation_breakout_trigger'),2)}")
            _ovs=pay.get('origin_validation_summary')
            if isinstance(_ovs,pd.DataFrame) and not _ovs.empty:
                try:
                    _om=dict(zip(_ovs['Metric'].astype(str),_ovs['Value']))
                    st.caption(f"Origin validation (research only): {int(float(_om.get('Clean outcomes',0) or 0))} clean outcomes • hit rate {safe(_om.get('Clean target-before-stop hit rate %'),1)}% • 95% Wilson {safe(_om.get('Hit-rate Wilson 95% low %'),1)}–{safe(_om.get('Hit-rate Wilson 95% high %'),1)}% • {_om.get('Research sample state','LOW SAMPLE — RESEARCH ONLY')}")
                except Exception: pass
            _omb=pay.get('origin_matched_baseline')
            if isinstance(_omb,pd.DataFrame) and not _omb.empty:
                try:
                    _w=_omb[_omb['OpeningBarOrdinal'].astype(str)=='WEIGHTED']
                    if not _w.empty:
                        _wr=_w.iloc[-1]
                        st.caption(f"Origin matched baseline: signal HR {safe(_wr.get('SignalHitRatePct'),1)}% vs same-opening-slot baseline {safe(_wr.get('BaselineHitRatePct'),1)}% • lift {safe(_wr.get('HitRateLiftX'),2)}x • expectancy delta {safe(_wr.get('ExpectancyDeltaPct'),2)}% • research only")
                        _omc=pay.get('origin_matched_confidence')
                        if isinstance(_omc,pd.DataFrame) and not _omc.empty:
                            _mm=dict(zip(_omc['Metric'].astype(str),_omc['Value']))
                            st.caption(f"Matched-edge uncertainty: ΔHR {safe(_mm.get('Hit-rate delta percentage points'),2)} pp • approx 95% CI {safe(_mm.get('Hit-rate delta approx 95% low pp'),1)} to {safe(_mm.get('Hit-rate delta approx 95% high pp'),1)} pp • p≈{safe(_mm.get('Approx two-sided p-value'),3)} • {_mm.get('Matched edge confidence','RESEARCH ONLY')}")
                except Exception: pass
            _cvs=pay.get('continuation_validation_summary')
            if isinstance(_cvs,pd.DataFrame) and not _cvs.empty:
                try:
                    _cm=dict(zip(_cvs['Metric'].astype(str),_cvs['Value']))
                    st.caption(f"Continuation validation (research only): {int(float(_cm.get('Continuation base candidates',0) or 0))} candidates • {int(float(_cm.get('Breakout touched candidates',0) or 0))} breakouts • clean hit rate {safe(_cm.get('Clean post-breakout hit rate %'),1)}% • {_cm.get('Research sample state','LOW SAMPLE — RESEARCH ONLY')}")
                except Exception: pass
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
        with cc1:
            st.caption("Early components")
            _render_dataframe_safe_v608(early_cal, "Insufficient Early evidence")
        with cc2:
            st.caption("Quant components")
            _render_dataframe_safe_v608(quant_cal, "Insufficient Quant evidence")
        if pay.get('excel'):
            with analyze_excel_top.container():st.download_button("⬇️ Download Analyze Excel",data=pay['excel'],file_name=f"AI_Stock_Hunter_V{APP_VERSION}_Analyze_{t}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True,key="analyze_excel_top_v624")
        elif pay.get('excel_error'):
            with analyze_excel_top.container():st.warning("Analyze completed, but Excel export failed: "+str(pay.get('excel_error'))+". The analysis below is still valid.")
        st.markdown("<div class='section'>📊 Price chart</div>",unsafe_allow_html=True);chart_period=st.radio("Range",["5D","1M","3M","6M","1Y","MAX"],horizontal=True,index=2,key=f"simple_period_{t}");chart_tf="1D" if chart_period in ("3M","6M","1Y","MAX") else "1H";chart_layers=["EMA20","EMA50","Volume"];chart_rsi=False;chart_macd=False
        with st.expander("Advanced chart",expanded=False):
            chart_tf=st.selectbox("Timeframe",["15m","1H","1D","1W"],2,key=f"adv_tf_{t}");chart_layers=st.multiselect("Layers",["EMA9","EMA20","EMA50","VWAP","Volume"],default=["EMA20","EMA50","Volume"],key=f"adv_layers_{t}");ac1,ac2=st.columns(2);chart_rsi=ac1.checkbox("RSI",False,key=f"adv_rsi_{t}");chart_macd=ac2.checkbox("MACD",False,key=f"adv_macd_{t}")
        chart_interval,chart_fetch_period,chart_capped=chart_request(chart_tf,chart_period);cd=fetch_ohlcv(t,chart_fetch_period,chart_interval)
        if cd is not None and len(cd)>0:
            cf=compute_features(cd,intraday=chart_interval in ("5m","15m","30m","1h"));st.plotly_chart(chart(cf,f"{t} • {chart_tf} • {chart_period}",chart_layers,chart_rsi,chart_macd,trade_plan=ent if ca_report.get('data_quality')=='OK' else None,current_price=latest_live.get('price')),use_container_width=True,config=CHART_CONFIG,key=f"main_chart_{t}_{chart_tf}_{chart_period}")
            if chart_capped:st.caption("Intraday display history is provider-capped. This affects the chart only, not model calculations.")

with tab_optimizer:
    st.markdown("<div class='section'>🧠 Adaptive Entry Optimizer</div>",unsafe_allow_html=True)
    optimizer_excel_top=st.empty()
    st.caption("Learns DAILY and HOURLY timing models with nested out-of-sample selection. Every completed run is stored in a Model Registry; Scanner uses the best eligible OOS model for each market/horizon/target, not the latest run.")
    with st.expander("Import prior V6.1.2 Optimizer workbooks into Model Registry"):
        imported_files=st.file_uploader("Optimizer .xlsx files",type=["xlsx"],accept_multiple_files=True,key="optimizer_import_v613")
        if st.button("⬆️ Import selected workbooks",key="optimizer_import_btn_v613",use_container_width=True,disabled=not imported_files):
            msgs=[]
            for uf in imported_files or []:
                ok,msg=_import_optimizer_workbook_v613(uf);msgs.append((ok,uf.name,msg))
            for ok,name,msg in msgs:
                (st.success if ok else st.warning)(f"{name}: {msg}")
            if any(x[0] for x in msgs):st.rerun()
        reg_now=_load_model_registry_v613();st.caption(f"Registry currently stores {len(reg_now.get('models',[]))} optimization run(s). Imported V6.1.2 daily models can be reused immediately; hourly OOS models are learned by V6.1.3+ optimizer runs.")
    o_market=st.radio("Optimization universe",["ALL 151","ALL 351","US 51","US 201","HONG KONG 50","HONG KONG 100","TEL AVIV 50"],horizontal=True,key="o_market_v612")
    o_hist=st.selectbox("History",["2y","3y","5y"],0,key="o_hist_v612")
    c1,c2,c3,c4=st.columns(4);o_horizon=c1.selectbox("Daily horizon",[1,2,3,5],2,key="o_horizon_v612");o_target=c2.selectbox("Daily target %",[3,5,10,15],0,key="o_target_v612");o_htarget=c3.selectbox("Hourly target %",[1,2,3],2,key="o_htarget_v612");o_min=c4.number_input("Min training events",10,150,25,5,key="o_min_v612")
    o_hours=st.multiselect("Hourly horizons",["1h","2h","4h"],default=["1h","2h","4h"],key="o_hours_v612");hour_map={'1h':1,'2h':2,'4h':4}
    a,_=_lab_snapshot_v603('entry');busy=bool(a and a.get('status') in ('running','stopping'));c1,c2=st.columns([2,1])
    with c1:
        if st.button("▶ Run Entry Optimization",key="entry612_start",use_container_width=True,disabled=busy):
            uni={'ALL 151':VALIDATION_151,'ALL 351':VALIDATION_351,'US 51':US_51,'US 201':US_201,'HONG KONG 50':HK_50,'HONG KONG 100':HK_100,'TEL AVIV 50':TASE_50}[o_market]
            cfg={'tickers':[x for x in uni.split(',') if x],'market':o_market,'history':o_hist,'target':float(o_target),'horizon':int(o_horizon),'min_events':int(o_min),'hourly_target':int(o_htarget),'hourly_bars':tuple(hour_map[x] for x in o_hours) or (1,2,4)}
            ok,msg=_start_lab_v603('entry',_entry_worker_v603,cfg,total=len(cfg['tickers']))
            if ok:st.success("Optimizer started server-side. You can leave this tab and return later.");st.rerun()
            else:st.warning(msg)
    with c2:
        if st.button("■ Stop Optimizer",key="entry612_stop",use_container_width=True,disabled=not busy or (a and a.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('entry');st.warning(msg) if ok else st.info(msg);st.rerun()
    if busy:_lab_live_fragment_v603('entry')
    else:_render_lab_status_v603('entry')
    a,last=_lab_snapshot_v603('entry');snap=a if a and a.get('payload') else last
    if snap and snap.get('payload'):
        pay=snap['payload'];opt=_coerce_dataframe_v608(pay.get('optimizer'));weights=_coerce_dataframe_v608(pay.get('optimizer_weights'));hop=_coerce_dataframe_v608(pay.get('hourly_optimizer'));hweights=_coerce_dataframe_v608(pay.get('hourly_optimizer_weights'));regsel=_coerce_dataframe_v608(pay.get('registry_selection'));pm=_coerce_dataframe_v608(pay.get('premove_summary'));hl=_coerce_dataframe_v608(pay.get('hourly_summary'))
        if not opt.empty:
            st.markdown("#### Learned Entry Model — OOS first");show=opt.copy()
            for c in ['Inner median OOS lift','Inner worst OOS lift','Final Fold4 OOS lift']:
                if c in show:show[c]=show[c].map(lambda x:f"{float(x):.3f}x ({(float(x)-1)*100:+.1f}%)" if pd.notna(x) else '—')
            st.dataframe(show,use_container_width=True,hide_index=True)
        if not weights.empty:
            st.markdown("#### Daily learned weights");st.dataframe(weights.round(3),use_container_width=True,hide_index=True)
        if not hop.empty:
            st.markdown("#### Hourly Timing Model — matched-hour OOS");hshow=hop.copy()
            for c in ['Inner median OOS lift','Inner worst OOS lift','Fold4 matched OOS lift']:
                if c in hshow:hshow[c]=hshow[c].map(lambda x:f"{float(x):.3f}x ({(float(x)-1)*100:+.1f}%)" if pd.notna(x) else '—')
            st.dataframe(hshow,use_container_width=True,hide_index=True)
        if not hweights.empty:
            st.markdown("#### Hourly learned weights");st.dataframe(hweights.round(3),use_container_width=True,hide_index=True)
        if not regsel.empty:
            st.markdown("#### Model Registry — currently selected eligible models");st.dataframe(regsel,use_container_width=True,hide_index=True)
        if not pm.empty:
            st.markdown("#### Pre-Move Lift — what appears before the move");st.dataframe(pm.round(3),use_container_width=True,hide_index=True)
        if not hl.empty:
            st.markdown("#### Hourly Lift — matched against the same hour baseline");st.dataframe(hl.round(3),use_container_width=True,hide_index=True)
        with st.expander("Component / market diagnostics"):
            _render_dataframe_safe_v608(pay.get('summary'),"No Entry Score diagnostics.");_render_dataframe_safe_v608(pay.get('market_gate'),"No market gate diagnostics.")

    st.markdown("#### 🧪 Cross-Stock Research Validator — fixed rule, session-cluster bootstrap")
    st.caption("Research only. Uses the unchanged Setup-Origin rule, a leave-one-session-out same-ticker/same-opening-slot baseline, and a calendar-session cluster bootstrap across stocks. No production weights, thresholds, ranks or Entry gates are changed.")
    rv1,rv2=st.columns(2)
    rv_scope=rv1.selectbox("Research scope",["ALL","NASDAQ","US","HONG KONG","TEL AVIV"],0,key="rv624_scope")
    rv_cap=rv2.selectbox("Stocks to test",[12,25,50,100,200,350],1,key="rv624_cap")
    rv_tickers=_research_validator_universe_v624(rv_scope,int(rv_cap))
    st.caption(f"Fixed research spec: +2.0% target / -1.5% stop / 16×15m forward bars • {len(rv_tickers)} ticker(s) • 60d intraday history when provider permits.")
    rva,_=_lab_snapshot_v603('research_validator');rv_busy=bool(rva and rva.get('status') in ('running','stopping'));rvc1,rvc2=st.columns([2,1])
    with rvc1:
        if st.button("▶ Run Cross-Stock Research Validator",key="rv624_start",use_container_width=True,disabled=rv_busy):
            cfg={'tickers':rv_tickers,'scope':rv_scope,'target_pct':.02,'stop_pct':.015,'horizon_bars':16,'bootstrap_runs':1200}
            ok,msg=_start_lab_v603('research_validator',_research_validator_worker_v624,cfg,total=len(rv_tickers))
            if ok:st.success("Cross-stock validator started server-side. You can leave the app and return later.");st.rerun()
            else:st.warning(msg)
    with rvc2:
        if st.button("■ Stop Research Validator",key="rv624_stop",use_container_width=True,disabled=not rv_busy or (rva and rva.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('research_validator');st.warning(msg) if ok else st.info(msg);st.rerun()
    if rv_busy:_lab_live_fragment_v603('research_validator')
    else:_render_lab_status_v603('research_validator')
    rva,rvlast=_lab_snapshot_v603('research_validator');rvsnap=rva if rva and rva.get('payload') else rvlast
    if rvsnap and rvsnap.get('payload'):
        rvp=rvsnap['payload'];rvsum=_coerce_dataframe_v608(rvp.get('summary'));rvstocks=_coerce_dataframe_v608(rvp.get('stocks'));rvskip=_coerce_dataframe_v608(rvp.get('skipped'))
        if not rvsum.empty:
            st.markdown("##### Cross-stock matched-edge evidence");st.dataframe(rvsum.round(3),use_container_width=True,hide_index=True)
        if not rvstocks.empty:
            with st.expander("Per-stock research audit",expanded=False):st.dataframe(rvstocks.round(3),use_container_width=True,hide_index=True)
        if not rvskip.empty:
            with st.expander(f"Skipped / provider errors ({len(rvskip)})",expanded=False):st.dataframe(rvskip,use_container_width=True,hide_index=True)
    st.markdown("#### 🔭 Pre-Move OOS Discovery — find strong indicators before the rise")
    st.caption("Research only. The first 70% of each stock's history discovers singles/pairs; the later 30% is untouched OOS validation. V6.2.8 separates the research radar from the trade trigger: correlated signals are de-duplicated into independent families, late/already-moved names are blocked, and research stages are WATCH / BUILDING / PRE-MOVE CANDIDATE / STRONG PRE-MOVE CANDIDATE. Trade confirmation remains in Scanner/Analyze.")
    pm1,pm2,pm3,pm4=st.columns(4)
    pm_scope=pm1.selectbox("Pre-Move scope",["NASDAQ","US","HONG KONG","TEL AVIV","ALL"],0,key="pm625_scope")
    pm_cap=pm2.selectbox("Stocks",[12,25,50,100,200,350],1,key="pm625_cap")
    pm_hist=pm3.selectbox("Research history",["2y","3y","5y"],1,key="pm625_hist")
    pm_target=pm4.selectbox("Future move target %",[3,5,8],1,key="pm625_target")
    pm5,pm6=st.columns(2)
    pm_horizon=pm5.selectbox("Future horizon (days)",[1,2,3,5],2,key="pm625_horizon")
    pm_min_lift=pm6.selectbox("Discovery minimum lift",[1.10,1.20,1.30],1,key="pm625_min_lift")
    pm_tickers=_research_validator_universe_v624(pm_scope,int(pm_cap))
    st.caption(f"Causal target: +{pm_target}% within the next {pm_horizon} daily bars • chronological 70% discovery / 30% validation • singles + automatically discovered indicator pairs • {len(pm_tickers)} ticker(s).")
    pma,_=_lab_snapshot_v603('pre_move');pm_busy=bool(pma and pma.get('status') in ('running','stopping'));pmc1,pmc2=st.columns([2,1])
    with pmc1:
        if st.button("▶ Run Pre-Move OOS Discovery",key="pm625_start",use_container_width=True,disabled=pm_busy):
            cfg={'tickers':pm_tickers,'scope':pm_scope,'history':pm_hist,'target_pct':float(pm_target)/100.0,'horizon_days':int(pm_horizon),'min_discovery_signals':25,'min_validation_signals':12,'min_discovery_lift':float(pm_min_lift)}
            ok,msg=_start_lab_v603('pre_move',_pre_move_discovery_worker_v625,cfg,total=len(pm_tickers))
            if ok:st.success("Pre-Move discovery started server-side. You can leave the app and return later.");st.rerun()
            else:st.warning(msg)
    with pmc2:
        if st.button("■ Stop Pre-Move",key="pm625_stop",use_container_width=True,disabled=not pm_busy or (pma and pma.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('pre_move');st.warning(msg) if ok else st.info(msg);st.rerun()
    if pm_busy:_lab_live_fragment_v603('pre_move')
    else:_render_lab_status_v603('pre_move')
    pma,pmlast=_lab_snapshot_v603('pre_move');pmsnap=pma if pma and pma.get('payload') else pmlast
    if pmsnap and pmsnap.get('payload'):
        pmp=pmsnap['payload'];pmcand=_coerce_dataframe_v608(pmp.get('candidates'));pmev=_coerce_dataframe_v608(pmp.get('evidence'));pmskip=_coerce_dataframe_v608(pmp.get('skipped'))
        if not pmcand.empty:
            st.markdown("##### Current Pre-Move research radar — not trade triggers")
            st.dataframe(pmcand.head(30),use_container_width=True,hide_index=True)
            st.caption("PreMoveProbabilityPct is an empirical OOS hit rate of de-duplicated representative signals, not a guaranteed market probability. PreMoveScore is freshness-adjusted; a Pre-Move Candidate is research radar only and is never the same thing as a live Trade Trigger.")
        else:st.info("No current stock has enough active discovery-selected signals that survived OOS validation for this run.")
        if not pmev.empty:
            with st.expander("OOS indicator / pair evidence",expanded=False):st.dataframe(pmev.head(250).round(3),use_container_width=True,hide_index=True)
        if not pmskip.empty:
            with st.expander(f"Skipped / provider errors ({len(pmskip)})",expanded=False):st.dataframe(pmskip,use_container_width=True,hide_index=True)
    _render_optimizer_top_excel_v625(optimizer_excel_top)

with tab_feedback:
    st.markdown("<div class='section'>↺ Feedback / Outcome Tracker</div>",unsafe_allow_html=True)
    feedback_excel_top=st.empty()
    st.caption("Every completed live Scanner run creates snapshots immediately. Live outcomes mature only after future 1D / 2D / 3D / 5D trading sessions. V6.3.0 also adds portable/remote persistence and a separate causal Historical Replay for immediate research statistics without mixing replay with live results.")

    # V6.3.0 Persistence Hub: portable DB backup/restore always works; optional
    # GitHub persistence survives Streamlit redeploys when a token is configured
    # in secrets. The token itself is never shown in the UI or exported.
    try:_feedback_conn_v600().close()
    except Exception:pass
    p_cfg=_feedback_persistence_cfg_v630()
    with st.expander("💾 Persistent Feedback DB — backup / restore",expanded=False):
        pc1,pc2,pc3=st.columns(3)
        pc1.metric("Storage", "GitHub + local" if p_cfg.get('enabled') else "Local + portable backup")
        pc2.metric("DB size",f"{len(_feedback_db_bytes_v630())/1024:.0f} KB")
        pc3.metric("Remote sync", "Configured" if p_cfg.get('enabled') else "Not configured")
        st.download_button("⬇️ Download Feedback DB backup",data=_feedback_db_bytes_v630(),file_name=f"AI_Stock_Hunter_V{APP_VERSION}_Feedback_DB_{datetime.now().strftime('%Y%m%d_%H%M')}.sqlite3",mime="application/octet-stream",use_container_width=True,key="feedback_db_backup_v630")
        restore_file=st.file_uploader("Restore Feedback DB backup (.sqlite3)",type=["sqlite3","db"],key="feedback_db_restore_file_v630")
        rc1,rc2,rc3=st.columns(3)
        with rc1:
            if st.button("♻️ Restore uploaded DB",key="feedback_db_restore_btn_v630",use_container_width=True,disabled=restore_file is None):
                ok,msg=_feedback_restore_bytes_v630(restore_file.getvalue(),push_remote=bool(p_cfg.get('enabled')))
                (st.success if ok else st.error)(msg)
                if ok:st.rerun()
        with rc2:
            if st.button("☁️ Sync DB now",key="feedback_db_push_btn_v630",use_container_width=True,disabled=not p_cfg.get('enabled')):
                ok,msg=_feedback_remote_push_v630();(st.success if ok else st.warning)(msg)
        with rc3:
            if st.button("⬇️ Restore from remote",key="feedback_db_pull_btn_v630",use_container_width=True,disabled=not p_cfg.get('enabled')):
                ok,msg=_feedback_remote_pull_v630(force=True);(st.success if ok else st.warning)(msg)
                if ok:st.rerun()
        if p_cfg.get('enabled'):
            st.caption(f"Durable store: {p_cfg.get('repo')} • {p_cfg.get('branch')} • {p_cfg.get('path')} • automatic sync runs after completed scans, replay runs and newly evaluated outcomes.")
        else:
            st.caption("Portable mode is active. Download the DB backup periodically. For automatic survival across Streamlit redeploys, add the optional [feedback_persistence] GitHub token/repo/path secrets described in the README.")

    st.markdown("#### 🧬 Historical Replay V3 — Combination Discovery + Walk-Forward")
    st.caption("V6.3.3 first reconstructs the same causal DAILY evidence, then uses only the earliest 70% of dates to discover 2–4 indicator combinations across different independent families. The final 30% is untouched OOS validation and is split into three chronological folds. A 70% result in Discovery is never called successful unless the later OOS period confirms it. Production Entry is unchanged.")
    rp1,rp2,rp3,rp4,rp5=st.columns(5)
    replay_scope=rp1.selectbox("Replay market",["NASDAQ","HONG KONG","TEL AVIV","ALL"],0,key="replay_scope_v630")
    replay_cap=rp2.selectbox("Replay stocks",[25,50,100,200,350],1,key="replay_cap_v630")
    replay_hist=rp3.selectbox("Replay history",["6mo","1y","2y","3y"],1,key="replay_hist_v630")
    replay_target=rp4.selectbox("Replay target %",[3,5,8],1,key="replay_target_v630")
    replay_horizon=rp5.selectbox("Replay horizon D",[1,2,3,5],2,key="replay_horizon_v630")
    replay_step=st.selectbox("Sample every N trading sessions",[1,3,5,10],2,key="replay_step_v630",help="5 is a balanced default. 1 creates many highly correlated observations; replay keeps them separate from Live Feedback regardless.")
    replay_tickers=_research_validator_universe_v624(replay_scope,int(replay_cap))
    ra,_=_lab_snapshot_v603('historical_replay');replay_busy=bool(ra and ra.get('status') in ('running','stopping'));rr1,rr2=st.columns([2,1])
    with rr1:
        if st.button("▶ Run Historical Replay",key="historical_replay_start_v630",use_container_width=True,disabled=replay_busy):
            rcfg={'tickers':replay_tickers,'scope':replay_scope,'history':replay_hist,'target_pct':float(replay_target)/100.0,'horizon_days':int(replay_horizon),'sample_every':int(replay_step)}
            ok,msg=_start_lab_v603('historical_replay',_historical_replay_worker_v630,rcfg,total=len(replay_tickers)+5)
            if ok:st.success("Historical Replay started server-side. You can leave the app and return later.");st.rerun()
            else:st.warning(msg)
    with rr2:
        if st.button("■ Stop Replay",key="historical_replay_stop_v630",use_container_width=True,disabled=not replay_busy or (ra and ra.get('status')=='stopping')):
            ok,msg=_stop_lab_v603('historical_replay');st.warning(msg) if ok else st.info(msg);st.rerun()
    if replay_busy:_lab_live_fragment_v603('historical_replay')
    else:_render_lab_status_v603('historical_replay')
    replay_runs,replay_events=_feedback_replay_frames_v630(latest_only=True)
    replay_head,replay_ind,replay_stocks,replay_gates,replay_cal=_feedback_replay_scorecards_v631(replay_events)
    if not replay_runs.empty:
        latest_run=replay_runs.iloc[0]
        st.caption(f"Latest replay: {latest_run.get('scope','')} • {latest_run.get('history','')} • +{100*float(latest_run.get('target_pct',0)):.0f}% / {int(latest_run.get('horizon_days',0))}D • {int(latest_run.get('event_rows',0))} sampled rows • {int(latest_run.get('successful_tickers',0))}/{int(latest_run.get('requested_tickers',0))} stocks with usable history.")
    if not replay_head.empty:
        rh=replay_head.iloc[0];rm1,rm2,rm3,rm4=st.columns(4)
        rm1.metric("All-row baseline",f"{float(rh['All Clean Baseline %']):.1f}%" if pd.notna(rh['All Clean Baseline %']) else "—")
        rm2.metric("V2 candidate success",f"{float(rh['V2 Candidate Success %']):.1f}%" if pd.notna(rh['V2 Candidate Success %']) else "—")
        rm3.metric("HIGH CONFIDENCE",f"{float(rh['High Confidence Success %']):.1f}%" if pd.notna(rh['High Confidence Success %']) else "—")
        rm4.metric("HC resolved",int(rh['High Confidence Resolved']))
        st.caption(f"V2 resolved: {int(rh['V2 Candidate Resolved'])} • V2 lift: {float(rh['V2 Lift x']):.2f}x" if pd.notna(rh['V2 Lift x']) else f"V2 resolved: {int(rh['V2 Candidate Resolved'])}. High Confidence is deliberately selective and may return zero cases rather than force a 70% result.")
        if not replay_gates.empty:st.dataframe(replay_gates.round(3),use_container_width=True,hide_index=True)
        if not replay_cal.empty:
            with st.expander("Causal Meta-Probability calibration",expanded=False):st.dataframe(replay_cal.round(2),use_container_width=True,hide_index=True)
    combo_latest,combo_folds_latest=_feedback_replay_combo_frames_v633(latest_only=True)
    # V6.3.3: prefer the already-built workbook kept in the completed background
    # job. This avoids rebuilding a multi-megabyte Excel file during the final
    # Streamlit rerun, which was the main reason the top Stop icon could linger
    # even after 'Run completed'.
    ra_now,rlast_now=_lab_snapshot_v603('historical_replay')
    replay_payload=(ra_now or {}).get('payload') if ra_now and ra_now.get('status')=='completed' else ((rlast_now or {}).get('payload') if rlast_now else None)
    if not combo_latest.empty:
        strong=int(combo_latest['OOS Status'].astype(str).isin(['OOS STRONG','OOS POSITIVE']).sum()) if 'OOS Status' in combo_latest else 0
        target70=int(combo_latest['Research Tier'].astype(str).eq('70% DISCOVERY TIER').sum()) if 'Research Tier' in combo_latest else 0
        valid70=combo_latest[(combo_latest.get('Research Tier','').astype(str)=='70% DISCOVERY TIER') & (combo_latest.get('Validation N',0)>=25)] if 'Research Tier' in combo_latest else pd.DataFrame()
        best_oos=pd.to_numeric(combo_latest.get('Validation Success %'),errors='coerce').max() if 'Validation Success %' in combo_latest else np.nan
        cm1,cm2,cm3=st.columns(3);cm1.metric('OOS-positive combinations',strong);cm2.metric('70% discovery candidates',target70);cm3.metric('Best OOS combination',f"{best_oos:.1f}%" if pd.notna(best_oos) else '—')
        st.caption('Green combinations survived the untouched final 30% and chronological folds. A 70% Discovery combination is only a hypothesis until its OOS column also holds up.')
        with st.expander('Combination Discovery — 70% Discovery / 30% untouched OOS',expanded=True):st.dataframe(_feedback_color_table_v629(combo_latest.head(100).round(3),'OOS Status'),use_container_width=True,hide_index=True,height=520)
        if not combo_folds_latest.empty:
            with st.expander('Walk-Forward OOS folds',expanded=False):st.dataframe(combo_folds_latest.head(500).round(3),use_container_width=True,hide_index=True,height=420)
    if not replay_ind.empty:
        with st.expander("Historical Replay indicator summary",expanded=False):st.dataframe(_feedback_color_table_v629(replay_ind.round(3),'Status'),use_container_width=True,hide_index=True)
    if not replay_stocks.empty:
        with st.expander("Historical Replay stock summary",expanded=False):st.dataframe(_feedback_color_table_v629(replay_stocks.round(2),'Model Status'),use_container_width=True,hide_index=True,height=420)
    if not replay_events.empty:
        replay_excel=(replay_payload or {}).get('excel') if isinstance(replay_payload,dict) else None
        if not replay_excel:
            replay_excel=_feedback_workbook_v629({'Replay Success':replay_head,'Replay Gate Comparison':replay_gates,'Combination Discovery':combo_latest,'WalkForward Folds':combo_folds_latest,'Replay Meta Calibration':replay_cal,'Replay Indicators':replay_ind,'Replay Stocks':replay_stocks,'Replay Events':replay_events},{'Tab':'Historical Replay V3','Version':APP_VERSION,'ResearchOnly':'YES — 70/30 combination discovery + untouched OOS; separate from Live Feedback'})
        st.download_button("⬇️ Download Historical Replay Excel",data=replay_excel,file_name=f"AI_Stock_Hunter_V{APP_VERSION}_Historical_Replay_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True,key='replay_excel_v630')

    st.markdown("#### 📡 Live Feedback — actual Scanner snapshots")
    fb1,fb2=st.columns(2)
    fb_half_life=fb1.selectbox("Recent-feedback half-life (days)",[30,60,90],1,key="feedback_half_life_v611",help="Lower = recent outcomes adapt faster; higher = more stable. This changes analytics only, never production weights automatically.")
    fb_batch=fb2.selectbox("Max outcome windows per refresh",[80,250,500],1,key="feedback_batch_v629",help="Larger universes create more pending outcomes. 250 is a good default; 500 is useful after several large scans.")
    a,_=_lab_snapshot_v603('feedback');busy=bool(a and a.get('status') in ('running','stopping'));c1,c2=st.columns([2,1])
    with c1:
        if st.button("▶ Refresh due outcomes",key="feedback603_start",use_container_width=True,disabled=busy):
            ok,msg=_start_lab_v603('feedback',_feedback_worker_v603,{'max_snapshots':int(fb_batch)},total=1)
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
    pending={h:0 for h in (1,2,3,5)}
    next_windows=[];now_utc=pd.Timestamp.now(tz='UTC');due_now=0
    if not sn.empty:
        for _,r in sn.iterrows():
            for h in (1,2,3,5):
                if (int(r.id),h) not in done:
                    pending[h]+=1
                    try:
                        eta=_feedback_due_at_v612(r.ts_utc,r.get('market',''),h,str(r.get('ticker','')))
                        if eta<=now_utc:due_now+=1
                        next_windows.append((eta,str(r.get('market','')),str(r.get('ticker','')),h))
                    except Exception:pass
    f1,f2,f3,f4,f5,f6=st.columns(6);f1.metric("Snapshots",len(sn));f2.metric("Evaluated",len(oc));f3.metric("Pending 1D",pending[1]);f4.metric("Pending 2D",pending[2]);f5.metric("Pending 3D",pending[3]);f6.metric("Pending 5D",pending[5])
    if next_windows:
        future=[x for x in next_windows if x[0]>now_utc]
        if future:
            nd,mkt,tk,hh=min(future,key=lambda x:x[0])
            st.caption(f"Next trading-session evaluation window: approximately {nd.strftime('%Y-%m-%d %H:%M')} UTC • {mkt} • {hh}D • DB: {_feedback_db_path_v600().name}")
        elif due_now:
            st.caption(f"{due_now} pending window(s) are calendar-eligible now; evaluation still waits for complete provider trading bars. • DB: {_feedback_db_path_v600().name}")
        else:st.caption(f"DB: {_feedback_db_path_v600().name}")
    else:st.caption(f"DB: {_feedback_db_path_v600().name}")
    st.caption("Feedback horizons are trading-session aware: weekends and exchange holidays do not count as 1D/2D/3D/5D. A window is evaluated only after the required number of completed daily bars exists for that ticker.")
    # V6.1.2 Feedback export hotfix: export is always available, even before the
    # first outcome window matures. This lets snapshots/pending windows be audited
    # immediately instead of hiding the Excel button until oc is non-empty.
    stage=pd.DataFrame();disagreement=pd.DataFrame();recent_summary=pd.DataFrame();recent_features=pd.DataFrame();merged=pd.DataFrame();primary=pd.DataFrame();headline=pd.DataFrame();indicator_summary=pd.DataFrame();stock_summary=pd.DataFrame()
    pending_summary=pd.DataFrame([{'Horizon':h,'Pending':int(pending[h])} for h in (1,2,3,5)])
    if sn.empty:
        st.info("No live scan snapshots yet. Run Scanner once; the completed scan will be recorded automatically.")
    elif oc.empty:
        st.info("Snapshots are being collected. 1D/2D/3D/5D outcome rows will appear when enough future market data exists.")
        st.dataframe(sn.head(30),use_container_width=True,hide_index=True)
    else:
        merged=oc.merge(sn,left_on='snapshot_id',right_on='id',how='left');merged['End Return %']=100*pd.to_numeric(merged.end_return,errors='coerce');merged['MFE %']=100*pd.to_numeric(merged.max_favorable,errors='coerce');merged['MAE %']=100*pd.to_numeric(merged.max_adverse,errors='coerce')
        st.markdown("#### Live-signal audit")
        merged['Clean Outcome']=merged['first_event'].astype(str).map(lambda x:'WIN' if x.startswith('TARGET1 FIRST') else ('LOSS' if x.startswith('INVALIDATION FIRST') else ('AMBIGUOUS' if x.startswith('AMBIGUOUS') else 'OPEN/NONE'))); clean=merged[merged['Clean Outcome'].isin(['WIN','LOSS'])].copy(); clean['Clean Win']=clean['Clean Outcome'].eq('WIN').astype(float); stage=merged.groupby(['market','horizon','trade_stage'],dropna=False).agg(Signals=('snapshot_id','count'),Avg_End_Return=('End Return %','mean'),Avg_MFE=('MFE %','mean'),Avg_MAE=('MAE %','mean'),Ambiguous=('Clean Outcome',lambda x:int((x=='AMBIGUOUS').sum()))).reset_index(); cw=clean.groupby(['market','horizon','trade_stage'],dropna=False)['Clean Win'].agg(['mean','count']).reset_index().rename(columns={'mean':'Clean Win Rate','count':'Clean Resolved'});stage=stage.merge(cw,on=['market','horizon','trade_stage'],how='left');stage['Clean Win Rate %']=100*stage.pop('Clean Win Rate')
        for c in ['Avg_End_Return','Avg_MFE','Avg_MAE','Clean Win Rate %']:
            if c in stage: stage[c]=pd.to_numeric(stage[c],errors='coerce').round(2)
        primary=_feedback_primary_rows_v629(merged);headline,indicator_summary,stock_summary=_feedback_scorecards_v629(sn,primary)
        st.markdown("#### 🎯 סיכום פשוט — אחוז הצלחה")
        if not headline.empty:
            h=headline.iloc[0];m1,m2,m3,m4=st.columns(4)
            m1.metric("אחוז הצלחה",f"{float(h['אחוז הצלחה']):.1f}%" if pd.notna(h['אחוז הצלחה']) else "—")
            m2.metric("הצלחות",int(h['הצלחות']));m3.metric("כשלונות",int(h['כשלונות']));m4.metric("מקרים נקיים",int(h['מקרים נקיים שהוכרעו']))
            st.caption(f"אחוז הצלחה = Target 1 לפני Invalidation מתוך מקרים נקיים שהוכרעו באופק הראשי של הסריקה. פתוחים/לא הוכרעו: {int(h['לא הוכרעו / פתוחים'])} • דו-משמעיים: {int(h['דו-משמעיים'])} • כיסוי הכרעה: {float(h['כיסוי הכרעה %']):.1f}%" if pd.notna(h['כיסוי הכרעה %']) else "אין עדיין מספיק תוצאות שהבשילו.")
        if not indicator_summary.empty:
            st.markdown("#### 🟢🔴 אינדיקטורים ותנאים — מה עובד ומה עדיין לא")
            st.dataframe(_feedback_color_table_v629(indicator_summary.round(2),'סטטוס'),use_container_width=True,hide_index=True)
            st.caption("ירוק = עבד במדגם הנוכחי מול בסיס הפידבק; אדום = פיגר אחרי הבסיס; צהוב = מעורב; LOW SAMPLE לא מקבל מסקנה.")
        if not stock_summary.empty:
            st.markdown("#### 🟢🔴 סיכום כל המניות שנאספו בפידבק")
            st.dataframe(_feedback_color_table_v629(stock_summary.round(2),'Model Status'),use_container_width=True,hide_index=True,height=520)
            st.caption("SUCCESS/FAILURE דורשים לפחות 3 תוצאות נקיות. מניה עם פחות מזה נשארת LOW SAMPLE / WAITING ולא נצבעת כאילו כבר הוכחה.")
        st.markdown("#### Live-signal audit by market / horizon / stage")
        st.dataframe(stage,use_container_width=True,hide_index=True)
        if 'model_disagreement' in merged:
            dg=merged.copy();dg['ResolvedWin']=dg['Clean Outcome'].map({'WIN':1.0,'LOSS':0.0});dgc=dg[np.isfinite(pd.to_numeric(dg['ResolvedWin'],errors='coerce'))]
            if not dgc.empty:
                dgkeys=['market','horizon']+(['optimized_model_horizon'] if 'optimized_model_horizon' in dgc else [])+['model_disagreement'];disagreement=dgc.groupby(dgkeys,dropna=False).agg(Resolved=('snapshot_id','count'),Win_Rate=('ResolvedWin','mean'),Avg_MFE=('MFE %','mean'),Avg_MAE=('MAE %','mean')).reset_index();disagreement['Win Rate %']=100*disagreement.pop('Win_Rate')
                st.markdown("#### Production vs Optimized — disagreement tracker");st.dataframe(disagreement.round(2),use_container_width=True,hide_index=True)
                st.caption("OPTIMIZED ONLY vs PRODUCTION ONLY is a natural live A/B test. Promotion decisions should wait for enough resolved outcomes, not a few recent examples.")
        recent_summary,recent_features=_feedback_learning_v611(merged,half_life_days=int(fb_half_life))
        if recent_summary is not None and not recent_summary.empty:
            st.markdown(f"#### 🧠 Recent-market learning — {int(fb_half_life)}-day half-life");st.dataframe(recent_summary.round(2),use_container_width=True,hide_index=True)
        if recent_features is not None and not recent_features.empty:
            st.markdown("#### Recent Lift by live confirmation");st.dataframe(recent_features.round(3),use_container_width=True,hide_index=True)
            st.caption("Recent data receives more weight, but LOW SAMPLE rows never change production weights automatically. Candidate changes must run in shadow first.")
        st.markdown("#### Recent evaluated snapshots");showcols=['ticker','market','horizon','scan_mode','trade_stage','entry_state','optimized_stage','model_disagreement','optimized_score','optimized_match','optimized_model_id','optimized_model_scope','optimized_model_horizon','optimized_oos_lift','optimized_hourly_match','optimized_hourly_horizon','confirmation_pct','daily_setup','fresh_signal','hourly_entry','volume_flow','no_chase','extension_guard','chase_risk_score','chase_risk_label','session_move_pct','since_trigger_pct','volume_trend','market_regime','movement_stage','top_score','opportunity','entry_score','hourly','exit_pressure','global_rank','End Return %','MFE %','MAE %','first_event','Clean Outcome'];st.dataframe(merged[[c for c in showcols if c in merged]].head(100),use_container_width=True,hide_index=True)
    excel_feedback=_feedback_workbook_v629({'Success Summary':headline,'Indicator Summary':indicator_summary,'Stock Summary':stock_summary,'Snapshots':sn,'Outcomes':oc,'Pending Summary':pending_summary,'Primary Outcomes':primary,'Merged Audit':merged,'Stage Summary':stage,'Production vs Optimized':disagreement,'Recent Weighted Summary':recent_summary,'Recent Feature Lift':recent_features,'Replay Runs':replay_runs,'Replay Success':replay_head,'Replay Indicators':replay_ind,'Replay Stocks':replay_stocks},{'Tab':'Feedback','Version':APP_VERSION,'RecencyHalfLifeDays':int(fb_half_life),'Snapshots':len(sn),'EvaluatedWindows':len(oc),'SuccessDefinition':'Target1 before invalidation on each scan primary feedback horizon','ReplaySeparation':'Historical Replay is research-only and excluded from Live Feedback success %'})
    with feedback_excel_top.container():st.download_button('⬇️ Download Feedback Excel',data=excel_feedback,file_name=f"AI_Stock_Hunter_V{APP_VERSION}_Feedback_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True,key='feedback_excel_top_v624')
    st.caption("V6.3.3 persistence: Live snapshots remain in SQLite and can be downloaded/restored as a portable DB. When [feedback_persistence] GitHub secrets are configured, the DB is also auto-synced after scans, replay runs and newly evaluated outcomes, so a fresh Streamlit host can restore it automatically. Historical Replay is stored separately and never inflates the Live Feedback success percentage.")

