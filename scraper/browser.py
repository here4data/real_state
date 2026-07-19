"""Shared-browser Playwright fetcher for JS-rendered portals.

The naive approach (launch Chromium per page + wait_until="networkidle")
costs 10-20s per page and made full builds impractical. This module gets
that down to ~1-3s per page with three tactics:

1. One browser + one context for the whole run (launch cost paid once).
2. Route-level resource blocking: images, media, fonts, stylesheets and
   ad/analytics domains are aborted, so "network idle" arrives fast and
   bandwidth stays tiny.
3. domcontentloaded + wait_for_selector on the portal's listing-link
   pattern instead of blind networkidle — we wait exactly for the data
   we need, not for every tracker to settle.

A real-Chrome user agent plus hiding navigator.webdriver gets past
Incapsula's basic tier on Metrocuadrado; no CAPTCHA solving or other
evasion is attempted — if a portal actively blocks, it stays blocked.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}
_BLOCKED_DOMAIN_SNIPPETS = (
    "googlesyndication", "doubleclick", "google-analytics", "googletagmanager",
    "facebook", "hotjar", "clarity.ms", "adsystem", "criteo", "taboola",
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class BrowserFetcher:
    """Lazily starts one headless Chromium and reuses it for every page."""

    def __init__(self, page_timeout_ms: int = 25_000):
        self._page_timeout_ms = page_timeout_ms
        self._pw = None
        self._browser = None
        self._context = None

    def _ensure_started(self) -> None:
        if self._context is not None:
            return
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            user_agent=_UA,
            locale="es-CO",
            viewport={"width": 1366, "height": 900},
        )
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._context.route("**/*", self._route)

    @staticmethod
    def _route(route) -> None:
        req = route.request
        if req.resource_type in _BLOCKED_RESOURCE_TYPES:
            route.abort()
            return
        url = req.url
        if any(s in url for s in _BLOCKED_DOMAIN_SNIPPETS):
            route.abort()
            return
        route.continue_()

    def get(self, url: str, wait_selector: str | None = None) -> str:
        """Render url and return HTML. wait_selector, when given, is the
        CSS selector whose presence means the data we need has hydrated."""
        self._ensure_started()
        assert self._context is not None
        page = self._context.new_page()
        try:
            page.set_default_timeout(self._page_timeout_ms)
            page.goto(url, wait_until="domcontentloaded")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=8_000)
                except Exception:
                    # Selector never appeared (empty results page or layout
                    # change) — return whatever rendered so the caller's
                    # parser decides; an empty parse is logged upstream.
                    logger.debug("wait_selector %r timed out on %s", wait_selector, url)
            else:
                page.wait_for_timeout(1_500)
            return page.content()
        finally:
            page.close()

    def close(self) -> None:
        for obj in (self._context, self._browser):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._pw = self._browser = self._context = None

    def __enter__(self) -> "BrowserFetcher":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
