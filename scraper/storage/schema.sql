CREATE TABLE IF NOT EXISTS listings (
    portal TEXT NOT NULL,
    portal_listing_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    operation TEXT NOT NULL,
    property_type TEXT NOT NULL,
    locality TEXT NOT NULL,
    address TEXT,
    price_cop INTEGER NOT NULL,
    rooms INTEGER,
    bathrooms INTEGER,
    parking_spots INTEGER,
    area_m2 REAL,
    description TEXT,
    photo_urls TEXT NOT NULL DEFAULT '[]',
    floor_plan_urls TEXT NOT NULL DEFAULT '[]',
    has_video INTEGER NOT NULL DEFAULT 0,
    latitude REAL,
    longitude REAL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (portal, portal_listing_id)
);

CREATE TABLE IF NOT EXISTS listing_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portal TEXT NOT NULL,
    portal_listing_id TEXT NOT NULL,
    price_cop INTEGER NOT NULL,
    scraped_at TEXT NOT NULL,
    FOREIGN KEY (portal, portal_listing_id) REFERENCES listings (portal, portal_listing_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_listing
    ON listing_snapshots (portal, portal_listing_id, scraped_at);
