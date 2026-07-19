# AI Real Estate Intelligence Bogotá — Scraper Engine

First sub-project: a portal comparison matrix and a working scraper engine
(fetch → parse → normalize → persist with history), proven end-to-end
against one real portal, FincaRaíz. Design spec:
[docs/superpowers/specs/2026-07-19-portal-research-and-scraper-design.md](docs/superpowers/specs/2026-07-19-portal-research-and-scraper-design.md).

## Setup

```bash
uv sync --extra dev
```

## Run tests

```bash
uv run pytest -q
```

## Run the FincaRaíz scraper

```python
from scraper.adapters.fincaraiz import FincaRaizAdapter
from scraper.engine import Engine
from scraper.storage.db import Storage

storage = Storage("listings.db")
engine = Engine(FincaRaizAdapter(), storage)
stats = engine.run(["usaquen", "chapinero", "suba"])
print(stats)
```

Listings and price/availability history persist to `listings.db`
(`listings` = current state, `listing_snapshots` = append-only history).

## Adding a new portal

Implement `scraper.adapters.base.PortalAdapter`'s three methods
(`search_urls`, `parse_listing_urls`, `parse_listing`) in a new file under
`scraper/adapters/`. `engine.py`, `normalizer.py`, and storage never change.

## Status

This is a backend engine with no web frontend or hosted endpoint yet — there
is no public link to click. It runs locally or in CI (`.github/workflows/ci.yml`)
via the commands above. The map/dashboard frontend and GitHub Pages
publishing are out of scope for this sub-project (see the design spec's
"out of scope" section) and will ship as a separate sub-project.
