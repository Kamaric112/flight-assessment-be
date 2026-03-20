from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Query, Request, Response

from app.models.api import (
    BookingSummary,
    CreateBookingRequest,
    ErrorResponse,
    FlightSearchRequest,
    OfferDetailsResponse,
    SearchResponse,
)

router = APIRouter(prefix="/api/v1")

FLIGHT_SEARCH_BODY = Body(
    openapi_examples={
        "oneWayEconomy": {
            "summary": "One-way economy search",
            "value": {
                "origin": "SIN",
                "destination": "BKK",
                "departureDate": "2026-04-15",
                "passengers": 1,
                "cabin": "Y",
            },
        }
    }
)

CREATE_BOOKING_BODY = Body(
    openapi_examples={
        "singleAdult": {
            "summary": "Single-adult booking",
            "value": {
                "offerId": "b441ff9174795f49",
                "contact": {
                    "email": "alice@example.com",
                    "phone": "+6591234567",
                },
                "passengers": [
                    {
                        "title": "MS",
                        "firstName": "Alice",
                        "lastName": "Tan",
                        "dateOfBirth": "1990-05-12",
                        "nationality": "SG",
                        "passportNumber": "E1234567",
                    }
                ],
            },
        }
    }
)


@router.post(
    "/flights/search",
    response_model=SearchResponse,
    responses={422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["Flights"],
)
async def search_flights(
    body: Annotated[FlightSearchRequest, FLIGHT_SEARCH_BODY],
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
) -> SearchResponse:
    service = request.app.state.flight_service
    payload = {
        "origin": body.origin,
        "destination": body.destination,
        "departure_date": body.departure_date.isoformat(),
        "return_date": body.return_date.isoformat() if body.return_date else None,
        "pax_count": body.passengers,
        "cabin": body.cabin,
    }
    normalized = await service.search(payload, page=page, page_size=page_size)
    return SearchResponse.model_validate(normalized)


@router.get(
    "/offers/{offer_id}",
    response_model=OfferDetailsResponse,
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["Offers"],
)
async def get_offer_details(offer_id: str, request: Request) -> OfferDetailsResponse:
    service = request.app.state.offer_service
    normalized = await service.get_offer(offer_id)
    return OfferDetailsResponse.model_validate(normalized)


@router.post(
    "/bookings",
    response_model=BookingSummary,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    tags=["Bookings"],
)
async def create_booking(
    body: Annotated[CreateBookingRequest, CREATE_BOOKING_BODY],
    request: Request,
) -> BookingSummary:
    service = request.app.state.booking_service
    payload = {
        "offer_id": body.offer_id,
        "contact_email": str(body.contact.email),
        "contact_phone": body.contact.phone,
        "passengers": [
            {
                "title": passenger.title,
                "first_name": passenger.first_name,
                "last_name": passenger.last_name,
                "dob": passenger.date_of_birth.isoformat(),
                "nationality": passenger.nationality,
                "passport_no": passenger.passport_number,
                "email": str(passenger.email) if passenger.email else str(body.contact.email),
                "phone": passenger.phone or body.contact.phone,
            }
            for passenger in body.passengers
        ],
    }
    normalized = await service.create_booking(payload)
    return BookingSummary.model_validate(normalized)


@router.get(
    "/bookings/{booking_reference}",
    response_model=BookingSummary,
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["Bookings"],
)
async def get_booking(booking_reference: str, request: Request, response: Response) -> BookingSummary:
    service = request.app.state.booking_service
    normalized, cache_status = await service.get_booking(booking_reference)
    response.headers["X-Cache"] = cache_status
    return BookingSummary.model_validate(normalized)
