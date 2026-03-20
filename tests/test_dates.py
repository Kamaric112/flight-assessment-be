from app.core.dates import normalize_datetime


def test_normalize_iso_datetime_with_offset() -> None:
    assert normalize_datetime("2026-04-15T19:15:00+08:00") == "2026-04-15T19:15:00+08:00"


def test_normalize_display_datetime_with_airport_offset() -> None:
    assert normalize_datetime("15-Apr-2026 12:50 PM", tz_offset_hours=8) == "2026-04-15T12:50:00+08:00"


def test_normalize_compact_datetime_with_airport_offset() -> None:
    assert normalize_datetime("20260415145300", tz_offset_hours=7) == "2026-04-15T14:53:00+07:00"


def test_normalize_unix_datetime_with_airport_offset() -> None:
    assert normalize_datetime(1776211800, tz_offset_hours=8) == "2026-04-15T08:10:00+08:00"

