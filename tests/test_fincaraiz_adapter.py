from pathlib import Path

import pytest

from scraper.adapters.fincaraiz import FincaRaizAdapter

FIXTURES = Path(__file__).parent / "fixtures" / "fincaraiz"


@pytest.fixture
def adapter():
    return FincaRaizAdapter()


def test_search_urls_maps_known_localities(adapter):
    urls = adapter.search_urls("usaquen")
    assert urls == ["https://www.fincaraiz.com.co/apartamentos-y-casas/venta/bogota/usaquen"]


def test_search_urls_rejects_unknown_locality(adapter):
    with pytest.raises(ValueError):
        adapter.search_urls("kennedy")


def test_parse_listing_urls_dedupes_and_filters(adapter):
    html = (FIXTURES / "search_usaquen.html").read_text(encoding="utf-8")
    urls = adapter.parse_listing_urls(html)
    assert urls == [
        "https://www.fincaraiz.com.co/inmueble/apartamento-en-venta-usaquen-bogota-123456",
        "https://www.fincaraiz.com.co/inmueble/casa-en-venta-usaquen-bogota-654321",
    ]


def test_parse_listing_extracts_required_fields(adapter):
    html = (FIXTURES / "listing_123456.html").read_text(encoding="utf-8")
    url = "https://www.fincaraiz.com.co/inmueble/apartamento-en-venta-usaquen-bogota-123456"

    raw = adapter.parse_listing(html, url)

    assert raw["portal_listing_id"] == "123456"
    assert raw["title"].startswith("Apartamento en venta")
    assert raw["price"] == "850000000"
    assert raw["operation"] == "venta"
    assert raw["property_type"] == "apartamento"
    assert raw["locality"] == "usaquen"
    assert raw["address"] == "Calle 116 # 15-20"
    assert raw["rooms"] == 3
    assert raw["bathrooms"] == 2
    assert raw["parking_spots"] == 1
    assert raw["area_m2"] == 85.5
    assert len(raw["photo_urls"]) == 3
    assert raw["has_video"] is True


def test_parse_listing_raises_on_invalid_url(adapter):
    with pytest.raises(ValueError):
        adapter.parse_listing("<html></html>", "https://www.fincaraiz.com.co/nosotros")


def test_parse_listing_handles_missing_price(adapter):
    html = (FIXTURES / "listing_malformed.html").read_text(encoding="utf-8")
    url = "https://www.fincaraiz.com.co/inmueble/casa-en-venta-chapinero-bogota-999999"

    raw = adapter.parse_listing(html, url)

    assert raw["price"] is None
