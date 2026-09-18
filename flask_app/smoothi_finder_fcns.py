import math
import os
import time
from threading import Lock

import requests

AZURE_SEARCH_URL = "https://atlas.microsoft.com/search/address/json"
AZURE_ROUTE_URL = "https://atlas.microsoft.com/route/directions/json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"
USER_AGENT = "SmoothieFinder/1.0 (local testing; contact: local)"

# In-memory caches to avoid repeat Azure/Nominatim/OSRM calls
_GEOCODE_CACHE_TTL_SEC = 24 * 60 * 60  # addresses rarely move
_ROUTE_CACHE_TTL_SEC = 15 * 60         # traffic can change
_CACHE_MAX_ENTRIES = 512


class _TtlCache:
    def __init__(self, ttl_seconds, maxsize=_CACHE_MAX_ENTRIES):
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._data = {}
        self._lock = Lock()

    def get(self, key):
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            value, expires = item
            if now > expires:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key, value):
        now = time.time()
        with self._lock:
            if len(self._data) >= self.maxsize:
                expired = [k for k, (_, exp) in self._data.items() if now > exp]
                for k in expired:
                    self._data.pop(k, None)
            if len(self._data) >= self.maxsize:
                oldest_key = min(self._data.items(), key=lambda kv: kv[1][1])[0]
                self._data.pop(oldest_key, None)
            self._data[key] = (value, now + self.ttl)


_geocode_cache = _TtlCache(_GEOCODE_CACHE_TTL_SEC)
_route_cache = _TtlCache(_ROUTE_CACHE_TTL_SEC)


def _round_coord(value, digits=4):
    """Round coordinates for cache keys (~11m at 4 decimal places)."""
    return round(float(value), digits)


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance (in kilometers) between two sets of latitude and longitude coordinates.
    """
    R = 6371  # Radius of the Earth in kilometers

    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


def find_closest_location(input_location, locations):
    """
    Find the closest location to the input location from a list of locations.
    """
    min_distance = float('inf')
    closest_location = None

    input_lat, input_lon = input_location[3], input_location[4]

    for location in locations:
        lat, lon = map(float, location[3:5])

        distance = calculate_distance(input_lat, input_lon, lat, lon)

        if distance < min_distance:
            min_distance = distance
            closest_location = location

    return closest_location, min_distance


def read_locations(file_path):
    import ast
    locations = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                location_data = ast.literal_eval(line)
            except (ValueError, SyntaxError):
                # Legacy fallback for older comma-split files
                location_data = line[1:-1].split(", ")
            locations.append(location_data)
    return locations


def load_api_keys(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        return []


def resolve_azure_maps_key(explicit_key=None):
    """Prefer an explicit key, then AZURE_MAPS_KEY env, then api.txt entries."""
    if explicit_key:
        return explicit_key
    env_key = os.environ.get('AZURE_MAPS_KEY', '').strip()
    if env_key:
        return env_key
    return None


def format_travel_time(trip_time_seconds):
    trip_hours, remainder = divmod(int(trip_time_seconds), 3600)
    trip_minutes, _ = divmod(remainder, 60)

    if trip_hours == 1:
        return f"{trip_hours} hour and {trip_minutes} minutes"
    if trip_hours == 0:
        return f"{trip_minutes} minutes"
    return f"{trip_hours} hours and {trip_minutes} minutes"


def _traffic_label(travel_seconds, delay_seconds):
    if delay_seconds is None:
        return "N/A"
    try:
        delay = float(delay_seconds)
        travel = max(float(travel_seconds or 0), 1.0)
    except (TypeError, ValueError):
        return "N/A"
    ratio = delay / travel
    if delay < 60 or ratio < 0.05:
        return "Low"
    if ratio < 0.2:
        return "Medium"
    return "Heavy"


def _geocode_azure(address, api_key):
    params = {
        "api-version": "1.0",
        "subscription-key": api_key,
        "query": address,
        "limit": 1,
        "countrySet": "US",
    }
    response = requests.get(AZURE_SEARCH_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    results = data.get("results") or []
    if not results:
        return None
    position = results[0].get("position") or {}
    return float(position["lat"]), float(position["lon"])


def _geocode_nominatim(address):
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    return None


def get_coordinates(address, api_key=None):
    """Geocode an address. Prefer Azure Maps, fall back to Nominatim. Cached."""
    if not address:
        return None

    cache_key = " ".join(address.strip().lower().split())
    cached = _geocode_cache.get(cache_key)
    if cached is not None:
        return cached

    azure_key = resolve_azure_maps_key(api_key)
    coords = None
    if azure_key:
        try:
            coords = _geocode_azure(address, azure_key)
        except (requests.RequestException, KeyError, TypeError, ValueError):
            coords = None

    if coords is None:
        try:
            coords = _geocode_nominatim(address)
        except (requests.RequestException, KeyError, TypeError, ValueError, IndexError):
            coords = None

    if coords is not None:
        _geocode_cache.set(cache_key, coords)
    return coords


def _route_from_azure(lat, lon, target_lat, target_lon, api_key):
    # Single lean request: one route, no alternatives, compact polyline points
    params = {
        "api-version": "1.0",
        "subscription-key": api_key,
        "query": f"{float(lat)},{float(lon)}:{float(target_lat)},{float(target_lon)}",
        "travelMode": "car",
        "traffic": "true",
        "routeRepresentation": "polyline",
        "computeBestOrder": "false",
    }
    response = requests.get(AZURE_ROUTE_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    routes = data.get("routes") or []
    if not routes:
        raise ValueError("Azure Maps returned no route")

    route = routes[0]
    summary = route.get("summary") or {}
    points = []
    for leg in route.get("legs") or []:
        for point in leg.get("points") or []:
            points.append((float(point["latitude"]), float(point["longitude"])))

    travel_seconds = summary.get("travelTimeInSeconds", 0)
    delay_seconds = summary.get("trafficDelayInSeconds", 0)

    return {
        "coordinates": points,
        "distance_km": round((summary.get("lengthInMeters") or 0) / 1000.0, 2),
        "duration_seconds": travel_seconds,
        "traffic": _traffic_label(travel_seconds, delay_seconds),
        "source": "azure_maps",
    }


def _route_from_osrm(lat, lon, target_lat, target_lon):
    url = (
        f"{OSRM_ROUTE_URL}/"
        f"{float(lon)},{float(lat)};{float(target_lon)},{float(target_lat)}"
    )
    params = {"overview": "simplified", "geometries": "geojson"}
    headers = {"User-Agent": USER_AGENT}

    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("OSRM returned no route")

    route = data["routes"][0]
    coordinates = [(pt[1], pt[0]) for pt in route["geometry"]["coordinates"]]

    return {
        "coordinates": coordinates,
        "distance_km": round(route.get("distance", 0) / 1000.0, 2),
        "duration_seconds": route.get("duration", 0),
        "traffic": "N/A",
        "source": "osrm",
    }


def get_driving_route(lat, lon, target_lat, target_lon, azure_maps_key=None, ors_api_key=None):
    """
    Get a driving route. Prefer Azure Maps when a key is set;
    otherwise fall back to the public OSRM demo server.
    Results are cached briefly to avoid repeat billed calls.
    """
    route_key = (
        _round_coord(lat),
        _round_coord(lon),
        _round_coord(target_lat),
        _round_coord(target_lon),
    )
    cached = _route_cache.get(route_key)
    if cached is not None:
        return cached

    azure_key = resolve_azure_maps_key(azure_maps_key or ors_api_key)
    route = None
    if azure_key:
        try:
            route = _route_from_azure(lat, lon, target_lat, target_lon, azure_key)
        except (requests.RequestException, KeyError, IndexError, ValueError, TypeError):
            route = None

    if route is None:
        try:
            route = _route_from_osrm(lat, lon, target_lat, target_lon)
        except (requests.RequestException, KeyError, IndexError, ValueError, TypeError):
            route = None

    if route is not None:
        _route_cache.set(route_key, route)
    return route
