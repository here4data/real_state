# Portal Research + First Scraper Adapter — Design Spec

Date: 2026-07-19
Status: Approved for implementation planning

## Purpose

First sub-project of the AI Real Estate Intelligence Bogotá engine. Two deliverables:

1. A comparison matrix of Colombian real estate portals, used to select the MVP portal set.
2. A working Scraper Engine + Adapter architecture, proven end-to-end (fetch → parse → normalize → persist with history) against **one real portal (FincaRaíz)**.

Everything else (additional adapters, cross-portal deduplication, ML pricing/Opportunity Score, map/dashboard frontend, GitHub Pages publishing) is out of scope here and will be separate sub-projects built on top of this foundation.

## Geographic & filter scope (inherited from project brief)

- Bogotá localities only: Usaquén, Chapinero, Suba.
- Approx range: Calle 80–134, Carrera 2–80.
- Compra hasta $1.000.000.000 COP · Arriendo hasta $7.000.000 COP.
- Mínimo 3 habitaciones, mínimo 1 parqueadero.
- Tipos: Apartamento, Casa, Dúplex.

## Portal comparison matrix

Research method: live `robots.txt`, search-results, and listing-detail page fetches per portal (not just search snippets), run 2026-07-19.

| Portal | Bogotá coverage | Photos | Geo coords | Floor plans | Description | Stable URL | HTML consistency | robots.txt | JS-heavy | Anti-bot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FincaRaíz | Confirmed (Usaquén, Chapinero live) | Yes, 8-15 + video | Not in HTML | No | Rich, ~250 words | Yes, numeric ID | High, server-rendered | Permissive (blocks only combined-filter/admin paths) | No | None | **MVP — first adapter** |
| Ciencuadras | Confirmed, highest volume (2,276 Usaquén) | Yes + video | Not in HTML | Yes | Good, ~180 words | Yes, code+ID | High, server-rendered | Very permissive | No | None | **MVP — second adapter** |
| Habi.co | Confirmed | Yes, up to 13 + 360° tour | Address text only | No | Thin | Yes, ID+slug | High, server-rendered | Most permissive of all | No | None | **MVP** (note: iBuyer stock, not full market feed) |
| Metrocuadrado | Large volume (unverified count) | Unknown (JS shell) | Unknown | Unknown | Unknown | Unknown | N/A, client-rendered | Blocks combined-locality URLs, Incapsula referenced | **Yes** | Incapsula bot-mgmt | **MVP** (needs Playwright) |
| GoPlaceIt | Confirmed live Usaquén/Chapinero URLs | Unconfirmed | Unconfirmed | Unconfirmed | Unconfirmed | Yes, stable ID | Unconfirmed (SPA shell) | Permissive at category level, sitemaps declared | **Yes** (React SPA) | None on fetch | **MVP** (needs Playwright; confirmed non-aggregator) |
| Houm.co | Confirmed, rental-focused | Presumed yes | Unconfirmed | Unconfirmed | Presumed good (proptech) | Yes, ID-based | Unconfirmed (JS shell) | Unusually permissive, explicitly allowlists AI bots | **Yes** (Next.js) | None | **MVP** (needs Playwright; rental-skewed) |
| La Haus | Partial (Usaquén search empty in test) | Yes, 3-5 | Not detected | Yes | Mixed, hydration gaps | Weak, slug-only | Medium, hybrid | Permissive on `/venta/...` | Partial | Cloudflare, permissive | **MVP** (new-dev niche, weakest URL stability of the 7) |
| Properati | Volume claimed, unconfirmed | Unknown | Unknown | Unknown | Unknown | Yes (opaque ID) | Unknown | Could not fetch (403) | Unknown | 403 on every fetch this session | **Backlog** — retest with real browser/proxy before deciding |
| estrenarvivienda.com | Confirmed, new-construction only | Presumed | Unconfirmed | Likely | Reasonable | Yes | Unconfirmed (401) | Unreachable (401) | Yes (unrendered template placeholders seen) | Mild (401 on plain fetch) | **Backlog** — narrow niche, low priority |
| Mercado Libre Inmuebles | Unconfirmed (403 on search) | Unknown | Unknown | Unknown | Unknown | Yes, ID-based | Unknown | Not fully checked | Presumed yes | 403, aggressive fingerprinting | **Backlog** — pursue as official API integration, not HTML scraping |
| inmuebles24.com.co / .co | N/A | — | — | — | — | — | — | N/A | — | — | **Excluded** — domain dead, redirects to Navent corporate site |
| biinmo.com | N/A | — | — | — | — | — | — | N/A | — | — | **Excluded** — domain expired/parked (HugeDomains) |
| Vivanuncios Colombia | N/A | — | — | — | — | — | — | N/A | — | — | **Excluded** — domain dead |
| OLX Colombia | N/A | — | — | — | — | — | — | N/A | — | — | **Excluded** — company shut down nationally, July 2023 |
| mitula.com.co | Indexed via search only | — | — | — | Thin | Unstable | — | Blocks 70+ named bots, listing paths disallowed | — | 401 on fetch | **Excluded** — meta-search aggregator, re-links to portals already in the pool |
| trovit.com.co | Indexed via search only | — | — | — | Thin | Unstable | — | Presumed similar to Mitula (same corporate family) | — | 401 on fetch | **Excluded** — confirmed aggregator (search results literally named `...-finca-raiz`) |
| facebook.com/marketplace | N/A | — | — | — | — | No, ephemeral | — | N/A | Yes | Login/ID-verification walls | **Excluded** — no stable schema, high ToS risk |

## MVP portal set (7)

FincaRaíz, Ciencuadras, Habi.co, Metrocuadrado, GoPlaceIt, Houm.co, La Haus.

Build order: **FincaRaíz first** (simplest, richest fields, this sub-project's scope), then Ciencuadras and Habi (same requests+BeautifulSoup approach transfers directly), then the four JS-rendered portals once a Playwright-based fetch path exists (future sub-project).

## Architecture (this sub-project)

```
scraper/
  adapters/
    base.py           # PortalAdapter ABC
    fincaraiz.py       # first concrete adapter
  engine.py             # discover -> fetch -> parse -> normalize -> persist orchestration
  normalizer.py         # raw dict -> canonical Listing (pydantic)
  models.py              # Listing schema (fields per project brief's "INFORMACIÓN A EXTRAER")
  storage/
    db.py                 # SQLite: upsert-with-history
    schema.sql
tests/
  fixtures/fincaraiz/      # saved HTML snapshots for offline unit tests
  test_fincaraiz_adapter.py
  test_normalizer.py
  test_storage.py
pyproject.toml (uv-managed)
```

### PortalAdapter contract

```python
class PortalAdapter(Protocol):
    portal_name: str
    def search_urls(self, locality: str) -> list[str]: ...       # locality in {usaquen, chapinero, suba}
    def parse_listing_urls(self, search_page_html: str) -> list[str]: ...
    def parse_listing(self, listing_html: str, url: str) -> dict: ...
```

Adding a new portal = new file implementing this contract. No changes to `engine.py`, `normalizer.py`, or storage.

FincaRaíz's adapter uses `requests` + `BeautifulSoup`/`lxml` (server-rendered, no Playwright needed). The interface itself stays renderer-agnostic — a future JS-heavy adapter (Metrocuadrado, GoPlaceIt, Houm) implements the same three methods internally using Playwright instead, with zero changes to the engine.

### Storage / history model

- `listings` table: current state per listing (keyed by portal + portal's listing ID).
- `listing_snapshots` table: append-only, one row per scrape run per listing — price, availability, timestamp. Never updated or deleted. This gives the "show listings found between two dates" / price-history requirement from day one, before the historical-database sub-project formalizes it further.

### Coordinates

Not present in any researched portal's rendered HTML. Normalization step geocodes address text (e.g., via Nominatim/OSM) rather than expecting embedded lat/long — flagged as a follow-up to verify empirically (some portals may embed coords in inline JSON/script tags not visible to a markdown-converting fetch).

### Compliance

- Respect each portal's `robots.txt` disallow rules (FincaRaíz: no combined-filter URLs, no admin paths).
- Rate-limit requests; no parallel hammering of a single portal.
- Always store the exact listing detail URL, never a portal homepage/search URL.

## Testing plan

- Unit tests for `fincaraiz.py` adapter against saved HTML fixtures (avoids repeated live traffic during iteration).
- Unit tests for `normalizer.py`: raw dict → canonical `Listing`, including edge cases (missing fields, malformed price strings).
- Unit tests for `storage/db.py`: upsert creates snapshot history, never deletes/overwrites prior rows.
- One live integration check: run the full engine against FincaRaíz for a small sample (10-20 listings) across Usaquén/Chapinero/Suba to confirm the adapter still matches the live site and required fields extract correctly.

## Open follow-ups (not blocking this sub-project)

- Verify Properati's 403s are session-specific before deciding include/exclude.
- Empirically confirm FincaRaíz/Ciencuadras price/room/parking URL query-parameters (only locality-path filtering was live-tested).
- Check whether coordinates exist in inline JSON/script tags on any portal before committing to address-geocoding as the only path.
- Playwright-based adapter path (Metrocuadrado, GoPlaceIt, Houm, La Haus) is a separate future sub-project.
- Mercado Libre: evaluate official API instead of HTML scraping, as a separate track.
