from __future__ import annotations

from typing import Iterable, Tuple



def ratio_to_float(value) -> float:
    if hasattr(value, "num") and hasattr(value, "den"):
        return float(value.num) / float(value.den)
    if isinstance(value, str) and "/" in value:
        num, den = value.split("/", 1)
        return float(num) / float(den)
    return float(value)



def dms_to_decimal(values: Iterable, ref: str) -> float:
    values = list(values)
    degrees = ratio_to_float(values[0])
    minutes = ratio_to_float(values[1])
    seconds = ratio_to_float(values[2])
    result = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in {"S", "W"}:
        result *= -1
    return round(result, 6)



def format_coordinates(latitude: float, longitude: float) -> str:
    return f"{latitude:.6f}, {longitude:.6f}"
