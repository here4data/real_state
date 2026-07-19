from pathlib import Path

import pytest

from scraper.adapters.fincaraiz import FincaRaizAdapter

FIXTURES = Path(__file__).parent / "fixtures" / "fincaraiz"


@pytest.fixture
def adapter():
    return FincaRaizAdapter()


def test_search_urls_covers_operations_and_property_types(adapter):
    urls = adapter.search_urls("usaquen")
    assert set(urls) == {
        "https://www.fincaraiz.com.co/venta/apartamentos/usaquen/bogota",
        "https://www.fincaraiz.com.co/venta/casas/usaquen/bogota",
        "https://www.fincaraiz.com.co/arriendo/apartamentos/usaquen/bogota",
        "https://www.fincaraiz.com.co/arriendo/casas/usaquen/bogota",
    }


def test_search_urls_rejects_unknown_locality(adapter):
    with pytest.raises(ValueError):
        adapter.search_urls("kennedy")


def test_parse_listing_urls_dedupes(adapter):
    html = (FIXTURES / "search_usaquen.html").read_text(encoding="utf-8")
    urls = adapter.parse_listing_urls(html)
    assert urls == [
        "https://www.fincaraiz.com.co/apartamento-en-venta-en-cedritos-bogota/193410777",
        "https://www.fincaraiz.com.co/serraclara-apartamento-en-venta-en-villas-de-aranjuez-bogota/193068462",
    ]


def test_parse_listing_urls_returns_empty_on_missing_payload(adapter):
    assert adapter.parse_listing_urls("<html><body>no data here</body></html>") == []


def test_parse_listing_extracts_required_fields(adapter):
    html = (FIXTURES / "listing_193410777.html").read_text(encoding="utf-8")
    url = "https://www.fincaraiz.com.co/apartamento-en-venta-en-cedritos-bogota/193410777"

    raw = adapter.parse_listing(html, url)

    assert raw["portal_listing_id"] == "193410777"
    assert raw["title"] == "Apartamento en Venta en Cedritos, Bogota"
    assert raw["price"] == 820000000
    assert raw["operation"] == "venta"
    assert raw["property_type"] == "apartamento"
    assert raw["locality"] == "usaquen"
    assert raw["rooms"] == 3
    assert raw["bathrooms"] == 2
    assert raw["parking_spots"] == 2
    assert raw["area_m2"] == 102
    assert raw["latitude"] == pytest.approx(4.7190125)
    assert raw["longitude"] == pytest.approx(-74.0411926)
    assert len(raw["photo_urls"]) == 2


def test_parse_listing_raises_on_invalid_url(adapter):
    with pytest.raises(ValueError):
        adapter.parse_listing("<html></html>", "https://www.fincaraiz.com.co/nosotros")


def test_parse_listing_handles_missing_price(adapter):
    html = (FIXTURES / "listing_malformed.html").read_text(encoding="utf-8")
    url = "https://www.fincaraiz.com.co/casa-en-venta-chapinero-bogota/999999"

    raw = adapter.parse_listing(html, url)

    assert raw["price"] is None
