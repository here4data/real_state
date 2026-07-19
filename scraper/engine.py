"""discover -> fetch -> parse -> normalize -> persist orchestration.

Adding a portal only means writing a new PortalAdapter; this module never
changes.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import requests

from scraper.adapters.base import PortalAdapter
from scraper.normalizer import NormalizationError, normalize
from scraper.storage.db import Storage

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {"User-Agent": "real-estate-intelligence-bogota-bot/0.1"}
DEFAULT_RATE_LIMIT_SECONDS = 1.0


@dataclass
class RunStats:
    localities_scanned: int = 0
    listings_found: int = 0
    listings_persisted: int = 0
    listings_skipped: int = 0
    errors: list[str] = field(default_factory=list)


class Fetcher:
    """Thin, rate-limited requests wrapper — no parallel hammering of a portal."""

    def __init__(self, rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS, session: requests.Session | None = None):
        self._rate_limit_seconds = rate_limit_seconds
        self._session = session or requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)
        self._last_request_at: float | None = None

    def get(self, url: str) -> str:
        """Fetch URL via requests."""
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            wait = self._rate_limit_seconds - elapsed
            if wait > 0:
                time.sleep(wait)
        response = self._session.get(url, timeout=30)
        response.raise_for_status()
        self._last_request_at = time.monotonic()
        return response.text


class Engine:
    """browser_fetcher is only consulted when the adapter declares
    fetch_method == "playwright"; passing one in lets a multi-portal run
    share a single Chromium instance across engines."""

    def __init__(
        self,
        adapter: PortalAdapter,
        storage: Storage,
        fetcher: Fetcher | None = None,
        browser_fetcher=None,
    ):
        self.adapter = adapter
        self.storage = storage
        self.fetcher = fetcher or Fetcher()
        self.browser_fetcher = browser_fetcher

    def run(self, localities: list[str]) -> RunStats:
        stats = RunStats()
        for locality in localities:
            stats.localities_scanned += 1
            for search_url in self.adapter.search_urls(locality):
                self._process_search_page(search_url, stats)
        return stats

    def _fetch(self, url: str) -> str:
        if getattr(self.adapter, "fetch_method", "requests") == "playwright":
            if self.browser_fetcher is None:
                raise RuntimeError(
                    f"{self.adapter.portal_name} needs a BrowserFetcher (fetch_method=playwright)"
                )
            return self.browser_fetcher.get(
                url, wait_selector=getattr(self.adapter, "wait_selector", None)
            )
        return self.fetcher.get(url)

    def _process_search_page(self, search_url: str, stats: RunStats) -> None:
        try:
            search_html = self._fetch(search_url)
        except Exception as exc:
            stats.errors.append(f"search page fetch failed ({search_url}): {exc}")
            return

        # Bulk adapters (Metrocuadrado flight data, Houm API) return complete
        # raw listings straight from the search response — no detail fetches.
        parse_items = getattr(self.adapter, "parse_search_items", None)
        if parse_items is not None:
            raws = parse_items(search_html, search_url)
            stats.listings_found += len(raws)
            for raw in raws:
                self._persist_raw(raw, search_url, stats)
            return

        listing_urls = self.adapter.parse_listing_urls(search_html)
        # JS portals cost seconds per detail page; adapters can cap how many
        # details we chase per search page to keep full builds bounded.
        cap = getattr(self.adapter, "max_listings_per_search", None)
        if cap:
            listing_urls = listing_urls[:cap]
        stats.listings_found += len(listing_urls)

        for url in listing_urls:
            self._process_listing(url, stats)

    def _process_listing(self, url: str, stats: RunStats) -> None:
        try:
            listing_html = self._fetch(url)
        except Exception as exc:
            stats.errors.append(f"listing fetch failed ({url}): {exc}")
            stats.listings_skipped += 1
            return

        try:
            raw = self.adapter.parse_listing(listing_html, url)
        except (NormalizationError, ValueError) as exc:
            stats.errors.append(f"normalization failed ({url}): {exc}")
            stats.listings_skipped += 1
            return
        self._persist_raw(raw, url, stats)

    def _persist_raw(self, raw: dict, source_url: str, stats: RunStats) -> None:
        try:
            listing = normalize(raw, portal=self.adapter.portal_name)
        except (NormalizationError, ValueError) as exc:
            stats.errors.append(f"normalization failed ({source_url}): {exc}")
            stats.listings_skipped += 1
            return
        self.storage.upsert_listing(listing)
        stats.listings_persisted += 1
