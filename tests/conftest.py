from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


FIXTURES = Path(__file__).parent / "fixtures" / "upstream"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class MockLegacyTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self.handler(request)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        upstream_base_url="https://mock-travel-api.vercel.app",
        airport_cache_ttl_seconds=86400,
        booking_cache_ttl_seconds=60,
    )


@pytest.fixture
def make_client(settings: Settings):
    def factory(handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
        transport = MockLegacyTransport(handler)
        app = create_app(settings, legacy_transport=transport)
        return TestClient(app)

    return factory

