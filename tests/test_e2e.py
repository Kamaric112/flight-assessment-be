from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest


pytestmark = pytest.mark.e2e


def _run_e2e_enabled() -> bool:
    return os.getenv("RUN_E2E") == "1"


@pytest.fixture
def bff_base_url() -> Iterator[str]:
    if not _run_e2e_enabled():
        pytest.skip("Set RUN_E2E=1 to run end-to-end tests.")

    external_base_url = os.getenv("E2E_BASE_URL")
    if external_base_url:
        yield external_base_url.rstrip("/")
        return

    with _running_local_bff() as base_url:
        yield base_url


@contextmanager
def _running_local_bff() -> Iterator[str]:
    project_root = Path(__file__).resolve().parents[1]
    port = _get_free_port()
    base_url = f"http://127.0.0.1:{port}"
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]

    process = subprocess.Popen(
        command,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_server(base_url, process)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _wait_for_server(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"BFF failed to start.\n{output}")

        try:
            response = httpx.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)

    process.terminate()
    output = process.stdout.read() if process.stdout else ""
    raise RuntimeError(f"Timed out waiting for BFF startup.\n{output}")


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def test_e2e_booking_flow_against_live_upstream(bff_base_url: str) -> None:
    unique_id = str(int(time.time()))

    with httpx.Client(base_url=bff_base_url, timeout=20.0) as client:
        search_response = client.post(
            "/api/v1/flights/search?page=1&pageSize=1",
            json={
                "origin": "SIN",
                "destination": "BKK",
                "departureDate": "2026-04-15",
                "passengers": 1,
                "cabin": "Y",
            },
        )
        assert search_response.status_code == 200, search_response.text
        search_body = search_response.json()
        assert search_body["items"]

        offer_id = search_body["items"][0]["offerId"]

        offer_response = client.get(f"/api/v1/offers/{offer_id}")
        assert offer_response.status_code == 200, offer_response.text
        offer_body = offer_response.json()
        assert offer_body["offerId"] == offer_id

        booking_response = client.post(
            "/api/v1/bookings",
            json={
                "offerId": offer_id,
                "contact": {
                    "email": f"e2e+{unique_id}@example.com",
                    "phone": "+6591234567",
                },
                "passengers": [
                    {
                        "title": "MS",
                        "firstName": "Alice",
                        "lastName": "Tan",
                        "dateOfBirth": "1990-05-12",
                        "nationality": "SG",
                        "passportNumber": f"E2E{unique_id}",
                    }
                ],
            },
        )
        assert booking_response.status_code == 200, booking_response.text
        booking_body = booking_response.json()
        booking_reference = booking_body["bookingReference"]
        assert booking_reference

        retrieve_first = client.get(f"/api/v1/bookings/{booking_reference}")
        assert retrieve_first.status_code == 200, retrieve_first.text
        assert retrieve_first.headers["X-Cache"] == "HIT"
        assert retrieve_first.json()["bookingReference"] == booking_reference

        retrieve_second = client.get(f"/api/v1/bookings/{booking_reference}")
        assert retrieve_second.status_code == 200, retrieve_second.text
        assert retrieve_second.headers["X-Cache"] == "HIT"
        assert retrieve_second.json()["bookingReference"] == booking_reference


def test_e2e_unified_offer_not_found_error(bff_base_url: str) -> None:
    with httpx.Client(base_url=bff_base_url, timeout=20.0) as client:
        response = client.get("/api/v1/offers/does-not-exist")

    assert response.status_code == 404, response.text
    body = response.json()
    assert body["error"]["code"] == "OFFER_NOT_FOUND"
    assert body["error"]["type"] == "not_found"
