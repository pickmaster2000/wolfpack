#!/usr/bin/env python3
"""Free, timestamped Wolfpack paper-trial tracker. No paid odds key required."""
import csv, json, os, re, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'trial-results.json'
CSV=ROOT/'trial-results.csv'
REPORT=ROOT/'trial-summary.json'
START=datetime(2026,11,11,tzinfo=timezone.utc)
END=datetime(2026,12,12,tzinfo=timezone.utc)
NOW=datetime.now(timezone.utc)
HEAD={'User-Agent':'WolfpackTrial/1.0 (college basketball statistics)','Accept':'application/json'}

def fetch(url):
    req=urllib.request.Request(url,headers=HEAD)
    with urllib.request.urlopen(req,timeout=20) as response:
        return json.load(response)
def numeric(v):
    try: return v is not None and v!='' and float(v)==float(v)
    except (ValueError,TypeError): return False
def record(c):
    records=c.get('records') or []
    item=next((r for r in records if r.get('type')=='total'),records[0] if records else {})
    m=re.match(r'^(\d+)-(\d+)',str(item.get('summary','')))
    if not m:return None
    w,l=map(int,m.groups())
    return (w/(w+l),w+l) if w+l else None
def rank(c):
    v=(c.get('curatedRank') or {}).get('current') or (c.get('team') or {}).get('rank') or 0
    try:return int(v)
    except (TypeError,ValueError):return 0
def model(h,a,history,market_spread=None):
    ht=str((h.get('team') or {}).get('id') or '')
    at=str((a.get('team') or {}).get('id') or '')
    hs=history.get(ht,[])
    aa=history.get(at,[])
    if len(hs)<2 or len(aa)<2:return None
    hr,ar=record(h),record(a)
    rh,ra=rank(h),rank(a)
    rank_signal=(4 if 1<=rh<=25 else 0)-(4 if 1<=ra<=25 else 0)
    record_signal=(hr[0]-ar[0])*8*min(1,min(hr[1],ar[1])/8) if hr and ar else 0
    prior=2.5+rank_signal+record_signal
    home_pts=(sum(x[0] for x in hs)/len(hs)+sum(x[1] for x in aa)/len(aa))/2+1.5
    away_pts=(sum(x[0] for x in aa)/len(aa)+sum(x[1] for x in hs)/len(hs))/2-1.5
    weight=min(.65,min(len(hs),len(aa))/8)
    total=max(115,min(175,144*(1-weight)+(home_pts+away_pts)*weight))
    margin=max(-22,min(22,prior*(1-weight)+(home_pts-away_pts)*weight))
    if market_spread is not None:
        center=-market_spread
        margin=max(center-9,min(center+9,margin))
    return round((total+margin)/2,1),round((total-margin)/2,1)

def lines(odds,h,a):
    if not odds:return None,None,None
    spread=odds.get('spread')
    total=odds.get('overUnder')
    fav=odds.get('favorite') or {}
    if not isinstance(fav,dict):fav={}
    favorite=fav.get('team') or fav.get('id') or {}
    if isinstance(favorite,dict):favorite=favorite.get('id')
    homeid=str(h.get('team',{}).get('id'))
    awayid=str(a.get('team',{}).get('id'))
    home_line=None
    if numeric(spread):
        if favorite is not None and str(favorite)==homeid:home_line=-abs(float(spread))
        elif favorite is not None and str(favorite)==awayid:home_line=abs(float(spread))
        elif numeric((odds.get('homeTeamOdds') or {}).get('spread')):home_line=float(odds['homeTeamOdds']['spread'])
        else:
            prefix=str(odds.get('details') or '').split(' ')[0]
            if prefix==h.get('team',{}).get('abbreviation'):home_line=-abs(float(spread))
            elif prefix==a.get('team',{}).get('abbreviation'):home_line=abs(float(spread))
    t=float(total) if numeric(total) and float(total)>0 else None
    provider=(odds.get('provider') or {}).get('name') or 'ESPN'
    return home_line,t,provider
def grade(p,home,away):
    if p=='home':return 'P' if home==away else 'W' if home>away else 'L'
    if p=='away':return 'P' if home==away else 'W' if away>home else 'L'
    return None

items=json.loads(PATH.read_text()) if PATH.exists() else {}
errors=[]
# Collect yesterday and the preceding week to grade games even if a run was delayed.
dates=[(NOW+timedelta(days=d)).strftime('%Y%m%d') for d in range(-14,2)]
history={}
MAJORS={'Boston College','Clemson','Duke','Florida State','Georgia Tech','Louisville','Miami','NC State','North Carolina','Notre Dame','Pittsburgh','SMU','Stanford','Syracuse','California','Virginia','Virginia Tech','Wake Forest','Illinois','Indiana','Iowa','Maryland','Michigan','Michigan State','Minnesota','Nebraska','Northwestern','Ohio State','Oregon','Penn State','Purdue','Rutgers','UCLA','USC','Washington','Wisconsin','Arizona','Arizona State','Baylor','BYU','Cincinnati','Colorado','Houston','Iowa State','Kansas','Kansas State','Oklahoma State','TCU','Texas Tech','UCF','Utah','West Virginia','Alabama','Arkansas','Auburn','Florida','Georgia','Kentucky','LSU','Mississippi State','Missouri','Oklahoma','Ole Miss','South Carolina','Tennessee','Texas','Texas A&M','Vanderbilt','Butler','Connecticut','Creighton','DePaul','Georgetown','Marquette','Providence','Seton Hall',"St. John's",'Villanova','Xavier'}
for day in dates:
    try:events=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates='+day+'&groups=50&limit=500').get('events',[])
    except Exception as e:
        errors.append(day+': '+str(e));continue
    events=sorted(events,key=lambda e:e.get('date',''))
    for event in events:
        eid=str(event.get('id') or '')
        comp=(event.get('competitions') or [{}])[0]
        competitors=comp.get('competitors') or []
        h=next((c for c in competitors if c.get('homeAway')=='home'),None)
        a=next((c for c in competitors if c.get('homeAway')=='away'),None)
        if not eid or not h or not a:continue
        if event.get('status',{}).get('type',{}).get('completed') and numeric(h.get('score')) and numeric(a.get('score')):
            for team,opponent in ((h,a),(a,h)):
                tid=str((team.get('team') or {}).get('id') or '')
                if tid:history.setdefault(tid,[]).append((float(team['score']),float(opponent['score'])))
        if eid in items:
            item=items[eid]
            if event.get('status',{}).get('type',{}).get('completed') and numeric(h.get('score')) and numeric(a.get('score')):
                item['final_home']=int(h['score']);item['final_away']=int(a['score'])
                if item.get('spread_pick'):
                    actual=item['final_home']-item['final_away']+item['home_spread']
                    item['spread_grade']='P' if abs(actual)<.001 else ('W' if (actual>0)==(item['spread_pick']=='home') else 'L')
                if item.get('total_pick'):
                    actual=item['final_home']+item['final_away']-item['total_line']
                    item['total_grade']='P' if abs(actual)<.001 else ('W' if (actual>0)==(item['total_pick']=='over') else 'L')
            continue
        if not (START<=NOW<END):continue
        try:tip=datetime.fromisoformat(event['date'].replace('Z','+00:00'))
        except (ValueError,KeyError):continue
        if tip<=NOW or tip>NOW+timedelta(days=2):continue
        if not any((c.get('team') or {}).get('location') in MAJORS for c in (h,a)):continue
        odds=(comp.get('odds') or [None])[0]
        if not odds:
            try:
                detail=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event='+eid)
                odds=(detail.get('pickcenter') or detail.get('odds') or [None])[0]
            except Exception:odds=None
        spread,total,provider=lines(odds,h,a)
        if spread is None and total is None:continue
        prediction=model(h,a,history,spread)
        if prediction is None:continue
        hp,ap=prediction
        edge=hp-ap+spread if spread is not None else None
        total_edge=hp+ap-total if total is not None else None
        items[eid]={'event_id':eid,'tip_utc':tip.isoformat(),'captured_utc':NOW.isoformat(),
            'home':h.get('team',{}).get('displayName'),'away':a.get('team',{}).get('displayName'),
            'projected_home':hp,'projected_away':ap,'home_spread':spread,'total_line':total,
            'odds_source':provider,'model_version':'recent-scoring-v2',
            'spread_edge':round(edge,2) if edge is not None else None,
            'total_edge':round(total_edge,2) if total_edge is not None else None,
            'spread_pick':('home' if edge>0 else 'away') if edge is not None and abs(edge)>.001 else None,
            'total_pick':('over' if total_edge>0 else 'under') if total_edge is not None and abs(total_edge)>.001 else None}
# Never replace a captured pick with hindsight.
PATH.write_text(json.dumps(items,indent=2,sort_keys=True)+'\n')
fields=['event_id','tip_utc','captured_utc','home','away','projected_home','projected_away','home_spread','total_line','odds_source','model_version','spread_edge','total_edge','spread_pick','total_pick','final_home','final_away','spread_grade','total_grade']
with CSV.open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(sorted(items.values(),key=lambda x:x['tip_utc']))
def stats(field):
    values=[i[field] for i in items.values() if i.get(field) in ('W','L','P')]
    w,l,p=(values.count(x) for x in ('W','L','P'))
    return {'wins':w,'losses':l,'pushes':p,'win_pct':round(100*w/(w+l),2) if w+l else None}
summary={'model_version':'recent-scoring-v2','updated_utc':NOW.isoformat(),'trial_start':'2026-11-11','trial_end':'2026-12-11','captured_games':len(items),'spread':stats('spread_grade'),'total':stats('total_grade'),'errors':errors}
REPORT.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
