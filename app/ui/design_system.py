from __future__ import annotations

"""Shared UI design tokens for GeoTrace Forensics X.

The app is still PyQt/QSS based, so this module documents the reusable
presentation language in code instead of scattering colors and intent across
pages. QSS selectors in styles.py consume the same naming vocabulary:
HeroPanel, MetricPill, CompactPanel, ReportArtifactCard, and GeoSignalRail.
"""

DESIGN_TOKENS = {
    "surface": "#07131d",
    "surface_alt": "#091827",
    "surface_deep": "#040b13",
    "border": "#16334a",
    "border_active": "#53d6ff",
    "text": "#eaf4fb",
    "muted": "#9ebed7",
    "accent": "#53d6ff",
    "success": "#61e3a8",
    "warning": "#ffd166",
    "danger": "#ff7f95",
}

PAGE_INTENT = {
    "Dashboard": "mission-control",
    "Review": "evidence-deep-dive",
    "Geo": "location-intelligence",
    "Timeline": "chronology",
    "Custody": "audit-integrity",
    "Reports": "export-command-center",
    "AI Guardian": "case-intelligence",
    "OSINT Workbench": "researcher-lab",
}
