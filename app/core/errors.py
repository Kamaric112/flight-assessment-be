from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorType(StrEnum):
    not_found = "not_found"
    validation_error = "validation_error"
    upstream_error = "upstream_error"
    upstream_timeout = "upstream_timeout"
    upstream_rate_limited = "upstream_rate_limited"
    upstream_unavailable = "upstream_unavailable"
    invalid_response = "invalid_response"


@dataclass(slots=True)
class ErrorPayload:
    code: str
    type: str
    message: str
    status: int
    request_id: str


class ApiException(Exception):
    def __init__(self, payload: ErrorPayload) -> None:
        super().__init__(payload.message)
        self.payload = payload


class UpstreamTransportError(Exception):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class UpstreamTimeoutError(UpstreamTransportError):
    pass


class UpstreamRateLimitError(UpstreamTransportError):
    pass


class UpstreamServerError(UpstreamTransportError):
    pass


class UpstreamDataError(Exception):
    pass


class CircuitBreakerOpenError(Exception):
    pass

