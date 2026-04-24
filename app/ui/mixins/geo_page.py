from __future__ import annotations

from PyQt5.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget
import webbrowser

from ..widgets import AutoHeightNarrativeView


class GeoPageMixin:

    def _build_geo_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("PanelFrame")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 14, 14, 14)
        hero_layout.setSpacing(8)
        title = QLabel("Geo Review")
        title.setObjectName("SectionLabel")
        meta = QLabel("GPS, venue pivots, map logic, and screenshot-derived location context live here in one cleaner stage.")
        meta.setObjectName("SectionMetaLabel")
        meta.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(meta)
        layout.addWidget(hero)

        badge_frame = QFrame()
        badge_frame.setObjectName("CompactPanel")
        badge_layout = QGridLayout(badge_frame)
        badge_layout.setContentsMargins(10, 10, 10, 10)
        badge_layout.setHorizontalSpacing(10)
        badge_layout.setVerticalSpacing(10)

        self.geo_badge_status = self._micro_badge("Geo State: —")
        self.geo_badge_coords = self._micro_badge("Coordinates: —")
        self.geo_badge_altitude = self._micro_badge("Altitude: —")
        self.geo_badge_map = self._micro_badge("Map Package: —")
        self.geo_badge_detected_context = self._micro_badge("Detected Map Context: —")
        self.geo_badge_possible_place = self._micro_badge("Possible Place: —")
        self.geo_badge_map_confidence = self._micro_badge("Map Confidence: —")
        self.geo_badge_route = self._micro_badge("Route Overlay: —")

        top_badges = [self.geo_badge_status, self.geo_badge_coords, self.geo_badge_altitude, self.geo_badge_map]
        bottom_badges = [self.geo_badge_detected_context, self.geo_badge_possible_place, self.geo_badge_map_confidence, self.geo_badge_route]
        for idx, badge in enumerate(top_badges):
            badge_layout.addWidget(badge, 0, idx)
        for idx, badge in enumerate(bottom_badges):
            badge_layout.addWidget(badge, 1, idx)
        for col in range(4):
            badge_layout.setColumnStretch(col, 1)
        layout.addWidget(badge_frame)

        main_grid = QGridLayout()
        main_grid.setContentsMargins(0, 0, 0, 0)
        main_grid.setHorizontalSpacing(12)
        main_grid.setVerticalSpacing(12)

        self.geo_status_view = AutoHeightNarrativeView("Select evidence to load native-vs-derived geo interpretation.", max_auto_height=250)
        self.geo_reasoning_view = AutoHeightNarrativeView("Geo reasoning appears here after you select an evidence item.", max_auto_height=250)
        self.geo_map_context_view = AutoHeightNarrativeView("Map Intelligence, detected app, route overlay, city/area candidates, and landmark pivots will appear here.", max_auto_height=260)
        self.next_pivots_view = AutoHeightNarrativeView("Follow-up pivots will appear here.", max_auto_height=260)

        # Backward-compatible aliases used by the review-selection mixin.
        # Keeping these aliases avoids breaking existing UI code while the Geo page evolves.
        self.geo_text = self.geo_status_view
        self.geo_reasoning_text = self.geo_reasoning_view
        self.geo_leads_text = self.next_pivots_view

        main_grid.addWidget(self._shell("Geo Status", self.geo_status_view, "Native vs derived coordinates, altitude, and acquisition posture at a glance."), 0, 0)
        main_grid.addWidget(self._shell("Geo Reasoning", self.geo_reasoning_view, "Explain whether missing GPS is normal, weak, or suspicious for this workflow."), 0, 1)
        main_grid.addWidget(self._shell("Map Intelligence", self.geo_map_context_view, "App, map type, route overlay, candidate city/place, and OCR language guidance."), 1, 0, 1, 2)
        main_grid.addWidget(self._shell("Next Pivots", self.next_pivots_view, "Timestamp, source workflow, upload context, and venue reasoning when native GPS is missing."), 2, 0, 1, 2)
        main_grid.setColumnStretch(0, 1)
        main_grid.setColumnStretch(1, 1)
        layout.addLayout(main_grid)
        layout.addStretch(1)
        return widget


    def open_map(self) -> None:
        if self.current_map_path is None:
            self.current_map_path = self.map_service.create_map(self.case_manager.records)
        if self.current_map_path is None:
            self.show_info(
                "No GPS Data",
                "No GPS-enabled images are available to plot. Use Geo Review, OSINT AI map context, timeline, source profile, and custody notes instead.",
            )
            return
        webbrowser.open(self.current_map_path.as_uri())
