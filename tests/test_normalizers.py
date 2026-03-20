from app.services.normalizers import normalize_booking_response, normalize_offer_response
from tests.conftest import load_fixture


def test_normalize_offer_response() -> None:
    payload = load_fixture("offer_success.json")
    normalized = normalize_offer_response(payload)

    assert normalized["offer_id"] == "b441ff9174795f49"
    assert normalized["status_label"] == "Available"
    assert normalized["fare_family"]["label"] == "Full Flex"
    assert normalized["payment"]["accepted_methods"][0]["label"] == "Credit Card"
    assert normalized["payment"]["time_limit"] == "2026-03-21T17:11:00+00:00"


def test_normalize_booking_response() -> None:
    payload = load_fixture("retrieve_booking_success.json")
    normalized = normalize_booking_response(payload)

    assert normalized["booking_reference"] == "EGABE5C6"
    assert normalized["status_label"] == "Confirmed"
    assert normalized["passengers"][0]["type_label"] == "Adult"
    assert normalized["created_at"] == "2026-03-19T18:11:38+00:00"

