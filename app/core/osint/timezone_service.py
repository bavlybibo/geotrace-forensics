from __future__ import annotations

"""Offline timezone lookup for native/derived coordinates."""

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any


@dataclass(slots=True)
class TimezoneLookupResult:
    available: bool = False
    timezone: str = "Unavailable"
    method: str = "timezonefinder"
    warning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@lru_cache(maxsize=1)
def _timezone_finder():
    try:
        from timezonefinder import TimezoneFinder  # type: ignore
        return TimezoneFinder()
    except Exception:
        return None


def lookup_timezone(latitude: float | None, longitude: float | None) -> TimezoneLookupResult:
    if latitude is None or longitude is None:
        return TimezoneLookupResult(warning="No coordinate pair available for timezone lookup.")
    finder = _timezone_finder()
    if finder is None:
        return TimezoneLookupResult(warning="timezonefinder is not installed.")
    try:
        tz = finder.timezone_at(lat=float(latitude), lng=float(longitude)) or finder.certain_timezone_at(lat=float(latitude), lng=float(longitude))
        if tz:
            return TimezoneLookupResult(available=True, timezone=str(tz))
        return TimezoneLookupResult(available=True, warning="No timezone polygon matched this coordinate.")
    except Exception as exc:
        return TimezoneLookupResult(available=True, warning=f"Timezone lookup failed: {exc.__class__.__name__}.")
