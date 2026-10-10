"""Bounded public GETs and short stream samples; remote content is data only."""
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import quote, urlsplit, urljoin
import xml.etree.ElementTree as ET

import requests
from .realtime_catalog import CATALOG

MAX_BYTES = 1024 * 1024
# Stable public instances used when no self-hosted endpoint is configured (OSRM's demo server).
PUBLIC_DEFAULTS = {'osrm': 'https://router.project-osrm.org'}
# Slow but healthy providers get a longer bounded read (seconds).
SLOW = {'overpass': 18, 'gdelt': 15, 'listenbrainz': 12, 'cover_art': 12, 'dbpedia': 10, 'semantic_scholar': 8,
        'worldbank': 10, 'countries': 10, 'epic': 10, 'power': 12, 'spacex': 10}
# When a provider is down or rate limited, an equivalent public source answers instead (labelled as such).
FALLBACK = {'worldtime': 'timeapi', 'semantic_scholar': 'openalex', 'gdelt': 'google_news', 'bluesky': 'google_news',
            'listenbrainz': 'musicbrainz'}
USER_AGENT = 'JarvisPersonalRealtime/1.0 (local personal assistant)'


def countries_key(base=None):
    """Prefer process credentials; otherwise read the ignored local key file."""
    token = os.environ.get('JARVIS_REALTIME_COUNTRIES_KEY', '')
    if not token:
        path = Path(base or Path(__file__).resolve().parent.parent) / 'secrets/realtime.json'
        try:
            if path.stat().st_size > 8192:
                raise ValueError('Local credential file exceeds 8 KiB')
            values = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(values, dict):
                raise ValueError('Local credential file must be a JSON object')
            token = values.get('countries_api_key', '')
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError, ValueError):
            raise ValueError('Check the ignored secrets/realtime.json credential file') from None
    if not isinstance(token, str) or len(token) > 2048 or any(c.isspace() or ord(c) < 32 for c in token):
        raise ValueError('Invalid local Countries key; it must be a single token')
    return token


def public_url(url, configured=False):
    """Receipts never contain URL credentials, query tokens or private feed paths."""
    parts = urlsplit(url)
    host = parts.hostname or ''
    if ':' in host:
        host = '[' + host + ']'
    port = ':' + str(parts.port) if parts.port else ''
    return parts.scheme + '://' + host + port + ('' if configured else parts.path)


def read_error(exc):
    """Request exception strings can include secret-bearing URLs and headers."""
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', None)
    if isinstance(status, int):
        return 'Provider returned HTTP ' + str(status)
    if isinstance(exc, requests.Timeout):
        return 'Provider request timed out within the bounded read'
    if isinstance(exc, requests.RequestException):
        return 'Provider connection failed (' + type(exc).__name__ + ')'
    return 'Provider read failed (' + type(exc).__name__ + ')'


def coordinates(args):
    lat, lon = float(args['latitude']), float(args['longitude'])
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('Invalid latitude/longitude')
    return lat, lon


def endpoint(provider, args, options, credential_base=None):
    """Construct requests without model-selected URLs, methods, headers or secrets."""
    key, url = provider.key, provider.url
    q = str(args.get('query', '')).strip()[:300]
    identity = str(args.get('id', q)).strip()[:150]
    symbol = str(args.get('symbol', 'BTC-USD')).upper()
    if not re.fullmatch(r'[A-Z0-9:/_-]{1,30}', symbol):
        raise ValueError('Invalid market symbol')
    params, headers, subscription = {}, {}, None
    if provider.requirement in {'self-host', 'feed'}:
        url = options.get('endpoints', {}).get(key, '') or PUBLIC_DEFAULTS.get(key, '')
        parts = urlsplit(url)
        if not url or parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password:
            raise ValueError('Configure realtime.endpoints.' + key + ' for your own service/feed')
        if key == 'searxng':
            url = url.rstrip('/') + '/search'; params = {'q': q, 'format': 'json'}
        elif key == 'rsshub':
            route = str(args.get('route', '')).strip('/')
            if not route or not re.fullmatch(r'[A-Za-z0-9/_-]{1,180}', route):
                raise ValueError('RSSHub requires an explicit route')
            url = url.rstrip('/') + '/' + route
        elif key == 'osrm':
            lat, lon = coordinates(args)
            endlat, endlon = coordinates({'latitude': args['to_latitude'], 'longitude': args['to_longitude']})
            url = url.rstrip('/') + f'/route/v1/driving/{lon},{lat};{endlon},{endlat}'
            params = {'overview': 'false'}
        elif key == 'opentripplanner':
            lat, lon = coordinates(args)
            elat, elon = coordinates({'latitude': args['to_latitude'], 'longitude': args['to_longitude']})
            url = url.rstrip('/') + '/otp/routers/default/plan'
            params = {'fromPlace': f'{lat},{lon}', 'toPlace': f'{elat},{elon}', 'numItineraries': 2}
    if provider.requirement == 'contact' and not options.get('contact'):
        raise ValueError('Configure realtime.contact with your application contact for this provider')
    if provider.requirement == 'free-key':
        token=countries_key(credential_base)
        if token:
            headers['Authorization']='Bearer '+token
        else:
            # Keyless: the World Bank country list (name, capital, region, income level, coordinates).
            if not identity: raise ValueError('Country name required')
            return 'https://api.worldbank.org/v2/country', {'format': 'json', 'per_page': 400}, headers, None
    if key in {'weather', 'air', 'marine', 'flood', 'met', 'nws', 'sunrise', 'power', 'adsblol', 'overpass'}:
        lat, lon = coordinates(args)
        if key == 'met': params = {'lat': round(lat, 4), 'lon': round(lon, 4)}
        elif key == 'nws':
            if not (18 <= lat <= 72 and -180 <= lon <= -60):
                raise ValueError('NWS covers US territories; no coverage is inferred elsewhere')
            params = {'point': f'{lat:.4f},{lon:.4f}'}
        elif key == 'sunrise': params = {'lat': lat, 'lng': lon, 'formatted': 0}
        elif key == 'adsblol': url += f'{lat}/{lon}/50'
        elif key == 'overpass':
            params = {'data': f'[out:json][timeout:10];nwr(around:1500,{lat},{lon})[amenity];out center 15;'}
        else:
            params = {'latitude': round(lat, 4), 'longitude': round(lon, 4)}
            if key == 'weather':
                params.update(current='temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m',
                    hourly='temperature_2m,precipitation,wind_speed_10m', forecast_days=1, timezone='auto', temperature_unit='celsius', wind_speed_unit='kmh')
            elif key == 'air': params.update(current='us_aqi,pm2_5,pm10', forecast_days=1)
            elif key == 'marine': params.update(current='wave_height,sea_surface_temperature', forecast_days=1)
            elif key == 'flood': params.update(daily='river_discharge', forecast_days=3)
            else:
                day = (datetime.now(timezone.utc)-timedelta(days=3)).strftime('%Y%m%d')
                params.update(parameters='T2M,PRECTOTCORR', community='RE', start=day, end=day, format='JSON')
    if key == 'gdelt': params = {'query': q or 'weather disaster', 'mode': 'artlist', 'format': 'json', 'maxrecords': 10, 'timespan': '1d'}
    elif key == 'google_news': params = {'q': q or 'world', 'hl': 'en', 'gl': 'IN', 'ceid': 'IN:en'}
    elif key == 'bluesky': params = {'q': q or 'news', 'limit': 10, 'sort': 'latest'}
    elif key == 'jetstream': params = {'wantedCollections': 'app.bsky.feed.post'}
    elif key == 'wikipedia':
        if not identity: raise ValueError('Wikipedia requires a page title')
        url += quote(identity.replace(' ', '_'), safe='')
    elif key == 'mediawiki': params = {'action': 'query', 'list': 'search', 'srsearch': q, 'srlimit': 5, 'format': 'json'}
    elif key == 'wikidata':
        if not re.fullmatch(r'Q[1-9][0-9]*', identity): raise ValueError('Wikidata REST requires an item ID such as Q42')
        url += identity
    elif key in {'wikidata_query', 'dbpedia'}:
        literal = json.dumps(q, ensure_ascii=False)
        query = 'SELECT ?item WHERE { ?item <http://www.w3.org/2000/01/rdf-schema#label> '+literal+'@en . } LIMIT 5'
        params = {'query': query, 'format': 'json'}; headers['Accept'] = 'application/sparql-results+json'
    elif key == 'openalex': params = {'search': q, 'per-page': 5}
    elif key == 'crossref': params = {'query': q, 'rows': 5}
    elif key == 'semantic_scholar': params = {'query': q, 'limit': 5, 'fields': 'title,year,url,abstract'}
    elif key == 'arxiv': params = {'search_query': 'all:'+q, 'max_results': 5, 'sortBy': 'submittedDate', 'sortOrder': 'descending'}
    elif key == 'europe_pmc': params = {'query': q, 'format': 'json', 'pageSize': 5}
    elif key == 'open_library': params = {'q': q, 'limit': 5}
    elif key == 'stack_exchange': params = {'q': q, 'site': 'stackoverflow', 'pagesize': 5}
    elif key == 'datamuse': params = {'ml': q, 'max': 10}
    elif key == 'dictionary':
        if not re.fullmatch(r'[A-Za-z-]{1,60}', identity): raise ValueError('Dictionary requires one word')
        url += quote(identity, safe='')
    elif key == 'internet_archive': params = {'q': q, 'output': 'json', 'rows': 5, 'fl[]': ['identifier', 'title', 'date']}
    elif key == 'nominatim': params = {'q': q, 'format': 'jsonv2', 'limit': 3}
    elif key == 'geocoding': params = {'name': q, 'count': 3, 'language': 'en', 'format': 'json'}
    elif key == 'ipify': params = {'format': 'json'}
    elif key == 'worldtime': url += quote(str(args.get('timezone', 'Asia/Kolkata')), safe='/')
    elif key == 'timeapi': params = {'timeZone': str(args.get('timezone', 'Asia/Kolkata'))}
    elif key == 'postcodes':
        country = str(args.get('country', 'IN')).upper()
        if not re.fullmatch(r'[A-Z]{2}', country) or not re.fullmatch(r'[A-Za-z0-9 -]{1,15}', identity): raise ValueError('Postcode and two-letter country required')
        url += country.lower()+'/'+quote(identity, safe='')
    elif key == 'countries':
        if not identity: raise ValueError('Country name required')
        params = {'q': identity, 'limit': 5}
    elif key == 'binance': params = {'symbol': symbol.replace('-', '').replace('/', '')}
    elif key == 'binance_stream': url += symbol.replace('-', '').replace('/', '').lower()+'@ticker'
    elif key == 'coinbase': url += quote(symbol, safe='')+'/ticker'
    elif key == 'coinbase_stream': subscription = {'type': 'subscribe', 'product_ids': [symbol], 'channels': ['ticker']}
    elif key == 'kraken': params = {'pair': symbol.replace('-', '').replace('/', '')}
    elif key == 'kraken_stream': subscription = {'method': 'subscribe', 'params': {'channel': 'ticker', 'symbol': [symbol.replace('-', '/')], 'snapshot': True}}
    elif key == 'coinpaprika': url += quote(identity or 'btc-bitcoin', safe='')
    elif key == 'defillama':
        protocol = identity or 'aave'
        if not re.fullmatch(r'[A-Za-z0-9-]{1,80}', protocol): raise ValueError('DeFiLlama requires a protocol slug')
        url = 'https://api.llama.fi/tvl/' + protocol.lower()
    elif key == 'dexscreener': params = {'q': q or 'BTC'}
    elif key == 'geckoterminal': params = {'query': q or 'BTC', 'page': 1}
    elif key == 'frankfurter':
        base, target = str(args.get('base', 'USD')).upper(), str(args.get('target', 'INR')).upper()
        if not re.fullmatch('[A-Z]{3}', base) or not re.fullmatch('[A-Z]{3}', target): raise ValueError('Currency codes required')
        params = {'base': base, 'symbols': target}
    elif key == 'ecb': params = {'lastNObservations': 1, 'format': 'csvdata'}
    elif key == 'worldbank': params = {'format': 'json', 'per_page': 5, 'mrnev': 1}
    elif key == 'opensky':
        lat, lon = coordinates(args)
        params = {'lamin': max(-90, lat-1), 'lamax': min(90, lat+1), 'lomin': max(-180, lon-1), 'lomax': min(180, lon+1)}
    elif key == 'mbta': params = {'page[limit]': 5}
    elif key == 'spacex': params = {'limit': 5, 'mode': 'list', **({'search': q} if q and q != 'climate' else {})}
    elif key == 'eonet': params = {'status': 'open', 'days': 7, 'limit': 30}
    elif key == 'celestrak': params = {'GROUP': 'stations', 'FORMAT': 'json'}
    elif key == 'spaceflight_news': params = {'limit': 5, **({'search': q} if q else {})}
    elif key == 'tvmaze': params = {'q': q}
    elif key == 'itunes': params = {'term': q, 'limit': 5}
    elif key == 'musicbrainz': params = {'query': q, 'fmt': 'json', 'limit': 5}
    elif key == 'listenbrainz':
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', identity): raise ValueError('ListenBrainz requires a public username')
        url += quote(identity, safe='')+'/listens'; params = {'count': 5}
    elif key == 'cover_art':
        if not re.fullmatch(r'[a-fA-F0-9-]{36}', identity): raise ValueError('Cover Art Archive requires a release MBID')
        url += identity
    elif key == 'food':
        if not re.fullmatch(r'[0-9]{8,14}', identity): raise ValueError('Open Food Facts requires a barcode')
        url += identity+'.json'; params = {'fields': 'code,product_name,nutriments,allergens,nutriscore_grade'}
    elif key == 'gbif': params = {'q': q, 'limit': 5}
    elif key == 'inaturalist': params = {'q': q, 'per_page': 5}
    return url, params, headers, subscription


def compact(data, depth=0, limit=10):
    if depth > 7: return '[nested data omitted]'
    if isinstance(data, list): return [compact(x, depth+1, limit) for x in data[:limit]]
    if isinstance(data, dict): return {str(k)[:100]: compact(v, depth+1, limit) for k, v in list(data.items())[:40]}
    if isinstance(data, str): return re.sub(r'<[^>]+>', '', data)[:1600]
    return data


def xml_data(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): raise ValueError('XML entities forbidden')
    root = ET.fromstring(raw)
    rows = []
    for node in root.iter():
        if node.tag.rsplit('}', 1)[-1] not in {'item', 'entry'}: continue
        row = {}
        for field in node:
            key = field.tag.rsplit('}', 1)[-1]
            value = ' '.join(''.join(field.itertext()).split())[:1600]
            if key == 'link' and not value: value = field.attrib.get('href', '')
            row[key] = value
            if key == 'Point':
                for coordinate in field:
                    name=coordinate.tag.rsplit('}',1)[-1]
                    if name in {'lat','long'}: row[name]=''.join(coordinate.itertext()).strip()
            elif key == 'point':
                parts=value.split()
                if len(parts)==2: row.update(lat=parts[0],long=parts[1])
        rows.append(row)
        if len(rows) >= 30: break
    return {'items': rows}


class Sources:
    def __init__(self, options=None, transport=None, clock=time.time, credential_base=None):
        self.options = options or {}
        self.http = transport or requests.Session()
        self.clock = clock
        self.credential_base = credential_base
        self.cache = OrderedDict()
        self.next = {}
        self.lock = threading.RLock()

    def fetch(self, key, args=None, cancelled=lambda: False):
        row = self._fetch(key, args, cancelled)
        backup = FALLBACK.get(key)
        if row.get('status') == 'unavailable' and backup and not cancelled():
            alternative = self._fetch(backup, args, cancelled)
            if alternative.get('status') == 'ok':
                return {**alternative, 'fallback_for': key,
                        'fallback_reason': row.get('detail', '') or 'primary provider unavailable'}
        return row

    def _fetch(self, key, args=None, cancelled=lambda: False):
        if key not in CATALOG: raise ValueError('Only registered green providers are allowed')
        args = args or {}
        if not isinstance(args, dict) or len(json.dumps(args)) > 2000: raise ValueError('Invalid bounded API arguments')
        provider = CATALOG[key]
        fingerprint = hashlib.sha256(json.dumps([key,args], sort_keys=True).encode()).hexdigest()
        now = self.clock()
        with self.lock:
            cached = self.cache.get(fingerprint)
            if cached and now-cached['fetched_at'] < provider.interval:
                return {**cached, 'cached': True}
            if now < self.next.get(key, 0):
                return {**cached, 'stale': True, 'status': 'rate_limited'} if cached else self.failure(provider, 'rate_limited')
            # Reserve before I/O; overlapping requests cannot exceed provider cadence.
            self.next[key] = now + provider.interval
        if cancelled(): return self.failure(provider, 'cancelled')
        try:
            url, params, headers, subscription = endpoint(provider, args, self.options, self.credential_base)
        except (ValueError,KeyError,TypeError) as exc:
            return self.failure(provider, 'needs_configuration', str(exc)[:220])
        try:
            headers = {'User-Agent': USER_AGENT + (' '+self.options['contact'] if self.options.get('contact') else ''), **headers}
            data, timestamp = self.read(provider, url, params, headers, subscription, cancelled)
            if cancelled(): return self.failure(provider, 'cancelled')
            if isinstance(data,dict) and (data.get('error') or data.get('errors') or data.get('success') is False or (provider.key=='food' and data.get('status')==0)):
                raise ValueError('Provider reports an error or no matching record')
            if provider.key == 'countries' and isinstance(data, list) and len(data) == 2 and isinstance(data[1], list):
                wanted = str(args.get('id', args.get('query', ''))).strip().casefold()
                data = [row for row in data[1] if isinstance(row, dict) and wanted and
                        (wanted == str(row.get('name', '')).casefold() or wanted in {str(row.get('iso2Code', '')).casefold(),
                                                                                      str(row.get('id', '')).casefold()})][:5]
                if not data: raise ValueError('No matching country')
            elif provider.key == 'countries':
                payload = data.get('data') if isinstance(data, dict) else None
                objects = payload.get('objects') if isinstance(payload, dict) else None
                if not isinstance(objects, list) or not all(isinstance(x, dict) for x in objects):
                    raise ValueError('Invalid Countries v5 objects envelope')
                data = objects[:5]
            if isinstance(data,dict):
                timestamp = data.get('time',data.get('timestamp',data.get('date_utc',data.get('date',timestamp))))
            row = {'provider': key, 'name': provider.name, 'status': 'ok', 'fetched_at': self.clock(),
                'fetched_utc':datetime.fromtimestamp(self.clock(),timezone.utc).isoformat(),
                'source_time': timestamp, 'url': public_url(url, provider.requirement in {'self-host', 'feed'}), 'reference': provider.docs, 'stale': False,
                'data_kind': 'forecast/model' if key in {'weather','air','marine','flood','met'} else 'daily/reference rate' if key in {'frankfurter','ecb'} else 'on-demand/reference or feed snapshot',
                'sample': provider.mode in {'sse','ws'}, 'data': compact(data, limit=30 if key in {'earthquakes','nws','eonet','gdacs','space_weather'} else 10)}
            # Bound the cache without cutting serialized JSON in the middle.
            if len(json.dumps(row)) > 24000: row['data'] = compact(row['data'], limit=3)
            with self.lock:
                self.cache[fingerprint] = row
                while len(self.cache) > 96: self.cache.popitem(last=False)
            return row
        except Exception as exc:
            if getattr(getattr(exc, 'response', None), 'status_code', None) == 404:
                # The service answered; it just has no record for this lookup (e.g. an unknown word).
                return self.failure(provider, 'not_found', 'No matching record')
            failure = self.failure(provider, 'unavailable', read_error(exc))
            if cached: failure.update(data=cached['data'], fetched_at=cached['fetched_at'], stale=True)
            return failure

    def _get(self, provider, url, params, headers, read_seconds, cancelled):
        """One GET, retried once after a dropped connection, a 5xx, or a 429 asking for at most 6 seconds."""
        for attempt in range(2):
            try:
                response = self.http.get(url, params=params, headers=headers, timeout=(3, read_seconds), stream=True,
                                         allow_redirects=False)
            except (requests.ConnectionError, requests.Timeout):
                if attempt or cancelled():
                    raise
                time.sleep(1)
                continue
            status = getattr(response, 'status_code', 200)
            if attempt == 0 and not cancelled() and isinstance(status, int):
                wait = None
                if status in {500, 502, 503, 504, 525}:
                    wait = 1.
                elif status == 429:
                    try:
                        asked = float((getattr(response, 'headers', {}) or {}).get('Retry-After', 'x'))
                    except (TypeError, ValueError):
                        asked = None
                    if asked is None and provider.key == 'gdelt':
                        asked = 5.5  # GDELT asks for one request every 5 seconds in its body.
                    if asked is not None and 0 <= asked <= 6:
                        wait = asked
                if wait is not None:
                    response.close()
                    time.sleep(wait)
                    continue
            return response
        return response

    def failure(self, provider, status, detail=''):
        return {'provider':provider.key, 'name':provider.name, 'status':status, 'detail':detail,
                'reference':provider.docs, 'stale':True, 'fetched_at':None}

    def read(self, provider, url, params, headers, subscription, cancelled):
        if provider.mode == 'ws':
            import websocket
            from urllib.parse import urlencode
            target = url + ('?'+urlencode(params) if params else '')
            connection = websocket.create_connection(target, timeout=5)
            try:
                if subscription: connection.send(json.dumps(subscription))
                samples, deadline = [], time.monotonic()+8
                while not cancelled() and time.monotonic() < deadline and len(samples) < 3:
                    try:
                        payload = connection.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if len(payload) > 64000: raise ValueError('Stream message exceeded limit')
                    message = json.loads(payload)
                    # Subscription acknowledgements and heartbeats aren't market data.
                    if isinstance(message, dict) and (message.get('type') in {'subscriptions','heartbeat'} or message.get('method') == 'subscribe' or message.get('channel') in {'status','heartbeat'}): continue
                    samples.append(message)
                if not samples: raise TimeoutError('No stream events received in bounded sample')
                return {'events':samples}, None
            finally: connection.close()
        # A few providers redirect official reads to canonical feed/data hosts.
        # Each hop is bounded and checked; arbitrary redirects are never followed.
        allowed = {
            'countries': {'api.restcountries.com', 'api.worldbank.org'},
            'cover_art': {'coverartarchive.org','archive.org'},
            'google_news': {'news.google.com'},
            'wikipedia': {'en.wikipedia.org'},
        }.get(provider.key, {urlsplit(url).hostname})
        response = None
        read_seconds = SLOW.get(provider.key, 5)
        for hop in range(3):
            response = self._get(provider, url, params, headers, read_seconds, cancelled)
            if response.status_code not in {301,302,303,307,308}: break
            target=urljoin(url,response.headers.get('Location','')); parsed=urlsplit(target)
            response.close()
            archive_host=provider.key=='cover_art' and (parsed.hostname or '').endswith('.archive.org')
            if cancelled() or parsed.scheme!='https' or (parsed.hostname not in allowed and not archive_host) or parsed.username or parsed.password:
                raise ValueError('Provider redirect target rejected')
            url,params=target,{}
        with response:
            if response.status_code == 429:
                try:
                    retry_after = float(response.headers.get('Retry-After', '300'))
                    if not math.isfinite(retry_after):
                        raise ValueError('Nonfinite Retry-After')
                except (TypeError, ValueError):
                    from email.utils import parsedate_to_datetime
                    try:
                        retry_after = parsedate_to_datetime(response.headers.get('Retry-After', '')).timestamp() - self.clock()
                    except (TypeError, ValueError, OverflowError):
                        retry_after = 300
                with self.lock:
                    self.next[provider.key] = self.clock()+max(provider.interval, min(3600, max(0, retry_after)))
            response.raise_for_status()
            if response.status_code != 200: raise ValueError('Unexpected response/redirect: '+str(response.status_code))
            raw, deadline = bytearray(), time.monotonic()+max(8, read_seconds+3)
            if provider.mode == 'sse':
                events = []
                for line in response.iter_lines(chunk_size=256):
                    if cancelled() or time.monotonic() > deadline: break
                    if line.startswith(b'data:'):
                        raw.extend(line)
                        if len(raw) > MAX_BYTES: raise ValueError('Stream exceeded limit')
                        events.append(json.loads(line[5:].strip()))
                    if len(events) >= 3: break
                if not events: raise TimeoutError('No events received in bounded sample')
                return {'events': events}, response.headers.get('Last-Modified')
            for chunk in response.iter_content(8192):
                if cancelled(): raise InterruptedError('Read cancelled')
                if time.monotonic() > deadline: raise TimeoutError('Public API read deadline')
                raw.extend(chunk)
                if len(raw) > MAX_BYTES: raise ValueError('Response exceeded 1 MiB')
            if provider.mode == 'xml': data = xml_data(bytes(raw))
            elif provider.mode == 'text': data = {'text':raw.decode('utf-8')[:6000]}
            else: data = json.loads(raw)
            if provider.key == 'hacker_news':
                stories = []
                for identity in data[:5]:
                    if cancelled() or time.monotonic()>deadline: break
                    with self.http.get(f'https://hacker-news.firebaseio.com/v0/item/{int(identity)}.json', timeout=(3,3)) as item:
                        item.raise_for_status(); stories.append(item.json())
                data = {'stories':stories}
            if provider.key == 'stack_exchange' and isinstance(data,dict) and data.get('backoff'):
                with self.lock: self.next[provider.key] = self.clock()+max(provider.interval, float(data['backoff']))
            return data, response.headers.get('Last-Modified')
