from __future__ import annotations

"""Small offline gazetteer for map/OCR place normalisation.

The first version intentionally ships as code constants so the app remains portable.
A future build can load JSON dictionaries from app/core/osint/gazetteer/*.json.
"""

import re
from typing import Iterable, Mapping

ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")

CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "Cairo": (
        "cairo", "القاهرة", "القاهره", "new cairo", "التجمع", "مصر الجديدة",
        "مدينة نصر", "nasr city", "heliopolis", "downtown cairo", "وسط البلد",
    ),
    "Giza": (
        "giza", "الجيزة", "جيزة", "dokki", "الدقي", "mohandessin", "المهندسين",
        "haram", "الهرم", "faisal", "فيصل", "sheikh zayed", "الشيخ زايد",
    ),
    "Alexandria": ("alexandria", "الإسكندرية", "الاسكندرية", "stanley", "سموحة", "sidi gaber"),
    "Luxor": ("luxor", "الأقصر", "الاقصر"),
    "Aswan": ("aswan", "أسوان", "اسوان"),
    "Madrid": ("madrid", "مدريد"),
    "Barcelona": ("barcelona", "برشلونة"),
    "Valencia": ("valencia", "valència", "فالنسيا"),
    "Zaragoza": ("zaragoza", "سرقسطة"),
    "Seville": ("seville", "sevilla", "إشبيلية", "اشبيلية"),
    "Bilbao": ("bilbao", "بلباو"),
    "Lisbon": ("lisbon", "lisboa", "لشبونة", "لشبونه"),
    "Porto": ("porto", "oporto", "بورتو"),
    "Toulouse": ("toulouse", "تولوز"),
    "Bordeaux": ("bordeaux", "بوردو"),
    "Montpellier": ("montpellier", "مونبلييه"),
}

AREA_ALIASES: dict[str, tuple[str, ...]] = {
    "Zamalek": ("zamalek", "الزمالك"),
    "Garden City": ("garden city", "جاردن سيتي", "جاردن سيتى"),
    "Heliopolis": ("heliopolis", "مصر الجديدة", "مصر الجديده"),
    "Nasr City": ("nasr city", "مدينة نصر", "مدينه نصر"),
    "New Cairo": ("new cairo", "التجمع", "التجمع الخامس", "القاهرة الجديدة", "القاهره الجديده"),
    "Dokki": ("dokki", "الدقي", "الدقى"),
    "Mohandessin": ("mohandessin", "المهندسين"),
    "Maadi": ("maadi", "المعادي", "المعادى"),
    "Tahrir": ("tahrir", "التحرير", "ميدان التحرير"),
    "Nile Corniche": ("nile", "corniche", "النيل", "كورنيش"),
    "Haram": ("haram", "الهرم", "pyramids road"),
    "6th of October": ("6th of october", "october city", "مدينة 6 أكتوبر", "مدينه 6 اكتوبر"),
    "Spain": ("spain", "españa", "espana", "إسبانيا", "اسبانيا"),
    "Portugal": ("portugal", "البرتغال"),
    "France": ("france", "فرنسا"),
    "Andorra": ("andorra", "اندورا"),
    "Morocco": ("morocco", "المغرب"),
    "Algeria": ("algeria", "الجزائر"),
}

LANDMARK_ALIASES: dict[str, tuple[str, ...]] = {
    "Fairmont Nile City": ("fairmont nile city", "فيرمونت نايل", "فيرمونت النيل"),
    "Cairo by Royal Tulip": ("cairo by royal tulip", "royal tulip"),
    "Cairo Tower": ("cairo tower", "برج القاهرة", "برج القاهره"),
    "Egyptian Museum": ("egyptian museum", "المتحف المصري", "المتحف المصرى"),
    "Cairo Stadium": ("cairo stadium", "استاد القاهرة", "ستاد القاهرة", "استاد القاهره"),
    "Nile River": ("nile", "river nile", "النيل", "نهر النيل"),
    "Tahrir Square": ("tahrir square", "ميدان التحرير"),
    "Giza Pyramids": ("giza pyramids", "pyramids", "الأهرامات", "الاهرامات", "اهرامات الجيزة"),
    "Khan el-Khalili": ("khan el khalili", "خان الخليلي", "خان الخليلى"),
    "Cairo International Airport": ("cairo international airport", "مطار القاهرة", "مطار القاهره"),
    "Google Maps": ("google maps", "خرائط google", "خرائط جوجل", "google خرائط"),
}


def contains_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text or ""))


def normalize_text(text: str) -> str:
    value = str(text or "").replace("\u200f", " ").replace("\u200e", " ")
    value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    value = value.replace("ى", "ي").replace("ة", "ه")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def unique(items: Iterable[str], limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = re.sub(r"\s+", " ", str(item or "")).strip(" -:|•·")
        if not clean:
            continue
        key = normalize_text(clean).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= limit:
            break
    return out


def first_match(text: str, aliases: Mapping[str, tuple[str, ...]]) -> str:
    lower = normalize_text(text).lower()
    for canonical, tokens in aliases.items():
        if any(normalize_text(token).lower() in lower for token in tokens):
            return canonical
    return "Unavailable"


def all_matches(text: str, aliases: Mapping[str, tuple[str, ...]], limit: int = 8) -> list[str]:
    lower = normalize_text(text).lower()
    matches = [canonical for canonical, tokens in aliases.items() if any(normalize_text(token).lower() in lower for token in tokens)]
    return unique(matches, limit=limit)


def classify_known_places(text: str) -> dict[str, list[str] | str]:
    return {
        "city": first_match(text, CITY_ALIASES),
        "area": first_match(text, AREA_ALIASES),
        "landmarks": all_matches(text, LANDMARK_ALIASES, limit=10),
    }


# ---------------------------------------------------------------------------
# v12.10.25: data-driven alias expansion + fuzzy matching helpers
# ---------------------------------------------------------------------------
try:
    from .geo_normalizer import load_geo_alias_data, normalize_place_text, fuzzy_ratio
except Exception:  # pragma: no cover
    load_geo_alias_data = None  # type: ignore[assignment]
    normalize_place_text = normalize_text  # type: ignore[assignment]
    fuzzy_ratio = None  # type: ignore[assignment]


def _expanded_aliases(base: Mapping[str, tuple[str, ...]], kind: str) -> dict[str, tuple[str, ...]]:
    expanded: dict[str, list[str]] = {key: list(values) for key, values in base.items()}
    if not load_geo_alias_data:
        return {key: tuple(values) for key, values in expanded.items()}
    data = load_geo_alias_data()  # type: ignore[misc]
    rows = data.get("cities" if kind == "city" else "countries", []) if isinstance(data, dict) else []
    for row in rows if isinstance(rows, list) else []:
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        values = expanded.setdefault(name, [])
        for alias in [name, *(row.get("aliases", []) or [])]:
            alias = str(alias or "").strip()
            if alias and alias not in values:
                values.append(alias)
    return {key: tuple(values) for key, values in expanded.items()}


CITY_ALIASES = _expanded_aliases(CITY_ALIASES, "city")
AREA_ALIASES = _expanded_aliases(AREA_ALIASES, "area")


def fuzzy_matches(text: str, aliases: Mapping[str, tuple[str, ...]], *, limit: int = 8, threshold: float = 0.88) -> list[str]:
    if not fuzzy_ratio:
        return []
    segments = unique(re.split(r"[\n,|;•]+", str(text or "")), limit=50)
    scored: list[tuple[float, str]] = []
    for canonical, tokens in aliases.items():
        best = 0.0
        for token in tokens:
            for segment in segments:
                best = max(best, fuzzy_ratio(token, segment))  # type: ignore[misc]
        if best >= threshold:
            scored.append((best, canonical))
    scored.sort(key=lambda x: (-x[0], x[1].lower()))
    return unique([name for _, name in scored], limit=limit)


def classify_known_places(text: str) -> dict[str, list[str] | str]:  # type: ignore[override]
    city = first_match(text, CITY_ALIASES)
    area = first_match(text, AREA_ALIASES)
    landmarks = all_matches(text, LANDMARK_ALIASES, limit=10)
    if city == "Unavailable":
        fm = fuzzy_matches(text, CITY_ALIASES, limit=1)
        city = fm[0] if fm else "Unavailable"
    if area == "Unavailable":
        fm = fuzzy_matches(text, AREA_ALIASES, limit=1)
        area = fm[0] if fm else "Unavailable"
    return {"city": city, "area": area, "landmarks": landmarks}

