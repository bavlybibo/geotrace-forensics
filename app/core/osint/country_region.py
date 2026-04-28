from __future__ import annotations

"""Offline country/region classifier for CTF-style geolocation clues."""

import re
from typing import Iterable

_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_EGYPT_PHONE_RE = re.compile(r"(?:\+?20|0)?1[0125][0-9]{8}\b")
_GULF_PHONE_RE = re.compile(r"(?:\+?966|\+?971|\+?974|\+?965|\+?968|\+?973)\b")
_UK_PHONE_RE = re.compile(r"(?:\+?44|0)7\d{9}\b")
_US_PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_COORD_EGYPT_BOX_RE = re.compile(r"\b(2[2-9]|3[01])\.\d{3,}\s*,\s*3[0-4]\.\d{3,}\b")

_EGYPT_WORDS = (
    "egypt", "cairo", "giza", "alexandria", "luxor", "aswan", "suez", "mansoura", "tanta",
    "القاهرة", "القاهره", "الجيزة", "جيزة", "الإسكندرية", "الاسكندرية", "اسكندرية", "مصر",
    "شارع", "ميدان", "كورنيش", "محطة", "كوبري", "كوبرى", "طريق", "حي", "مول",
)
_GULF_WORDS = (
    "saudi", "riyadh", "jeddah", "uae", "dubai", "abu dhabi", "doha", "kuwait", "muscat", "bahrain",
    "دبي", "دبى", "الرياض", "جدة", "جده", "أبوظبي", "ابوظبي", "الدوحة", "الكويت",
)
_UK_WORDS = ("london", "manchester", "birmingham", "glasgow", "westminster", ".uk", "postcode")
_US_WORDS = ("new york", "california", "los angeles", "nyc", "usa", "united states", ".gov", ".us")
_EU_WORDS = ("paris", "france", "berlin", "germany", "madrid", "rome", "italy", "spain", ".fr", ".de", ".it", ".es")
_JORDAN_WORDS = ("jordan", "amman", "petra", "dead sea", "الأردن", "الاردن", "عمان", "البتراء")
_SAUDI_WORDS = ("saudi arabia", "saudi", "riyadh", "jeddah", "mecca", "makkah", "kaaba", "السعودية", "السعوديه", "الرياض", "جدة", "جده", "مكة", "مكه", "الكعبة", "الكعبه")
_UAE_WORDS = ("united arab emirates", "uae", "dubai", "abu dhabi", "burj khalifa", "الإمارات", "الامارات", "دبي", "دبى", "أبوظبي", "ابوظبي", "برج خليفة")
_JAPAN_WORDS = ("japan", "tokyo", "osaka", "kyoto", ".jp", "日本", "東京", "طوكيو", "اليابان")
_AUSTRALIA_WORDS = ("australia", "sydney", "melbourne", ".au", "sydney opera house", "أستراليا", "استراليا", "سيدني")
_TURKEY_WORDS = ("turkey", "istanbul", "ankara", "bosphorus", "hagia sophia", "sultanahmet", ".tr", "تركيا", "اسطنبول", "إسطنبول")
_INDIA_WORDS = ("india", "delhi", "mumbai", "agra", "taj mahal", ".in", "الهند", "دلهي", "تاج محل")
_CANADA_WORDS = ("canada", "toronto", "vancouver", "montreal", ".ca", "كندا", "تورنتو", "فانكوفر")
_BRAZIL_WORDS = ("brazil", "rio de janeiro", "sao paulo", "christ the redeemer", ".br", "البرازيل", "ريو دي جانيرو")
_SINGAPORE_WORDS = ("singapore", "marina bay", "sentosa", ".sg", "سنغافورة", "مارينا باي")


def _hits(blob: str, words: Iterable[str]) -> list[str]:
    return [word for word in words if word.lower() in blob]


def classify_country_region(texts: Iterable[str]) -> tuple[str, int, list[str]]:
    blob = "\n".join(str(t or "") for t in texts).lower()
    reasons: list[str] = []

    profiles: list[tuple[str, int, list[str]]] = []

    egypt_score = 0
    egypt_reasons: list[str] = []
    if _ARABIC_RE.search(blob):
        egypt_score += 14
        egypt_reasons.append("Arabic script detected")
    if _EGYPT_PHONE_RE.search(blob):
        egypt_score += 36
        egypt_reasons.append("Egyptian mobile-phone pattern detected")
    if _COORD_EGYPT_BOX_RE.search(blob):
        egypt_score += 34
        egypt_reasons.append("Coordinates fall inside the broad Egypt bounding box")
    egypt_hits = _hits(blob, _EGYPT_WORDS)
    if egypt_hits:
        egypt_score += min(50, 16 + len(egypt_hits) * 7)
        egypt_reasons.append("Egypt place/language tokens: " + ", ".join(egypt_hits[:6]))
    if ".eg" in blob:
        egypt_score += 30
        egypt_reasons.append(".eg domain clue detected")
    profiles.append(("Egypt / Arabic-speaking region", min(96, egypt_score), egypt_reasons))

    gulf_score = 0
    gulf_reasons: list[str] = []
    if _ARABIC_RE.search(blob):
        gulf_score += 12
        gulf_reasons.append("Arabic script detected")
    if _GULF_PHONE_RE.search(blob):
        gulf_score += 34
        gulf_reasons.append("Gulf country calling-code pattern detected")
    gulf_hits = _hits(blob, _GULF_WORDS)
    if gulf_hits:
        gulf_score += min(46, 18 + len(gulf_hits) * 8)
        gulf_reasons.append("Gulf/Middle East tokens: " + ", ".join(gulf_hits[:6]))
    profiles.append(("Gulf / Middle East region", min(88, gulf_score), gulf_reasons))

    uk_score = 0
    uk_reasons: list[str] = []
    if _UK_PHONE_RE.search(blob):
        uk_score += 28
        uk_reasons.append("UK mobile-phone pattern detected")
    uk_hits = _hits(blob, _UK_WORDS)
    if uk_hits:
        uk_score += min(45, 18 + len(uk_hits) * 8)
        uk_reasons.append("UK tokens: " + ", ".join(uk_hits[:5]))
    profiles.append(("United Kingdom / UK-region clue", min(78, uk_score), uk_reasons))

    us_score = 0
    us_reasons: list[str] = []
    if _US_PHONE_RE.search(blob):
        us_score += 18
        us_reasons.append("US-style phone-number pattern detected")
    us_hits = _hits(blob, _US_WORDS)
    if us_hits:
        us_score += min(45, 18 + len(us_hits) * 8)
        us_reasons.append("US tokens: " + ", ".join(us_hits[:5]))
    profiles.append(("United States / North America clue", min(72, us_score), us_reasons))

    eu_hits = _hits(blob, _EU_WORDS)
    if eu_hits:
        profiles.append(("Europe / major-city clue", min(72, 18 + len(eu_hits) * 8), ["Europe tokens: " + ", ".join(eu_hits[:5])]))

    # More specific regional profiles help CTF mode rank broad country clues
    # without relying on online lookups. They only become useful when explicit
    # text/phone/domain/landmark tokens are present.
    specific_profiles = [
        ("Saudi Arabia", _SAUDI_WORDS, "+966"),
        ("United Arab Emirates", _UAE_WORDS, "+971"),
        ("Jordan", _JORDAN_WORDS, "+962"),
        ("Japan", _JAPAN_WORDS, "+81"),
        ("Australia", _AUSTRALIA_WORDS, "+61"),
        ("Turkey", _TURKEY_WORDS, "+90"),
        ("India", _INDIA_WORDS, "+91"),
        ("Canada", _CANADA_WORDS, "+1"),
        ("Brazil", _BRAZIL_WORDS, "+55"),
        ("Singapore", _SINGAPORE_WORDS, "+65"),
    ]
    for label, words, phone_code in specific_profiles:
        score = 0
        local_reasons: list[str] = []
        hits = _hits(blob, words)
        if hits:
            score += min(62, 22 + len(hits) * 10)
            local_reasons.append(f"{label} tokens: " + ", ".join(hits[:6]))
        if phone_code in blob:
            score += 34
            local_reasons.append(f"{label} calling-code clue detected")
        if score:
            profiles.append((f"{label} / country clue", min(90, score), local_reasons))

    best = max(profiles, key=lambda row: row[1]) if profiles else ("Unknown", 0, [])
    if best[1] >= 30:
        return best[0], best[1], best[2][:6]
    if _ARABIC_RE.search(blob):
        return "Arabic-speaking region", 28, ["Arabic script visible but no strong country token"]
    if re.search(r"[A-Za-z]", blob):
        return "Latin-script / global", 24, ["Latin script visible but no strong country token"]
    return "Unknown", 0, reasons
