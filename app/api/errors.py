from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import ApiException, ErrorPayload
from app.models.api import ErrorResponse


def register_error_handlers(app: FastAPI) -> None:
    def serialize_payload(payload: ErrorPayload) -> ErrorResponse:
        return ErrorResponse(
            error={
                "code": payload.code,
                "type": payload.type,
                "message": payload.message,
                "status": payload.status,
                "request_id": payload.request_id,
            }
        )

    @app.exception_handler(ApiException)
    async def handle_api_exception(_: Request, exc: ApiException) -> JSONResponse:
        response = serialize_payload(exc.payload)
        return JSONResponse(status_code=exc.payload.status, content=response.model_dump(by_alias=True))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        payload = ErrorPayload(
            code="VALIDATION_ERROR",
            type="validation_error",
            message="Request validation failed.",
            status=422,
            request_id=request_id,
        )
        response = serialize_payload(payload)
        return JSONResponse(
            status_code=422,
            content=response.model_dump(by_alias=True),
        )
