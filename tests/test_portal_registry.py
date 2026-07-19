"""The system must register (at least) the 10 portals required by the brief,
every adapter must satisfy the PortalAdapter contract, and duplex must be part
of the search matrix."""
from scraper.adapters.portals import ALL_ADAPTERS, crawlable_adapters, registry_summary

REQUIRED_PORTALS = {
    "metrocuadrado", "fincaraiz", "ciencuadras", "properati", "inmuebles24",
    "habi", "mercadolibre", "estrenarvivienda", "mitula", "trovit",
}


def test_all_required_portals_registered():
    assert REQUIRED_PORTALS <= {a.portal_name for a in ALL_ADAPTERS}


def test_adapters_satisfy_contract():
    for a in ALL_ADAPTERS:
        assert a.portal_name
        assert callable(a.search_urls)
        assert callable(a.parse_listing_urls)
        assert callable(a.parse_listing)
        urls = a.search_urls("usaquen")
        assert isinstance(urls, list)
        assert all(u.startswith("http") for u in urls)


def test_duplex_included_in_search_matrix():
    from scraper.adapters.fincaraiz import FincaRaizAdapter
    urls = FincaRaizAdapter().search_urls("usaquen")
    assert any("duplex" in u for u in urls)


def test_dead_and_robots_excluded_portals_not_crawled():
    crawlable = {a.portal_name for a in crawlable_adapters()}
    for name in ("inmuebles24", "mitula", "trovit"):
        assert name not in crawlable


def test_registry_summary_has_status():
    summary = registry_summary()
    assert len(summary) >= 10
    assert all(e["status"] for e in summary)


def test_generic_adapter_parses_jsonld_listing():
    from scraper.adapters.portals import CiencuadrasAdapter
    html = """
    <html><head>
    <meta property="og:title" content="Apartamento en venta Usaquén">
    <meta property="og:image" content="https://img.example/1.jpg">
    <script type="application/ld+json">
    {"@type": "Apartment", "name": "Apartamento en venta Usaquén",
     "numberOfRooms": 3, "numberOfBathroomsTotal": 2,
     "floorSize": {"@type": "QuantitativeValue", "value": 120},
     "geo": {"latitude": 4.7101, "longitude": -74.0301},
     "address": {"streetAddress": "Cra 7 # 120-30, Usaquén"},
     "offers": {"@type": "Offer", "price": 850000000}}
    </script></head><body>
    <a href="/inmueble/apartamento-venta-usaquen-123456">x</a>
    </body></html>
    """
    a = CiencuadrasAdapter()
    urls = a.parse_listing_urls(html)
    assert urls == ["https://www.ciencuadras.com/inmueble/apartamento-venta-usaquen-123456"]
    raw = a.parse_listing(html, urls[0])
    assert raw["price"] == 850000000
    assert raw["rooms"] == 3
    assert raw["latitude"] == 4.7101
    assert raw["locality"] == "usaquen"
    assert raw["property_type"] == "apartamento"
    assert raw["operation"] == "venta"
    assert raw["portal_listing_id"] == "123456"
