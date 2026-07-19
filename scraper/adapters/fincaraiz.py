"""FincaRaiz adapter — server-rendered HTML, requests + BeautifulSoup.

Selectors target FincaRaiz's listing-detail and search-results markup as
documented in docs/superpowers/specs/2026-07-19-portal-research-and-scraper-design.md:
numeric-ID detail URLs, JSON-LD product data on the detail page, and a plain
anchor grid on the search-results page.
"""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

BASE_URL = "https://www.fincaraiz.com.co"

_LOCALITY_PATHS = {
    "usaquen": "apartamentos-y-casas/venta/bogota/usaquen",
    "chapinero": "apartamentos-y-casas/venta/bogota/chapinero",
    "suba": "apartamentos-y-casas/venta/bogota/suba",
}

_LISTING_HREF_RE = re.compile(r"/inmueble/.*-(\d+)$")


class FincaRaizAdapter:
    portal_name = "fincaraiz"

    def search_urls(self, locality: str) -> list[str]:
        try:
            path = _LOCALITY_PATHS[locality]
        except KeyError as exc:
            raise ValueError(f"unknown locality: {locality!r}") from exc
        return [f"{BASE_URL}/{path}"]

    def parse_listing_urls(self, search_page_html: str) -> list[str]:
        soup = BeautifulSoup(search_page_html, "lxml")
        urls: list[str] = []
        seen: set[str] = set()
        for anchor in soup.select("a[href]"):
            href = str(anchor["href"])
            if not _LISTING_HREF_RE.search(href):
                continue
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            if full_url not in seen:
                seen.add(full_url)
                urls.append(full_url)
        return urls

    def parse_listing(self, listing_html: str, url: str) -> dict:
        soup = BeautifulSoup(listing_html, "lxml")

        listing_id_match = _LISTING_HREF_RE.search(url)
        if not listing_id_match:
            raise ValueError(f"could not extract listing id from url: {url}")
        portal_listing_id = listing_id_match.group(1)

        json_ld = self._extract_json_ld(soup)

        title = (json_ld.get("name") or self._text(soup, "h1") or "").strip()
        description = (json_ld.get("description") or self._text(soup, "[data-testid='description']") or "").strip()

        offers = json_ld.get("offers") or {}
        price = offers.get("price") or self._text(soup, "[data-testid='price']")

        photo_urls = self._photo_urls(json_ld, soup)

        attrs = self._attributes(soup)

        return {
            "portal_listing_id": portal_listing_id,
            "url": url,
            "title": title,
            "operation": attrs.get("operation", "venta"),
            "property_type": attrs.get("property_type", "apartamento"),
            "locality": attrs.get("locality", "usaquen"),
            "address": attrs.get("address"),
            "price": price,
            "rooms": attrs.get("rooms"),
            "bathrooms": attrs.get("bathrooms"),
            "parking_spots": attrs.get("parking_spots"),
            "area_m2": attrs.get("area_m2"),
            "description": description,
            "photo_urls": photo_urls,
            "floor_plan_urls": [],
            "has_video": bool(soup.select_one("[data-testid='video-player'], video")),
        }

    @staticmethod
    def _extract_json_ld(soup: BeautifulSoup) -> dict:
        for tag in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(tag.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, dict) and data.get("@type") in ("Product", "House", "Apartment"):
                return data
        return {}

    @staticmethod
    def _text(soup: BeautifulSoup, selector: str) -> str | None:
        node = soup.select_one(selector)
        return node.get_text(strip=True) if node else None

    @staticmethod
    def _photo_urls(json_ld: dict, soup: BeautifulSoup) -> list[str]:
        images = json_ld.get("image")
        if isinstance(images, list) and images:
            return images
        if isinstance(images, str):
            return [images]
        return [str(img["src"]) for img in soup.select("[data-testid='gallery'] img[src]")]

    @staticmethod
    def _attributes(soup: BeautifulSoup) -> dict:
        result: dict = {}
        for item in soup.select("[data-testid='feature']"):
            key = item.get("data-feature-key")
            value = item.get_text(strip=True)
            if not key:
                continue
            if key == "rooms":
                result["rooms"] = _to_int(value)
            elif key == "bathrooms":
                result["bathrooms"] = _to_int(value)
            elif key == "parking_spots":
                result["parking_spots"] = _to_int(value)
            elif key == "area_m2":
                result["area_m2"] = _to_float(value)
            elif key == "operation":
                result["operation"] = value.lower()
            elif key == "property_type":
                result["property_type"] = value.lower()
            elif key == "locality":
                result["locality"] = value.lower()
            elif key == "address":
                result["address"] = value
        return result


def _to_int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _to_float(value: str) -> float | None:
    match = re.search(r"[\d.]+", value)
    return float(match.group(0)) if match else None
