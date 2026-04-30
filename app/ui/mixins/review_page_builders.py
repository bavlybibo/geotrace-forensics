from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..widgets import AutoHeightNarrativeView, ResizableImageLabel, ScoreRing, TerminalView


class ReviewPageBuilderMixin:

    def _build_review_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setOpaqueResize(False)
        splitter.addWidget(self._build_inventory_panel())
        splitter.addWidget(self._build_review_center())
        splitter.addWidget(self._build_review_sidebar())
        splitter.setSizes([350, 1240, 430])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        layout.addWidget(splitter)
        return container

    def _build_inventory_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("PanelFrame")
        frame.setMinimumWidth(320)
        frame.setMaximumWidth(410)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Evidence Inbox")
        title.setObjectName("SectionLabel")
        meta = QLabel("Search, filter, and select evidence without crowding the review stage.")
        meta.setObjectName("SectionMetaLabel")

        self.inventory_meta = QLabel("No evidence loaded in the current case.")
        self.inventory_meta.setObjectName("MutedLabel")

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search evidence • gps:yes • geo:yes • risk:high")
        self.search_box.textChanged.connect(self.apply_filters)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All Evidence",
            "Has GPS",
            "Has Geo Anchor",
            "High Risk",
            "Medium Risk",
            "Low Risk",
            "Screenshots / Exports",
            "Camera Photos",
            "Edited / Exported",
            "Duplicate Cluster",
            "Parser Issues",
            "Bookmarked",
        ])
        self.filter_combo.currentTextChanged.connect(self.apply_filters)
        filter_row.addWidget(self.filter_combo)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Score ↓", "Time ↑", "Time ↓", "Filename A→Z", "Filename Z→A", "Confidence ↓", "Bookmarked First"])
        self.sort_combo.currentTextChanged.connect(self.apply_filters)
        filter_row.addWidget(self.sort_combo)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        self.progress_bar.setMinimumHeight(26)

        self.inventory_list = QListWidget()
        self.inventory_list.setObjectName("EvidenceList")
        self.inventory_list.setSpacing(8)
        self.inventory_list.setSelectionMode(QListWidget.SingleSelection)
        self.inventory_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.inventory_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inventory_list.currentItemChanged.connect(self.populate_details)

        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addWidget(self.inventory_meta)
        layout.addWidget(self.search_box)
        layout.addLayout(filter_row)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.inventory_list, 1)
        return frame

    def _build_review_center(self) -> QWidget:
        self.review_tabs = QTabWidget()
        self.review_tabs.setObjectName("ReviewTabs")
        self.review_tabs.setUsesScrollButtons(True)
        self.review_tabs.setDocumentMode(True)
        tab_bar = self.review_tabs.tabBar()
        tab_bar.setElideMode(Qt.ElideRight)
        tab_bar.setExpanding(False)
        tab_bar.setMinimumHeight(38)

        self.review_tab_preview = self._build_preview_shell()
        self.review_tab_overview = self._build_overview_tab()
        self.review_tab_metadata = self._build_metadata_panel()
        self.review_tab_hidden = self._build_hidden_content_tab()
        self.review_tab_notes = self._build_notes_tab()
        self.review_tab_audit = self._build_review_audit_tab()

        self.review_tabs.addTab(self.review_tab_preview, "Preview")
        self.review_tabs.addTab(self.review_tab_overview, "Overview")
        self.review_tabs.addTab(self.review_tab_metadata, "Metadata")
        self.review_tabs.addTab(self.review_tab_hidden, "Hidden / Code")
        self.review_tabs.addTab(self.review_tab_notes, "Notes")
        self.review_tabs.addTab(self.review_tab_audit, "Audit")
        return self.review_tabs

    def _build_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.review_time_shell = self._preview_meta_block("Recovered Time", "—")
        self.review_file_shell = self._preview_meta_block("Evidence", "—")
        self.review_profile_shell = self._preview_meta_block("Source Profile", "—")
        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(10)
        top_grid.setVerticalSpacing(10)
        top_grid.addWidget(self.review_time_shell, 0, 0, 1, 2)
        top_grid.addWidget(self.review_file_shell, 1, 0)
        top_grid.addWidget(self.review_profile_shell, 1, 1)
        layout.addLayout(top_grid)

        self.metadata_overview = AutoHeightNarrativeView("Metadata overview will appear here.", max_auto_height=300)
        self.confidence_tree_view = AutoHeightNarrativeView("Select one evidence item to explain what raised or lowered confidence.", max_auto_height=300)
        layout.addWidget(self._shell("Metadata Overview", self.metadata_overview, "Readable summary first. Technical dumps stay hidden until requested."))
        self.acquisition_view = AutoHeightNarrativeView("Acquisition and custody posture will appear here.", max_auto_height=260)
        layout.addWidget(self._shell("Acquisition & Custody", self.acquisition_view, "Original path, import posture, hashes, and courtroom-strength posture for the selected item."))
        layout.addWidget(self._shell("Confidence / Value / Courtroom Tree", self.confidence_tree_view, "Shows why analytic confidence, evidentiary value, and courtroom strength are not the same metric."))

        quick = QHBoxLayout()
        quick.setSpacing(8)
        self.btn_review_export = QPushButton("Export This Case")
        self.btn_review_export.setObjectName("SmallGhostButton")
        self.btn_review_export.clicked.connect(self.generate_reports)
        self.btn_review_compare = QPushButton("Compare With…")
        self.btn_review_compare.setObjectName("SmallGhostButton")
        self.btn_review_compare.clicked.connect(self.open_compare_mode)
        quick.addWidget(self.btn_review_export)
        quick.addWidget(self.btn_review_compare)
        quick.addStretch(1)
        self.review_hint_label = QLabel("Quick actions: F fullscreen • +/- zoom")
        self.review_hint_label.setObjectName("MutedLabel")
        quick.addWidget(self.review_hint_label)
        layout.addLayout(quick)
        layout.addStretch(1)
        return widget

    def _build_notes_tab(self) -> QWidget:
        notes_shell = QFrame()
        notes_shell.setObjectName("CompactPanel")
        notes_layout = QVBoxLayout(notes_shell)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.setSpacing(8)
        notes_label = QLabel("Case Notes, Tags & Bookmarks")
        notes_label.setObjectName("SectionLabel")
        notes_meta = QLabel("Keep analyst notes on their own tab so the preview stage stays clean and readable.")
        notes_meta.setObjectName("SectionMetaLabel")
        template_row = QHBoxLayout()
        template_row.setSpacing(8)
        self.note_template_combo = QComboBox()
        self.note_template_combo.addItems(["Choose template…", *self.note_templates.keys()])
        apply_template_button = QPushButton("Insert Template")
        apply_template_button.clicked.connect(self.insert_note_template)
        template_row.addWidget(self.note_template_combo)
        template_row.addWidget(apply_template_button)
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText("Add analyst observations, correlation ideas, or courtroom caveats for the selected evidence item…")
        self.note_editor.setMinimumHeight(180)
        self.tags_editor = QLineEdit()
        self.tags_editor.setPlaceholderText("Tags (comma-separated), e.g. malformed, timeline-anchor, priority-review")
        self.bookmark_checkbox = QCheckBox("Pin / bookmark selected evidence")
        save_button = QPushButton("Save Notes & Tags")
        save_button.clicked.connect(self.save_note_and_tags)
        notes_layout.addWidget(notes_label)
        notes_layout.addWidget(notes_meta)
        notes_layout.addLayout(template_row)
        notes_layout.addWidget(self.note_editor)
        notes_layout.addWidget(self.tags_editor)
        notes_layout.addWidget(self.bookmark_checkbox)
        notes_layout.addWidget(save_button, alignment=Qt.AlignLeft)
        return notes_shell

    def _build_hidden_content_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.hidden_overview_view = AutoHeightNarrativeView("Hidden-content scan results will appear here.", max_auto_height=220)
        self.hidden_code_view = TerminalView("Code-like markers, URLs, and context strings will appear here when detected.")
        layout.addWidget(self._shell("Embedded Text & Code Scan", self.hidden_overview_view, "Byte-level heuristics look for readable strings, URLs, and obvious script or credential markers hidden inside the container. Readable strings without code markers stay contextual only."))
        layout.addWidget(self._shell("Recovered Markers", self.hidden_code_view, "Heuristic view only: code-like markers are higher priority than plain readable strings."), 1)
        return widget

    def _build_review_audit_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.review_audit_view = TerminalView("Select an evidence item to load its case-scoped audit activity.")
        layout.addWidget(self._shell("Evidence Audit Trail", self.review_audit_view, "Case-scoped events filtered to the selected evidence item so note, import, and analysis activity stay visible during review."), 1)
        return widget

    def _build_review_sidebar(self) -> QWidget:
        widget = QWidget()
        widget.setMinimumWidth(360)
        widget.setMaximumWidth(430)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        verdict = QFrame()
        verdict.setObjectName("VerdictPanel")
        verdict.setMinimumWidth(360)
        verdict_layout = QVBoxLayout(verdict)
        verdict_layout.setContentsMargins(16, 16, 16, 16)
        verdict_layout.setSpacing(12)
        top_title = QLabel("Decision Rail")
        top_title.setObjectName("SectionLabel")
        top_meta = QLabel("Score, value, and next move for the selected item.")
        top_meta.setObjectName("SectionMetaLabel")

        self.decision_empty_hint = QLabel("Choose one item to load score, value, integrity, and next actions.")
        self.decision_empty_hint.setObjectName("MutedLabel")
        self.decision_empty_hint.setWordWrap(True)

        self.score_ring = ScoreRing(154)
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setObjectName("ConfidenceBar")
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar_label = QLabel("Analytic confidence appears after selection")
        self.confidence_bar_label.setObjectName("MutedLabel")
        self.evidence_value_label = QLabel("Evidentiary value appears after selection")
        self.evidence_value_label.setObjectName("MutedLabel")
        self.courtroom_strength_label = QLabel("Courtroom strength appears after selection")
        self.courtroom_strength_label.setObjectName("MutedLabel")

        self.decision_score_shell = QWidget()
        decision_score_layout = QVBoxLayout(self.decision_score_shell)
        decision_score_layout.setContentsMargins(0, 0, 0, 0)
        decision_score_layout.setSpacing(10)
        decision_score_layout.addWidget(self.score_ring, alignment=Qt.AlignHCenter)
        ring_gap = QLabel("")
        ring_gap.setFixedHeight(4)
        decision_score_layout.addWidget(ring_gap)
        decision_score_layout.addWidget(self.confidence_bar)
        decision_score_layout.addWidget(self.confidence_bar_label)
        decision_score_layout.addWidget(self.evidence_value_label)
        decision_score_layout.addWidget(self.courtroom_strength_label)

        self.decision_facts_shell = QWidget()
        facts = QGridLayout(self.decision_facts_shell)
        facts.setContentsMargins(0, 0, 0, 0)
        facts.setHorizontalSpacing(8)
        facts.setVerticalSpacing(8)
        self.badge_parser = self._micro_badge("Parser / Trust", semantic="parser")
        self.badge_time = self._micro_badge("Time Anchor", semantic="time")
        self.badge_source = self._micro_badge("Source Profile", semantic="source")
        self.badge_gps = self._micro_badge("GPS", semantic="gps")
        for idx, badge in enumerate([self.badge_parser, self.badge_time, self.badge_source, self.badge_gps]):
            facts.addWidget(badge, idx // 2, idx % 2)

        self.badge_signature = self._micro_badge("Signature")
        self.badge_trust = self._micro_badge("Trust")
        self.badge_risk = self._risk_badge("Risk", "Low")
        self.badge_format = self._micro_badge("Format")

        self.decision_breakdown_shell = QWidget()
        scores_row = QHBoxLayout(self.decision_breakdown_shell)
        scores_row.setContentsMargins(0, 0, 0, 0)
        scores_row.setSpacing(8)
        self.score_auth_badge = QLabel("Authenticity")
        self.score_auth_badge.setObjectName("ScoreBreakdownBadge")
        self.score_auth_badge.setProperty("role", "auth")
        self.score_meta_badge = QLabel("Metadata")
        self.score_meta_badge.setObjectName("ScoreBreakdownBadge")
        self.score_meta_badge.setProperty("role", "meta")
        self.score_tech_badge = QLabel("Technical")
        self.score_tech_badge.setObjectName("ScoreBreakdownBadge")
        self.score_tech_badge.setProperty("role", "tech")
        scores_row.addWidget(self.score_auth_badge)
        scores_row.addWidget(self.score_meta_badge)
        scores_row.addWidget(self.score_tech_badge)

        self.selection_verdict_view = AutoHeightNarrativeView("Select an item to load a focused verdict summary.", max_auto_height=260)
        self.agent_insight_view = AutoHeightNarrativeView("AI review is ready. Select evidence to see local risk context.", max_auto_height=210)
        self.review_pivots_text = AutoHeightNarrativeView("Select evidence to load next-step pivots.", max_auto_height=230)
        verdict_layout.addWidget(top_title)
        verdict_layout.addWidget(top_meta)
        verdict_layout.addWidget(self.decision_empty_hint)
        verdict_layout.addWidget(self.decision_score_shell)
        verdict_layout.addWidget(self.decision_facts_shell)
        verdict_layout.addWidget(self.decision_breakdown_shell)
        verdict_layout.addWidget(self._shell("Analyst Verdict", self.selection_verdict_view, "Observed posture first, then what still needs confirmation."))
        verdict_layout.addWidget(self._shell("AI Risk Assistant", self.agent_insight_view, "Local agent output plus batch-level GeoTrace AI Risk Engine findings."))
        verdict_layout.addWidget(self._shell("Next Steps", self.review_pivots_text, "Concise pivots only — no repeated narrative blocks."))

        layout.addWidget(verdict)
        layout.addStretch(1)
        return widget

    def _build_preview_shell(self) -> QWidget:
        preview_shell = QFrame()
        preview_shell.setObjectName("HeroPreviewPanel")
        layout = QVBoxLayout(preview_shell)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hero_row = QHBoxLayout()
        hero_row.setSpacing(8)
        title = QLabel("Evidence Stage")
        title.setObjectName("SectionLabel")
        subtitle = QLabel("Preview first. Deeper detail stays in secondary tabs.")
        subtitle.setObjectName("SectionMetaLabel")
        subtitle.setWordWrap(True)
        hero_row.addWidget(title)
        hero_row.addStretch(1)
        hero_row.addWidget(subtitle, 0, Qt.AlignRight)
        layout.addLayout(hero_row)

        control_row_top = QHBoxLayout()
        control_row_top.setSpacing(8)
        self.preview_zoom_pill = QLabel("Zoom 100%")
        self.preview_zoom_pill.setObjectName("PreviewZoomPill")
        control_row_top.addWidget(self.preview_zoom_pill)
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setObjectName("SmallGhostButton")
        self.btn_zoom_out.setToolTip("Zoom out")
        self.btn_zoom_out.clicked.connect(self._zoom_preview_out)
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setObjectName("SmallGhostButton")
        self.btn_zoom_in.setToolTip("Zoom in")
        self.btn_zoom_in.clicked.connect(self._zoom_preview_in)
        self.btn_zoom_fit = QPushButton("Fit")
        self.btn_zoom_fit.setObjectName("SmallGhostButton")
        self.btn_zoom_fit.clicked.connect(self._zoom_preview_fit)
        self.btn_zoom_reset = QPushButton("100%")
        self.btn_zoom_reset.setObjectName("SmallGhostButton")
        self.btn_zoom_reset.clicked.connect(self._zoom_preview_reset)
        for btn in [self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit, self.btn_zoom_reset]:
            control_row_top.addWidget(btn)
        control_row_top.addStretch(1)

        control_row_bottom = QHBoxLayout()
        control_row_bottom.setSpacing(8)
        self.btn_prev_frame = QPushButton("Prev")
        self.btn_prev_frame.setObjectName("SmallGhostButton")
        self.btn_prev_frame.clicked.connect(self._show_previous_frame)
        self.btn_next_frame = QPushButton("Next")
        self.btn_next_frame.setObjectName("SmallGhostButton")
        self.btn_next_frame.clicked.connect(self._show_next_frame)
        self.frame_index_badge = QLabel("Frame 0/0")
        self.frame_index_badge.setObjectName("PreviewZoomPill")
        self.btn_fullscreen_preview = QPushButton("Full")
        self.btn_fullscreen_preview.setObjectName("SmallGhostButton")
        self.btn_fullscreen_preview.clicked.connect(self._open_preview_fullscreen)
        self.btn_open_external = QPushButton("Original")
        self.btn_open_external.setObjectName("SmallGhostButton")
        self.btn_open_external.clicked.connect(self.open_selected_file)
        self.btn_export_from_review = QPushButton("Export")
        self.btn_export_from_review.setObjectName("SmallGhostButton")
        self.btn_export_from_review.clicked.connect(self.generate_reports)
        for btn in [self.btn_prev_frame, self.btn_next_frame]:
            control_row_bottom.addWidget(btn)
        control_row_bottom.addWidget(self.frame_index_badge)
        control_row_bottom.addStretch(1)
        for btn in [self.btn_fullscreen_preview, self.btn_open_external, self.btn_export_from_review]:
            control_row_bottom.addWidget(btn)

        state_row = QGridLayout()
        state_row.setHorizontalSpacing(8)
        state_row.setVerticalSpacing(8)
        self.preview_state_badge = QLabel("Preview State: Awaiting selection")
        self.preview_state_badge.setObjectName("PreviewStateBadge")
        self.preview_parser_badge = QLabel("Parser: Awaiting selection")
        self.preview_parser_badge.setObjectName("PreviewStateBadge")
        self.preview_signature_badge = QLabel("Signature: Awaiting selection")
        self.preview_signature_badge.setObjectName("PreviewStateBadge")
        self.preview_trust_badge = QLabel("Trust: Awaiting selection")
        self.preview_trust_badge.setObjectName("PreviewStateBadge")
        for idx, badge in enumerate([self.preview_parser_badge, self.preview_signature_badge, self.preview_trust_badge]):
            state_row.addWidget(badge, 0, idx)

        hint = QLabel("F fullscreen • +/- zoom")
        hint.setObjectName("MutedLabel")

        preview_frame = QFrame()
        preview_frame.setObjectName("PreviewCanvasFrame")
        preview_frame_layout = QVBoxLayout(preview_frame)
        preview_frame_layout.setContentsMargins(6, 6, 6, 6)
        self.image_preview = ResizableImageLabel("Choose one evidence item. Deep details live in tabs, not on the image stage.", min_height=560)
        self.image_preview.setMinimumHeight(560)
        preview_frame_layout.addWidget(self.image_preview, 1)

        meta_grid = QGridLayout()
        meta_grid.setHorizontalSpacing(10)
        meta_grid.setVerticalSpacing(10)
        self.preview_file_meta = self._preview_meta_block("Evidence", "—")
        self.preview_source_meta = self._preview_meta_block("Source Profile", "—")
        self.preview_time_meta = self._preview_meta_block("Recovered Time", "—")
        self.preview_geo_meta = self._preview_meta_block("GPS / Geo", "—")
        self.preview_hash_meta = self._preview_meta_block("SHA-256", "—")
        self.preview_hash_aux_meta = self._preview_meta_block("MD5 / pHash", "—")
        self.preview_hash_meta.hide()
        self.preview_hash_aux_meta.hide()
        meta_grid.addWidget(self.preview_file_meta, 0, 0, 1, 2)
        meta_grid.addWidget(self.preview_source_meta, 1, 0)
        meta_grid.addWidget(self.preview_time_meta, 1, 1)
        meta_grid.addWidget(self.preview_geo_meta, 2, 0, 1, 2)

        layout.addLayout(control_row_top)
        layout.addLayout(control_row_bottom)
        layout.addLayout(state_row)
        layout.addWidget(preview_frame, 1)
        layout.addLayout(meta_grid)
        return preview_shell

    def _preview_meta_block(self, title: str, value: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("SecondaryPanel")
        block = QVBoxLayout(frame)
        block.setContentsMargins(12, 10, 12, 10)
        block.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("PreviewMetaTitle")
        value_label = QLabel(value)
        value_label.setObjectName("PreviewMetaValue")
        value_label.setWordWrap(True)
        block.addWidget(title_label)
        block.addWidget(value_label)
        frame.value_label = value_label  # type: ignore[attr-defined]
        return frame
