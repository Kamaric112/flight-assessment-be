from __future__ import annotations

from app.clients.legacy_api import LegacyApiClient
from app.core.cache import InMemoryTTLStore
from app.services.normalizers import normalize_booking_response


class BookingService:
    def __init__(self, client: LegacyApiClient, booking_cache: InMemoryTTLStore[dict]) -> None:
        self._client = client
        self._booking_cache = booking_cache

    async def create_booking(self, payload: dict) -> dict:
        upstream = await self._client.create_booking(payload)
        normalized = normalize_booking_response(upstream)
        booking_reference = normalized["booking_reference"]
        self._booking_cache.set(booking_reference, normalized)
        return normalized

    async def get_booking(self, booking_reference: str) -> tuple[dict, str]:
        cached = self._booking_cache.get(booking_reference)
        if cached is not None:
            return cached, "HIT"

        upstream = await self._client.get_booking(booking_reference)
        normalized = normalize_booking_response(upstream)
        self._booking_cache.set(booking_reference, normalized)
        return normalized, "MISS"

