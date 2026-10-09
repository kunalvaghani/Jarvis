"""One bounded read per green adapter, plus live idle-model/readiness evidence.

Never changes provider accounts or the user's location. Reports unavailable and
configuration-dependent services separately; does not claim all providers work.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from jarvis.realtime import settings, reader
from jarvis.realtime_catalog import CATALOG
from jarvis.realtime_sources import Sources

BASE=Path(__file__).resolve().parents[2]


def main():
    options=settings(json.loads((BASE/'config/config.json').read_text())['realtime'])
    sources=Sources(options)
    args={'query':'Earth','id':'Earth','latitude':38.9,'longitude':-77.0,
        'symbol':'BTC-USD','timezone':'Asia/Kolkata','base':'USD','target':'INR','country':'IN'}
    overrides={
        'weather':{},'air':{},'marine':{'latitude':35,'longitude':-15},'flood':{},
        'wikidata':{'id':'Q42'},'dictionary':{'id':'earth'},'postcodes':{'id':'390001'},
        'food':{'id':'3017620422003'},'cover_art':{'id':'b84ee12a-09ef-421b-82de-0441a926375b'},
        'listenbrainz':{'id':'iliekcomputers'},'defillama':{'id':'aave'},'coinpaprika':{'id':'btc-bitcoin'},
        'binance':{'symbol':'BTCUSDT'},'binance_stream':{'symbol':'BTCUSDT'},
        'kraken_stream':{'symbol':'BTC/USD'},'google_news':{'query':'weather'},
        'gdelt':{'query':'climate'},'tvmaze':{'query':'Sherlock'},'itunes':{'query':'Beethoven'},
        'nominatim':{'query':'London'},'geocoding':{'query':'London'},'countries':{'id':'India'},
        'rsshub':{'route':'bbc/world'},'osrm':{'to_latitude':39,'to_longitude':-77.1},
        'opentripplanner':{'to_latitude':39,'to_longitude':-77.1}}
    checks=[]; started=time.monotonic()
    def probe(key):
        began=time.monotonic(); row=sources.fetch(key,{**args,**overrides.get(key,{})})
        data=row.get('data'); count=len(data) if isinstance(data,(list,dict)) else int(data is not None)
        # Public receipt excludes IP addresses, inferred location, private cache and prompt text.
        return {'provider':key,'name':CATALOG[key].name,'status':row['status'],
            'seconds':round(time.monotonic()-began,3),'record_fields':count,
            'fetched_at':row.get('fetched_at'),'sample':row.get('sample',False),
            'detail':row.get('detail',''),'reference':CATALOG[key].docs}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(probe,key) for key in CATALOG]):
            row=future.result(); checks.append(row)
            print(row['provider']+': '+row['status'],flush=True)
    try:
        model=reader([{'provider':'verification_fixture','fetched_at':time.time(),
            'data':{'weather':'ordinary','danger':False}}],lambda:False,options)
    except Exception as exc: model={'status':'unavailable','detail':type(exc).__name__+': '+str(exc)[:200]}
    counts={status:sum(row['status']==status for row in checks) for status in sorted({r['status'] for r in checks})}
    result={'date':datetime.now(timezone.utc).isoformat(),'scope':'Actual bounded public reads of green-selected APIs; failures/setup needs reported explicitly. No complete worldwide/live coverage claim.',
        'providers':len(CATALOG),'counts':counts,'checks':sorted(checks,key=lambda r:r['provider']),
        'background_reader':model,'seconds':round(time.monotonic()-started,3)}
    path=BASE/'artifacts/reports/realtime-live-check.json'
    if path.exists():
        history=BASE/'artifacts/reports/realtime-live-history.json'
        rows=json.loads(history.read_text()) if history.exists() else []
        rows.append(json.loads(path.read_text())); history.write_text(json.dumps(rows,indent=2)+'\n')
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'counts':counts,'reader':model}),flush=True)


if __name__=='__main__': main()
