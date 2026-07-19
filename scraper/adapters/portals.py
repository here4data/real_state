"""One adapter per requested portal (10), all on the GenericPortalAdapter
JSON-LD strategy except FincaRaiz (dedicated __NEXT_DATA__ adapter).

Status per the 2026-07-19 portal research spec:
  active           — scrapeable with requests today
  needs_js         — client-rendered / bot-managed; requests may return a shell.
                     Adapter still works whenever JSON-LD is server-emitted;
                     full support needs a Playwright fetcher (same contract).
  blocked          — 403/401 on plain fetch this session; retried best-effort
  dead             — domain gone; registered for traceability, never crawled
  excluded_robots  — aggregator whose robots.txt disallows listing paths;
                     registered but never crawled (compliance)
"""
from __future__ import annotations

import re

from scraper.adapters.fincaraiz import FincaRaizAdapter
from scraper.adapters.generic import GenericPortalAdapter
from scraper.adapters.houm import HoumAdapter
from scraper.adapters.metrocuadrado import MetrocuadradoAdapter


class CiencuadrasAdapter(GenericPortalAdapter):
    portal_name = "ciencuadras"
    base_url = "https://www.ciencuadras.com"
    status = "active"
    property_paths = {"apartamento": "apartamento", "casa": "casa", "duplex": "apartamento"}
    listing_href_re = re.compile(r'href="((?:https://www\.ciencuadras\.com)?/inmueble/[^"]+)"')

    def search_path(self, operation, property_path, locality):
        return f"/{operation}/{property_path}/bogota/{locality}"


class ProperatiAdapter(GenericPortalAdapter):
    portal_name = "properati"
    base_url = "https://www.properati.com.co"
    status = "blocked"
    status_note = "403 on plain fetch in research session; retried each run."
    listing_href_re = re.compile(r'href="((?:https://www\.properati\.com\.co)?/detalle/[^"]+)"')

    def search_path(self, operation, property_path, locality):
        op = "venta" if operation == "venta" else "arriendo"
        return f"/s/{locality}-bogota-d-c/{property_path}/{op}"


class Inmuebles24Adapter(GenericPortalAdapter):
    portal_name = "inmuebles24"
    base_url = "https://www.inmuebles24.com.co"
    status = "dead"
    status_note = "Domain redirects to Navent corporate site; nothing to crawl."

    def search_path(self, operation, property_path, locality):
        return f"/{operation}/{property_path}/{locality}"


class HabiAdapter(GenericPortalAdapter):
    portal_name = "habi"
    base_url = "https://habi.co"
    status = "blocked"
    status_note = "Redirect loop (>30 redirects) en la ruta de búsqueda; verificado 2026-07."
    property_paths = {"apartamento": "apartamentos", "casa": "casas", "duplex": "apartamentos"}
    listing_href_re = re.compile(r'href="((?:https://habi\.co)?/(?:comprar|inmueble)[^"]+)"')

    def search_path(self, operation, property_path, locality):
        return f"/venta-{property_path}/bogota/{locality}"

    def search_urls(self, locality):
        # venta-only portal: drop the arriendo half of the matrix
        return [u for u in super().search_urls(locality) if "arriendo" not in u]


class GoPlaceItAdapter(GenericPortalAdapter):
    portal_name = "goplaceit"
    base_url = "https://www.goplaceit.com"
    status = "dead"
    status_note = "Portal cerrado: homepage redirige a /404 y solo queda una página de despedida (verificado 2026-07)."

    def search_path(self, operation, property_path, locality):
        return f"/{operation}-{property_path}/bogota/{locality}"


class LaHausAdapter(GenericPortalAdapter):
    portal_name = "lahaus"
    base_url = "https://www.lahaus.com"
    status = "dead"
    status_note = ("Sin inventario rastreable: sitemap solo trae guías/contenido, la búsqueda "
                   "renderiza vacía y no llama ninguna API de listados (verificado 2026-07; "
                   "pivote del negocio a proyectos nuevos).")

    def search_path(self, operation, property_path, locality):
        return f"/{operation}/{property_path}/bogota/{locality}"


class MercadoLibreAdapter(GenericPortalAdapter):
    portal_name = "mercadolibre"
    base_url = "https://listado.mercadolibre.com.co"
    status = "blocked"
    status_note = "Aggressive fingerprinting (403); official API is the durable path."
    property_paths = {"apartamento": "apartamentos", "casa": "casas", "duplex": "casas"}
    listing_href_re = re.compile(r'href="(https://(?:apartamento|casa|inmueble|articulo)[^"]*mercadolibre\.com\.co/MCO-[^"]+)"')

    def search_path(self, operation, property_path, locality):
        return f"/inmuebles/{property_path}/{operation}/bogota-dc/{locality}/"


class EstrenarViviendaAdapter(GenericPortalAdapter):
    portal_name = "estrenarvivienda"
    base_url = "https://www.estrenarvivienda.com"
    status = "blocked"
    status_note = "401 on plain fetch; new-construction niche."
    listing_href_re = re.compile(r'href="((?:https://www\.estrenarvivienda\.com)?/proyecto[^"]+)"')

    def search_path(self, operation, property_path, locality):
        return f"/proyectos-vivienda/bogota/{locality}"


class MitulaAdapter(GenericPortalAdapter):
    portal_name = "mitula"
    base_url = "https://casas.mitula.com.co"
    status = "excluded_robots"
    status_note = "Meta-search aggregator; robots.txt disallows listing paths. Not crawled."

    def search_path(self, operation, property_path, locality):
        return f"/searchRE/q-{locality}-bogota"


class TrovitAdapter(GenericPortalAdapter):
    portal_name = "trovit"
    base_url = "https://casas.trovit.com.co"
    status = "excluded_robots"
    status_note = "Aggregator re-linking to portals already in the pool. Not crawled."

    def search_path(self, operation, property_path, locality):
        return f"/{locality}-bogota"


ALL_ADAPTERS = [
    FincaRaizAdapter(),
    MetrocuadradoAdapter(),
    CiencuadrasAdapter(),
    ProperatiAdapter(),
    Inmuebles24Adapter(),
    HabiAdapter(),
    GoPlaceItAdapter(),
    HoumAdapter(),
    LaHausAdapter(),
    MercadoLibreAdapter(),
    EstrenarViviendaAdapter(),
    MitulaAdapter(),
    TrovitAdapter(),
]

CRAWLABLE_STATUSES = ("active", "needs_js", "blocked")


def crawlable_adapters():
    return [a for a in ALL_ADAPTERS if getattr(a, "status", "active") in CRAWLABLE_STATUSES]


def registry_summary() -> list[dict]:
    return [
        {
            "portal": a.portal_name,
            "status": getattr(a, "status", "active"),
            "note": getattr(a, "status_note", ""),
        }
        for a in ALL_ADAPTERS
    ]
