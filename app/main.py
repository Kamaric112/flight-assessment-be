from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request

from app.api.errors import register_error_handlers
from app.api.routes import router
from app.clients.legacy_api import LegacyApiClient
from app.core.cache import InMemoryTTLStore
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.services.bookings import BookingService
from app.services.flights import FlightService
from app.services.offers import OfferService
from app.services.reference_data import ReferenceDataService

request_id_context: ContextVar[str] = ContextVar("request_id", default="startup")


def create_app(
    settings: Settings | None = None,
    *,
    legacy_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.airport_cache = InMemoryTTLStore[dict](ttl_seconds=settings.airport_cache_ttl_seconds)
        app.state.booking_cache = InMemoryTTLStore[dict](ttl_seconds=settings.booking_cache_ttl_seconds)
        app.state.legacy_client = LegacyApiClient(
            settings,
            request_id_getter=lambda: request_id_context.get(),
            transport=legacy_transport,
        )
        app.state.reference_data_service = ReferenceDataService(
            app.state.legacy_client,
            app.state.airport_cache,
        )
        app.state.flight_service = FlightService(app.state.legacy_client, app.state.reference_data_service)
        app.state.offer_service = OfferService(app.state.legacy_client)
        app.state.booking_service = BookingService(app.state.legacy_client, app.state.booking_cache)
        yield
        await app.state.legacy_client.aclose()

    app = FastAPI(
        title="Flight BFF",
        version="0.1.0",
        description="Frontend-friendly wrapper for the easyGDS legacy flight API.",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

    app.include_router(router)
    register_error_handlers(app)

    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
