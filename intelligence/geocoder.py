"""
Geocoder — uses Nominatim (OpenStreetMap) which is 100% free, no key needed.
Rate-limited to 1 req/sec per OSM policy.
"""
import time
import re
import requests
from config import Config

_cache = {}   # in-memory cache: query → (lat, lng)
_last_req = 0.0

# Known city centres as fallback seeds when we can't geocode a specific address
CITY_CENTRES = {
    'miami':         (25.7617,  -80.1918),
    'broward':       (26.1901,  -80.3659),
    'fort lauderdale': (26.1901,  -80.3659),
    'newyork':       (40.7128,  -74.0060),
    'new york':       (40.7128,  -74.0060),
    'losangeles':    (34.0522, -118.2437),
    'los angeles':    (34.0522, -118.2437),
    'chicago':       (41.8781,  -87.6298),
    'houston':       (29.7604,  -95.3698),
    'phoenix':       (33.4484, -112.0740),
    'philadelphia':  (39.9526,  -75.1652),
    'sandiego':      (32.7157, -117.1611),
    'san diego':      (32.7157, -117.1611),
    'dallas':        (32.7767,  -96.7970),
    'austin':        (30.2672,  -97.7431),
    'seattle':       (47.6062, -122.3321),
    'denver':        (39.7392, -104.9903),
    'boston':        (42.3601,  -71.0589),
    'atlanta':       (33.7490,  -84.3880),
    'nashville':     (36.1627,  -86.7816),
    'portland':      (45.5051, -122.6750),
    'lasvegas':      (36.1699, -115.1398),
    'las vegas':      (36.1699, -115.1398),
    'orlando':       (28.5383,  -81.3792),
    'tampa':         (27.9506,  -82.4572),
    'jacksonville':  (30.3322,  -81.6557),
    'charlotte':     (35.2271,  -80.8431),
    'raleigh':       (35.7796,  -78.6382),
    'minneapolis':   (44.9778,  -93.2650),
    'stlouis':       (38.6270,  -90.1994),
    'st louis':       (38.6270,  -90.1994),
    'pittsburgh':    (40.4406,  -79.9959),
    'cleveland':     (41.4993,  -81.6944),
    'columbus':      (39.9612,  -82.9988),
    'indianapolis':  (39.7684,  -86.1581),
    'sanantonio':    (29.4241,  -98.4936),
    'san antonio':    (29.4241,  -98.4936),
}


def _throttle():
    global _last_req
    elapsed = time.time() - _last_req
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _last_req = time.time()


def geocode(location_str: str, city: str = '') -> tuple:
    """Return (lat, lng) or None."""
    if not location_str:
        return _city_fallback(city)

    # Clean up location
    query = re.sub(r'\s+', ' ', location_str.strip())
    if city and city.lower() not in query.lower():
        query = f"{query}, {city}"

    cache_key = query.lower()
    if cache_key in _cache:
        return _cache[cache_key]

    _throttle()
    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': query, 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'TradeDistrict/1.0 (local research tool)'},
            timeout=8
        )
        data = resp.json()
        if data:
            result = (float(data[0]['lat']), float(data[0]['lon']))
            _cache[cache_key] = result
            return result
    except Exception:
        pass

    # Fallback: try just the city
    result = _city_fallback(city)
    if result:
        _cache[cache_key] = result
    return result


def _city_fallback(city: str):
    if not city:
        return None
    # Try display name first, then stripped key
    lower = city.lower()
    return CITY_CENTRES.get(lower) or CITY_CENTRES.get(lower.replace(' ', ''))


def geocode_opportunity(opp: dict) -> tuple:
    """Best-effort geocode from whatever location data the opp has."""
    loc = opp.get('location') or ''
    city = opp.get('city') or ''
    # Already has coords?
    if opp.get('lat') and opp.get('lng'):
        return opp['lat'], opp['lng']
    if loc:
        result = geocode(loc, city)
        if result:
            return result
    return _city_fallback(city)
