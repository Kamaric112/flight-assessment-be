from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.json import to_camel


PHONE_PATTERN = r"^\+[1-9]\d{7,14}$"
API_MODEL_CONFIG = {
    "alias_generator": to_camel,
    "populate_by_name": True,
    "extra": "forbid",
}


def api_model_config(**kwargs) -> ConfigDict:
    return ConfigDict(**API_MODEL_CONFIG, **kwargs)


class ApiModel(BaseModel):
    model_config = api_model_config()


class ErrorBody(ApiModel):
    code: str
    type: str
    message: str
    status: int
    request_id: str


class ErrorResponse(ApiModel):
    model_config = api_model_config(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "OFFER_NOT_FOUND",
                    "type": "not_found",
                    "message": "Offer does-not-exist not found or expired",
                    "status": 404,
                    "requestId": "f02f8d5b-59ae-42e0-b1fd-b44a6e618100",
                }
            }
        }
    )
    error: ErrorBody


class FlightSearchRequest(ApiModel):
    model_config = api_model_config(
        json_schema_extra={
            "example": {
                "origin": "SIN",
                "destination": "BKK",
                "departureDate": "2026-04-15",
                "passengers": 1,
                "cabin": "Y",
            }
        }
    )
    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)
    departure_date: date
    return_date: date | None = None
    passengers: int = Field(default=1, ge=1, le=9)
    cabin: str = Field(default="Y", min_length=1, max_length=1)

    @field_validator("origin", "destination", "cabin")
    @classmethod
    def uppercase_codes(cls, value: str) -> str:
        return value.upper()


class Pagination(ApiModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class AirportSummary(ApiModel):
    code: str
    city: str | None = None
    country_code: str | None = None
    label: str
    terminal: str | None = None
    timezone_offset_hours: float | None = None


class CarrierSummary(ApiModel):
    code: str
    name: str
    flight_number: str


class CabinSummary(ApiModel):
    code: str
    label: str


class FlightPoint(ApiModel):
    airport: AirportSummary
    date_time: str | None = None


class FlightSegment(ApiModel):
    carrier: CarrierSummary
    departure: FlightPoint
    arrival: FlightPoint
    duration_minutes: int | None = None
    aircraft_code: str | None = None
    cabin: CabinSummary


class BaggageAllowance(ApiModel):
    quantity: int | None = None
    max_weight_kg: int | None = None


class BaggageSummary(ApiModel):
    checked: BaggageAllowance
    cabin: BaggageAllowance


class PriceSummary(ApiModel):
    amount: float
    currency: str
    base_amount: float | None = None
    tax_amount: float | None = None


class SearchItem(ApiModel):
    offer_id: str
    price: PriceSummary
    stops: int
    duration_minutes: int | None = None
    duration: str | None = None
    is_refundable: bool
    seats_remaining: int | None = None
    carrier: CarrierSummary
    validating_carrier: CarrierSummary
    cabin: CabinSummary
    departure: FlightPoint
    arrival: FlightPoint
    segments: list[FlightSegment]
    baggage: BaggageSummary


class SearchMeta(ApiModel):
    search_id: str | None = None
    provider: str | None = None
    request_time_ms: int | None = None
    cache_hit: bool | None = None


class SearchResponse(ApiModel):
    model_config = api_model_config(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "offerId": "b441ff9174795f49",
                        "price": {
                            "amount": 271.14,
                            "currency": "MYR",
                            "baseAmount": 237.82,
                            "taxAmount": 33.32,
                        },
                        "stops": 0,
                        "durationMinutes": 123,
                        "duration": "2h 03m",
                        "isRefundable": False,
                        "seatsRemaining": 6,
                        "carrier": {
                            "code": "SQ",
                            "name": "Singapore Airlines",
                            "flightNumber": "SQ531",
                        },
                        "validatingCarrier": {
                            "code": "SQ",
                            "name": "Singapore Airlines",
                            "flightNumber": "SQ",
                        },
                        "cabin": {"code": "Y", "label": "Economy"},
                        "departure": {
                            "airport": {
                                "code": "SIN",
                                "city": "Singapore",
                                "countryCode": "SG",
                                "label": "Singapore (SIN)",
                                "terminal": "1",
                                "timezoneOffsetHours": 8,
                            },
                            "dateTime": "2026-04-15T12:50:00+08:00",
                        },
                        "arrival": {
                            "airport": {
                                "code": "BKK",
                                "city": "Bangkok",
                                "countryCode": "TH",
                                "label": "Bangkok (BKK)",
                                "terminal": "2",
                                "timezoneOffsetHours": 7,
                            },
                            "dateTime": "2026-04-15T14:53:00+07:00",
                        },
                        "segments": [
                            {
                                "carrier": {
                                    "code": "SQ",
                                    "name": "Singapore Airlines",
                                    "flightNumber": "SQ531",
                                },
                                "departure": {
                                    "airport": {
                                        "code": "SIN",
                                        "city": "Singapore",
                                        "countryCode": "SG",
                                        "label": "Singapore (SIN)",
                                        "terminal": "1",
                                        "timezoneOffsetHours": 8,
                                    },
                                    "dateTime": "2026-04-15T12:50:00+08:00",
                                },
                                "arrival": {
                                    "airport": {
                                        "code": "BKK",
                                        "city": "Bangkok",
                                        "countryCode": "TH",
                                        "label": "Bangkok (BKK)",
                                        "terminal": "2",
                                        "timezoneOffsetHours": 7,
                                    },
                                    "dateTime": "2026-04-15T14:53:00+07:00",
                                },
                                "durationMinutes": 123,
                                "aircraftCode": "388",
                                "cabin": {"code": "Y", "label": "Economy"},
                            }
                        ],
                        "baggage": {
                            "checked": {"quantity": 1, "maxWeightKg": 20},
                            "cabin": {"quantity": 1, "maxWeightKg": 7},
                        },
                    }
                ],
                "pagination": {
                    "page": 1,
                    "pageSize": 10,
                    "totalItems": 11,
                    "totalPages": 2,
                },
                "meta": {
                    "searchId": "83e6cdf7-03dc-4dc3-ae21-6dee69dd1e61",
                    "provider": "NDC_DIRECT",
                    "requestTimeMs": 557,
                    "cacheHit": False,
                },
            }
        }
    )
    items: list[SearchItem]
    pagination: Pagination
    meta: SearchMeta


class Money(ApiModel):
    amount: float | None = None
    currency: str | None = None


class PolicyRule(ApiModel):
    allowed: bool | None = None
    penalty: Money | None = None


class OfferPolicies(ApiModel):
    refund: PolicyRule
    change: PolicyRule
    no_show: PolicyRule


class FareFamily(ApiModel):
    code: str | None = None
    name: str | None = None
    label: str


class OfferConditions(ApiModel):
    advance_purchase_days: int | None = None
    min_stay_days: int | None = None
    max_stay_days: int | None = None


class PaymentMethod(ApiModel):
    code: str
    label: str


class PaymentRequirements(ApiModel):
    accepted_methods: list[PaymentMethod]
    time_limit: str | None = None
    instant_ticketing_required: bool


class OfferDetailsResponse(ApiModel):
    model_config = api_model_config(
        json_schema_extra={
            "example": {
                "offerId": "b441ff9174795f49",
                "status": "LIVE",
                "statusLabel": "Available",
                "fareFamily": {
                    "code": "BS",
                    "name": "FULL",
                    "label": "Full Flex",
                },
                "policies": {
                    "refund": {"allowed": True, "penalty": {"amount": 150.0, "currency": "MYR"}},
                    "change": {"allowed": True, "penalty": {"amount": 200.0, "currency": "MYR"}},
                    "noShow": {"allowed": None, "penalty": {"amount": 200.0, "currency": "MYR"}},
                },
                "baggage": {
                    "checked": {"quantity": 1, "maxWeightKg": 20},
                    "cabin": {"quantity": 1, "maxWeightKg": 7},
                },
                "conditions": {
                    "advancePurchaseDays": 3,
                    "minStayDays": 0,
                    "maxStayDays": 90,
                },
                "payment": {
                    "acceptedMethods": [
                        {"code": "CC", "label": "Credit Card"},
                        {"code": "DC", "label": "Debit Card"},
                        {"code": "BT", "label": "Bank Transfer"},
                    ],
                    "timeLimit": "2026-03-21T17:11:00+00:00",
                    "instantTicketingRequired": True,
                },
                "createdAt": "2026-03-19T18:11:19.677935+00:00",
                "expiresAt": "2026-03-19T20:06:00+00:00",
            }
        }
    )
    offer_id: str
    status: str | None = None
    status_label: str
    fare_family: FareFamily
    policies: OfferPolicies
    baggage: BaggageSummary
    conditions: OfferConditions
    payment: PaymentRequirements
    created_at: str | None = None
    expires_at: str | None = None


class BookingContact(ApiModel):
    email: EmailStr
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)


class BookingPassengerRequest(ApiModel):
    title: str | None = None
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    date_of_birth: date
    nationality: str = Field(min_length=2, max_length=3)
    passport_number: str = Field(min_length=3)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)

    @field_validator("title", "nationality", "passport_number")
    @classmethod
    def uppercase_optional(cls, value: str | None) -> str | None:
        return value.upper() if isinstance(value, str) else value

    @field_validator("date_of_birth")
    @classmethod
    def validate_past_dob(cls, value: date) -> date:
        if value >= date.today():
            raise ValueError("dateOfBirth must be in the past")
        return value


class CreateBookingRequest(ApiModel):
    model_config = api_model_config(
        json_schema_extra={
            "example": {
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
            }
        }
    )
    offer_id: str = Field(min_length=1)
    contact: BookingContact
    passengers: list[BookingPassengerRequest] = Field(min_length=1)


class BookingPassengerSummary(ApiModel):
    passenger_id: str | None = None
    type: str | None = None
    type_label: str | None = None
    title: str | None = None
    first_name: str
    last_name: str
    full_name: str | None = None
    date_of_birth: str | None = None
    nationality: str | None = None
    passport_number: str | None = None


class TicketingSummary(ApiModel):
    status: str | None = None
    status_label: str | None = None
    time_limit: str | None = None
    ticket_numbers: list[str]


class BookingSummary(ApiModel):
    model_config = api_model_config(
        json_schema_extra={
            "example": {
                "bookingReference": "EGABE5C6",
                "pnr": "X62106U",
                "status": "CONFIRMED",
                "statusLabel": "Confirmed",
                "offerId": "b441ff9174795f49",
                "passengers": [
                    {
                        "passengerId": "PAX1",
                        "type": "ADT",
                        "typeLabel": "Adult",
                        "title": "MS",
                        "firstName": "Alice",
                        "lastName": "Tan",
                        "fullName": "Tan/Alice MS",
                        "dateOfBirth": "1990-05-12",
                        "nationality": "SG",
                        "passportNumber": "E1234567",
                    }
                ],
                "contact": {
                    "email": "alice@example.com",
                    "phone": "+6591234567",
                },
                "ticketing": {
                    "status": "PENDING",
                    "statusLabel": "Pending",
                    "timeLimit": "2026-03-22T09:11:38.727336+00:00",
                    "ticketNumbers": [],
                },
                "createdAt": "2026-03-19T18:11:38+00:00",
            }
        }
    )
    booking_reference: str
    pnr: str
    status: str | None = None
    status_label: str
    offer_id: str | None = None
    passengers: list[BookingPassengerSummary]
    contact: BookingContact
    ticketing: TicketingSummary
    created_at: str | None = None
