"""SQLite storage: upsert-with-history.

`listings` holds current state per (portal, portal_listing_id).
`listing_snapshots` is append-only — one row per scrape run per listing,
never updated or deleted, giving price/availability history from day one.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scraper.models import Listing

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Storage:
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def upsert_listing(self, listing: Listing) -> None:
        """Insert/refresh the current row and always append a snapshot."""
        scraped_at = listing.scraped_at.isoformat()
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO listings (
                portal, portal_listing_id, url, title, operation, property_type,
                locality, address, price_cop, rooms, bathrooms, parking_spots,
                area_m2, description, photo_urls, floor_plan_urls, has_video,
                latitude, longitude, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (portal, portal_listing_id) DO UPDATE SET
                url=excluded.url, title=excluded.title, operation=excluded.operation,
                property_type=excluded.property_type, locality=excluded.locality,
                address=excluded.address, price_cop=excluded.price_cop,
                rooms=excluded.rooms, bathrooms=excluded.bathrooms,
                parking_spots=excluded.parking_spots, area_m2=excluded.area_m2,
                description=excluded.description, photo_urls=excluded.photo_urls,
                floor_plan_urls=excluded.floor_plan_urls, has_video=excluded.has_video,
                latitude=excluded.latitude, longitude=excluded.longitude,
                last_seen_at=excluded.last_seen_at
            """,
            (
                listing.portal,
                listing.portal_listing_id,
                listing.url,
                listing.title,
                listing.operation.value,
                listing.property_type.value,
                listing.locality.value,
                listing.address,
                listing.price_cop,
                listing.rooms,
                listing.bathrooms,
                listing.parking_spots,
                listing.area_m2,
                listing.description,
                json.dumps(listing.photo_urls),
                json.dumps(listing.floor_plan_urls),
                int(listing.has_video),
                listing.latitude,
                listing.longitude,
                scraped_at,
                scraped_at,
            ),
        )
        cur.execute(
            """
            INSERT INTO listing_snapshots (portal, portal_listing_id, price_cop, scraped_at)
            VALUES (?, ?, ?, ?)
            """,
            (listing.portal, listing.portal_listing_id, listing.price_cop, scraped_at),
        )
        self._conn.commit()

    def get_listing(self, portal: str, portal_listing_id: str) -> sqlite3.Row | None:
        cur = self._conn.execute(
            "SELECT * FROM listings WHERE portal = ? AND portal_listing_id = ?",
            (portal, portal_listing_id),
        )
        return cur.fetchone()

    def get_snapshots(self, portal: str, portal_listing_id: str) -> list[sqlite3.Row]:
        cur = self._conn.execute(
            """
            SELECT * FROM listing_snapshots
            WHERE portal = ? AND portal_listing_id = ?
            ORDER BY scraped_at ASC
            """,
            (portal, portal_listing_id),
        )
        return cur.fetchall()

    def count_listings(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
