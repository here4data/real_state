"""Houm adapter — direct JSON API, no browser needed.

Houm's marketplace is a Next.js SPA whose SEO pages carry only i18n
strings, but the SPA feeds from a public, unauthenticated JSON API
(apis.houm.com/backend/properties/marketplace/) that accepts a lat/long
bounding box. We query one box per target locality — which maps cleanly
onto the project's Calle 80-134 / Carrera 2-60 zone — and get complete
structured listings (price, rooms, baths, m², lat/long, comuna, photos)
in bulk: no search-page scraping, no detail fetches, no Playwright.

Compliance: houm.com/robots.txt explicitly allowlists AI agents
(ClaudeBot, Claude-User, anthropic-ai...) for the whole site, and the
API answers our declared bot User-Agent without complaint.
"""
from __future__ import annotations

import json
import urllib.parse

API_BASE = "https://apis.houm.com/backend/properties/marketplace/"
SITE_BASE = "https://houm.com/co/propiedades/"

_LOCALITIES = ("usaquen", "chapinero", "suba")

# Approximate lat/long boxes per locality, chosen to blanket the brief's
# Calle 80-134 / Carrera 2-60 corridor; results are still filtered by the
# comuna the API reports, so overlap between boxes only costs duplicates
# that the storage upsert absorbs.
_BOUNDS = {
    "usaquen": [[4.66, -74.07], [4.78, -74.01]],
    "chapinero": [[4.62, -74.08], [4.68, -74.03]],
    "suba": [[4.68, -74.13], [4.78, -74.05]],
}

_MODES = {"venta": "sale", "arriendo": "rent"}
_TYPES = {"apartamento": "departamento", "casa": "casa"}

_COMUNA_MAP = {
    "usaquén": "usaquen",
    "usaquen": "usaquen",
    "chapinero": "chapinero",
    "localidad de chapinero": "chapinero",
    "comuna chapinero": "chapinero",
    "suba": "suba",
}

_PAGES = (1, 2, 3)  # page_size=100 → up to 300 per combo, covers current stock


class HoumAdapter:
    portal_name = "houm"
    status = "active"
    status_note = "API JSON pública consultada por bounding box; robots.txt permite agentes de IA."
    fetch_method = "requests"

    def search_urls(self, locality: str) -> list[str]:
        if locality not in _LOCALITIES:
            raise ValueError(f"unknown locality: {locality!r}")
        bounds = urllib.parse.quote(json.dumps(_BOUNDS[locality]))
        urls = []
        for op, mode in _MODES.items():
            for _ptype, api_type in _TYPES.items():
                for page in _PAGES:
                    urls.append(
                        f"{API_BASE}?page_size=100&photos_number=1&mode={mode}"
                        f"&type={api_type}&page={page}&boundings={bounds}"
                    )
        return urls

    def parse_search_items(self, search_html: str, search_url: str) -> list[dict]:
        try:
            payload = json.loads(search_html)
        except ValueError:
            return []
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(search_url).query)
        mode = (qs.get("mode") or ["sale"])[0]
        api_type = (qs.get("type") or ["departamento"])[0]
        operation = "venta" if mode == "sale" else "arriendo"
        property_type = "apartamento" if api_type == "departamento" else "casa"

        raws = []
        for item in payload.get("results", []):
            raw = self._item_to_raw(item, operation, property_type)
            if raw is not None:
                raws.append(raw)
        return raws

    @staticmethod
    def _item_to_raw(item: dict, operation: str, property_type: str) -> dict | None:
        uid = item.get("uid")
        if not uid:
            return None

        comuna = (item.get("comuna") or (item.get("neighborhood") or {}).get("commune") or "")
        locality = _COMUNA_MAP.get(comuna.strip().lower())
        if locality is None:
            return None  # box overlaps other comunas; keep only the brief's three

        prices = item.get("price") or []
        price = None
        for p in prices:
            if p.get("currency") == "COP" and p.get("value"):
                price = p["value"]
                break
        if price is None and prices:
            price = prices[0].get("value")
        if not price:
            return None

        details = (item.get("property_details") or [{}])[0]
        photos = item.get("photos") or []
        photo_urls = [p["url"] for p in photos if p.get("url")]

        return {
            "portal_listing_id": str(item.get("id") or uid),
            "url": SITE_BASE + uid,
            "title": f"{property_type.capitalize()} en {operation} — "
                     f"{(item.get('neighborhood') or {}).get('neighborhood') or comuna}",
            "operation": operation,
            "property_type": property_type,
            "locality": locality,
            "address": item.get("address"),
            "price": price,
            "rooms": details.get("dormitorios"),
            "bathrooms": details.get("banos"),
            "parking_spots": None,  # the marketplace API does not expose it
            "area_m2": details.get("m_construidos") or details.get("m_terreno"),
            "description": None,
            "photo_urls": photo_urls,
            "floor_plan_urls": [],
            "has_video": False,
            "latitude": details.get("latitud"),
            "longitude": details.get("longitud"),
        }

    # Protocol compat — bulk adapters never chase detail pages.
    def parse_listing_urls(self, search_page_html: str) -> list[str]:
        return []

    def parse_listing(self, listing_html: str, url: str) -> dict:
        raise NotImplementedError("bulk adapter: data comes from parse_search_items")
