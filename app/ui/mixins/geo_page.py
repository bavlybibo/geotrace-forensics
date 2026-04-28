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
        hero.setObjectName("HeroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(10)
        title = QLabel("Geo Intelligence Review")
        title.setObjectName("SectionLabel")
        meta = QLabel(
            "Native GPS, screenshot-derived map context, route overlays, OCR labels, venue pivots, and next-step reasoning "
            "are grouped here so location evidence reads like an analyst board, not a raw metadata dump."
        )
        meta.setObjectName("SectionMetaLabel")
        meta.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(meta)
        metric_row = QGridLayout()
        metric_row.setHorizontalSpacing(10)
        metric_row.setVerticalSpacing(10)
        metric_row.addWidget(self._build_metric_pill("Native GPS", "Awaiting", "Select evidence to inspect EXIF coordinates.", value_attr="geo_metric_native_value", note_attr="geo_metric_native_note"), 0, 0)
        metric_row.addWidget(self._build_metric_pill("Derived Context", "Awaiting", "Map screenshots and OCR labels appear here.", value_attr="geo_metric_context_value", note_attr="geo_metric_context_note"), 0, 1)
        metric_row.addWidget(self._build_metric_pill("Candidate Place", "—", "No place candidate selected yet.", value_attr="geo_metric_place_value", note_attr="geo_metric_place_note"), 0, 2)
        metric_row.addWidget(self._build_metric_pill("Route Signal", "—", "Route overlays and navigation context.", value_attr="geo_metric_route_value", note_attr="geo_metric_route_note"), 0, 3)
        for col in range(4):
            metric_row.setColumnStretch(col, 1)
        hero_layout.addLayout(metric_row)
        layout.addWidget(hero)

        badge_frame = QFrame()
        badge_frame.setObjectName("GeoSignalRail")
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

        self.geo_status_view = AutoHeightNarrativeView("Select evidence to load native-vs-derived geo interpretation.", max_auto_height=210)
        self.geo_reasoning_view = AutoHeightNarrativeView("Geo reasoning appears here after you select an evidence item.", max_auto_height=210)
        self.geo_map_context_view = AutoHeightNarrativeView("Map Intelligence, detected app, route overlay, city/area candidates, and landmark pivots will appear here.", max_auto_height=220)
        self.next_pivots_view = AutoHeightNarrativeView("Follow-up pivots will appear here.", max_auto_height=210)

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
                "No Map Anchor Yet",
                "No native GPS, visible coordinates, known place coordinate, or map-context board is available yet. Run map_deep OCR/manual crop OCR or import evidence with coordinates/map URL/place labels.",
            )
            return
        webbrowser.open(self.current_map_path.as_uri())
