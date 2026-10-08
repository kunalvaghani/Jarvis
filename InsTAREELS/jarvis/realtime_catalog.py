"""Only the green services in the user's October 7 screenshots.

Access labels are the user's selection, not promises of uptime or timeliness.
No paid/key-only alternatives are silently substituted.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    category: str
    url: str
    docs: str
    interval: int = 60
    mode: str = 'json'
    requirement: str = ''


# key | name | category | endpoint | official reference | minimum interval | format | setup
_ROWS = '''
weather|Open-Meteo|weather|https://api.open-meteo.com/v1/forecast|https://open-meteo.com/en/docs|300|json|
air|Open-Meteo Air Quality|weather|https://air-quality-api.open-meteo.com/v1/air-quality|https://open-meteo.com/en/docs/air-quality-api|900|json|
marine|Open-Meteo Marine|weather|https://marine-api.open-meteo.com/v1/marine|https://open-meteo.com/en/docs/marine-weather-api|1800|json|
flood|Open-Meteo Flood|weather|https://flood-api.open-meteo.com/v1/flood|https://open-meteo.com/en/docs/flood-api|3600|json|
met|MET Norway|weather|https://api.met.no/weatherapi/locationforecast/2.0/compact|https://api.met.no/doc/TermsOfService|1800|json|contact
nws|US National Weather Service|weather|https://api.weather.gov/alerts/active|https://www.weather.gov/documentation/services-web-api|300|json|
earthquakes|USGS Earthquakes|weather|https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson|https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php|300|json|
space_weather|NOAA Space Weather|weather|https://services.swpc.noaa.gov/products/alerts.json|https://www.swpc.noaa.gov/products-and-data|900|json|
gdacs|GDACS|weather|https://www.gdacs.org/xml/rss.xml|https://www.gdacs.org/|900|xml|
gdelt|GDELT|news|https://api.gdeltproject.org/api/v2/doc/doc|https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/|900|json|
hacker_news|Hacker News|news|https://hacker-news.firebaseio.com/v0/topstories.json|https://github.com/HackerNews/API|300|json|
google_news|Google News RSS|news|https://news.google.com/rss/search|https://news.google.com/|900|xml|
bbc|BBC News RSS|news|https://feeds.bbci.co.uk/news/world/rss.xml|https://www.bbc.co.uk/news/10628494|900|xml|
bluesky|Bluesky Public API|news|https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts|https://docs.bsky.app/docs/api/app-bsky-feed-search-posts|60|json|
jetstream|Bluesky Jetstream|news|wss://jetstream2.us-east.bsky.network/subscribe|https://github.com/bluesky-social/jetstream|300|ws|
wikimedia_events|Wikimedia EventStreams|news|https://stream.wikimedia.org/v2/stream/recentchange|https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams|300|sse|
rsshub|RSSHub|news||https://docs.rsshub.app/deploy/|900|xml|self-host
searxng|SearXNG|knowledge||https://docs.searxng.org/dev/search_api.html|60|json|self-host
wikipedia|Wikipedia REST API|knowledge|https://en.wikipedia.org/api/rest_v1/page/summary/|https://www.mediawiki.org/wiki/REST_API|60|json|
mediawiki|MediaWiki API|knowledge|https://en.wikipedia.org/w/api.php|https://www.mediawiki.org/wiki/API:Main_page|60|json|
wikidata_query|Wikidata Query|knowledge|https://query.wikidata.org/sparql|https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service|60|json|
wikidata|Wikidata REST|knowledge|https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/|https://www.wikidata.org/wiki/Wikidata:REST_API|60|json|
openalex|OpenAlex|knowledge|https://api.openalex.org/works|https://help.openalex.org/api/authentication/|60|json|
crossref|Crossref|knowledge|https://api.crossref.org/works|https://www.crossref.org/documentation/retrieve-metadata/rest-api/|60|json|
semantic_scholar|Semantic Scholar|knowledge|https://api.semanticscholar.org/graph/v1/paper/search|https://api.semanticscholar.org/api-docs/|60|json|
arxiv|arXiv|knowledge|https://export.arxiv.org/api/query|https://info.arxiv.org/help/api/user-manual.html|60|xml|
europe_pmc|Europe PMC|knowledge|https://www.ebi.ac.uk/europepmc/webservices/rest/search|https://europepmc.org/RestfulWebService|60|json|
open_library|Open Library|knowledge|https://openlibrary.org/search.json|https://openlibrary.org/developers/api|60|json|
stack_exchange|Stack Exchange|knowledge|https://api.stackexchange.com/2.3/search/advanced|https://api.stackexchange.com/docs|60|json|
datamuse|Datamuse|knowledge|https://api.datamuse.com/words|https://www.datamuse.com/api/|60|json|
dictionary|Free Dictionary API|knowledge|https://api.dictionaryapi.dev/api/v2/entries/en/|https://dictionaryapi.dev/|60|json|
dbpedia|DBpedia|knowledge|https://dbpedia.org/sparql|https://www.dbpedia.org/resources/sparql/|60|json|
internet_archive|Internet Archive|knowledge|https://archive.org/advancedsearch.php|https://archive.org/developers/|60|json|
nominatim|OpenStreetMap Nominatim|maps|https://nominatim.openstreetmap.org/search|https://operations.osmfoundation.org/policies/nominatim/|2|json|
overpass|Overpass API|maps|https://overpass-api.de/api/interpreter|https://wiki.openstreetmap.org/wiki/Overpass_API|60|json|
geocoding|Open-Meteo Geocoding|maps|https://geocoding-api.open-meteo.com/v1/search|https://open-meteo.com/en/docs/geocoding-api|60|json|
osrm|OSRM|maps||https://project-osrm.org/docs/v5.24.0/api/|60|json|self-host
ipify|ipify|maps|https://api.ipify.org/|https://www.ipify.org/|3600|json|
ipwho|ipwho.is|maps|https://ipwho.is/|https://ipwhois.io/documentation|3600|json|
geojs|GeoJS|maps|https://get.geojs.io/v1/ip/geo.json|https://www.geojs.io/docs/v1/endpoints/geo/|3600|json|
worldtime|WorldTimeAPI|maps|https://worldtimeapi.org/api/timezone/|https://worldtimeapi.org/|300|json|
timeapi|TimeAPI.io|maps|https://timeapi.io/api/time/current/zone|https://timeapi.io/swagger/index.html|300|json|
sunrise|Sunrise-Sunset|maps|https://api.sunrise-sunset.org/json|https://sunrise-sunset.org/api|3600|json|
postcodes|Zippopotam.us|maps|https://api.zippopotam.us/|https://www.zippopotam.us/|3600|json|
countries|REST Countries|maps|https://api.restcountries.com/countries/v5/names.common|https://restcountries.com/docs/countries|86400|json|free-key
binance|Binance REST|finance|https://api.binance.com/api/v3/ticker/price|https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints|60|json|
binance_stream|Binance WebSocket|finance|wss://stream.binance.com:9443/ws/|https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams|60|ws|
coinbase|Coinbase Exchange REST|finance|https://api.exchange.coinbase.com/products/|https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductticker|60|json|
coinbase_stream|Coinbase WebSocket|finance|wss://ws-feed.exchange.coinbase.com|https://docs.cdp.coinbase.com/exchange/websocket-feed/overview|60|ws|
kraken|Kraken REST|finance|https://api.kraken.com/0/public/Ticker|https://docs.kraken.com/api/docs/rest-api/get-ticker-information|60|json|
kraken_stream|Kraken WebSocket|finance|wss://ws.kraken.com/v2|https://docs.kraken.com/api/docs/websocket-v2/ticker|60|ws|
coinpaprika|CoinPaprika|finance|https://api.coinpaprika.com/v1/tickers/|https://docs.coinpaprika.com/|300|json|
dexscreener|DexScreener|finance|https://api.dexscreener.com/latest/dex/search|https://docs.dexscreener.com/api/reference|60|json|
defillama|DeFiLlama|finance|https://api.llama.fi/protocols|https://api-docs.defillama.com/|300|json|
geckoterminal|GeckoTerminal|finance|https://api.geckoterminal.com/api/v2/search/pools|https://apiguide.geckoterminal.com/|60|json|
frankfurter|Frankfurter|finance|https://api.frankfurter.dev/v1/latest|https://frankfurter.dev/|3600|json|
ecb|ECB Data|finance|https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A|https://data.ecb.europa.eu/help/api/overview|3600|text|
worldbank|World Bank API|finance|https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD|https://datahelpdesk.worldbank.org/knowledgebase/topics/125589|86400|json|
opensky|OpenSky Network|transport|https://opensky-network.org/api/states/all|https://openskynetwork.github.io/opensky-api/rest.html|900|json|
adsblol|ADSB.lol|transport|https://api.adsb.lol/v2/point/|https://api.adsb.lol/|60|json|
tfl|TfL Unified API|transport|https://api.tfl.gov.uk/Line/Mode/tube/Status|https://api.tfl.gov.uk/|300|json|
mbta|MBTA|transport|https://api-v3.mbta.com/alerts|https://www.mbta.com/developers/v3-api|300|json|
gbfs|GBFS|transport||https://gbfs.org/|60|json|feed
opentripplanner|OpenTripPlanner|transport||https://docs.opentripplanner.org/en/latest/|60|json|self-host
jolpica|Jolpica F1|transport|https://api.jolpi.ca/ergast/f1/current/last/results.json|https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md|3600|json|
openligadb|OpenLigaDB|transport|https://api.openligadb.de/getmatchdata/bl1|https://www.openligadb.de/|300|json|
eonet|NASA EONET|space|https://eonet.gsfc.nasa.gov/api/v3/events|https://eonet.gsfc.nasa.gov/docs/v3|1800|json|
epic|NASA EPIC|space|https://epic.gsfc.nasa.gov/api/natural|https://epic.gsfc.nasa.gov/about/api|3600|json|
power|NASA POWER|space|https://power.larc.nasa.gov/api/temporal/daily/point|https://power.larc.nasa.gov/docs/services/api/|86400|json|
open_notify|Open Notify ISS|space|http://api.open-notify.org/iss-now.json|http://open-notify.org/Open-Notify-API/|60|json|
whereiss|WhereTheISS|space|https://api.wheretheiss.at/v1/satellites/25544|https://wheretheiss.at/w/developer|60|json|
celestrak|CelesTrak|space|https://celestrak.org/NORAD/elements/gp.php|https://celestrak.org/NORAD/documentation/gp-data-formats.php|7200|json|
spaceflight_news|Spaceflight News|space|https://api.spaceflightnewsapi.net/v4/articles/|https://api.spaceflightnewsapi.net/v4/docs/|900|json|
spacex|SpaceX API|space|https://api.spacexdata.com/v4/launches/latest|https://github.com/r-spacex/SpaceX-API|3600|json|
tvmaze|TVmaze|media|https://api.tvmaze.com/search/shows|https://www.tvmaze.com/api|300|json|
itunes|iTunes Search|media|https://itunes.apple.com/search|https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/|300|json|
musicbrainz|MusicBrainz|media|https://musicbrainz.org/ws/2/artist/|https://musicbrainz.org/doc/MusicBrainz_API|2|json|contact
listenbrainz|ListenBrainz|media|https://api.listenbrainz.org/1/user/|https://listenbrainz.readthedocs.io/en/latest/users/api/|60|json|
cover_art|Cover Art Archive|media|https://coverartarchive.org/release/|https://musicbrainz.org/doc/Cover_Art_Archive/API|300|json|
food|Open Food Facts|media|https://world.openfoodfacts.org/api/v2/product/|https://openfoodfacts.github.io/openfoodfacts-server/api/|300|json|
gbif|GBIF|media|https://api.gbif.org/v1/occurrence/search|https://techdocs.gbif.org/en/openapi/|300|json|
inaturalist|iNaturalist|media|https://api.inaturalist.org/v1/observations|https://api.inaturalist.org/v1/docs/|300|json|
'''

CATALOG = {}
for _line in _ROWS.strip().splitlines():
    _key, _name, _category, _url, _docs, _interval, _mode, _need = _line.split('|')
    CATALOG[_key] = Provider(_key, _name, _category, _url, _docs, int(_interval), _mode, _need)

BACKGROUND = ('weather', 'air', 'nws', 'earthquakes', 'gdacs', 'space_weather', 'eonet')
