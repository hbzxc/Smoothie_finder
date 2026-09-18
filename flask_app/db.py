"""SQLite storage for smoothie franchise locations."""

from __future__ import annotations

import ast
import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, Optional

DEFAULT_DB_NAME = "smoothie_locations.db"

FRANCHISE_KEYS = {
    "tropical": "Tropical Smoothie",
    "jamba": "Jamba Juice",
    "king": "Smoothie King",
}

FRANCHISE_FILES = {
    "Tropical Smoothie": "TropicalLocations.txt",
    "Jamba Juice": "Jamba_Locations.txt",
    "Smoothie King": "Smoothie_King_Locations.txt",
}


def db_path(base_dir: str) -> str:
    return os.path.join(base_dir, DEFAULT_DB_NAME)


@contextmanager
def connect(path: str):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: str) -> None:
    with connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY,
                franchise TEXT NOT NULL,
                state TEXT NOT NULL,
                town TEXT NOT NULL,
                address TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                hours TEXT,
                scraped_at TEXT,
                UNIQUE(franchise, state, town, address)
            );
            CREATE INDEX IF NOT EXISTS idx_locations_franchise
                ON locations(franchise);
            CREATE INDEX IF NOT EXISTS idx_locations_coords
                ON locations(lat, lon);
            CREATE INDEX IF NOT EXISTS idx_locations_franchise_coords
                ON locations(franchise, lat, lon);
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )


def set_meta(path: str, key: str, value: str) -> None:
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_meta(path: str, key: str, default: str = "unknown") -> str:
    with connect(path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def count_locations(path: str, franchise: Optional[str] = None) -> int:
    with connect(path) as conn:
        if franchise:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM locations WHERE franchise=?",
                (franchise,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM locations").fetchone()
    return int(row["n"])


def humanize_slug(value: str) -> str:
    return str(value).replace("-", " ").strip().title()


def replace_franchise_locations(
    path: str,
    franchise: str,
    rows: Iterable,
    scraped_at: Optional[str] = None,
) -> int:
    """Replace all rows for one franchise. rows: [state, town, address, lat, lon, hours?]."""
    scraped_at = scraped_at or datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = []
    for row in rows:
        if len(row) < 5:
            continue
        try:
            lat = float(row[3])
            lon = float(row[4])
        except (TypeError, ValueError):
            continue
        hours = row[5] if len(row) >= 6 and row[5] else None
        payload.append(
            (
                franchise,
                str(row[0]).lower(),
                str(row[1]).lower(),
                str(row[2]).lower(),
                lat,
                lon,
                hours,
                scraped_at,
            )
        )

    with connect(path) as conn:
        conn.execute("DELETE FROM locations WHERE franchise=?", (franchise,))
        conn.executemany(
            """
            INSERT OR REPLACE INTO locations
                (franchise, state, town, address, lat, lon, hours, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    set_meta(path, f"updated:{franchise}", scraped_at)
    return len(payload)


def markers_for_franchise(path: str, franchise: str) -> list[dict]:
    with connect(path) as conn:
        rows = conn.execute(
            """
            SELECT state, town, address, lat, lon, hours, scraped_at
            FROM locations
            WHERE franchise=?
            """,
            (franchise,),
        ).fetchall()

    markers = []
    for row in rows:
        markers.append(
            {
                "lat": row["lat"],
                "lon": row["lon"],
                "address": (
                    f"{humanize_slug(row['address'])}, "
                    f"{humanize_slug(row['town'])}, "
                    f"{str(row['state']).upper()}"
                ),
                "hours": row["hours"] or "Hours unavailable",
                "updated": row["scraped_at"] or get_meta(path, f"updated:{franchise}"),
            }
        )
    return markers


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(
        math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)]
    )
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_closest_in_db(
    path: str,
    lat: float,
    lon: float,
    franchise: Optional[str] = None,
):
    """
    Find closest store using an expanding lat/lon window, then exact haversine.
    Returns (location_tuple, distance_km) where location_tuple matches the old
    list format: [state, town, address, lat, lon, hours?, franchise].
    """
    lat = float(lat)
    lon = float(lon)

    # Start ~50km box (~0.45 deg lat), expand until candidates exist
    for radius_deg in (0.5, 1.0, 2.0, 5.0, 15.0, 180.0):
        params = [lat - radius_deg, lat + radius_deg, lon - radius_deg, lon + radius_deg]
        sql = """
            SELECT franchise, state, town, address, lat, lon, hours
            FROM locations
            WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
        """
        if franchise:
            sql += " AND franchise=?"
            params.append(franchise)

        with connect(path) as conn:
            rows = conn.execute(sql, params).fetchall()
        if rows:
            break
    else:
        return None, float("inf")

    closest = None
    min_distance = float("inf")
    for row in rows:
        dist = calculate_distance(lat, lon, row["lat"], row["lon"])
        if dist < min_distance:
            min_distance = dist
            closest = row

    if closest is None:
        return None, float("inf")

    location = [
        closest["state"],
        closest["town"],
        closest["address"],
        closest["lat"],
        closest["lon"],
    ]
    if closest["hours"]:
        location.append(closest["hours"])
    location.append(closest["franchise"])
    return location, min_distance


def _read_text_locations(file_path: str) -> list:
    rows = []
    if not os.path.exists(file_path):
        return rows
    with open(file_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(list(ast.literal_eval(line)))
            except (ValueError, SyntaxError):
                rows.append(line[1:-1].split(", "))
    return rows


def migrate_from_text_files(base_dir: str, path: Optional[str] = None) -> dict:
    """Load legacy *.txt location files into SQLite."""
    path = path or db_path(base_dir)
    init_db(path)
    summary = {}
    for franchise, filename in FRANCHISE_FILES.items():
        file_path = os.path.join(base_dir, filename)
        stamp_path = file_path + ".updated"
        scraped_at = None
        if os.path.exists(stamp_path):
            scraped_at = open(stamp_path, encoding="utf-8").read().strip() or None
        if not scraped_at and os.path.exists(file_path):
            scraped_at = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime(
                "%Y-%m-%d %H:%M"
            )
        rows = _read_text_locations(file_path)
        count = replace_franchise_locations(path, franchise, rows, scraped_at=scraped_at)
        summary[franchise] = count
    return summary


def ensure_db(base_dir: str) -> str:
    """Create/migrate DB if missing or empty."""
    path = db_path(base_dir)
    init_db(path)
    if count_locations(path) == 0:
        migrate_from_text_files(base_dir, path)
    return path
