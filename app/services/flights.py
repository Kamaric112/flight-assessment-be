from __future__ import annotations

from app.clients.legacy_api import LegacyApiClient
from app.services.normalizers import normalize_search_response
from app.services.reference_data import ReferenceDataService


class FlightService:
    def __init__(self, client: LegacyApiClient, reference_data: ReferenceDataService) -> None:
        self._client = client
        self._reference_data = reference_data

    async def search(
        self,
        payload: dict,
        *,
        page: int,
        page_size: int,
    ) -> dict:
        upstream = await self._client.search_flights(payload)
        return await normalize_search_response(
            upstream,
            page=page,
            page_size=page_size,
            reference_data=self._reference_data,
        )

