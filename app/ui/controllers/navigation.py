from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt5.QtWidgets import QWidget


@dataclass(frozen=True)
class WorkspacePageSpec:
    key: str
    builder_name: str
    scrollable: bool = True
    attr_name: str = ""

    @property
    def attribute(self) -> str:
        return self.attr_name or f"{self.key.lower().replace(' ', '_')}_page"


WORKSPACE_PAGES: tuple[WorkspacePageSpec, ...] = (
    WorkspacePageSpec("Dashboard", "_build_dashboard_page", True, "dashboard_page"),
    WorkspacePageSpec("Review", "_build_review_page", True, "review_page"),
    WorkspacePageSpec("Geo", "_build_geo_page", True, "geo_page"),
    WorkspacePageSpec("Timeline", "_build_timeline_page", True, "timeline_page"),
    WorkspacePageSpec("Custody", "_build_custody_page", True, "custody_page"),
    WorkspacePageSpec("Reports", "_build_reports_page", True, "reports_page"),
    WorkspacePageSpec("Cases", "_build_cases_page", True, "cases_page"),
    WorkspacePageSpec("AI Guardian", "_build_ai_guardian_page", True, "ai_guardian_page"),
)


PAGE_KEYS = tuple(spec.key for spec in WORKSPACE_PAGES)


def build_workspace_pages(window) -> dict[str, QWidget]:
    """Build workspace pages from declarative specs so MainWindow remains navigation-focused."""
    pages: dict[str, QWidget] = {}
    for spec in WORKSPACE_PAGES:
        builder: Callable[[], QWidget] = getattr(window, spec.builder_name)
        page = window._wrap_page(builder(), scrollable=spec.scrollable)
        setattr(window, spec.attribute, page)
        pages[spec.key] = page
    return pages
