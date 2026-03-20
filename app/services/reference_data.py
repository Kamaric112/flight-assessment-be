from __future__ import annotations

from typing import Any

from app.clients.legacy_api import LegacyApiClient
from app.core.cache import InMemoryTTLStore


class ReferenceDataService:
    def __init__(self, client: LegacyApiClient, airport_cache: InMemoryTTLStore[dict[str, Any]]) -> None:
        self._client = client
        self._airport_cache = airport_cache
        self._all_airports_cache_key = "__all_airports__"

    async def get_airport(self, code: str) -> dict[str, Any]:
        airport_code = code.upper()
        cached = self._airport_cache.get(airport_code)
        if cached is not None:
            return cached

        airports = await self._get_airports_index()
        airport = airports.get(airport_code, {"code": airport_code})

        if not airport.get("city"):
            try:
                airport_detail = await self._client.get_airport(airport_code)
            except Exception:
                airport_detail = {}
            airport = {**airport, **airport_detail}

        airport.setdefault("code", airport_code)
        self._airport_cache.set(airport_code, airport)
        return airport

    async def _get_airports_index(self) -> dict[str, dict[str, Any]]:
        cached = self._airport_cache.get(self._all_airports_cache_key)
        if cached is not None:
            return cached

        payload = await self._client.list_airports()
        index = {
            item.get("code", "").upper(): item
            for item in payload.get("airports", [])
            if item.get("code")
        }
        self._airport_cache.set(self._all_airports_cache_key, index)
        return index

