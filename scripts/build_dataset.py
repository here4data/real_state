"""Live-scrape FincaRaiz for the project's target localities, persist full
history to SQLite, and export a filtered JSON snapshot for the static
frontend (docs/data/listings.json).

Filter criteria are the ones fixed in the project brief: minimum 3 rooms,
minimum 1 parking spot, venta <= $1.000.000.000 COP, arriendo <= $7.000.000
COP, property type in {apartamento, casa, duplex}.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.adapters.fincaraiz import FincaRaizAdapter  # noqa: E402
from scraper.engine import Engine, Fetcher  # noqa: E402
from scraper.storage.db import Storage  # noqa: E402

LOCALITIES = ["usaquen", "chapinero", "suba"]
DB_PATH = str(Path(__file__).resolve().parents[1] / "listings.db")
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "listings.json"

MAX_PRICE_VENTA = 1_000_000_000
MAX_PRICE_ARRIENDO = 7_000_000
MIN_ROOMS = 3
MIN_PARKING = 1


def passes_brief_filters(row) -> bool:
    if row["rooms"] is None or row["rooms"] < MIN_ROOMS:
        return False
    if row["parking_spots"] is None or row["parking_spots"] < MIN_PARKING:
        return False
    if row["operation"] == "venta" and row["price_cop"] > MAX_PRICE_VENTA:
        return False
    if row["operation"] == "arriendo" and row["price_cop"] > MAX_PRICE_ARRIENDO:
        return False
    return True


def row_to_dict(row) -> dict:
    return {
        "portal": row["portal"],
        "portal_listing_id": row["portal_listing_id"],
        "url": row["url"],
        "title": row["title"],
        "operation": row["operation"],
        "property_type": row["property_type"],
        "locality": row["locality"],
        "address": row["address"],
        "price_cop": row["price_cop"],
        "rooms": row["rooms"],
        "bathrooms": row["bathrooms"],
        "parking_spots": row["parking_spots"],
        "area_m2": row["area_m2"],
        "description": row["description"],
        "photo_urls": json.loads(row["photo_urls"] or "[]"),
        "has_video": bool(row["has_video"]),
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "last_seen_at": row["last_seen_at"],
    }


def main() -> None:
    storage = Storage(DB_PATH)
    adapter = FincaRaizAdapter()
    engine = Engine(adapter, storage, fetcher=Fetcher(rate_limit_seconds=1.0))

    stats = engine.run(LOCALITIES)
    print(f"scrape stats: {stats}")

    rows = storage._conn.execute("SELECT * FROM listings").fetchall()
    filtered = [row_to_dict(r) for r in rows if passes_brief_filters(r)]
    filtered.sort(key=lambda r: r["price_cop"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generated_from_total_scraped": len(rows),
                "count": len(filtered),
                "localities": LOCALITIES,
                "filters": {
                    "min_rooms": MIN_ROOMS,
                    "min_parking": MIN_PARKING,
                    "max_price_venta_cop": MAX_PRICE_VENTA,
                    "max_price_arriendo_cop": MAX_PRICE_ARRIENDO,
                },
                "listings": filtered,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {len(filtered)} listings (of {len(rows)} scraped) to {OUTPUT_PATH}")

    storage.close()


if __name__ == "__main__":
    main()
