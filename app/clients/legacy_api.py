from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import field
from time import monotonic
from typing import Any

import httpx
import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.core.config import Settings
from app.core.errors import (
    ApiException,
    CircuitBreakerOpenError,
    ErrorPayload,
    ErrorType,
    UpstreamDataError,
    UpstreamRateLimitError,
    UpstreamServerError,
    UpstreamTimeoutError,
)

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class CircuitBreaker:
    failure_threshold: int
    recovery_seconds: int
    _failures: int = 0
    _opened_at: float | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def before_call(self) -> None:
        async with self._lock:
            if self._opened_at is None:
                return
            if monotonic() - self._opened_at >= self.recovery_seconds:
                self._opened_at = None
                self._failures = 0
                return
            raise CircuitBreakerOpenError("Circuit breaker is open")

    async def record_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._opened_at = None

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = monotonic()


class LegacyApiClient:
    def __init__(
        self,
        settings: Settings,
        *,
        request_id_getter,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._request_id_getter = request_id_getter
        self._client = httpx.AsyncClient(
            base_url=settings.upstream_base_url,
            timeout=httpx.Timeout(
                connect=settings.connect_timeout_seconds,
                read=settings.read_timeout_seconds,
                write=settings.read_timeout_seconds,
                pool=settings.read_timeout_seconds,
            ),
            limits=httpx.Limits(
                max_connections=settings.max_connections,
                max_keepalive_connections=settings.max_keepalive_connections,
            ),
            transport=transport,
        )
        self._breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_seconds=settings.circuit_breaker_recovery_seconds,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def search_flights(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/flightsearch",
            operation="search_flights",
            json=payload,
            retryable=True,
        )

    async def get_offer_details(self, offer_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v2/offer/{offer_id}",
            operation="get_offer_details",
            retryable=True,
        )

    async def create_booking(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/booking/create",
            operation="create_booking",
            json=payload,
            retryable=False,
        )

    async def get_booking(self, booking_reference: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v1/reservations/{booking_reference}",
            operation="get_booking",
            retryable=True,
        )

    async def list_airports(self) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/api/airports",
            operation="list_airports",
            retryable=True,
        )

    async def get_airport(self, code: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/airports/{code}",
            operation="get_airport",
            retryable=True,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        retryable: bool,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            await self._breaker.before_call()
        except CircuitBreakerOpenError:
            raise self._api_exception(
                code="UPSTREAM_UNAVAILABLE",
                error_type=ErrorType.upstream_unavailable,
                message="The upstream flight service is temporarily unavailable.",
                status=503,
            )

        headers = {"X-Request-ID": self._request_id_getter()}

        try:
            if retryable:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(self._settings.retry_attempts),
                    wait=wait_exponential_jitter(initial=0.2, max=2),
                    retry=retry_if_exception_type(
                        (UpstreamTimeoutError, UpstreamRateLimitError, UpstreamServerError)
                    ),
                    reraise=True,
                ):
                    with attempt:
                        response = await self._send(method, path, headers=headers, json=json)
            else:
                response = await self._send(method, path, headers=headers, json=json)
        except UpstreamTimeoutError as exc:
            await self._breaker.record_failure()
            raise self._api_exception(
                code="UPSTREAM_TIMEOUT",
                error_type=ErrorType.upstream_timeout,
                message="The upstream flight service timed out.",
                status=504,
            ) from exc
        except UpstreamRateLimitError as exc:
            await self._breaker.record_failure()
            raise self._api_exception(
                code="UPSTREAM_RATE_LIMITED",
                error_type=ErrorType.upstream_rate_limited,
                message="The upstream flight service rate limited the request.",
                status=429,
            ) from exc
        except UpstreamServerError as exc:
            await self._breaker.record_failure()
            raise self._api_exception(
                code="UPSTREAM_UNAVAILABLE",
                error_type=ErrorType.upstream_unavailable,
                message="The upstream flight service is temporarily unavailable.",
                status=503,
            ) from exc
        except ApiException:
            raise
        except UpstreamDataError as exc:
            await self._breaker.record_failure()
            raise self._api_exception(
                code="UPSTREAM_INVALID_RESPONSE",
                error_type=ErrorType.invalid_response,
                message=str(exc),
                status=502,
            ) from exc

        await self._breaker.record_success()
        return response

    async def _send(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, headers=headers, json=json)
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError("Upstream request timed out.", status_code=504) from exc
        except httpx.TransportError as exc:
            raise UpstreamServerError("Upstream transport error.", status_code=503) from exc
        if response.status_code >= 400:
            self._raise_for_response(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamDataError("The upstream service returned malformed JSON.") from exc
        if not isinstance(payload, dict):
            raise UpstreamDataError("The upstream service returned an unexpected payload shape.")
        return payload

    def _raise_for_response(self, response: httpx.Response) -> None:
        status = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = {}

        if status == 429:
            raise UpstreamRateLimitError("Upstream rate limited the request.", status_code=429)
        if status >= 500:
            raise UpstreamServerError("Upstream server error.", status_code=status)

        raise self._translate_error(body, status_code=status)

    def _translate_error(self, body: dict[str, Any], *, status_code: int) -> ApiException:
        message = "Request to upstream service failed."
        code = "UPSTREAM_ERROR"
        error_type = ErrorType.upstream_error

        if isinstance(body.get("error"), dict):
            message = body["error"].get("message", message)
            code = "INVALID_SEARCH_REQUEST" if status_code == 400 else code
            error_type = ErrorType.validation_error if status_code == 400 else error_type
        elif isinstance(body.get("errors"), list) and body["errors"]:
            error = body["errors"][0]
            message = error.get("detail", message)
            code = "OFFER_NOT_FOUND" if status_code == 404 else error.get("code", code)
            error_type = ErrorType.not_found if status_code == 404 else error_type
        elif isinstance(body.get("fault"), dict):
            message = body["fault"].get("faultstring", message)
            code = "INVALID_BOOKING_REQUEST" if status_code == 400 else body["fault"].get("faultcode", code)
            error_type = ErrorType.validation_error if status_code == 400 else error_type
        elif body.get("status") == "error":
            message = body.get("msg", message)
            code = "NOT_FOUND" if status_code == 404 else code
            error_type = ErrorType.not_found if status_code == 404 else error_type

        if status_code == 404 and code == "NOT_FOUND":
            if "booking" in message.lower():
                code = "BOOKING_NOT_FOUND"
            elif "airport" in message.lower():
                code = "AIRPORT_NOT_FOUND"

        return self._api_exception(
            code=code,
            error_type=error_type,
            message=message,
            status=status_code,
        )

    def _api_exception(
        self,
        *,
        code: str,
        error_type: ErrorType,
        message: str,
        status: int,
    ) -> ApiException:
        return ApiException(
            ErrorPayload(
                code=code,
                type=error_type.value,
                message=message,
                status=status,
                request_id=self._request_id_getter(),
            )
        )
