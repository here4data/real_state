"""Generic JSON-LD / meta-tag adapter base.

Most Colombian real-estate portals embed schema.org JSON-LD and OpenGraph
meta tags for SEO. Parsing those (instead of visual markup) gives one
requests-only, pure-Python parser that works across many portals and is
resilient to redesigns. Portal specifics (URL patterns, listing-link regex)
live in small subclasses — see portals.py.
"""
from __future__ import annotations

import json
import re
from html import unescape

LOCALITIES = ("usaquen", "chapinero", "suba")
OPERATIONS = ("venta", "arriendo")
PROPERTY_TYPES = ("apartamento", "casa", "duplex")

_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S
)
_META_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']'
)
_LAT_RE = re.compile(r'"latitude"\s*:\s*"?(-?\d+\.\d+)')
_LON_RE = re.compile(r'"longitude"\s*:\s*"?(-?\d+\.\d+)')
_PRICE_RE = re.compile(r'"price"\s*:\s*"?([\d.,]+)')
_ID_RE = re.compile(r"(\d{5,})")


def _iter_jsonld(html: str):
    for m in _JSONLD_RE.finditer(html):
        try:
            data = json.loads(unescape(m.group(1).strip()))
        except (ValueError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict):
                yield item
                for sub in item.get("@graph", []) or []:
                    if isinstance(sub, dict):
                        yield sub


def _first(*values):
    for v in values:
        if v not in (None, "", []):
            return v
    return None


def _to_num(v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        digits = re.sub(r"[^\d.]", "", v.replace(",", "."))
        try:
            return float(digits) if "." in digits else int(digits)
        except ValueError:
            return None
    if isinstance(v, dict):
        return _to_num(v.get("value"))
    return None


def _guess_from_text(text: str, options: tuple[str, ...], default: str) -> str:
    low = text.lower()
    for opt in options:
        if opt in low or opt.replace("u", "ú") in low:
            return opt
    return default


class GenericPortalAdapter:
    """Subclass and set: portal_name, base_url, listing_href_re,
    search_path(operation, property_path, locality) -> str, status."""

    portal_name = ""
    base_url = ""
    status = "active"          # active | needs_js | blocked | dead | excluded_robots
    status_note = ""
    listing_href_re: re.Pattern | None = None
    # duplex included per project brief (venta/arriendo x apto/casa/duplex)
    property_paths = {"apartamento": "apartamentos", "casa": "casas", "duplex": "duplex"}

    def search_path(self, operation: str, property_path: str, locality: str) -> str:
        raise NotImplementedError

    def search_urls(self, locality: str) -> list[str]:
        if locality not in LOCALITIES:
            raise ValueError(f"unknown locality: {locality!r}")
        if self.status in ("dead", "excluded_robots"):
            return []  # compliance: do not crawl dead domains or robots-disallowed aggregators
        return [
            self.base_url + self.search_path(op, path, locality)
            for op in OPERATIONS
            for path in self.property_paths.values()
        ]

    def parse_listing_urls(self, search_page_html: str) -> list[str]:
        if not self.listing_href_re:
            return []
        urls, seen = [], set()
        for m in self.listing_href_re.finditer(search_page_html):
            href = unescape(m.group(1))
            full = href if href.startswith("http") else self.base_url + href
            full = full.split("?")[0].split("#")[0]
            if full not in seen:
                seen.add(full)
                urls.append(full)
        return urls

    def parse_listing(self, listing_html: str, url: str) -> dict:
        meta = dict(_META_RE.findall(listing_html))
        merged: dict = {}
        for block in _iter_jsonld(listing_html):
            t = str(block.get("@type", ""))
            if any(k in t for k in ("Residence", "Apartment", "House", "Product",
                                    "RealEstate", "Offer", "Place", "Accommodation")):
                merged.update({k: v for k, v in block.items() if v not in (None, "")})

        offers = merged.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = _first(offers.get("price"), merged.get("price"),
                       meta.get("product:price:amount"), meta.get("og:price:amount"))
        if price is None:
            pm = _PRICE_RE.search(listing_html)
            price = pm.group(1) if pm else None

        geo = merged.get("geo") or {}
        lat = _to_num(_first(geo.get("latitude"), merged.get("latitude")))
        lon = _to_num(_first(geo.get("longitude"), merged.get("longitude")))
        if lat is None:
            lm, gm = _LAT_RE.search(listing_html), _LON_RE.search(listing_html)
            lat = float(lm.group(1)) if lm else None
            lon = float(gm.group(1)) if gm else None

        address = merged.get("address")
        if isinstance(address, dict):
            address = address.get("streetAddress") or address.get("addressLocality")

        title = _first(merged.get("name"), meta.get("og:title"), "") or ""
        text_ctx = f"{url} {title}"
        area = merged.get("floorSize")

        idm = _ID_RE.search(url)
        return {
            "portal_listing_id": idm.group(1) if idm else url.rstrip("/").rsplit("/", 1)[-1],
            "url": url,
            "title": title,
            "operation": _guess_from_text(text_ctx, ("arriendo", "venta"), "venta"),
            "property_type": _guess_from_text(text_ctx, ("duplex", "casa", "apartamento"), "apartamento"),
            "locality": _guess_from_text(f"{text_ctx} {address or ''}", LOCALITIES, "usaquen"),
            "address": address if isinstance(address, str) else None,
            "price": _to_num(price),
            "rooms": _to_num(merged.get("numberOfRooms") or merged.get("numberOfBedrooms")),
            "bathrooms": _to_num(merged.get("numberOfBathroomsTotal")),
            "parking_spots": _to_num(_first(
                merged.get("numberOfParkingSpaces"), merged.get("parkingSpaces")
            )),
            "area_m2": _to_num(area),
            "description": _first(merged.get("description"), meta.get("og:description")),
            "photo_urls": _photo_list(merged.get("image"), meta.get("og:image")),
            "floor_plan_urls": [],
            "has_video": False,
            "latitude": lat,
            "longitude": lon,
        }


def _photo_list(image, og_image) -> list[str]:
    photos: list[str] = []
    if isinstance(image, str):
        photos.append(image)
    elif isinstance(image, list):
        photos.extend(i for i in image if isinstance(i, str))
    if og_image and og_image not in photos:
        photos.append(og_image)
    return photos
