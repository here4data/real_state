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
    def __init__(self, adapter: PortalAdapter, storage: Storage, fetcher: Fetcher | None = None):
        self.adapter = adapter
        self.storage = storage
        self.fetcher = fetcher or Fetcher()

    def run(self, localities: list[str]) -> RunStats:
        stats = RunStats()
        for locality in localities:
            stats.localities_scanned += 1
            for search_url in self.adapter.search_urls(locality):
                self._process_search_page(search_url, stats)
        return stats

    def _process_search_page(self, search_url: str, stats: RunStats) -> None:
        try:
            search_html = self.fetcher.get(search_url)
        except requests.RequestException as exc:
            stats.errors.append(f"search page fetch failed ({search_url}): {exc}")
            return

        listing_urls = self.adapter.parse_listing_urls(search_html)
        stats.listings_found += len(listing_urls)

        for url in listing_urls:
            self._process_listing(url, stats)

    def _process_listing(self, url: str, stats: RunStats) -> None:
        try:
            listing_html = self.fetcher.get(url)
        except requests.RequestException as exc:
            stats.errors.append(f"listing fetch failed ({url}): {exc}")
            stats.listings_skipped += 1
            return

        try:
            raw = self.adapter.parse_listing(listing_html, url)
            listing = normalize(raw, portal=self.adapter.portal_name)
        except (NormalizationError, ValueError) as exc:
            stats.errors.append(f"normalization failed ({url}): {exc}")
            stats.listings_skipped += 1
            return

        self.storage.upsert_listing(listing)
        stats.listings_persisted += 1
