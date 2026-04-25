from __future__ import annotations

STRICT_PRIVACY_LEVELS = {"redacted_text", "courtroom_redacted"}


def normalize_privacy_level(privacy_mode: bool, privacy_level: str | None) -> str:
    if privacy_level:
        normalized = privacy_level.strip().lower().replace("-", "_")
        if normalized in {"full", "path_only", "redacted_text", "courtroom_redacted"}:
            return normalized
    return "redacted_text" if privacy_mode else "full"


def is_strict_redacted(privacy_level: str) -> bool:
    return privacy_level in STRICT_PRIVACY_LEVELS


def privacy_suffix(privacy_level: str) -> str:
    return {
        "full": "internal",
        "path_only": "path_only",
        "redacted_text": "shareable_redacted",
        "courtroom_redacted": "courtroom_redacted",
    }.get(privacy_level, "redacted")
