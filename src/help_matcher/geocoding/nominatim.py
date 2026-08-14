from typing import Any

import httpx

from help_matcher.config import Settings
from help_matcher.geocoding import GeocodingCandidate

HTTP_TIMEOUT_SECONDS = 15


def geocode_location(queries: list[str], *, settings: Settings) -> list[GeocodingCandidate]:
    """Return Nominatim GeoJSON geometry candidates with fixed confidence."""

    candidates: list[GeocodingCandidate] = []
    for query in queries:
        response = httpx.get(
            f"{settings.nominatim_base_url.rstrip('/')}/search",
            params={
                "q": query,
                "format": "geojson",
                "polygon_geojson": 1,
                "addressdetails": 1,
                "limit": 1,
                "countrycodes": "co",
            },
            headers={"User-Agent": settings.nominatim_user_agent},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        for feature in response.json().get("features", []):
            geometry = feature.get("geometry")
            if geometry:
                candidates.append(GeocodingCandidate(geometry=geometry, confidence=0.5))
    return candidates
