from typing import Any

import httpx

from help_matcher.config import Settings, get_settings


def build_geocoding_query(
    *,
    administrative_area_name: str | None = None,
    address_text: str | None = None,
    country: str = "Colombia",
    location_suffix: str | None = None,
) -> str:
    suffix = location_suffix.strip().strip(",") if location_suffix else ""
    parts = [address_text, administrative_area_name]
    if suffix:
        parts.append(suffix)
    else:
        parts.append(country)
    return ", ".join(part.strip() for part in parts if part and part.strip())


def build_geocoding_queries(
    *,
    administrative_area_name: str | None = None,
    address_text: str | None = None,
    country: str = "Colombia",
    location_suffixes: list[str] | None = None,
) -> list[str]:
    suffixes = location_suffixes or [""]
    queries = [
        build_geocoding_query(
            administrative_area_name=administrative_area_name,
            address_text=address_text,
            country=country,
            location_suffix=suffix,
        )
        for suffix in suffixes
    ]
    return list(dict.fromkeys(query for query in queries if query))


def geocode_location(
    *,
    administrative_area_name: str | None = None,
    address_text: str | None = None,
    country: str = "Colombia",
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    """Return the best Nominatim GeoJSON geometry for an address/admin area."""

    current_settings = settings or get_settings()
    queries = build_geocoding_queries(
        administrative_area_name=administrative_area_name,
        address_text=address_text,
        country=country,
        location_suffixes=current_settings.geocoding_location_suffix_list,
    )
    if not queries:
        return None

    for query in queries:
        response = httpx.get(
            f"{current_settings.nominatim_base_url.rstrip('/')}/search",
            params={
                "q": query,
                "format": "geojson",
                "polygon_geojson": 1,
                "addressdetails": 1,
                "limit": 1,
                "countrycodes": "co",
            },
            headers={"User-Agent": current_settings.nominatim_user_agent},
            timeout=10,
        )
        response.raise_for_status()
        features = response.json().get("features", [])
        if features:
            return features[0].get("geometry")
    return None
