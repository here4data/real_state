"""Canonical Listing schema shared by every portal adapter."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Operation(str, Enum):
    VENTA = "venta"
    ARRIENDO = "arriendo"


class PropertyType(str, Enum):
    APARTAMENTO = "apartamento"
    CASA = "casa"
    DUPLEX = "duplex"


class Locality(str, Enum):
    USAQUEN = "usaquen"
    CHAPINERO = "chapinero"
    SUBA = "suba"


class Listing(BaseModel):
    portal: str
    portal_listing_id: str
    url: str

    title: str
    operation: Operation
    property_type: PropertyType
    locality: Locality
    address: Optional[str] = None

    price_cop: int
    rooms: Optional[int] = None
    bathrooms: Optional[int] = None
    parking_spots: Optional[int] = None
    area_m2: Optional[float] = None

    description: Optional[str] = None
    photo_urls: list[str] = Field(default_factory=list)
    floor_plan_urls: list[str] = Field(default_factory=list)
    has_video: bool = False

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    scraped_at: datetime

    @field_validator("price_cop")
    @classmethod
    def price_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("price_cop must be positive")
        return v
