from __future__ import annotations

import pytest

pytest.importorskip("PyQt5.QtWidgets")

from app.ui.main_window import GeoTraceMainWindow
from app.ui.mixins.analysis_actions import AnalysisActionsMixin
from app.ui.mixins.case_actions import CaseActionsMixin
from app.ui.mixins.filtering import FilteringMixin
from app.ui.mixins.timeline_page import TimelinePageMixin
from app.ui.mixins.geo_page import GeoPageMixin
from app.ui.mixins.report_actions import ReportActionsMixin
from app.ui.mixins.review_page_builders import ReviewPageBuilderMixin
from app.ui.mixins.review_selection import ReviewSelectionMixin


def test_main_window_imports_all_refactored_mixins() -> None:
    expected_mixins = (
        AnalysisActionsMixin,
        CaseActionsMixin,
        FilteringMixin,
        TimelinePageMixin,
        GeoPageMixin,
        ReportActionsMixin,
        ReviewPageBuilderMixin,
        ReviewSelectionMixin,
    )
    for mixin in expected_mixins:
        assert issubclass(GeoTraceMainWindow, mixin)
