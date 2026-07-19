"""Metrocuadrado adapter — Playwright search pages, zero detail fetches.

Metrocuadrado's results pages are a Next.js app behind Incapsula: plain
requests get a JS shell, but a headless render (see scraper/browser.py)
passes and the page then contains the app's flight data
(`self.__next_f.push`), which embeds an `initialResults` object with the
full card JSON for every result on the page: price, built area, rooms,
bathrooms, garages, stratum, admin fee, lat/long and description.

Parsing that blob makes this a *bulk* adapter (parse_search_items): one
rendered search page yields ~50 complete listings and no per-listing
detail fetches are needed — the whole portal costs a handful of renders.
"""
from __future__ import annotations

import codecs
import json
import re

BASE_URL = "https://www.metrocuadrado.com"

_LOCALITIES = ("usaquen", "chapinero", "suba")
_OPERATIONS = ("venta", "arriendo")
_PROPERTY_PATHS = {"apartamento": "apartamento", "casa": "casa"}

_TYPE_MAP = {"apartamento": "apartamento", "casa": "casa", "apartaestudio": "apartamento"}

_LOCALITY_IN_URL_RE = re.compile(r"/bogota/([a-z-]+)/?")


def _extract_initial_results(search_html: str) -> dict | None:
    """Unescape the flight-data JS strings and brace-match initialResults."""
    if '"initialResults"' not in search_html.replace('\\"', '"'):
        return None
    un = search_html.replace('\\"', '"').replace("\\\\", "\\")
    un = codecs.decode(un, "unicode_escape", errors="ignore")
    i = un.find('"initialResults":')
    if i == -1:
        return None
    j = un.find("{", i)
    depth = 0
    for k in range(j, len(un)):
        if un[k] == "{":
            depth += 1
        elif un[k] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(un[j:k + 1], strict=False)
                except ValueError:
                    return None
    return None


def _to_int(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


class MetrocuadradoAdapter:
    portal_name = "metrocuadrado"
    status = "active"
    status_note = "Render Playwright de la página de resultados; datos completos vía flight data (bulk)."
    fetch_method = "playwright"
    wait_selector = "a[href*='/inmueble/']"

    def search_urls(self, locality: str) -> list[str]:
        if locality not in _LOCALITIES:
            raise ValueError(f"unknown locality: {locality!r}")
        return [
            f"{BASE_URL}/{path}/{op}/bogota/{locality}/"
            for op in _OPERATIONS
            for path in _PROPERTY_PATHS.values()
        ]

    def parse_search_items(self, search_html: str, search_url: str) -> list[dict]:
        data = _extract_initial_results(search_html)
        if not data:
            return []
        m = _LOCALITY_IN_URL_RE.search(search_url)
        locality = m.group(1) if m else "usaquen"
        if locality not in _LOCALITIES:
            locality = "usaquen"

        raws = []
        for card in data.get("results", []):
            raw = self._card_to_raw(card, locality)
            if raw is not None:
                raws.append(raw)
        return raws

    @staticmethod
    def _card_to_raw(card: dict, locality: str) -> dict | None:
        listing_id = card.get("midinmueble")
        link = card.get("link") or (card.get("data") or {}).get("murldetalle")
        if not listing_id or not link:
            return None

        tipo = ((card.get("mtipoinmueble") or {}).get("nombre") or "").strip().lower()
        property_type = _TYPE_MAP.get(tipo)
        if property_type is None:
            return None

        operation = (card.get("mtiponegocio") or "").strip().lower()
        if operation not in ("venta", "arriendo"):
            return None
        price = card.get("mvalorventa") if operation == "venta" else card.get("mvalorarriendo")
        if not price:
            return None

        loc = card.get("localizacion") or {}
        extra = card.get("data") or {}
        photo = card.get("imageLink")

        return {
            "portal_listing_id": str(listing_id),
            "url": BASE_URL + link.split("?")[0],
            "title": card.get("title") or "",
            "operation": operation,
            "property_type": property_type,
            "locality": locality,
            "address": card.get("mnombrecomunbarrio") or card.get("mbarrio"),
            "price": price,
            "rooms": _to_int(card.get("mnrocuartos")),
            "bathrooms": _to_int(card.get("mnrobanos")),
            "parking_spots": _to_int(card.get("mnrogarajes")),
            "area_m2": card.get("mareac") or card.get("marea"),
            "description": card.get("comment"),
            "photo_urls": [photo] if photo else [],
            "floor_plan_urls": [],
            "has_video": False,
            "latitude": loc.get("lat"),
            "longitude": loc.get("lon"),
            "stratum": _to_int(card.get("estrato")),
            "common_expenses_cop": _to_int(extra.get("mvaloradministracion")),
        }

    # Protocol compat — bulk adapters never chase detail pages.
    def parse_listing_urls(self, search_page_html: str) -> list[str]:
        return []

    def parse_listing(self, listing_html: str, url: str) -> dict:
        raise NotImplementedError("bulk adapter: data comes from parse_search_items")
