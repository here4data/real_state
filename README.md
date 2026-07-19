# AI Real Estate Intelligence Bogotá

A scraper engine + adapter architecture, proven end-to-end against FincaRaíz,
feeding a static web GUI you can browse in the browser — no backend server,
no build step. Design spec:
[docs/superpowers/specs/2026-07-19-portal-research-and-scraper-design.md](docs/superpowers/specs/2026-07-19-portal-research-and-scraper-design.md).

## Live site

**https://here4data.github.io/real_state/**

Search/filter panel over real, currently-listed properties in Usaquén,
Chapinero and Suba — venta ≤ $1.000M COP, arriendo ≤ $7M COP, ≥3 habitaciones,
≥1 parqueadero, apartamento/casa/dúplex (the filters fixed in the project
brief). Deployed automatically from `docs/` by
`.github/workflows/pages.yml` on every push to `main`.

## Architecture

```
scraper/adapters/fincaraiz.py   # requests + the site's own __NEXT_DATA__ JSON
scraper/engine.py               # discover -> fetch -> parse -> normalize -> persist
scraper/normalizer.py           # raw dict -> canonical Listing (pydantic)
scraper/storage/db.py           # SQLite: upsert-with-history
scripts/build_dataset.py        # live scrape -> listings.db + docs/data/listings.json
docs/                           # static GUI (GitHub Pages root): index.html, app.js, style.css
tests/                          # unit + integration tests, offline fixtures
```

## Setup

```bash
uv sync --extra dev
```

## Run tests

```bash
uv run pytest -q
```

## Refresh the dataset (live scrape)

```bash
uv run python scripts/build_dataset.py
```

Scrapes FincaRaíz (rate-limited, 1 req/s) for Usaquén, Chapinero and Suba,
persists full history to `listings.db` (`listings` = current state,
`listing_snapshots` = append-only price/availability history), and writes
the filtered dataset the GUI reads to `docs/data/listings.json`. Commit and
push `docs/data/listings.json` to publish the refresh.

## Adding a new portal

Implement `scraper.adapters.base.PortalAdapter`'s three methods
(`search_urls`, `parse_listing_urls`, `parse_listing`) in a new file under
`scraper/adapters/`. `engine.py`, `normalizer.py`, and storage never change.

## Portal coverage

Per the design spec's research matrix, FincaRaíz, Ciencuadras and Habi.co are
server-rendered and reachable with `requests` + JSON/HTML parsing (this
sub-project ships FincaRaíz; Ciencuadras/Habi follow the same adapter
pattern). Metrocuadrado, GoPlaceIt, Houm.co and La Haus are JS-rendered and
need a Playwright-based fetch path — flagged in the spec as a separate
future sub-project, since the adapter interface stays renderer-agnostic and
requires no engine changes when that lands.
