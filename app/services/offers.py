from __future__ import annotations

from app.clients.legacy_api import LegacyApiClient
from app.services.normalizers import normalize_offer_response


class OfferService:
    def __init__(self, client: LegacyApiClient) -> None:
        self._client = client

    async def get_offer(self, offer_id: str) -> dict:
        upstream = await self._client.get_offer_details(offer_id)
        return normalize_offer_response(upstream)

