"""
Geocode address-only *Out.txt files.

Uses Azure Maps when flask_app/api.txt (or AZURE_MAPS_KEY) is set;
otherwise falls back to Nominatim.

Examples:
  python AddCord.py --file JambaOut.txt
  python AddCord.py --all --copy-to-flask
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from SmoothieIngredients import (
    HttpClient,
    export_list_to_text_file,
    get_coordinates,
)

OUT_TO_LOCATIONS = {
    "tropical_smoothieOut.txt": ("tropical_smoothie_Locations.txt", "TropicalLocations.txt"),
    "JambaOut.txt": ("Jamba_Locations.txt", "Jamba_Locations.txt"),
    "Smoothie_KingOut.txt": ("Smoothie_King_Locations.txt", "Smoothie_King_Locations.txt"),
}


def parse_args():
    parser = argparse.ArgumentParser(description="Add coordinates to scraped location lists")
    parser.add_argument("--file", help="Single *Out.txt file to geocode")
    parser.add_argument("--all", action="store_true", help="Geocode all known *Out.txt files")
    parser.add_argument("--limit", type=int, default=0, help="Only process first N rows")
    parser.add_argument("--copy-to-flask", action="store_true", help="Copy results into flask_app/")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def read_locations_from_file(file_path: Path) -> list:
    import ast

    locations = []
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                cleaned = list(ast.literal_eval(line))
            except (ValueError, SyntaxError):
                raw = line[1:-1].split(", ")
                cleaned = [part.strip().strip("'\"") for part in raw]
            if len(cleaned) < 3:
                continue
            locations.append(cleaned)
    return locations


def human_address(state: str, town: str, address: str) -> str:
    town_h = town.replace("-", " ")
    address_h = address.replace("-", " ")
    return f"{address_h}, {town_h}, {state}, United States"


def process_file(path: Path, client: HttpClient, args, azure_maps_key: str = "") -> list:
    verbose = not args.quiet
    rows = read_locations_from_file(path)
    if args.limit:
        rows = rows[: args.limit]

    output = []
    for row in rows:
        state, town, address = row[0], row[1], row[2]
        existing_hours = row[5] if len(row) >= 6 else None
        if len(row) >= 5:
            try:
                entry = [state, town, address, float(row[3]), float(row[4])]
                if existing_hours:
                    entry.append(existing_hours)
                output.append(entry)
                if verbose:
                    print(f"Already geocoded: {town}, {state}")
                continue
            except (ValueError, TypeError):
                pass

        query = human_address(state, town, address)
        coords = get_coordinates(client, query, azure_maps_key=azure_maps_key)
        if coords:
            lat, lon = coords
            entry = [state, town, address, lat, lon]
            if existing_hours:
                entry.append(existing_hours)
            output.append(entry)
            if verbose:
                print(f"OK {town}, {state}: {lat}, {lon}")
        else:
            print(f"Coordinates not found for: {town}, {state} ({query})")
    return output


def load_azure_key() -> str:
    env_key = os.environ.get("AZURE_MAPS_KEY", "").strip()
    if env_key:
        return env_key
    for candidate in (Path("flask_app") / "api.txt", Path("api.txt")):
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    return line.strip()
    return ""


def main():
    args = parse_args()
    azure_maps_key = load_azure_key()
    # Azure can handle faster requests than Nominatim's 1 req/sec guidance
    client = HttpClient(delay=0.2 if azure_maps_key else 1.05)
    if azure_maps_key:
        print("Using Azure Maps for geocoding")
    else:
        print("No Azure Maps key found; using Nominatim")

    if args.file:
        targets = [Path(args.file)]
    elif args.all:
        targets = [Path(name) for name in OUT_TO_LOCATIONS if Path(name).exists()]
    else:
        # Default: every *Out.txt in the current directory
        targets = sorted(Path(".").glob("*Out.txt"))

    if not targets:
        print("No input *Out.txt files found.")
        return

    for path in targets:
        if not path.exists():
            print(f"Missing file: {path}")
            continue
        print(f"--- Geocoding {path} ---")
        results = process_file(path, client, args, azure_maps_key=azure_maps_key)

        mapping = OUT_TO_LOCATIONS.get(path.name)
        out_name = mapping[0] if mapping else path.name.replace("Out.txt", "_Locations.txt")
        out_path = Path(out_name)
        export_list_to_text_file(results, out_path)
        print(f"Wrote {len(results)} rows -> {out_path}")

        if args.copy_to_flask and mapping:
            flask_path = Path("flask_app") / mapping[1]
            shutil.copyfile(out_path, flask_path)
            print(f"Copied to {flask_path}")


if __name__ == "__main__":
    main()
