from datetime import datetime, timezone

import pytest

from scraper.models import Listing, Locality, Operation, PropertyType
from scraper.storage.db import Storage


@pytest.fixture
def storage():
    s = Storage(":memory:")
    yield s
    s.close()


def _listing(price_cop=850_000_000, scraped_at=None):
    return Listing(
        portal="fincaraiz",
        portal_listing_id="123456",
        url="https://www.fincaraiz.com.co/inmueble/apto-123456",
        title="Apartamento en Usaquén",
        operation=Operation.VENTA,
        property_type=PropertyType.APARTAMENTO,
        locality=Locality.USAQUEN,
        address="Calle 116 # 15-20",
        price_cop=price_cop,
        rooms=3,
        bathrooms=2,
        parking_spots=1,
        area_m2=85.5,
        description="Amplio apartamento",
        photo_urls=["https://cdn/1.jpg"],
        floor_plan_urls=[],
        has_video=True,
        scraped_at=scraped_at or datetime(2026, 7, 19, tzinfo=timezone.utc),
    )


def test_upsert_creates_listing_and_snapshot(storage):
    storage.upsert_listing(_listing())

    row = storage.get_listing("fincaraiz", "123456")
    assert row["price_cop"] == 850_000_000
    assert row["title"] == "Apartamento en Usaquén"

    snapshots = storage.get_snapshots("fincaraiz", "123456")
    assert len(snapshots) == 1
    assert snapshots[0]["price_cop"] == 850_000_000

    assert storage.count_listings() == 1


def test_repeated_upsert_updates_current_row_but_never_deletes_snapshots(storage):
    storage.upsert_listing(_listing(price_cop=850_000_000, scraped_at=datetime(2026, 7, 19, tzinfo=timezone.utc)))
    storage.upsert_listing(_listing(price_cop=800_000_000, scraped_at=datetime(2026, 7, 26, tzinfo=timezone.utc)))

    row = storage.get_listing("fincaraiz", "123456")
    assert row["price_cop"] == 800_000_000

    snapshots = storage.get_snapshots("fincaraiz", "123456")
    assert [s["price_cop"] for s in snapshots] == [850_000_000, 800_000_000]

    assert storage.count_listings() == 1


def test_get_listing_returns_none_for_unknown_id(storage):
    assert storage.get_listing("fincaraiz", "does-not-exist") is None
