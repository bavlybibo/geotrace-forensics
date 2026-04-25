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
