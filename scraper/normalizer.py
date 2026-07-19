"""Raw adapter dict -> canonical Listing."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from scraper.models import Listing

_PRICE_RE = re.compile(r"[\d.,]+")


class NormalizationError(ValueError):
    pass


def parse_price_cop(raw: str | int | float) -> int:
    """Parse a Colombian-peso price string like '$ 850.000.000' into an int."""
    if isinstance(raw, (int, float)):
        return int(raw)
    match = _PRICE_RE.search(raw or "")
    if not match:
        raise NormalizationError(f"could not parse price from {raw!r}")
    digits = match.group(0).replace(".", "").replace(",", "")
    if not digits:
        raise NormalizationError(f"could not parse price from {raw!r}")
    return int(digits)


def normalize(raw: dict, *, portal: str, now: datetime | None = None) -> Listing:
    """Convert a raw adapter dict into a canonical Listing.

    Raises NormalizationError with a clear message on missing/malformed
    required fields, so callers can skip bad listings without crashing a run.
    """
    try:
        price_cop = parse_price_cop(raw["price"])
    except KeyError:
        raise NormalizationError("missing required field: price")

    try:
        listing = Listing(
            portal=portal,
            portal_listing_id=str(raw["portal_listing_id"]),
            url=raw["url"],
            title=raw.get("title") or "",
            operation=raw["operation"],
            property_type=raw["property_type"],
            locality=raw["locality"],
            address=raw.get("address"),
            price_cop=price_cop,
            rooms=raw.get("rooms"),
            bathrooms=raw.get("bathrooms"),
            parking_spots=raw.get("parking_spots"),
            area_m2=raw.get("area_m2"),
            description=raw.get("description"),
            photo_urls=raw.get("photo_urls") or [],
            floor_plan_urls=raw.get("floor_plan_urls") or [],
            has_video=bool(raw.get("has_video", False)),
            latitude=raw.get("latitude"),
            longitude=raw.get("longitude"),
            stratum=raw.get("stratum"),
            floor=raw.get("floor"),
            floors_count=raw.get("floors_count"),
            construction_year=raw.get("construction_year"),
            common_expenses_cop=raw.get("common_expenses_cop"),
            scraped_at=now or datetime.now(timezone.utc),
        )
    except KeyError as exc:
        raise NormalizationError(f"missing required field: {exc.args[0]}") from exc
    except Exception as exc:  # pydantic.ValidationError and friends
        raise NormalizationError(str(exc)) from exc

    return listing
