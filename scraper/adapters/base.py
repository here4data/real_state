"""Adapter contract. A new portal = a new file implementing this Protocol;
engine.py, normalizer.py and storage never change."""
from __future__ import annotations

from typing import Protocol


class PortalAdapter(Protocol):
    portal_name: str

    def search_urls(self, locality: str) -> list[str]:
        """locality in {"usaquen", "chapinero", "suba"}."""
        ...

    def parse_listing_urls(self, search_page_html: str) -> list[str]:
        ...

    def parse_listing(self, listing_html: str, url: str) -> dict:
        """Return a raw dict consumable by scraper.normalizer.normalize()."""
        ...
