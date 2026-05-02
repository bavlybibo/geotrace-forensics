from __future__ import annotations

"""Optional country normalization using pycountry with local aliases."""

from functools import lru_cache
from typing import Any

ALIASES = {
    "egypt": "EG",
    "مصر": "EG",
    "arab republic of egypt": "EG",
    "usa": "US",
    "united states": "US",
    "uk": "GB",
    "united kingdom": "GB",
}


@lru_cache(maxsize=1)
def _pycountry():
    try:
        import pycountry  # type: ignore
        return pycountry
    except Exception:
        return None


def normalize_country(value: str) -> dict[str, Any]:
    text = (value or "").strip()
    if not text:
        return {"available": False, "input": value, "match": "", "alpha_2": "", "name": ""}
    module = _pycountry()
    alias = ALIASES.get(text.lower(), text.upper() if len(text) == 2 else text)
    if module is None:
        return {"available": False, "input": value, "match": alias, "alpha_2": "", "name": "", "warning": "pycountry is not installed."}
    try:
        country = module.countries.lookup(alias)
        return {"available": True, "input": value, "match": getattr(country, "alpha_2", ""), "alpha_2": getattr(country, "alpha_2", ""), "alpha_3": getattr(country, "alpha_3", ""), "name": getattr(country, "name", "")}
    except Exception:
        return {"available": True, "input": value, "match": "", "alpha_2": "", "name": "", "warning": "No ISO country match."}
