# Green public APIs, idle reader and serious alerts

Jarvis has **82 adapters**, matching only the green rows in the supplied
2026-10-07 screenshots. Blue/orange services are excluded. Screenshots select
the services; their old access labels are not proof of current availability.
Jarvis does not create provider accounts, start heavy self-hosted services,
subscribe to paid plans or substitute another provider without configuration.

## Questions and tasks

Relevant questions fetch at most two selected sources, reuse timestamped cached
data within provider cadence and pass bounded evidence to the question model.
This path precedes the older quick-weather answer and search fallback. Task
planning receives relevant cached evidence with freshness labels; the task tool
fetches precise observations when needed, without sending an entire private
task description to a news/search service. The `realtime_query` tool supports every
registered provider, exact arguments and a `catalog` read. All calls are reads;
no trading, posting, account changes or desktop actions result from feed content.

Examples:

- `What is the weather here?` uses approximate IP location when available.
- `Weather in Paris, France` disambiguates the city/country; unresolved locations
  ask for clarification instead of selecting a home city.
- `Weather at 40.7, -74.0` uses those exact requested coordinates.
- `Free Dictionary API: hello`, `Wikipedia REST API: Earth`,
  `Wikidata REST: Q42` and `Open Food Facts: 3017620422003` use exact operands.
- `USD to INR exchange rate` uses reference rates, clearly marked as daily data.
- In a task, `realtime_query` uses `value=catalog` first, then a provider ID and
  `content` containing JSON arguments such as `query`, `id`, `symbol`,
  `latitude`, `longitude`, `timezone`, `base`, `target`, `country` or `route`.

API records are untrusted evidence, never instructions or authorization. Answers
receive provider URLs, retrieval times, available source times, data type,
location accuracy and stale/unavailable status. A fresh retrieval does not imply
the underlying observation is current. Forecasts, research metadata, country
facts and daily exchange rates are not second-by-second feeds. Streams provide
short samples, with the connection closed afterward; they do not ingest the
complete global firehose.

## Background behavior and resources

The monitor polls seven relevant hazard sources: Open-Meteo weather/air, NWS,
USGS, GDACS, NOAA space weather and EONET. Other APIs run on demand. Background
reads wait for 60 seconds of idle time, yield to questions/tasks/dictation/speech
and screen work, and honor Stop listening, Stop all tasks, pause and Quit.
The service has registered health checks and bounded silent recovery. Stop all
tasks cancels the current cycle; it may run again after the idle interval.
`pause realtime` remains paused until resumed. Stop listening pauses background
monitoring until listening is deliberately started again.

The separate **Qwen2.5 0.5B** reader reviews changed source excerpts at most
once per ten minutes. It uses CPU by default, one thread, a 1,024-token context,
64 output tokens and `keep_alive=0` to unload afterward. October 8's
[GPU coordinator](gpu-priority.md) permits optional idle helper offload; the
default remains CPU after the measured cold-load comparison. It runs only with at
least 4 GB available RAM, CPU utilization at most 35%, an installed model under
600 MB and **no loaded Ollama model**. It never unloads a foreground model or
falls back to the large coding model. Missing/slow models leave raw evidence
and deterministic hazard checks usable. Setup/model recovery declare this small
model when enabled; its installed download is approximately 398 MB.

Zero resource use is impossible: inference temporarily uses RAM and CPU. These
are best-effort limits; a task arriving after inference starts can briefly share
the backend until cancellation/completion. The reader checks cancellation during
streaming and a 12-second processing budget, with bounded socket waits. Idle
summaries are schema-bound routine/review/insufficient-evidence labels, not the
evidence used to decide alerts. The schema keeps tiny-model output bounded and
prevents unsupported fields or invented narratives. The API
cache holds at most 96 bounded records; responses have a 1 MiB limit, individual
cached projections are bounded, and raw global streams are not retained.

## Serious alerts and location

Fresh structured evidence gates alerts independently of the model:

- USGS: magnitude at least 6 within 250 km, issued within the last hour.
- NWS: Severe/Extreme, Immediate/Expected, unexpired, recently issued warning
  returned for the requested US point.
- GDACS: red event with published coordinates within 300 km and a recent date.
- NOAA: a recent G4/G5, S4/S5 or R4/R5 bulletin.
- Open-Meteo: modelled wind at least 90 km/h, temperature at least 45°C or
  modelled US AQI at least 301. These are explicitly model-data notices with a
  request to check local official advice, not invented official warnings.

Malformed/stale data, distant events, unknown location and ordinary headlines,
social posts, market prices and EONET event listings cannot become serious
alerts. The LLM cannot raise an alert. Duplicate IDs/times are checkpointed before
notification, so interruption does not replay spoken alerts. Failed checkpoint
writes stop monitoring instead of retrying an uncertain notification. Notifications
use the existing island/transcript and optional speech; they do not interrupt
active work with a modal popup.

Location defaults to approximate IP lookup, refreshed hourly with GeoJS fallback.
VPNs/carrier networks can move the estimate. Stale/unknown estimates suppress
location-dependent monitoring. **This is not GPS tracking, complete worldwide
awareness or an emergency warning service.** Provider coverage and bounded feed
samples can miss events. Use official local warnings for safety decisions.
The old Vadodara weather fallback is not used for this monitor.

Say `realtime status`, `pause realtime`, `resume realtime`,
`set realtime location 22.3, 73.2` or `use current realtime location`.
Location commands apply to the current session. To persist an explicit location,
set `realtime.location` to a latitude/longitude object in `config.json`.
IP estimates and public API payloads stay in RAM; the private alert checkpoint
stores only notified IDs and times, not a travel log.

## Setup and provider limitations

Restart using Stop/Start Jarvis. The new dependency is
`websocket-client>=1.8,<2`, declared in requirements and the runtime manifest.
Normal setup installs it. The reader uses the existing Ollama server and
`qwen2.5:0.5b`; no paid model API is involved.

`config.json` contains a `realtime` object. Monitoring, alerts, reader, auto
location, CPU/RAM limits and intervals are configurable. `contact` is the
verified Jarvis project URL, identifying calls to MET Norway and MusicBrainz.
No credentials are embedded in this URL.

Five services require a configured `realtime.endpoints` entry: `searxng`,
`rsshub`, `osrm`, `opentripplanner` and `gbfs`. The first four require your own
server; GBFS requires a public feed for the relevant bike/scooter network.
Their adapters are available, but no endpoint or dataset is invented. SearXNG
must enable JSON responses; RSSHub additionally needs an exact route. OSRM uses
the route API; OpenTripPlanner's adapter targets the legacy REST router/plan
interface, so the configured server must expose that interface. These services
are not automatically installed, avoiding their substantial background cost.

REST Countries changed after the screenshot: keyless v3 was retired and v5
requires authentication. Its adapter accepts a **free-plan** key in ignored local
`secrets/realtime.json` under `countries_api_key`, or
`JARVIS_REALTIME_COUNTRIES_KEY` in the process environment (takes priority).
Keep credentials out of `config.json`, README files and GitHub. No account is
created, paid features requested or key stored in URLs/receipts.
[Official migration and access rules](https://restcountries.com/docs/countries/api-versions).
The production repair uses the documented property-query path and `data.objects`
envelope; its public demo read, credential privacy tests and fresh provider
results are in [production validation](production-validation.md).

Open-Meteo's hosted free APIs are for non-commercial use and have usage limits,
not an uptime guarantee. [Official free tier](https://open-meteo.com/en/pricing).
Nominatim calls are explicit user lookups, cached and limited to at most one
request per two seconds; no autocomplete, periodic geocoding or systematic
downloads. It attributes OpenStreetMap via the source/reference URL and accepts
only the deliberately selected personal lookup use.
[Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/).
MET identifies the application and avoids unnecessary traffic.
[MET terms](https://api.met.no/doc/TermsOfService).
Queries respect provider cadence and HTTP 429/Stack Exchange backoff. Canonical
redirects are bounded and restricted to provider hosts; TLS verification stays on.

NWS, TfL, MBTA, GBFS and OpenLigaDB have regional/dataset limits. Marine/flood
models may lack data inland or away from modelled rivers. Crypto services can be
region-restricted; free reference data do not include universal live stock quotes.
Public streams, API outages, authentication changes and rate limits are reported
honestly. Open Notify supplies its public observations over HTTP. No account
credentials or private recordings are submitted to these public providers.

## Verification, 2026-10-07 IST

Fresh regression/readiness and live provider results are recorded separately:

The final full regression passed **1,117 tests in 143.861 seconds**, including
the **50 focused realtime tests** (also run independently in **0.305 seconds**).
Launcher readiness returned `ready` with no missing requirements.
An actual foreground question-model answer matched a live Frankfurter record's
rate, observation date and provider attribution. This verifies the question path;
it does not establish that every provider or every possible question works.

The final live probe made bounded reads against all **82** registered adapters:
**68 succeeded**, **8 were unavailable/rate-limited**, and **6 required setup**.
The six are the five configured service/feed endpoints and REST Countries' free
v5 key. Provider outages are not hidden by switching to blue/orange services.
The actual idle small reader processed live weather and NOAA excerpts successfully
in **5.968 seconds**; the final provider-verification run also completed an
actual reader assessment in **6.484 seconds**. A subsequent `/api/ps` read returned
no resident models. Earlier cold/input-heavy and incomplete-JSON attempts are
preserved rather than presented as successes.

- [Live provider probes](../artifacts/realtime-live-check.json) and
  [earlier attempts](../artifacts/realtime-live-history.json) distinguish successful
  reads, configuration needs, outages and rate limits. They do not claim all 82
  endpoints currently work or that their data is equally fresh.
- [Idle reader evidence](../artifacts/realtime-reader-check.json) records the
  actual small-model result independently of simulated alert tests;
  [reader history](../artifacts/realtime-reader-history.json) preserves the
  earlier incomplete-output attempt.
- [Regression/readiness receipt](../artifacts/realtime-regression-check.json)
  records the final full suite, focused integration checks and launcher status.
- [Actual question evidence](../artifacts/realtime-question-check.json) records
  the foreground answer using a fetched reference-rate observation.

Regression tests exercise provider construction, exact green exclusions,
canonical/hostile redirects, size bounds, malformed XML/JSON, rate limits,
stream closure, freshness/location/seriousness negatives, model resource
deferral, cancellation, duplicate checkpointing, uncertain writes, model failure,
task-tool routing and source-bound answers. Self-hosted adapter tests use labelled
fixtures, not live server claims. Synthetic hazards never notify the real user.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_realtime.py -q
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m jarvis.launcher --check
.\.venv\Scripts\python.exe verify_realtime.py
```

## Green provider inventory

Intervals are minimum client cadences, not promises about provider updates.
`json`/`xml`/`text` are bounded reads; `sse`/`ws` are short stream samples.

| ID | Selected API | Category | Minimum seconds | Format | Setup |
|---|---|---|---:|---|---|
| `weather` | [Open-Meteo](https://open-meteo.com/en/docs) | weather | 300 | json | none |
| `air` | [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api) | weather | 900 | json | none |
| `marine` | [Open-Meteo Marine](https://open-meteo.com/en/docs/marine-weather-api) | weather | 1800 | json | none |
| `flood` | [Open-Meteo Flood](https://open-meteo.com/en/docs/flood-api) | weather | 3600 | json | none |
| `met` | [MET Norway](https://api.met.no/doc/TermsOfService) | weather | 1800 | json | contact |
| `nws` | [US National Weather Service](https://www.weather.gov/documentation/services-web-api) | weather | 300 | json | none |
| `earthquakes` | [USGS Earthquakes](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php) | weather | 300 | json | none |
| `space_weather` | [NOAA Space Weather](https://www.swpc.noaa.gov/products-and-data) | weather | 900 | json | none |
| `gdacs` | [GDACS](https://www.gdacs.org/) | weather | 900 | xml | none |
| `gdelt` | [GDELT](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) | news | 900 | json | none |
| `hacker_news` | [Hacker News](https://github.com/HackerNews/API) | news | 300 | json | none |
| `google_news` | [Google News RSS](https://news.google.com/) | news | 900 | xml | none |
| `bbc` | [BBC News RSS](https://www.bbc.co.uk/news/10628494) | news | 900 | xml | none |
| `bluesky` | [Bluesky Public API](https://docs.bsky.app/docs/api/app-bsky-feed-search-posts) | news | 60 | json | none |
| `jetstream` | [Bluesky Jetstream](https://github.com/bluesky-social/jetstream) | news | 300 | ws | none |
| `wikimedia_events` | [Wikimedia EventStreams](https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams) | news | 300 | sse | none |
| `rsshub` | [RSSHub](https://docs.rsshub.app/deploy/) | news | 900 | xml | self-host |
| `searxng` | [SearXNG](https://docs.searxng.org/dev/search_api.html) | knowledge | 60 | json | self-host |
| `wikipedia` | [Wikipedia REST API](https://www.mediawiki.org/wiki/REST_API) | knowledge | 60 | json | none |
| `mediawiki` | [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page) | knowledge | 60 | json | none |
| `wikidata_query` | [Wikidata Query](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service) | knowledge | 60 | json | none |
| `wikidata` | [Wikidata REST](https://www.wikidata.org/wiki/Wikidata:REST_API) | knowledge | 60 | json | none |
| `openalex` | [OpenAlex](https://help.openalex.org/api/authentication/) | knowledge | 60 | json | none |
| `crossref` | [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) | knowledge | 60 | json | none |
| `semantic_scholar` | [Semantic Scholar](https://api.semanticscholar.org/api-docs/) | knowledge | 60 | json | none |
| `arxiv` | [arXiv](https://info.arxiv.org/help/api/user-manual.html) | knowledge | 60 | xml | none |
| `europe_pmc` | [Europe PMC](https://europepmc.org/RestfulWebService) | knowledge | 60 | json | none |
| `open_library` | [Open Library](https://openlibrary.org/developers/api) | knowledge | 60 | json | none |
| `stack_exchange` | [Stack Exchange](https://api.stackexchange.com/docs) | knowledge | 60 | json | none |
| `datamuse` | [Datamuse](https://www.datamuse.com/api/) | knowledge | 60 | json | none |
| `dictionary` | [Free Dictionary API](https://dictionaryapi.dev/) | knowledge | 60 | json | none |
| `dbpedia` | [DBpedia](https://www.dbpedia.org/resources/sparql/) | knowledge | 60 | json | none |
| `internet_archive` | [Internet Archive](https://archive.org/developers/) | knowledge | 60 | json | none |
| `nominatim` | [OpenStreetMap Nominatim](https://operations.osmfoundation.org/policies/nominatim/) | maps | 2 | json | none |
| `overpass` | [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) | maps | 60 | json | none |
| `geocoding` | [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api) | maps | 60 | json | none |
| `osrm` | [OSRM](https://project-osrm.org/docs/v5.24.0/api/) | maps | 60 | json | self-host |
| `ipify` | [ipify](https://www.ipify.org/) | maps | 3600 | json | none |
| `ipwho` | [ipwho.is](https://ipwhois.io/documentation) | maps | 3600 | json | none |
| `geojs` | [GeoJS](https://www.geojs.io/docs/v1/endpoints/geo/) | maps | 3600 | json | none |
| `worldtime` | [WorldTimeAPI](https://worldtimeapi.org/) | maps | 300 | json | none |
| `timeapi` | [TimeAPI.io](https://timeapi.io/swagger/index.html) | maps | 300 | json | none |
| `sunrise` | [Sunrise-Sunset](https://sunrise-sunset.org/api) | maps | 3600 | json | none |
| `postcodes` | [Zippopotam.us](https://www.zippopotam.us/) | maps | 3600 | json | none |
| `countries` | [REST Countries](https://restcountries.com/docs/countries/api-versions) | maps | 86400 | json | free-key |
| `binance` | [Binance REST](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints) | finance | 60 | json | none |
| `binance_stream` | [Binance WebSocket](https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams) | finance | 60 | ws | none |
| `coinbase` | [Coinbase Exchange REST](https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductticker) | finance | 60 | json | none |
| `coinbase_stream` | [Coinbase WebSocket](https://docs.cdp.coinbase.com/exchange/websocket-feed/overview) | finance | 60 | ws | none |
| `kraken` | [Kraken REST](https://docs.kraken.com/api/docs/rest-api/get-ticker-information) | finance | 60 | json | none |
| `kraken_stream` | [Kraken WebSocket](https://docs.kraken.com/api/docs/websocket-v2/ticker) | finance | 60 | ws | none |
| `coinpaprika` | [CoinPaprika](https://docs.coinpaprika.com/) | finance | 300 | json | none |
| `dexscreener` | [DexScreener](https://docs.dexscreener.com/api/reference) | finance | 60 | json | none |
| `defillama` | [DeFiLlama](https://api-docs.defillama.com/) | finance | 300 | json | none |
| `geckoterminal` | [GeckoTerminal](https://apiguide.geckoterminal.com/) | finance | 60 | json | none |
| `frankfurter` | [Frankfurter](https://frankfurter.dev/) | finance | 3600 | json | none |
| `ecb` | [ECB Data](https://data.ecb.europa.eu/help/api/overview) | finance | 3600 | text | none |
| `worldbank` | [World Bank API](https://datahelpdesk.worldbank.org/knowledgebase/topics/125589) | finance | 86400 | json | none |
| `opensky` | [OpenSky Network](https://openskynetwork.github.io/opensky-api/rest.html) | transport | 900 | json | none |
| `adsblol` | [ADSB.lol](https://api.adsb.lol/) | transport | 60 | json | none |
| `tfl` | [TfL Unified API](https://api.tfl.gov.uk/) | transport | 300 | json | none |
| `mbta` | [MBTA](https://www.mbta.com/developers/v3-api) | transport | 300 | json | none |
| `gbfs` | [GBFS](https://gbfs.org/) | transport | 60 | json | feed |
| `opentripplanner` | [OpenTripPlanner](https://docs.opentripplanner.org/en/latest/) | transport | 60 | json | self-host |
| `jolpica` | [Jolpica F1](https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md) | transport | 3600 | json | none |
| `openligadb` | [OpenLigaDB](https://www.openligadb.de/) | transport | 300 | json | none |
| `eonet` | [NASA EONET](https://eonet.gsfc.nasa.gov/docs/v3) | space | 1800 | json | none |
| `epic` | [NASA EPIC](https://epic.gsfc.nasa.gov/about/api) | space | 3600 | json | none |
| `power` | [NASA POWER](https://power.larc.nasa.gov/docs/services/api/) | space | 86400 | json | none |
| `open_notify` | [Open Notify ISS](http://open-notify.org/Open-Notify-API/) | space | 60 | json | none |
| `whereiss` | [WhereTheISS](https://wheretheiss.at/w/developer) | space | 60 | json | none |
| `celestrak` | [CelesTrak](https://celestrak.org/NORAD/documentation/gp-data-formats.php) | space | 7200 | json | none |
| `spaceflight_news` | [Spaceflight News](https://api.spaceflightnewsapi.net/v4/docs/) | space | 900 | json | none |
| `spacex` | [SpaceX API](https://github.com/r-spacex/SpaceX-API) | space | 3600 | json | none |
| `tvmaze` | [TVmaze](https://www.tvmaze.com/api) | media | 300 | json | none |
| `itunes` | [iTunes Search](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/) | media | 300 | json | none |
| `musicbrainz` | [MusicBrainz](https://musicbrainz.org/doc/MusicBrainz_API) | media | 2 | json | contact |
| `listenbrainz` | [ListenBrainz](https://listenbrainz.readthedocs.io/en/latest/users/api/) | media | 60 | json | none |
| `cover_art` | [Cover Art Archive](https://musicbrainz.org/doc/Cover_Art_Archive/API) | media | 300 | json | none |
| `food` | [Open Food Facts](https://openfoodfacts.github.io/openfoodfacts-server/api/) | media | 300 | json | none |
| `gbif` | [GBIF](https://techdocs.gbif.org/en/openapi/) | media | 300 | json | none |
| `inaturalist` | [iNaturalist](https://api.inaturalist.org/v1/docs/) | media | 300 | json | none |
