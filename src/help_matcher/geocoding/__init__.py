from dataclasses import dataclass
from typing import Any, Protocol

from help_matcher.config import Settings, get_settings


@dataclass(frozen=True)
class GeocodingCandidate:
    geometry: dict[str, Any]
    confidence: float


class LocationProvider(Protocol):
    def __call__(self, queries: list[str], *, settings: Settings) -> list[GeocodingCandidate]:
        """Return GeoJSON geometry candidates with confidence scores."""


from help_matcher.geocoding import geoapify, nominatim  # noqa: E402


PROVIDERS: dict[str, LocationProvider] = {
    "geoapify": geoapify.geocode_location,
    "nominatim": nominatim.geocode_location,
}


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
    """Return the best configured-provider GeoJSON geometry for an address/admin area."""

    current_settings = settings or get_settings()
    queries = build_geocoding_queries(
        administrative_area_name=administrative_area_name,
        address_text=address_text,
        country=country,
        location_suffixes=current_settings.geocoding_location_suffix_list,
    )
    if not queries:
        return None

    provider_name = current_settings.geocoder_provider.lower()
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        raise ValueError(f"Unsupported geocoder provider: {current_settings.geocoder_provider}")
    candidates = provider(queries, settings=current_settings)
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.confidence).geometry
