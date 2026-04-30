from __future__ import annotations

"""Reusable privacy redaction engine for reports, previews, and package verification.

The engine is intentionally local and deterministic. It does not delete source
records; it produces redacted display/export values and an auditable hit summary.
"""

from dataclasses import asdict, dataclass, field
import re
from typing import Iterable

SENSITIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "url": re.compile(r"https?://[^\s)>'\"]+|www\.[^\s)>'\"]+", re.I),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "username": re.compile(r"(?<![\w.])@[A-Za-z0-9_.-]{2,}\b"),
    "coordinates": re.compile(r"(?<![\w.])-?\d{1,3}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}(?![\w.])"),
    "phone": re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}(?!\w)"),
    "windows_path": re.compile(r"\b[A-Za-z]:[\\/][^\s\n\r\t]+"),
    "unix_path": re.compile(r"(?<!\w)/(?:Users|home|mnt|var|tmp|private|Volumes)/[^\s\n\r\t]+"),
    "token": re.compile(r"\b(?:token|api[_-]?key|secret|password|passwd|bearer)\s*[:=]\s*[^\s,;]{8,}", re.I),
}

REPLACEMENTS = {
    "url": "[REDACTED_URL]",
    "email": "[REDACTED_EMAIL]",
    "username": "[REDACTED_USERNAME]",
    "coordinates": "[REDACTED_COORDINATES]",
    "phone": "[REDACTED_PHONE]",
    "windows_path": "[REDACTED_PATH]",
    "unix_path": "[REDACTED_PATH]",
    "token": "[REDACTED_SECRET]",
}

STRICT_LEVELS = {"redacted_text", "courtroom_redacted"}


@dataclass(slots=True)
class RedactionHit:
    kind: str
    count: int
    replacement: str
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class RedactionResult:
    original_length: int
    redacted_text: str
    hits: list[RedactionHit] = field(default_factory=list)

    @property
    def total_hits(self) -> int:
        return sum(hit.count for hit in self.hits)

    def to_dict(self) -> dict:
        return {
            "original_length": self.original_length,
            "redacted_text": self.redacted_text,
            "total_hits": self.total_hits,
            "hits": [h.to_dict() for h in self.hits],
        }


def detect_sensitive_tokens(text: str) -> list[RedactionHit]:
    hits: list[RedactionHit] = []
    value = str(text or "")
    for kind, pattern in SENSITIVE_PATTERNS.items():
        matches = pattern.findall(value)
        if not matches:
            continue
        examples: list[str] = []
        for match in matches[:3]:
            clean = str(match)
            examples.append(clean[:64] + ("…" if len(clean) > 64 else ""))
        hits.append(RedactionHit(kind=kind, count=len(matches), replacement=REPLACEMENTS[kind], examples=examples))
    return hits


def redact_text(text: str, privacy_level: str = "redacted_text") -> str:
    value = str(text or "")
    if privacy_level not in STRICT_LEVELS or not value:
        return value
    redacted = value
    for kind in ("windows_path", "unix_path", "url", "email", "username", "coordinates", "phone", "token"):
        redacted = SENSITIVE_PATTERNS[kind].sub(REPLACEMENTS[kind], redacted)
    return redacted


def redact_with_audit(text: str, privacy_level: str = "redacted_text") -> RedactionResult:
    original = str(text or "")
    return RedactionResult(
        original_length=len(original),
        redacted_text=redact_text(original, privacy_level),
        hits=detect_sensitive_tokens(original) if privacy_level in STRICT_LEVELS else [],
    )


def build_redaction_preview(lines: Iterable[str], privacy_level: str = "redacted_text") -> dict:
    joined = "\n".join(str(line or "") for line in lines)
    result = redact_with_audit(joined, privacy_level)
    return {
        "privacy_level": privacy_level,
        "total_hits": result.total_hits,
        "redacted_text": result.redacted_text,
        "hits": [hit.to_dict() for hit in result.hits],
        "decision": "safe_to_share" if privacy_level in STRICT_LEVELS and result.total_hits == 0 else "redaction_applied" if privacy_level in STRICT_LEVELS else "internal_full_not_redacted",
    }
