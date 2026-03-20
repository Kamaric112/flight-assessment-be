from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from dateutil import parser


KNOWN_DATETIME_FORMATS = (
    "%d-%b-%Y %I:%M %p",
    "%d/%m/%Y %H:%M",
    "%Y%m%d%H%M%S",
)


def timezone_from_offset(offset_hours: float | int | None) -> timezone | None:
    if offset_hours is None:
        return None
    return timezone(timedelta(hours=float(offset_hours)))


def normalize_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC).date().isoformat()

    text = str(value).strip()
    try:
        return parser.isoparse(text).date().isoformat()
    except ValueError:
        try:
            return parser.parse(text, dayfirst=True).date().isoformat()
        except (ValueError, OverflowError):
            return text


def normalize_datetime(value: Any, *, tz_offset_hours: float | int | None = None) -> str | None:
    if value in (None, ""):
        return None

    target_tz = timezone_from_offset(tz_offset_hours)
    parsed: datetime

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(value, UTC)
    else:
        text = str(value).strip()
        try:
            parsed = parser.isoparse(text)
        except ValueError:
            parsed = _parse_fallback_datetime(text)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=target_tz or UTC)
    elif target_tz is not None:
        parsed = parsed.astimezone(target_tz)

    return parsed.isoformat()


def _parse_fallback_datetime(value: str) -> datetime:
    for fmt in KNOWN_DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return parser.parse(value, dayfirst=True)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Unsupported datetime value: {value}") from exc

