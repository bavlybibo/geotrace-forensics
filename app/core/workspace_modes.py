from __future__ import annotations

"""Data-driven workspace profiles for a cleaner UI.

Executive mode is for short demos and non-technical review. Analyst mode is the
day-to-day workflow. Technical mode exposes every parser/OCR/report page.
"""

from dataclasses import asdict, dataclass, field

@dataclass(frozen=True, slots=True)
class WorkspaceModeProfile:
    name: str
    allowed_pages: tuple[str, ...]
    headline: str
    intent: str
    density: str
    default_export_privacy: str
    review_focus: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

ALL_PAGES: tuple[str, ...] = (
    'Dashboard', 'Review', 'Geo', 'Map Workspace', 'Timeline', 'Custody',
    'Reports', 'Cases', 'AI Guardian', 'System Health', 'OSINT Workbench'
)

_MODE_PROFILES: dict[str, WorkspaceModeProfile] = {
    'Executive': WorkspaceModeProfile(
        name='Executive',
        allowed_pages=('Dashboard', 'Reports', 'Cases', 'System Health'),
        headline='Executive cockpit',
        intent='Risk, readiness, inventory, and export decisions without technical noise.',
        density='compact',
        default_export_privacy='redacted_text',
        review_focus=('case summary', 'risk mix', 'readiness blockers', 'report preview'),
    ),
    'Analyst': WorkspaceModeProfile(
        name='Analyst',
        allowed_pages=('Dashboard', 'Review', 'Geo', 'Map Workspace', 'Timeline', 'Custody', 'Reports', 'Cases', 'AI Guardian', 'System Health'),
        headline='Analyst workflow',
        intent='Balanced evidence review, map/OCR leads, custody, and next actions.',
        density='balanced',
        default_export_privacy='redacted_text',
        review_focus=('selected evidence', 'claim links', 'map/OCR corroboration', 'custody timeline'),
    ),
    'Technical': WorkspaceModeProfile(
        name='Technical',
        allowed_pages=ALL_PAGES,
        headline='Deep technical workspace',
        intent='Full parser, OCR, hidden-content, OSINT, validation, and audit workspace.',
        density='full',
        default_export_privacy='full',
        review_focus=('metadata dumps', 'hidden/code scan', 'structured logs', 'validation dataset', 'package verifier'),
    ),
}

def list_mode_names() -> list[str]:
    return list(_MODE_PROFILES)

def normalize_mode(mode: str | None) -> str:
    raw = (mode or 'Analyst').strip().lower()
    for name in _MODE_PROFILES:
        if raw == name.lower():
            return name
    return 'Analyst'

def get_workspace_mode_profile(mode: str | None) -> WorkspaceModeProfile:
    return _MODE_PROFILES[normalize_mode(mode)]

def allowed_pages_for_mode(mode: str | None) -> set[str]:
    return set(get_workspace_mode_profile(mode).allowed_pages)

def mode_tooltip(mode: str | None) -> str:
    profile = get_workspace_mode_profile(mode)
    return f"{profile.headline} — {profile.intent} Focus: {', '.join(profile.review_focus)}."

def list_mode_profiles() -> list[dict[str, object]]:
    return [profile.to_dict() for profile in _MODE_PROFILES.values()]
