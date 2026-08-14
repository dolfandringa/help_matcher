from help_matcher.config import Settings
from help_matcher.geocoding import geocode_location


def test_geocode_location_uses_geoapify_provider(monkeypatch) -> None:
    captured_posts = []
    captured_gets = []

    class FakeResponse:
        def __init__(self, payload: dict | list) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict | list:
            return self._payload

    def fake_post(url, *, params, json, timeout):
        captured_posts.append({"url": url, "params": params, "json": json, "timeout": timeout})
        return FakeResponse({"id": "job-id", "status": "pending", "url": "https://batch-result"})

    def fake_get(url, *, params, timeout):
        captured_gets.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(
            [
                {
                    "id": "0",
                    "result": {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "geometry": {"type": "Point", "coordinates": [-76.5684843, 3.5200925]},
                                "properties": {"rank": {"confidence": 1}},
                            }
                        ],
                    },
                }
            ]
        )

    monkeypatch.setattr("help_matcher.geocoding.geoapify.httpx.post", fake_post)
    monkeypatch.setattr("help_matcher.geocoding.geoapify.httpx.get", fake_get)

    geometry = geocode_location(
        administrative_area_name="Corregimiento La Paz, Cali",
        settings=Settings(
            _env_file=None,
            GEOCODER_PROVIDER="geoapify",
            GEOAPIFY_API_KEY="test-key",
            GEOCODING_LOCATION_SUFFIXES="Valle del Cauca, Colombia;Risaralda, Colombia",
        ),
    )

    assert geometry == {"type": "Point", "coordinates": [-76.5684843, 3.5200925]}
    assert captured_posts[0]["url"] == "https://api.geoapify.com/v1/batch"
    assert captured_posts[0]["params"] == {"apiKey": "test-key"}
    assert captured_posts[0]["timeout"] == 15
    assert captured_gets[0]["timeout"] == 15
    assert captured_posts[0]["json"] == {
        "api": "/v1/geocode/search",
        "params": {
            "format": "geojson",
            "filter": "countrycode:co",
            "limit": 2,
        },
        "inputs": [
            {"id": "0", "params": {"text": "Corregimiento La Paz, Cali, Valle del Cauca, Colombia"}},
            {"id": "1", "params": {"text": "Corregimiento La Paz, Cali, Risaralda, Colombia"}},
        ],
    }


def test_geocode_location_chooses_highest_geoapify_confidence(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, payload: dict | list) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict | list:
            return self._payload

    def fake_post(url, *, params, json, timeout):
        return FakeResponse({"id": "job-id", "status": "pending", "url": "https://batch-result"})

    def fake_get(url, *, params, timeout):
        return FakeResponse(
            [
                {
                    "id": "0",
                    "result": {
                        "type": "FeatureCollection",
                        "features": [
                            {"geometry": {"type": "Point", "coordinates": [1, 1]}, "properties": {"rank": {"confidence": 0.25}}}
                        ],
                    },
                },
                {
                    "id": "1",
                    "result": {
                        "type": "FeatureCollection",
                        "features": [
                            {"geometry": {"type": "Point", "coordinates": [2, 2]}, "properties": {"rank": {"confidence": 0.9}}}
                        ],
                    },
                },
            ]
        )

    monkeypatch.setattr("help_matcher.geocoding.geoapify.httpx.post", fake_post)
    monkeypatch.setattr("help_matcher.geocoding.geoapify.httpx.get", fake_get)

    geometry = geocode_location(
        administrative_area_name="Cali",
        settings=Settings(
            _env_file=None,
            GEOCODER_PROVIDER="geoapify",
            GEOAPIFY_API_KEY="test-key",
            GEOCODING_LOCATION_SUFFIXES="Valle del Cauca, Colombia;Risaralda, Colombia",
        ),
    )

    assert geometry == {"type": "Point", "coordinates": [2, 2]}


def test_geocode_location_requires_geoapify_key() -> None:
    try:
        geocode_location(
            administrative_area_name="Cali",
            settings=Settings(_env_file=None, GEOCODER_PROVIDER="geoapify", GEOAPIFY_API_KEY=""),
        )
    except ValueError as exc:
        assert str(exc) == "GEOAPIFY_API_KEY is required when GEOCODER_PROVIDER=geoapify"
    else:
        raise AssertionError("Expected Geoapify geocoding to require an API key")


def test_geocode_location_keeps_first_nominatim_match_on_equal_confidence(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, coordinates: list[int]) -> None:
            self._coordinates = coordinates

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"features": [{"geometry": {"type": "Point", "coordinates": self._coordinates}}]}

    def fake_get(url, *, params, headers, timeout):
        if "Valle del Cauca" in params["q"]:
            return FakeResponse([1, 1])
        return FakeResponse([2, 2])

    monkeypatch.setattr("help_matcher.geocoding.nominatim.httpx.get", fake_get)

    geometry = geocode_location(
        administrative_area_name="Cali",
        settings=Settings(
            _env_file=None,
            GEOCODER_PROVIDER="nominatim",
            GEOCODING_LOCATION_SUFFIXES="Valle del Cauca, Colombia;Risaralda, Colombia",
        ),
    )

    assert geometry == {"type": "Point", "coordinates": [1, 1]}
