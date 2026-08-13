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


def geocode_location(
    *,
    administrative_area_name: str | None = None,
    address_text: str | None = None,
    country: str = "Colombia",
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    """Return the best Nominatim GeoJSON geometry for an address/admin area."""

    current_settings = settings or get_settings()
    query = build_geocoding_query(
        administrative_area_name=administrative_area_name,
        address_text=address_text,
        country=country,
        location_suffix=current_settings.geocoding_location_suffix,
    )
    if not query:
        return None

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
    if not features:
        return None
    return features[0].get("geometry")
