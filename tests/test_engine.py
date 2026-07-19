from pathlib import Path

import responses

from scraper.adapters.fincaraiz import FincaRaizAdapter
from scraper.engine import Engine, Fetcher
from scraper.storage.db import Storage

FIXTURES = Path(__file__).parent / "fixtures" / "fincaraiz"


@responses.activate
def test_engine_run_persists_valid_listings_and_skips_bad_ones():
    search_html = (FIXTURES / "search_usaquen.html").read_text(encoding="utf-8")
    good_html = (FIXTURES / "listing_193410777.html").read_text(encoding="utf-8")
    bad_html = (FIXTURES / "listing_malformed.html").read_text(encoding="utf-8")

    for search_url in FincaRaizAdapter().search_urls("usaquen"):
        responses.add(responses.GET, search_url, body=search_html, status=200)

    responses.add(
        responses.GET,
        "https://www.fincaraiz.com.co/apartamento-en-venta-en-cedritos-bogota/193410777",
        body=good_html,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://www.fincaraiz.com.co/serraclara-apartamento-en-venta-en-villas-de-aranjuez-bogota/193068462",
        body=bad_html,
        status=200,
    )

    storage = Storage(":memory:")
    engine = Engine(FincaRaizAdapter(), storage, fetcher=Fetcher(rate_limit_seconds=0))

    stats = engine.run(["usaquen"])

    assert stats.localities_scanned == 1
    # 6 search pages (venta/arriendo x apartamentos/casas/duplex), each yielding
    # the same 2 listing URLs from the fixture.
    assert stats.listings_found == 12
    assert stats.listings_persisted >= 1
    assert stats.listings_skipped >= 1
    assert storage.count_listings() == 1

    storage.close()
