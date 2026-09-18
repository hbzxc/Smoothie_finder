"""
Scrape Tropical Smoothie Cafe, Jamba, and Smoothie King store directories.

Examples:
  python SmoothiePls.py --brand tropical --state al --with-coords
  python SmoothiePls.py --brand all --limit 20
  python SmoothiePls.py --brand king --with-coords --copy-to-flask
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from SmoothieIngredients import (
    STATE_ABBRS,
    STATE_NAME_TO_ABBR,
    HttpClient,
    dedupe_locations,
    enrich_store_from_html,
    export_list_to_text_file,
    normalize_path_parts,
)

BRANDS = {
    "tropical": {
        "name": "tropical_smoothie",
        "index": "https://locations.tropicalsmoothiecafe.com/",
        "out": "tropical_smoothieOut.txt",
        "locations": "tropical_smoothie_Locations.txt",
        "flask": "TropicalLocations.txt",
    },
    "jamba": {
        "name": "Jamba",
        "index": "https://locations.jamba.com/",
        "out": "JambaOut.txt",
        "locations": "Jamba_Locations.txt",
        "flask": "Jamba_Locations.txt",
    },
    "king": {
        "name": "Smoothie_King",
        "index": "https://locations.smoothieking.com/site-map/us/",
        "out": "Smoothie_KingOut.txt",
        "locations": "Smoothie_King_Locations.txt",
        "flask": "Smoothie_King_Locations.txt",
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape smoothie franchise locations")
    parser.add_argument(
        "--brand",
        choices=["tropical", "jamba", "king", "all"],
        default="all",
        help="Which franchise to scrape",
    )
    parser.add_argument(
        "--state",
        default=None,
        help="Limit to one state abbreviation, e.g. al or TX",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after N locations (0 = no limit). Useful for testing.",
    )
    parser.add_argument(
        "--with-coords",
        action="store_true",
        help="Fetch each store page and extract lat/lon from schema.org metadata",
    )
    parser.add_argument(
        "--copy-to-flask",
        action="store_true",
        help="Copy the locations file into flask_app/ using the app's expected filename",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="Delay between HTTP requests in seconds",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Less console output",
    )
    return parser.parse_args()


def log(enabled: bool, message: str) -> None:
    if enabled:
        print(message)


def collect_state_abbrs_yext(soup, only_state: str | None) -> list[str]:
    found = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip().strip("/")
        text = a.get_text(strip=True)
        abbr = None
        if href.lower() in STATE_ABBRS:
            abbr = href.lower()
        elif text in STATE_NAME_TO_ABBR:
            abbr = STATE_NAME_TO_ABBR[text].lower()
        if abbr and abbr not in found:
            found.append(abbr)
    if only_state:
        only = only_state.lower()
        return [s for s in found if s == only]
    return found


def enrich_store(client: HttpClient, store_url: str, row: list, with_coords: bool, verbose: bool):
    """Fetch store page and attach coordinates + hours when requested."""
    if not with_coords:
        return row
    response = client.get(store_url)
    if response is None:
        return row

    geo, hours = enrich_store_from_html(response.text)
    extras = []
    if geo:
        lat, lon = geo
        extras.extend([lat, lon])
        log(verbose, f"    coords {lat}, {lon}")
    else:
        log(verbose, f"    no coords on {store_url}")

    if hours:
        # Keep hours after lat/lon: [state, town, address, lat, lon, hours]
        if len(extras) == 2:
            extras.append(hours)
        else:
            # No coords — still record hours after the address fields
            extras.extend(["", "", hours])
        log(verbose, f"    hours {hours}")
    elif len(extras) == 2:
        log(verbose, "    no hours found")

    if extras:
        row = row[:3] + extras
    return row


def scrape_yext_brand(client: HttpClient, brand_key: str, args) -> list:
    """Tropical and Jamba use Yext-style /{state}/{city}/{address} pages."""
    cfg = BRANDS[brand_key]
    base = cfg["index"]
    verbose = not args.quiet
    locations = []

    log(verbose, f"--------- Now checking {cfg['name']} ---------")
    index_soup = client.soup(base if brand_key != "tropical" else urljoin(base, "index.html"))
    if index_soup is None:
        return locations

    states = collect_state_abbrs_yext(index_soup, args.state)
    log(verbose, f"  states found: {len(states)}")

    for state in states:
        state_url = urljoin(base, state)
        state_soup = client.soup(state_url)
        if state_soup is None:
            continue
        log(verbose, f"  state {state.upper()} -> {state_url}")

        city_or_store_links = []
        for a in state_soup.find_all("a", href=True):
            parts = normalize_path_parts(a["href"])
            if len(parts) >= 2 and parts[0].lower() == state:
                city_or_store_links.append(a["href"])

        # Preserve order, unique
        seen_links = set()
        ordered_links = []
        for href in city_or_store_links:
            key = href.strip().lower()
            if key in seen_links:
                continue
            seen_links.add(key)
            ordered_links.append(href)

        for href in ordered_links:
            parts = normalize_path_parts(href)
            if len(parts) >= 3:
                store_paths = [parts[:3]]
            elif len(parts) == 2:
                city_url = urljoin(state_url + "/", parts[1])
                city_soup = client.soup(city_url)
                if city_soup is None:
                    continue
                store_paths = []
                for a in city_soup.find_all("a", href=True):
                    p = normalize_path_parts(a["href"])
                    if len(p) >= 3 and p[0].lower() == state and p[1].lower() == parts[1].lower():
                        store_paths.append(p[:3])
                # unique
                uniq = []
                seen = set()
                for p in store_paths:
                    key = tuple(x.lower() for x in p)
                    if key not in seen:
                        seen.add(key)
                        uniq.append(p)
                store_paths = uniq
            else:
                continue

            for state_slug, town, address in store_paths:
                row = [state_slug.lower(), town.lower(), address.lower()]
                store_url = urljoin(base, f"{state_slug}/{town}/{address}")
                log(verbose, f"    location {row}")
                row = enrich_store(client, store_url, row, args.with_coords, verbose)
                locations.append(row)
                if args.limit and len(locations) >= args.limit:
                    return dedupe_locations(locations)

    return dedupe_locations(locations)


def scrape_smoothie_king(client: HttpClient, args) -> list:
    cfg = BRANDS["king"]
    base = "https://locations.smoothieking.com"
    verbose = not args.quiet
    locations = []

    log(verbose, f"--------- Now checking {cfg['name']} ---------")
    index_soup = client.soup(cfg["index"])
    if index_soup is None:
        return locations

    state_links = []
    for a in index_soup.select('a[href*="/site-map/us/"]'):
        href = a.get("href", "")
        parts = normalize_path_parts(href)
        # Expect site-map/us/{state}
        if len(parts) >= 3 and parts[0] == "site-map" and parts[1] == "us" and parts[2].lower() in STATE_ABBRS:
            abbr = parts[2].lower()
            if args.state and abbr != args.state.lower():
                continue
            full = urljoin(base + "/", href.lstrip("/"))
            if (abbr, full) not in state_links:
                state_links.append((abbr, full))

    log(verbose, f"  states found: {len(state_links)}")

    for state, state_url in state_links:
        state_soup = client.soup(state_url)
        if state_soup is None:
            continue
        log(verbose, f"  state {state.upper()} -> {state_url}")

        city_urls = []
        for a in state_soup.select('a[href*="/site-map/us/"]'):
            href = a.get("href", "")
            parts = normalize_path_parts(href)
            if len(parts) >= 4 and parts[2].lower() == state:
                city_urls.append(urljoin(base + "/", href.lstrip("/")))
        city_urls = list(dict.fromkeys(city_urls))

        for city_url in city_urls:
            city_soup = client.soup(city_url)
            if city_soup is None:
                continue

            store_hrefs = []
            for a in city_soup.select('a[href*="/ll/us/"]'):
                href = a.get("href", "")
                parts = normalize_path_parts(href)
                # ll/us/{state}/{city}/{address}
                if len(parts) >= 5 and parts[0] == "ll" and parts[1] == "us":
                    store_hrefs.append(parts[2:5])

            uniq = []
            seen = set()
            for p in store_hrefs:
                key = tuple(x.lower() for x in p)
                if key not in seen:
                    seen.add(key)
                    uniq.append(p)

            for state_slug, town, address in uniq:
                row = [state_slug.lower(), town.lower(), address.lower()]
                store_url = f"{base}/ll/us/{state_slug}/{town}/{address}/"
                log(verbose, f"    location {row}")
                row = enrich_store(client, store_url, row, args.with_coords, verbose)
                locations.append(row)
                if args.limit and len(locations) >= args.limit:
                    return dedupe_locations(locations)

    return dedupe_locations(locations)


def write_outputs(brand_key: str, locations: list, args) -> None:
    cfg = BRANDS[brand_key]
    root = Path(".")
    out_path = root / cfg["out"]
    export_list_to_text_file([[*loc[:3]] for loc in locations], out_path)
    print(f"Wrote {len(locations)} address rows -> {out_path}")

    with_coords = [
        loc for loc in locations
        if len(loc) >= 5 and loc[3] != "" and loc[4] != ""
    ]
    if with_coords:
        loc_path = root / cfg["locations"]
        export_list_to_text_file(with_coords, loc_path)
        print(f"Wrote {len(with_coords)} geocoded rows -> {loc_path}")
        scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        stamp_path = loc_path.with_suffix(loc_path.suffix + ".updated")
        stamp_path.write_text(scraped_at, encoding="utf-8")

        # Always refresh SQLite used by the Flask app
        from flask_app.db import (
            FRANCHISE_KEYS,
            db_path,
            init_db,
            replace_franchise_locations,
        )

        franchise = FRANCHISE_KEYS[brand_key]
        sqlite_path = db_path("flask_app")
        init_db(sqlite_path)
        saved = replace_franchise_locations(sqlite_path, franchise, with_coords, scraped_at=scraped_at)
        print(f"Updated SQLite ({saved} rows) -> {sqlite_path}")

        if args.copy_to_flask:
            flask_path = root / "flask_app" / cfg["flask"]
            shutil.copyfile(loc_path, flask_path)
            shutil.copyfile(stamp_path, Path(str(flask_path) + ".updated"))
            print(f"Copied text snapshot to {flask_path}")
    elif args.copy_to_flask:
        print("Skipping flask/DB update: no coordinates in results (use --with-coords)")


def main():
    args = parse_args()
    client = HttpClient(delay=args.delay)
    brand_keys = list(BRANDS) if args.brand == "all" else [args.brand]

    for brand_key in brand_keys:
        if brand_key == "king":
            locations = scrape_smoothie_king(client, args)
        else:
            locations = scrape_yext_brand(client, brand_key, args)
        write_outputs(brand_key, locations, args)
        print(f"Done {BRANDS[brand_key]['name']}: {len(locations)} locations\n")


if __name__ == "__main__":
    main()
