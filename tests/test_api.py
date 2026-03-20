from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import load_fixture
from tests.conftest import MockLegacyTransport


def make_response(request: httpx.Request, payload: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=payload, request=request)


def test_search_endpoint_normalizes_and_paginates(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/flightsearch":
            return make_response(request, load_fixture("search_success.json"))
        if request.url.path == "/api/airports":
            return make_response(request, load_fixture("airport_list.json"))
        if request.url.path == "/api/airports/SIN":
            return make_response(request, load_fixture("airport_detail_sin.json"))
        if request.url.path == "/api/airports/BKK":
            return make_response(request, {"code": "BKK", "city": "Bangkok", "country_code": "TH", "tz_offset": 7})
        if request.url.path == "/api/airports/KUL":
            return make_response(request, {"code": "KUL", "city": "Kuala Lumpur", "country_code": "MY", "tz_offset": 8})
        raise AssertionError(f"Unexpected path: {request.url.path}")

    with make_client(handler) as client:
        response = client.post(
            "/api/v1/flights/search?page=1&pageSize=1",
            json={
                "origin": "sin",
                "destination": "bkk",
                "departureDate": "2026-04-15",
                "passengers": 1,
                "cabin": "y",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {"page": 1, "pageSize": 1, "totalItems": 2, "totalPages": 2}
    assert body["items"][0]["offerId"] == "b441ff9174795f49"
    assert body["items"][0]["carrier"]["name"] == "Singapore Airlines"
    assert body["items"][0]["departure"]["airport"]["label"] == "Singapore (SIN)"
    assert body["items"][0]["arrival"]["dateTime"] == "2026-04-15T14:53:00+07:00"


def test_search_endpoint_returns_unified_error(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/flightsearch":
            return make_response(request, load_fixture("search_error.json"), status_code=400)
        raise AssertionError(f"Unexpected path: {request.url.path}")

    with make_client(handler) as client:
        response = client.post(
            "/api/v1/flights/search",
            json={
                "origin": "XXX",
                "destination": "BKK",
                "departureDate": "2026-04-15",
                "passengers": 1,
                "cabin": "Y",
            },
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_SEARCH_REQUEST"
    assert body["error"]["type"] == "validation_error"


def test_offer_details_endpoint(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/offer/b441ff9174795f49":
            return make_response(request, load_fixture("offer_success.json"))
        raise AssertionError(f"Unexpected path: {request.url.path}")

    with make_client(handler) as client:
        response = client.get("/api/v1/offers/b441ff9174795f49")

    assert response.status_code == 200
    body = response.json()
    assert body["offerId"] == "b441ff9174795f49"
    assert body["statusLabel"] == "Available"
    assert body["payment"]["acceptedMethods"][1]["label"] == "Debit Card"


def test_create_booking_endpoint(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/booking/create":
            payload = load_fixture("create_booking_success.json")
            return make_response(request, payload)
        raise AssertionError(f"Unexpected path: {request.url.path}")

    with make_client(handler) as client:
        response = client.post(
            "/api/v1/bookings",
            json={
                "offerId": "b441ff9174795f49",
                "contact": {"email": "alice@example.com", "phone": "+6591234567"},
                "passengers": [
                    {
                        "title": "MS",
                        "firstName": "Alice",
                        "lastName": "Tan",
                        "dateOfBirth": "1990-05-12",
                        "nationality": "SG",
                        "passportNumber": "E1234567",
                    }
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["bookingReference"] == "EGABE5C6"
    assert body["ticketing"]["statusLabel"] == "Pending"


def test_create_booking_validation_rejects_future_dob(make_client) -> None:
    with make_client(lambda request: make_response(request, {})) as client:
        response = client.post(
            "/api/v1/bookings",
            json={
                "offerId": "b441ff9174795f49",
                "contact": {"email": "alice@example.com", "phone": "+6591234567"},
                "passengers": [
                    {
                        "firstName": "Alice",
                        "lastName": "Tan",
                        "dateOfBirth": "2090-05-12",
                        "nationality": "SG",
                        "passportNumber": "E1234567",
                    }
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_retrieve_booking_endpoint_uses_cache(make_client) -> None:
    call_count = {"booking": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/reservations/EGABE5C6":
            call_count["booking"] += 1
            return make_response(request, load_fixture("retrieve_booking_success.json"))
        raise AssertionError(f"Unexpected path: {request.url.path}")

    with make_client(handler) as client:
        first = client.get("/api/v1/bookings/EGABE5C6")
        second = client.get("/api/v1/bookings/EGABE5C6")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert call_count["booking"] == 1


def test_offer_not_found_is_unified(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/offer/does-not-exist":
            return make_response(request, load_fixture("offer_not_found.json"), status_code=404)
        raise AssertionError(f"Unexpected path: {request.url.path}")

    with make_client(handler) as client:
        response = client.get("/api/v1/offers/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "OFFER_NOT_FOUND"


def test_booking_not_found_is_unified(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/reservations/UNKNOWN123":
            return make_response(request, load_fixture("booking_not_found.json"), status_code=404)
        raise AssertionError(f"Unexpected path: {request.url.path}")

    with make_client(handler) as client:
        response = client.get("/api/v1/bookings/UNKNOWN123")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BOOKING_NOT_FOUND"


def test_offer_rate_limit_is_unified(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/offer/b441ff9174795f49":
            return make_response(request, {"errors": [{"detail": "Too many requests"}]}, status_code=429)
        raise AssertionError(f"Unexpected path: {request.url.path}")

    with make_client(handler) as client:
        response = client.get("/api/v1/offers/b441ff9174795f49")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "UPSTREAM_RATE_LIMITED"


def test_search_timeout_is_unified(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout", request=request)

    with make_client(handler) as client:
        response = client.post(
            "/api/v1/flights/search",
            json={
                "origin": "SIN",
                "destination": "BKK",
                "departureDate": "2026-04-15",
                "passengers": 1,
                "cabin": "Y",
            },
        )

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_circuit_breaker_short_circuits_repeated_failures() -> None:
    call_count = {"offer": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/offer/b441ff9174795f49":
            call_count["offer"] += 1
            return make_response(request, {"error": "boom"}, status_code=500)
        raise AssertionError(f"Unexpected path: {request.url.path}")

    settings = Settings(
        circuit_breaker_failure_threshold=1,
        circuit_breaker_recovery_seconds=60,
        retry_attempts=1,
    )
    app = create_app(settings, legacy_transport=MockLegacyTransport(handler))

    with TestClient(app) as client:
        first = client.get("/api/v1/offers/b441ff9174795f49")
        second = client.get("/api/v1/offers/b441ff9174795f49")

    assert first.status_code == 503
    assert second.status_code == 503
    assert call_count["offer"] == 1
