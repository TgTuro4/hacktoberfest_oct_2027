"""Coordinates for events. Known venues come from the local venue table (no network). Remaining street
addresses are geocoded once with OpenStreetMap Nominatim and cached forever in the local database."""

from __future__ import annotations

import logging
import math
import re
import time
from typing import Callable

from ..config import UMD_CENTER, Settings
from ..http import HttpClient
from ..models import Event

log = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Rough box around the DC/MD area so a bad match in another state is ignored.
_BOUNDS = (38.6, 39.4, -77.4, -76.5)


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_from_campus(lat: float | None, lon: float | None) -> float | None:
    if lat is None or lon is None:
        return None
    return round(haversine_miles(UMD_CENTER[0], UMD_CENTER[1], lat, lon), 2)


def geocodable(address: str | None) -> str | None:
    """Only full street addresses are worth a lookup ('4310 Gallatin Street Hyattsville MD 20781')."""
    if not address or not re.search(r"\d+\s+\w+", address):
        return None
    return " ".join(address.replace(" - ", " ").split())


class Geocoder:
    def __init__(self, http: HttpClient, settings: Settings,
                 cache_get: Callable[[str], tuple[float, float] | None | bool],
                 cache_put: Callable[[str, float | None, float | None, str | None], None]):
        self.http = http
        self.settings = settings
        self.cache_get = cache_get
        self.cache_put = cache_put
        self.lookups = 0

    def lookup(self, query: str) -> tuple[float, float] | None:
        cached = self.cache_get(query)
        if cached is not False:
            return cached or None
        if self.settings.geocoder != "nominatim" or self.lookups >= self.settings.geocode_max_per_run:
            return None
        self.lookups += 1
        time.sleep(1.1)  # Nominatim usage policy: at most one request per second
        try:
            results = self.http.get_json(
                NOMINATIM_URL,
                params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
                expire_after=-1,
            )
        except Exception as exc:
            log.warning("geocoding failed for %r: %s", query, exc)
            return None
        if results:
            lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
            if _BOUNDS[0] <= lat <= _BOUNDS[1] and _BOUNDS[2] <= lon <= _BOUNDS[3]:
                self.cache_put(query, lat, lon, results[0].get("display_name"))
                return lat, lon
        self.cache_put(query, None, None, None)
        return None

    def fill(self, events: list[Event]) -> int:
        filled = 0
        for event in events:
            if event.latitude is not None or event.is_online:
                continue
            query = geocodable(event.address)
            if not query:
                continue
            coords = self.lookup(query)
            if coords:
                event.latitude, event.longitude = coords
                filled += 1
        if self.lookups:
            log.info("geocoded %d new addresses (%d events filled)", self.lookups, filled)
        return filled
