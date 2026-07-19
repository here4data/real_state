"""FincaRaiz adapter — requests + the site's own Next.js data blob.

FincaRaiz server-renders a `<script id="__NEXT_DATA__">` JSON payload on
both search-results and listing-detail pages. That payload already contains
every field this project needs (price, bedrooms, bathrooms, garage, m2,
lat/long, locality) in structured form, so this adapter parses that JSON
directly instead of scraping visual markup — far more robust than CSS
selectors against a page that can restyle at any time.

URL patterns were confirmed against the live site 2026-07-19 (see the design
spec): `/{operation}/{apartamentos|casas}/{locality}/bogota` for search,
`/{slug}/{numeric id}` for listing detail.
"""
from __future__ import annotations

import json
import re

BASE_URL = "https://www.fincaraiz.com.co"

_LOCALITIES = ("usaquen", "chapinero", "suba")
_OPERATIONS = ("venta", "arriendo")
# duplex included per project brief; a 404 on portals without that path is
# tolerated by the engine (logged as an error, run continues).
_PROPERTY_PATHS = {"apartamento": "apartamentos", "casa": "casas", "duplex": "duplex"}

_LISTING_PATH_RE = re.compile(r"/(\d+)/?$")
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
)

_OPERATION_NAME_TO_CODE = {"venta": "venta", "arriendo": "arriendo"}
_PROPERTY_NAME_TO_CODE = {
    "apartamento": "apartamento",
    "casa": "casa",
    "duplex": "duplex",
}


class FincaRaizAdapter:
    portal_name = "fincaraiz"
    status = "active"
    status_note = "Server-rendered __NEXT_DATA__; richest fields incl. lat/long."

    def search_urls(self, locality: str) -> list[str]:
        if locality not in _LOCALITIES:
            raise ValueError(f"unknown locality: {locality!r}")
        return [
            f"{BASE_URL}/{operation}/{path}/{locality}/bogota"
            for operation in _OPERATIONS
            for path in _PROPERTY_PATHS.values()
        ]

    def parse_listing_urls(self, search_page_html: str) -> list[str]:
        try:
            data = self._next_data(search_page_html)
        except ValueError:
            return []
        try:
            items = data["props"]["pageProps"]["fetchResult"]["searchFast"]["data"]
        except (KeyError, TypeError):
            return []

        urls: list[str] = []
        seen: set[str] = set()
        for item in items:
            link = item.get("link")
            if not link:
                continue
            full_url = link if link.startswith("http") else f"{BASE_URL}{link}"
            if full_url not in seen:
                seen.add(full_url)
                urls.append(full_url)
        return urls

    def parse_listing(self, listing_html: str, url: str) -> dict:
        match = _LISTING_PATH_RE.search(_path_of(url))
        if not match:
            raise ValueError(f"could not extract listing id from url: {url}")
        portal_listing_id = match.group(1)

        data = self._next_data(listing_html)
        try:
            item = data["props"]["pageProps"]["data"]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"missing __NEXT_DATA__ property payload: {url}") from exc

        return self._item_to_raw(item, url, portal_listing_id)

    @staticmethod
    def _item_to_raw(item: dict, url: str, portal_listing_id: str) -> dict:
        price = (item.get("price") or {}).get("amount")
        locality_name = (
            (item.get("locations") or {}).get("location_main", {}).get("name")
            or ""
        ).lower()
        # location_main is often a neighbourhood; fall back to scanning the
        # locality list FincaRaiz nests under locations.locality.
        localities = (item.get("locations") or {}).get("locality") or []
        for loc in localities:
            name = (loc.get("name") or "").lower()
            if name in _LOCALITIES:
                locality_name = name
                break

        images = [img.get("image") for img in (item.get("images") or []) if img.get("image")]
        if not images and item.get("img"):
            images = [item["img"]]

        return {
            "portal_listing_id": portal_listing_id,
            "url": url,
            "title": item.get("title") or "",
            "operation": _OPERATION_NAME_TO_CODE.get(
                ((item.get("operation_type") or {}).get("name") or "").lower(), "venta"
            ),
            "property_type": _PROPERTY_NAME_TO_CODE.get(
                ((item.get("property_type") or {}).get("name") or "").lower(), "apartamento"
            ),
            "locality": locality_name if locality_name in _LOCALITIES else "usaquen",
            "address": item.get("address"),
            "price": price,
            "rooms": item.get("bedrooms"),
            "bathrooms": item.get("bathrooms"),
            "parking_spots": item.get("garage"),
            "area_m2": item.get("m2") or item.get("m2Built"),
            "description": item.get("description"),
            "photo_urls": images,
            "floor_plan_urls": [],
            "has_video": bool(item.get("has_video")),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
        }

    @staticmethod
    def _next_data(html: str) -> dict:
        match = _NEXT_DATA_RE.search(html)
        if not match:
            raise ValueError("__NEXT_DATA__ script not found in page")
        return json.loads(match.group(1))


def _path_of(url: str) -> str:
    return url[len(BASE_URL):] if url.startswith(BASE_URL) else url
