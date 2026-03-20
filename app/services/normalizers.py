from __future__ import annotations

from math import ceil
from typing import Any

from app.core.codes import (
    AIRLINE_NAMES,
    BOOKING_STATUS_LABELS,
    CABIN_LABELS,
    FARE_FAMILY_LABELS,
    PASSENGER_TYPE_LABELS,
    PAYMENT_METHOD_LABELS,
)
from app.core.dates import normalize_date, normalize_datetime


def paginate(items: list[Any], *, page: int, page_size: int) -> tuple[list[Any], int]:
    total_items = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total_items


def total_pages(*, total_items: int, page_size: int) -> int:
    return max(1, ceil(total_items / page_size)) if total_items else 0


async def normalize_search_response(
    payload: dict[str, Any],
    *,
    page: int,
    page_size: int,
    reference_data,
) -> dict[str, Any]:
    raw_items = (
        payload.get("data", {})
        .get("flight_results", {})
        .get("outbound", {})
        .get("results", [])
    )
    selected_items, total_items = paginate(raw_items, page=page, page_size=page_size)
    normalized_items = [
        await normalize_search_item(item, reference_data=reference_data) for item in selected_items
    ]

    meta = payload.get("meta", {})
    search_id = payload.get("data", {}).get("search_id") or payload.get("data", {}).get("SearchId")

    return {
        "items": normalized_items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages(total_items=total_items, page_size=page_size),
        },
        "meta": {
            "search_id": search_id,
            "provider": meta.get("provider"),
            "request_time_ms": meta.get("request_time_ms"),
            "cache_hit": meta.get("cache_hit"),
        },
    }


async def normalize_search_item(item: dict[str, Any], *, reference_data) -> dict[str, Any]:
    segments = item.get("segments", {}).get("segment_list", [])
    leg_summaries: list[dict[str, Any]] = []

    for segment in segments:
        for leg in segment.get("leg_data", []):
            leg_summaries.append(await normalize_leg(leg, reference_data=reference_data))

    first_leg = leg_summaries[0] if leg_summaries else _blank_leg()
    last_leg = leg_summaries[-1] if leg_summaries else _blank_leg()

    validating_code = item.get("validating_carrier") or first_leg["carrier"]["code"]
    price = item.get("pricing", {})
    tax_info = price.get("taxes_fees", {})
    cabin_code = item.get("booking_class") or item.get("cabin") or first_leg["cabin"]["code"] or "Y"

    return {
        "offer_id": item.get("offer_id") or item.get("offerId"),
        "price": {
            "amount": float(_coerce_number(price.get("totalAmountDecimal"), price.get("total")) or 0),
            "currency": price.get("currency") or price.get("CurrencyCode"),
            "base_amount": _coerce_number(price.get("base_fare"), price.get("BaseFare")),
            "tax_amount": _coerce_number(tax_info.get("total_tax"), tax_info.get("TotalTax")),
        },
        "stops": item.get("num_stops", item.get("stops", 0)),
        "duration_minutes": item.get("total_journey_time"),
        "duration": item.get("total_journey"),
        "is_refundable": bool(item.get("refundable", item.get("isRefundable"))),
        "seats_remaining": item.get("seats_remaining", item.get("seatAvailability", item.get("avl_seats"))),
        "carrier": first_leg["carrier"],
        "validating_carrier": {
            "code": validating_code,
            "name": AIRLINE_NAMES.get(validating_code, validating_code),
            "flight_number": validating_code,
        },
        "cabin": {"code": cabin_code, "label": CABIN_LABELS.get(cabin_code, cabin_code)},
        "departure": first_leg["departure"],
        "arrival": last_leg["arrival"],
        "segments": leg_summaries,
        "baggage": {
            "checked": {
                "quantity": item.get("baggage", {}).get("checked", {}).get("pieces"),
                "max_weight_kg": item.get("baggage", {}).get("checked", {}).get("weight_kg"),
            },
            "cabin": {
                "quantity": item.get("baggage", {}).get("cabin_baggage", {}).get("pieces"),
                "max_weight_kg": item.get("baggage", {}).get("cabin_baggage", {}).get("weight_kg"),
            },
        },
    }


async def normalize_leg(leg: dict[str, Any], *, reference_data) -> dict[str, Any]:
    departure_info = leg.get("departure_info", {})
    arrival_info = leg.get("arrival_info", {})

    departure_airport_code = departure_info.get("airport", {}).get("code")
    arrival_airport_code = arrival_info.get("airport", {}).get("code")

    departure_airport = await reference_data.get_airport(departure_airport_code)
    arrival_airport = await reference_data.get_airport(arrival_airport_code)

    departure_tz = departure_airport.get("tz_offset")
    arrival_tz = arrival_airport.get("tz_offset")

    carrier_code = (
        leg.get("carrier", {}).get("marketing")
        or leg.get("carrier", {}).get("mktg_carrier")
        or leg.get("carrier", {}).get("operating")
        or ""
    )
    flight_number = leg.get("carrier", {}).get("number") or f"{carrier_code}{leg.get('carrier', {}).get('flight_no', '')}"
    cabin_code = leg.get("cabin_class") or leg.get("cabin") or "Y"

    return {
        "carrier": {
            "code": carrier_code,
            "name": AIRLINE_NAMES.get(carrier_code, carrier_code),
            "flight_number": flight_number,
        },
        "departure": {
            "airport": airport_summary(
                departure_airport,
                terminal=departure_info.get("airport", {}).get("terminal"),
            ),
            "date_time": normalize_datetime(
                departure_info.get("scheduled_time") or departure_info.get("dt"),
                tz_offset_hours=departure_tz,
            ),
        },
        "arrival": {
            "airport": airport_summary(
                arrival_airport,
                terminal=arrival_info.get("airport", {}).get("terminal"),
            ),
            "date_time": normalize_datetime(
                arrival_info.get("scheduled_time") or arrival_info.get("arr_date"),
                tz_offset_hours=arrival_tz,
            ),
        },
        "duration_minutes": leg.get("duration_minutes"),
        "aircraft_code": leg.get("equipment", {}).get("aircraft_code") or leg.get("equipment", {}).get("type"),
        "cabin": {"code": cabin_code, "label": CABIN_LABELS.get(cabin_code, cabin_code)},
    }


def normalize_offer_response(payload: dict[str, Any]) -> dict[str, Any]:
    offer = payload.get("data", {}).get("offer", {})
    fare_details = offer.get("fare_details", {})
    rules = fare_details.get("rules", {})
    baggage = offer.get("baggage_allowance", {})

    fare_code = fare_details.get("FareFamily")
    fare_name = fare_details.get("fare_family")

    return {
        "offer_id": offer.get("id") or offer.get("offer_id"),
        "status": offer.get("status") or offer.get("StatusCode"),
        "status_label": BOOKING_STATUS_LABELS.get(offer.get("status"), offer.get("status", "Unknown")),
        "fare_family": {
            "code": fare_code,
            "name": fare_name,
            "label": FARE_FAMILY_LABELS.get(fare_code) or FARE_FAMILY_LABELS.get(fare_name, fare_name or "Unknown"),
        },
        "policies": {
            "refund": policy_rule(rules.get("refund")),
            "change": policy_rule(rules.get("change")),
            "no_show": policy_rule(rules.get("no_show")),
        },
        "baggage": {
            "checked": {
                "quantity": baggage.get("checked", {}).get("quantity"),
                "max_weight_kg": baggage.get("checked", {}).get("max_weight_kg"),
            },
            "cabin": {
                "quantity": baggage.get("carry_on", {}).get("quantity"),
                "max_weight_kg": baggage.get("carry_on", {}).get("max_weight_kg"),
            },
        },
        "conditions": {
            "advance_purchase_days": offer.get("conditions", {}).get("advance_purchase_days"),
            "min_stay_days": offer.get("conditions", {}).get("min_stay_days"),
            "max_stay_days": offer.get("conditions", {}).get("max_stay_days"),
        },
        "payment": {
            "accepted_methods": [
                {"code": code, "label": PAYMENT_METHOD_LABELS.get(code, code)}
                for code in offer.get("payment_requirements", {}).get("accepted_methods", [])
            ],
            "time_limit": normalize_datetime(offer.get("payment_requirements", {}).get("time_limit")),
            "instant_ticketing_required": bool(
                offer.get("payment_requirements", {}).get("instant_ticketing_required", False)
            ),
        },
        "created_at": normalize_datetime(offer.get("created_at")),
        "expires_at": normalize_datetime(offer.get("expires_at")),
    }


def normalize_booking_response(payload: dict[str, Any]) -> dict[str, Any]:
    booking = (
        payload.get("data", {}).get("reservation")
        or payload.get("data", {}).get("Reservation")
        or payload.get("data", {})
    )

    return {
        "booking_reference": booking.get("booking_ref") or booking.get("BookingReference"),
        "pnr": booking.get("pnr") or booking.get("PNR"),
        "status": booking.get("status") or booking.get("StatusCode"),
        "status_label": BOOKING_STATUS_LABELS.get(
            booking.get("status") or booking.get("StatusCode"),
            booking.get("status") or booking.get("StatusCode") or "Unknown",
        ),
        "offer_id": booking.get("offer_id"),
        "passengers": [
            {
                "passenger_id": passenger.get("pax_id"),
                "type": passenger.get("type") or passenger.get("PaxType"),
                "type_label": PASSENGER_TYPE_LABELS.get(
                    passenger.get("type") or passenger.get("PaxType"),
                    passenger.get("type") or passenger.get("PaxType"),
                ),
                "title": passenger.get("title"),
                "first_name": passenger.get("first_name") or passenger.get("FirstName"),
                "last_name": passenger.get("last_name") or passenger.get("LastName"),
                "full_name": passenger.get("name"),
                "date_of_birth": normalize_date(passenger.get("dob") or passenger.get("DateOfBirth")),
                "nationality": passenger.get("nationality"),
                "passport_number": passenger.get("passport_no"),
            }
            for passenger in booking.get("passengers", [])
        ],
        "contact": {
            "email": booking.get("contact", {}).get("email") or booking.get("contact", {}).get("EmailAddress"),
            "phone": booking.get("contact", {}).get("phone"),
        },
        "ticketing": {
            "status": booking.get("ticketing", {}).get("status"),
            "status_label": BOOKING_STATUS_LABELS.get(
                booking.get("ticketing", {}).get("status"),
                booking.get("ticketing", {}).get("status"),
            ),
            "time_limit": normalize_datetime(booking.get("ticketing", {}).get("time_limit")),
            "ticket_numbers": booking.get("ticketing", {}).get("ticket_numbers", []),
        },
        "created_at": normalize_datetime(booking.get("created_at") or booking.get("CreatedDateTime")),
    }


def airport_summary(airport: dict[str, Any], *, terminal: str | None) -> dict[str, Any]:
    code = airport.get("code") or airport.get("IATA") or "UNK"
    city = airport.get("city")
    label = f"{city} ({code})" if city else code

    return {
        "code": code,
        "city": city,
        "country_code": airport.get("country_code") or airport.get("CC"),
        "label": label,
        "terminal": terminal,
        "timezone_offset_hours": airport.get("tz_offset"),
    }


def policy_rule(value: dict[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    penalty = value.get("penalty") or {}
    return {
        "allowed": value.get("allowed"),
        "penalty": {
            "amount": _coerce_number(penalty.get("amount")),
            "currency": penalty.get("currency") or penalty.get("CurrencyCode"),
        }
        if penalty
        else None,
    }


def _coerce_number(*values: Any) -> float | None:
    for value in values:
        if value in (None, ""):
            continue
        return float(value)
    return None


def _blank_leg() -> dict[str, Any]:
    return {
        "carrier": {"code": "", "name": "", "flight_number": ""},
        "departure": {"airport": airport_summary({"code": "UNK"}, terminal=None), "date_time": None},
        "arrival": {"airport": airport_summary({"code": "UNK"}, terminal=None), "date_time": None},
        "cabin": {"code": "Y", "label": CABIN_LABELS["Y"]},
    }

