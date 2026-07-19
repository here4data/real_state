from datetime import datetime, timezone

import pytest

from scraper.normalizer import NormalizationError, normalize, parse_price_cop


@pytest.mark.parametrize(
    "raw_price,expected",
    [
        ("$ 850.000.000", 850_000_000),
        ("850000000", 850_000_000),
        ("$3.500.000", 3_500_000),
        (7_000_000, 7_000_000),
    ],
)
def test_parse_price_cop_handles_common_formats(raw_price, expected):
    assert parse_price_cop(raw_price) == expected


def test_parse_price_cop_raises_on_unparseable_value():
    with pytest.raises(NormalizationError):
        parse_price_cop("precio a consultar")


def _valid_raw(**overrides):
    raw = {
        "portal_listing_id": "123456",
        "url": "https://www.fincaraiz.com.co/inmueble/apto-123456",
        "title": "Apartamento en Usaquén",
        "operation": "venta",
        "property_type": "apartamento",
        "locality": "usaquen",
        "address": "Calle 116 # 15-20",
        "price": "$ 850.000.000",
        "rooms": 3,
        "bathrooms": 2,
        "parking_spots": 1,
        "area_m2": 85.5,
        "description": "Amplio apartamento...",
        "photo_urls": ["https://cdn/1.jpg"],
        "floor_plan_urls": [],
        "has_video": True,
    }
    raw.update(overrides)
    return raw


def test_normalize_builds_canonical_listing():
    now = datetime(2026, 7, 19, tzinfo=timezone.utc)
    listing = normalize(_valid_raw(), portal="fincaraiz", now=now)

    assert listing.portal == "fincaraiz"
    assert listing.portal_listing_id == "123456"
    assert listing.price_cop == 850_000_000
    assert listing.operation.value == "venta"
    assert listing.scraped_at == now


def test_normalize_raises_on_missing_required_field():
    raw = _valid_raw()
    del raw["price"]
    with pytest.raises(NormalizationError):
        normalize(raw, portal="fincaraiz")


def test_normalize_raises_on_malformed_price():
    raw = _valid_raw(price="precio a consultar")
    with pytest.raises(NormalizationError):
        normalize(raw, portal="fincaraiz")


def test_normalize_raises_on_non_positive_price():
    raw = _valid_raw(price="0")
    with pytest.raises(NormalizationError):
        normalize(raw, portal="fincaraiz")


def test_normalize_raises_on_invalid_enum_value():
    raw = _valid_raw(operation="alquiler")
    with pytest.raises(NormalizationError):
        normalize(raw, portal="fincaraiz")
