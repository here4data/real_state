"""Live-scrape FincaRaiz for the project's target localities, persist full
history to SQLite, and export a filtered JSON snapshot for the static
frontend (docs/data/listings.json).

Filter criteria are the ones fixed in the project brief: minimum 3 rooms,
minimum 1 parking spot, venta <= $1.000.000.000 COP, arriendo <= $7.000.000
COP, property type in {apartamento, casa, duplex}.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.adapters.portals import crawlable_adapters, registry_summary  # noqa: E402
from scraper.engine import Engine, Fetcher  # noqa: E402
from scraper.storage.db import Storage  # noqa: E402

LOCALITIES = ["usaquen", "chapinero", "suba"]
DB_PATH = str(Path(__file__).resolve().parents[1] / "listings.db")
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "listings.json"

MAX_PRICE_VENTA = 1_000_000_000
MAX_PRICE_ARRIENDO = 7_000_000
MIN_ROOMS = 3

# Project brief's approximate geo box: Calle 80-134, Carrera 2-60.
CALLE_MIN, CALLE_MAX = 80, 134
CARRERA_MIN, CARRERA_MAX = 2, 60

_CALLE_RE = re.compile(r"\b(?:calle|cl|cll)\.?\s*(\d{1,3})", re.I)
_CARRERA_RE = re.compile(r"\b(?:carrera|cra|kr|cr)\.?\s*(\d{1,3})", re.I)


def geo_zone_check(address: str | None) -> bool | None:
    """True/False when the address text lets us verify the Calle 80-134 /
    Carrera 2-60 box; None when the address has no parseable street number
    (kept, not excluded, rather than silently dropping most listings)."""
    if not address:
        return None
    calle_m = _CALLE_RE.search(address)
    carrera_m = _CARRERA_RE.search(address)
    if not calle_m and not carrera_m:
        return None
    ok = True
    if calle_m:
        ok = ok and CALLE_MIN <= int(calle_m.group(1)) <= CALLE_MAX
    if carrera_m:
        ok = ok and CARRERA_MIN <= int(carrera_m.group(1)) <= CARRERA_MAX
    return ok


def passes_brief_filters(row) -> bool:
    if row["rooms"] is None or row["rooms"] < MIN_ROOMS:
        return False
    if row["operation"] == "venta" and row["price_cop"] > MAX_PRICE_VENTA:
        return False
    if row["operation"] == "arriendo" and row["price_cop"] > MAX_PRICE_ARRIENDO:
        return False
    if geo_zone_check(row["address"]) is False:
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
        "stratum": row["stratum"],
        "floor": row["floor"],
        "floors_count": row["floors_count"],
        "construction_year": row["construction_year"],
        "common_expenses_cop": row["common_expenses_cop"],
        "in_declared_zone": geo_zone_check(row["address"]),
        "last_seen_at": row["last_seen_at"],
    }


def add_opportunity_scores(listings: list[dict]) -> None:
    """Opportunity Score = % discount of a listing's price/m2 vs the median
    price/m2 of its comparable segment (operation + property_type + locality).
    Positive score => cheaper than its segment. rank = 1 is best deal."""
    segments: dict[tuple, list[float]] = {}
    for l in listings:
        if l["area_m2"]:
            l["price_per_m2"] = round(l["price_cop"] / l["area_m2"])
            key = (l["operation"], l["property_type"], l["locality"])
            segments.setdefault(key, []).append(l["price_per_m2"])
        else:
            l["price_per_m2"] = None

    medians = {}
    for key, values in segments.items():
        values.sort()
        n = len(values)
        medians[key] = (values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2)

    for l in listings:
        key = (l["operation"], l["property_type"], l["locality"])
        median = medians.get(key)
        if l["price_per_m2"] and median:
            l["segment_median_price_per_m2"] = round(median)
            l["opportunity_score"] = round(100 * (1 - l["price_per_m2"] / median), 1)
            # "Buen precio": >=5% below the segment median price/m2.
            l["good_price"] = l["opportunity_score"] >= 5
        else:
            l["segment_median_price_per_m2"] = None
            l["opportunity_score"] = None
            l["good_price"] = None

    ranked = sorted(
        (l for l in listings if l["opportunity_score"] is not None),
        key=lambda l: l["opportunity_score"],
        reverse=True,
    )
    for i, l in enumerate(ranked, start=1):
        l["opportunity_rank"] = i
    for l in listings:
        l.setdefault("opportunity_rank", None)


def main() -> None:
    storage = Storage(DB_PATH)
    for adapter in crawlable_adapters():
        engine = Engine(adapter, storage, fetcher=Fetcher(rate_limit_seconds=1.0))
        stats = engine.run(LOCALITIES)
        print(f"[{adapter.portal_name}] scrape stats: {stats}")

    rows = storage._conn.execute("SELECT * FROM listings").fetchall()
    filtered = [row_to_dict(r) for r in rows if passes_brief_filters(r)]
    add_opportunity_scores(filtered)
    filtered.sort(key=lambda r: r["price_cop"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generated_from_total_scraped": len(rows),
                "count": len(filtered),
                "localities": LOCALITIES,
                "portals": registry_summary(),
                "filters": {
                    "min_rooms": MIN_ROOMS,
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
