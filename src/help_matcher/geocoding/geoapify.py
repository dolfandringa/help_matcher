from time import monotonic, sleep
from typing import Any

import httpx

from help_matcher.config import Settings
from help_matcher.geocoding import GeocodingCandidate

HTTP_TIMEOUT_SECONDS = 15


def geocode_location(queries: list[str], *, settings: Settings) -> list[GeocodingCandidate]:
    """Return Geoapify GeoJSON geometry candidates with API confidence scores."""

    if not settings.geoapify_api_key:
        raise ValueError("GEOAPIFY_API_KEY is required when GEOCODER_PROVIDER=geoapify")

    batch_result = submit_batch_geocoding_job(queries, settings=settings)
    return extract_candidates(batch_result)


def submit_batch_geocoding_job(queries: list[str], *, settings: Settings) -> Any:
    response = httpx.post(
        f"{settings.geoapify_base_url.rstrip('/')}/v1/batch",
        params={"apiKey": settings.geoapify_api_key},
        json={
            "api": "/v1/geocode/search",
            "params": {
                "format": "geojson",
                "filter": "countrycode:co",
                "limit": len(queries),
            },
            "inputs": [
                {"id": str(index), "params": {"text": query}}
                for index, query in enumerate(queries)
            ],
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    result_url = payload.get("url")
    job_id = payload.get("id")
    if not result_url and not job_id:
        return payload

    deadline = monotonic() + settings.geoapify_batch_timeout_seconds
    while monotonic() < deadline:
        sleep(settings.geoapify_batch_poll_seconds)
        result_response = httpx.get(
            result_url or f"{settings.geoapify_base_url.rstrip('/')}/v1/batch/geocode/search",
            params=None if result_url else {"id": job_id, "apiKey": settings.geoapify_api_key},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        result_response.raise_for_status()
        result_payload = result_response.json()
        if isinstance(result_payload, dict) and result_payload.get("status") == "pending":
            continue
        return result_payload
    raise TimeoutError(f"Geoapify batch geocoding job {job_id} did not complete in time")


def extract_candidates(batch_result: Any) -> list[GeocodingCandidate]:
    candidates: list[GeocodingCandidate] = []
    for item in iter_batch_features(batch_result):
        geometry = item.get("geometry") or geometry_from_flat_result(item)
        if geometry:
            confidence = float(item.get("properties", {}).get("rank", {}).get("confidence") or item.get("rank", {}).get("confidence") or 0)
            candidates.append(GeocodingCandidate(geometry=geometry, confidence=confidence))
    return candidates


def iter_batch_features(batch_result: Any):
    if isinstance(batch_result, dict):
        if "features" in batch_result:
            yield from batch_result["features"]
        elif "results" in batch_result:
            yield from iter_batch_features(batch_result["results"])
        elif "result" in batch_result:
            yield from iter_batch_features(batch_result["result"])
        return
    if not isinstance(batch_result, list):
        return
    for item in batch_result:
        if isinstance(item, dict) and "features" in item:
            yield from item["features"]
        elif isinstance(item, dict) and "result" in item:
            yield from iter_batch_features(item["result"])
        elif isinstance(item, dict) and "results" in item:
            yield from iter_batch_features(item["results"])
        elif isinstance(item, list):
            yield from item
        elif isinstance(item, dict):
            yield item


def geometry_from_flat_result(item: dict[str, Any]) -> dict[str, Any] | None:
    lon = item.get("lon")
    lat = item.get("lat")
    if lon is None or lat is None:
        return None
    return {"type": "Point", "coordinates": [lon, lat]}
