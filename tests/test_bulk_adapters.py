"""Metrocuadrado (flight-data) and Houm (API) bulk adapters against real
fixtures captured from the live services on 2026-07-19."""
import json
from pathlib import Path

from scraper.adapters.houm import HoumAdapter
from scraper.adapters.metrocuadrado import MetrocuadradoAdapter
from scraper.normalizer import normalize

FIXTURES = Path(__file__).parent / "fixtures"

M2_SEARCH_URL = "https://www.metrocuadrado.com/apartamento/venta/bogota/usaquen/"
HOUM_SEARCH_URL = (
    "https://apis.houm.com/backend/properties/marketplace/"
    "?page_size=5&photos_number=1&mode=sale&type=departamento&page=1"
    "&boundings=%5B%5B4.66%2C%20-74.07%5D%2C%20%5B4.78%2C%20-74.01%5D%5D"
)


def _m2_html() -> str:
    return (FIXTURES / "metrocuadrado" / "search_flight_segment.html").read_text(encoding="utf-8")


def _houm_json() -> str:
    return (FIXTURES / "houm" / "marketplace_page1.json").read_text(encoding="utf-8")


def test_metrocuadrado_bulk_parse_yields_complete_listings():
    raws = MetrocuadradoAdapter().parse_search_items(_m2_html(), M2_SEARCH_URL)
    assert len(raws) >= 40  # one search page carries ~50 cards

    for raw in raws:
        listing = normalize(raw, portal="metrocuadrado")
        assert listing.operation == "venta"
        assert listing.locality == "usaquen"
        assert listing.price_cop > 0
        assert listing.url.startswith("https://www.metrocuadrado.com/inmueble/")

    # spot fields that only exist because we parse the flight data (bulk):
    sample = raws[0]
    assert sample["stratum"] is not None
    assert sample["latitude"] is not None
    assert sample["common_expenses_cop"] is not None


def test_metrocuadrado_bulk_parse_empty_on_shell_html():
    assert MetrocuadradoAdapter().parse_search_items("<html>shell</html>", M2_SEARCH_URL) == []


def test_houm_api_parse_yields_normalized_listings():
    raws = HoumAdapter().parse_search_items(_houm_json(), HOUM_SEARCH_URL)
    assert raws, "fixture should yield at least one in-zone listing"

    for raw in raws:
        listing = normalize(raw, portal="houm")
        assert listing.operation == "venta"
        assert listing.property_type == "apartamento"
        assert listing.locality in ("usaquen", "chapinero", "suba")
        assert listing.url.startswith("https://houm.com/co/propiedades/")
        assert listing.price_cop > 0


def test_houm_filters_out_other_communes():
    payload = {
        "results": [
            {
                "uid": "x-1", "id": 1, "comuna": "Teusaquillo", "address": "Calle 45",
                "price": [{"currency": "COP", "value": 100}], "property_details": [{}],
            }
        ]
    }
    raws = HoumAdapter().parse_search_items(json.dumps(payload), HOUM_SEARCH_URL)
    assert raws == []


def test_houm_search_urls_cover_both_operations_and_types():
    urls = HoumAdapter().search_urls("suba")
    assert any("mode=sale" in u for u in urls)
    assert any("mode=rent" in u for u in urls)
    assert any("type=departamento" in u for u in urls)
    assert any("type=casa" in u for u in urls)
