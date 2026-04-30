from __future__ import annotations

"""Country/city/place normalization helpers for offline geolocation triage.

The module is intentionally dependency-light: it uses only the Python standard
library so GeoTrace can run offline on Windows releases. It improves Arabic/Latin
normalization, country/city alias handling, and conservative fuzzy matching.
"""

from functools import lru_cache
import json
from pathlib import Path
import re
from difflib import SequenceMatcher
import unicodedata
from typing import Any, Iterable

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_TOKEN_RE = re.compile(r"[a-z0-9\u0600-\u06ff]{2,}", re.I)


def data_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "osint"


def strip_accents(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in value if not unicodedata.combining(ch))


@lru_cache(maxsize=20000)
def normalize_place_text(text: str) -> str:
    value = str(text or "").replace("\u200f", " ").replace("\u200e", " ")
    value = _ARABIC_DIACRITICS.sub("", value)
    value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    value = value.replace("ٱ", "ا").replace("ى", "ي").replace("ة", "ه")
    value = value.replace("ؤ", "و").replace("ئ", "ي")
    value = strip_accents(value).casefold()
    value = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def token_set(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(normalize_place_text(text)))


def fuzzy_ratio(a: str, b: str) -> float:
    na, nb = normalize_place_text(a), normalize_place_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ta, tb = token_set(na), token_set(nb)
    token_score = len(ta & tb) / max(1, len(ta | tb)) if ta or tb else 0.0
    seq_score = SequenceMatcher(None, na, nb).ratio()
    return max(seq_score, token_score)


def alias_in_text(alias: str, text: str) -> bool:
    alias_norm = normalize_place_text(alias)
    text_norm = normalize_place_text(text)
    if not alias_norm or not text_norm:
        return False
    # Avoid weak one-token accidental matches such as "la".
    if len(alias_norm) <= 2:
        return False
    return re.search(rf"(?<![a-z0-9\u0600-\u06ff]){re.escape(alias_norm)}(?![a-z0-9\u0600-\u06ff])", text_norm) is not None


@lru_cache(maxsize=1)
def load_geo_alias_data() -> dict[str, Any]:
    path = data_root() / "geo_aliases.json"
    if not path.exists():
        return {"countries": [], "cities": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"countries": [], "cities": []}
    return data if isinstance(data, dict) else {"countries": [], "cities": []}


def _iter_alias_rows(kind: str) -> Iterable[dict[str, Any]]:
    rows = load_geo_alias_data().get(kind, [])
    return rows if isinstance(rows, list) else []


@lru_cache(maxsize=4096)
def normalize_country(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return "Unknown"
    target = normalize_place_text(clean)
    for row in _iter_alias_rows("countries"):
        aliases = [row.get("name", ""), row.get("iso2", ""), *(row.get("aliases", []) or [])]
        if any(normalize_place_text(alias) == target for alias in aliases if alias):
            return str(row.get("name") or clean)
    for row in _iter_alias_rows("countries"):
        aliases = [row.get("name", ""), *(row.get("aliases", []) or [])]
        if any(alias_in_text(str(alias), target) or alias_in_text(target, str(alias)) for alias in aliases if alias):
            return str(row.get("name") or clean)
    return clean


@lru_cache(maxsize=8192)
def normalize_city(value: str, *, country: str = "") -> tuple[str, str]:
    clean = str(value or "").strip()
    if not clean:
        return "Unknown", normalize_country(country) if country else "Unknown"
    target = normalize_place_text(clean)
    best: tuple[float, dict[str, Any] | None] = (0.0, None)
    for row in _iter_alias_rows("cities"):
        if country:
            row_country = normalize_country(str(row.get("country", "")))
            if row_country != normalize_country(country):
                continue
        aliases = [row.get("name", ""), *(row.get("aliases", []) or [])]
        for alias in aliases:
            score = 1.0 if normalize_place_text(str(alias)) == target else fuzzy_ratio(str(alias), clean)
            if alias_in_text(str(alias), clean) or alias_in_text(clean, str(alias)):
                score = max(score, 0.94)
            if score > best[0]:
                best = (score, row)
    if best[1] and best[0] >= 0.84:
        return str(best[1].get("name") or clean), normalize_country(str(best[1].get("country") or country))
    return clean, normalize_country(country) if country else "Unknown"


def enrich_aliases(name: str, aliases: Iterable[str] = (), *, city: str = "", country: str = "") -> list[str]:
    values: list[str] = []
    for item in [name, city, country, *aliases]:
        text = str(item or "").strip()
        if text and text not in values:
            values.append(text)
    norm_country = normalize_country(country)
    norm_city, _ = normalize_city(city, country=norm_country) if city else ("", norm_country)
    for row in _iter_alias_rows("countries"):
        if normalize_country(str(row.get("name", ""))) == norm_country:
            for alias in [row.get("name", ""), row.get("iso2", ""), *(row.get("aliases", []) or [])]:
                if alias and alias not in values:
                    values.append(str(alias))
    for row in _iter_alias_rows("cities"):
        if norm_city and normalize_place_text(str(row.get("name", ""))) == normalize_place_text(norm_city):
            for alias in [row.get("name", ""), *(row.get("aliases", []) or [])]:
                if alias and alias not in values:
                    values.append(str(alias))
    return values


def score_alias_against_text(alias: str, text_segments: Iterable[str]) -> tuple[int, str]:
    """Return a conservative 0-100 text score and evidence label."""
    alias_norm = normalize_place_text(alias)
    if len(alias_norm) < 3:
        return 0, ""
    best = 0
    best_label = ""
    for segment in text_segments:
        segment = str(segment or "")
        seg_norm = normalize_place_text(segment)
        if not seg_norm:
            continue
        if alias_in_text(alias_norm, seg_norm):
            score = 100 if len(alias_norm) >= 5 else 82
            label = alias
        else:
            # Fuzzy compare against short OCR lines/tokens, not the whole document blob.
            ratio = fuzzy_ratio(alias_norm, seg_norm)
            alias_tokens = token_set(alias_norm)
            seg_tokens = token_set(seg_norm)
            if alias_tokens and alias_tokens <= seg_tokens:
                ratio = max(ratio, 0.92)
            if ratio >= 0.88 and len(alias_norm) >= 5:
                score = int(70 + min(25, (ratio - 0.88) * 200))
                label = f"fuzzy:{alias}:{ratio:.2f}"
            else:
                score = 0
                label = ""
        if score > best:
            best, best_label = score, label
    return best, best_label
