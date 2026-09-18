"""Shared helpers for smoothie store scrapers and geocoding."""

from __future__ import annotations

import json
import re
import time
from typing import Iterable, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

USER_AGENT = "SmoothieFinder/1.0 (local research; respectful rate limits)"
DEFAULT_DELAY_SEC = 0.35
REQUEST_TIMEOUT = 25

US_STATES = [
    ("Alabama", "AL"), ("Alaska", "AK"), ("Arizona", "AZ"), ("Arkansas", "AR"),
    ("California", "CA"), ("Colorado", "CO"), ("Connecticut", "CT"), ("Delaware", "DE"),
    ("District of Columbia", "DC"), ("Florida", "FL"), ("Georgia", "GA"), ("Hawaii", "HI"),
    ("Idaho", "ID"), ("Illinois", "IL"), ("Indiana", "IN"), ("Iowa", "IA"),
    ("Kansas", "KS"), ("Kentucky", "KY"), ("Louisiana", "LA"), ("Maine", "ME"),
    ("Maryland", "MD"), ("Massachusetts", "MA"), ("Michigan", "MI"), ("Minnesota", "MN"),
    ("Mississippi", "MS"), ("Missouri", "MO"), ("Montana", "MT"), ("Nebraska", "NE"),
    ("Nevada", "NV"), ("New Hampshire", "NH"), ("New Jersey", "NJ"), ("New Mexico", "NM"),
    ("New York", "NY"), ("North Carolina", "NC"), ("North Dakota", "ND"), ("Ohio", "OH"),
    ("Oklahoma", "OK"), ("Oregon", "OR"), ("Pennsylvania", "PA"), ("Rhode Island", "RI"),
    ("South Carolina", "SC"), ("South Dakota", "SD"), ("Tennessee", "TN"), ("Texas", "TX"),
    ("Utah", "UT"), ("Vermont", "VT"), ("Virginia", "VA"), ("Washington", "WA"),
    ("West Virginia", "WV"), ("Wisconsin", "WI"), ("Wyoming", "WY"),
]
STATE_NAME_TO_ABBR = {name: abbr for name, abbr in US_STATES}
STATE_ABBRS = {abbr.lower() for _, abbr in US_STATES}


class HttpClient:
    def __init__(self, delay: float = DEFAULT_DELAY_SEC):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        self.delay = delay
        self._last_request = 0.0

    def get(self, url: str, retries: int = 3) -> Optional[requests.Response]:
        for attempt in range(retries):
            elapsed = time.time() - self._last_request
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                self._last_request = time.time()
                if response.status_code == 429:
                    time.sleep(2 + attempt * 2)
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                if attempt == retries - 1:
                    print(f"  request failed: {url} ({exc})")
                    return None
                time.sleep(1 + attempt)
        return None

    def soup(self, url: str) -> Optional[BeautifulSoup]:
        response = self.get(url)
        if response is None:
            return None
        return BeautifulSoup(response.content, "html.parser")


def export_list_to_text_file(lst: Iterable, file_path: str) -> None:
    with open(file_path, "w", encoding="utf-8") as file:
        for item in lst:
            file.write(str(item) + "\n")


def slugify(value: str) -> str:
    return re.sub(r"\s+", "-", value.strip()).lower()


def normalize_path_parts(href: str) -> list[str]:
    """Return path segments without domain/query/fragment, resolving . and .."""
    href = href.strip()
    if href.startswith("http"):
        href = href.split("://", 1)[1]
        href = href.split("/", 1)[1] if "/" in href else ""
    href = href.split("?", 1)[0].split("#", 1)[0]
    parts = []
    for part in href.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return parts


def extract_geo_from_html(html: str) -> Optional[tuple[float, float]]:
    """Pull lat/lon from JSON-LD or common meta tags."""
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        geo = _find_geo(data)
        if geo:
            return geo

    lat_meta = soup.find("meta", attrs={"property": "place:location:latitude"}) or soup.find(
        "meta", attrs={"name": "geo.latitude"}
    ) or soup.find("meta", attrs={"itemprop": "latitude"})
    lon_meta = soup.find("meta", attrs={"property": "place:location:longitude"}) or soup.find(
        "meta", attrs={"name": "geo.longitude"}
    ) or soup.find("meta", attrs={"itemprop": "longitude"})
    if lat_meta and lon_meta and lat_meta.get("content") and lon_meta.get("content"):
        try:
            return float(lat_meta["content"]), float(lon_meta["content"])
        except ValueError:
            pass

    # Fallback: first latitude/longitude pair in page source
    match = re.search(
        r'"latitude"\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*"longitude"\s*:\s*(-?\d+(?:\.\d+)?)',
        html,
    )
    if match:
        return float(match.group(1)), float(match.group(2))
    return None


DAY_ALIASES = {
    "monday": "Mon", "mon": "Mon", "mo": "Mon",
    "tuesday": "Tue", "tue": "Tue", "tu": "Tue",
    "wednesday": "Wed", "wed": "Wed", "we": "Wed",
    "thursday": "Thu", "thu": "Thu", "th": "Thu",
    "friday": "Fri", "fri": "Fri", "fr": "Fri",
    "saturday": "Sat", "sat": "Sat", "sa": "Sat",
    "sunday": "Sun", "sun": "Sun", "su": "Sun",
}
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _normalize_day(value: str) -> Optional[str]:
    token = value.strip().split("/")[-1].lower()
    return DAY_ALIASES.get(token)


def _collect_hours_nodes(node, bucket: list) -> None:
    if isinstance(node, dict):
        if "openingHoursSpecification" in node:
            bucket.append(("spec", node["openingHoursSpecification"]))
        if "openingHours" in node:
            bucket.append(("hours", node["openingHours"]))
        for value in node.values():
            _collect_hours_nodes(value, bucket)
    elif isinstance(node, list):
        for item in node:
            _collect_hours_nodes(item, bucket)


def extract_hours_from_html(html: str) -> Optional[str]:
    """Return a compact hours string from schema.org JSON-LD, if available."""
    soup = BeautifulSoup(html, "html.parser")
    collected = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        _collect_hours_nodes(data, collected)

    day_hours: dict[str, str] = {}
    fallback_strings = []

    for kind, payload in collected:
        if kind == "hours":
            if isinstance(payload, str):
                fallback_strings.append(payload)
            elif isinstance(payload, list):
                fallback_strings.extend(str(x) for x in payload)
            continue

        specs = payload if isinstance(payload, list) else [payload]
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            opens = spec.get("opens")
            closes = spec.get("closes")
            if not opens or not closes:
                continue
            # Treat all-day zeros as unknown/closed placeholder
            if opens == "00:00" and closes == "00:00":
                continue
            days = spec.get("dayOfWeek", [])
            if isinstance(days, str):
                days = [days]
            for day in days:
                short = _normalize_day(str(day))
                if short:
                    day_hours[short] = f"{opens}-{closes}"

    if day_hours:
        return _format_day_hours(day_hours)

    for raw in fallback_strings:
        cleaned = raw.strip()
        if cleaned and "00:00-00:00" not in cleaned:
            return cleaned
    return None


def _format_day_hours(day_hours: dict[str, str]) -> str:
    """Collapse consecutive days with the same hours: Mon-Fri 07:00-21:00; Sat 08:00-21:00."""
    parts = []
    i = 0
    while i < len(DAY_ORDER):
        day = DAY_ORDER[i]
        if day not in day_hours:
            i += 1
            continue
        hours = day_hours[day]
        j = i
        while j + 1 < len(DAY_ORDER) and day_hours.get(DAY_ORDER[j + 1]) == hours:
            j += 1
        if j == i:
            label = day
        elif j == i + 1:
            label = f"{day}, {DAY_ORDER[j]}"
        else:
            label = f"{DAY_ORDER[i]}-{DAY_ORDER[j]}"
        parts.append(f"{label} {hours}")
        i = j + 1
    return "; ".join(parts)


def enrich_store_from_html(html: str) -> tuple[Optional[tuple[float, float]], Optional[str]]:
    """Extract coordinates and hours from a store detail page."""
    return extract_geo_from_html(html), extract_hours_from_html(html)


def _find_geo(node) -> Optional[tuple[float, float]]:
    if isinstance(node, dict):
        geo = node.get("geo")
        if isinstance(geo, dict) and "latitude" in geo and "longitude" in geo:
            try:
                return float(geo["latitude"]), float(geo["longitude"])
            except (TypeError, ValueError):
                pass
        if "latitude" in node and "longitude" in node and "@type" in node:
            try:
                return float(node["latitude"]), float(node["longitude"])
            except (TypeError, ValueError):
                pass
        for value in node.values():
            found = _find_geo(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_geo(item)
            if found:
                return found
    return None


def get_coordinates_nominatim(client: HttpClient, address: str) -> Optional[tuple[float, float]]:
    """Geocode with Nominatim. Uses a slower delay to respect usage policy."""
    if not address:
        return None
    # Nominatim expects roughly 1 request/sec
    time.sleep(max(0.0, 1.05 - (time.time() - client._last_request)))
    try:
        response = client.session.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        client._last_request = time.time()
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    return None


def get_coordinates_azure(client: HttpClient, address: str, api_key: str) -> Optional[tuple[float, float]]:
    """Geocode with Azure Maps Search API."""
    if not address or not api_key:
        return None
    try:
        response = client.session.get(
            "https://atlas.microsoft.com/search/address/json",
            params={
                "api-version": "1.0",
                "subscription-key": api_key,
                "query": address,
                "limit": 1,
                "countrySet": "US",
            },
            timeout=REQUEST_TIMEOUT,
        )
        client._last_request = time.time()
        response.raise_for_status()
        data = response.json()
        results = data.get("results") or []
        if not results:
            return None
        position = results[0]["position"]
        return float(position["lat"]), float(position["lon"])
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


def get_coordinates(client: HttpClient, address: str, azure_maps_key: str = "") -> Optional[tuple[float, float]]:
    """Prefer Azure Maps when a key is available; otherwise Nominatim."""
    if azure_maps_key:
        coords = get_coordinates_azure(client, address, azure_maps_key)
        if coords:
            return coords
    return get_coordinates_nominatim(client, address)


def dedupe_locations(locations: list) -> list:
    seen = set()
    unique = []
    for item in locations:
        key = tuple(str(x).lower() for x in item[:3])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
