"""If docs/data/listings.json exists (built by scripts/build_dataset.py),
verify it matches the schema the frontend (docs/app.js) expects and that
every listing satisfies the project brief's hard filters."""
import json
from pathlib import Path

import pytest

DATA_PATH = Path(__file__).parent.parent / "docs" / "data" / "listings.json"

REQUIRED_FIELDS = {
    "portal", "portal_listing_id", "url", "title", "operation",
    "property_type", "locality", "price_cop", "rooms", "parking_spots",
}


@pytest.mark.skipif(not DATA_PATH.exists(), reason="dataset not built yet")
def test_dataset_matches_frontend_schema():
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    assert "listings" in payload
    assert isinstance(payload["listings"], list)
    assert payload["count"] == len(payload["listings"])

    for listing in payload["listings"]:
        missing = REQUIRED_FIELDS - listing.keys()
        assert not missing, f"listing {listing.get('portal_listing_id')} missing {missing}"

        assert listing["locality"] in {"usaquen", "chapinero", "suba"}
        assert listing["operation"] in {"venta", "arriendo"}
        assert listing["property_type"] in {"apartamento", "casa", "duplex"}
        assert listing["rooms"] >= 3
        assert listing["parking_spots"] >= 1
        if listing["operation"] == "venta":
            assert listing["price_cop"] <= 1_000_000_000
        else:
            assert listing["price_cop"] <= 7_000_000


@pytest.mark.skipif(not DATA_PATH.exists(), reason="dataset not built yet")
def test_dataset_has_no_duplicate_listings():
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    keys = [(l["portal"], l["portal_listing_id"]) for l in payload["listings"]]
    assert len(keys) == len(set(keys))
