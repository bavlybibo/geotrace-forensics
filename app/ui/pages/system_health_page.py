from __future__ import annotations

from html import escape

from PyQt5.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

try:
    from ...core.system_health import build_system_health_report
    from ...core.dependency_check import ensure_runtime_folders, run_dependency_check
except ImportError:  # pragma: no cover
    from app.core.system_health import build_system_health_report
    from app.core.dependency_check import ensure_runtime_folders, run_dependency_check


def _pill(label: str, value: str, note: str = "") -> str:
    return (
        "<div style='border:1px solid #214761;border-radius:14px;padding:12px;margin:0 8px 10px 0;background:#081824;'>"
        f"<div style='color:#89dcff;font-weight:900;font-size:13px;'>{escape(label)}</div>"
        f"<div style='color:#f4fbff;font-weight:900;font-size:20px;margin-top:4px;'>{escape(value)}</div>"
        f"<div style='color:#9fb8c9;margin-top:6px;'>{escape(note)}</div>"
        "</div>"
    )


def _render_overview(report) -> str:
    p2 = report.p2_readiness
    dep = report.dependency_report
    return "".join([
        _pill("Overall", report.overall_status, f"Health score {report.score}/100"),
        _pill("Dependencies", f"{dep.required_ok}/{dep.required_total}", f"Optional {dep.optional_ok}/{dep.optional_total}"),
        _pill("Landmarks", str(p2.get("landmark_index_rows", 0)), "Offline alias/visual seed rows"),
        _pill("Geocoder", str(p2.get("offline_geocoder_rows", 0)), "Offline place rows"),
        _pill("Validation", str(p2.get("validation_dataset_template", "missing")), "Template only; replace with real labels"),
        _pill("Similarity", str(p2.get("visual_similarity_search", "missing")), "Local visual fingerprint search"),
    ])


def _render_sections(report) -> str:
    colors = {"PASS": "#72e6a5", "WARN": "#ffd166", "FAIL": "#ff7c93"}
    cards: list[str] = []
    for section in report.sections:
        color = colors.get(section.status, "#91dfff")
        details = "".join(f"<li>{escape(str(item))}</li>" for item in section.details[:8]) or "<li>No extra notes.</li>"
        cards.append(
            f"<div style='border:1px solid {color};border-radius:16px;padding:13px;margin:0 0 10px 0;background:#081723;'>"
            f"<div style='color:{color};font-weight:950;'>{escape(section.status)} • {escape(section.title)}</div>"
            f"<div style='color:#eef8ff;margin-top:7px;'>{escape(section.summary)}</div>"
            f"<ul style='color:#a9c3d6;margin-top:8px;'>{details}</ul>"
            "</div>"
        )
    return "".join(cards)


def build_system_health_page(window) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    hero = window._shell(
        "System Health & Dependency Center",
        QLabel("Runtime readiness, dependency checks, first-run setup, security hygiene, and P2 AI/vision readiness in one local page."),
        "No network calls. No evidence upload. This page validates local setup before demo, build, or delivery.",
    )
    layout.addWidget(hero)

    action_row = QHBoxLayout()
    window.btn_refresh_system_health = QPushButton("Refresh Health")
    window.btn_refresh_system_health.clicked.connect(window.refresh_system_health)
    window.btn_dependency_check = QPushButton("Dependency Check")
    window.btn_dependency_check.clicked.connect(window.run_dependency_check_ui)
    window.btn_first_run_setup = QPushButton("First Run Setup Wizard")
    window.btn_first_run_setup.clicked.connect(window.open_first_run_setup_wizard)
    action_row.addWidget(window.btn_refresh_system_health)
    action_row.addWidget(window.btn_dependency_check)
    action_row.addWidget(window.btn_first_run_setup)
    action_row.addStretch(1)
    layout.addLayout(action_row)

    grid = QGridLayout()
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(12)
    window.system_health_overview_view = window._make_guardian_view("System health overview appears here.", 230)
    window.system_health_sections_view = window._make_guardian_view("Detailed readiness sections appear here.", 360)
    window.dependency_check_view = window._make_guardian_view("Dependency checker output appears here.", 360)
    window.p2_readiness_view = window._make_guardian_view("P2 readiness guidance appears here.", 260)
    grid.addWidget(window._shell("Overview", window.system_health_overview_view, "Score, dependency, landmark, validation, and similarity readiness."), 0, 0)
    grid.addWidget(window._shell("Readiness Sections", window.system_health_sections_view, "Build hygiene, AI/vision, security, validation, and release checks."), 0, 1)
    grid.addWidget(window._shell("Dependency Check", window.dependency_check_view, "Python packages and external tools without importing heavy modules."), 1, 0)
    grid.addWidget(window._shell("P2 Upgrade Guidance", window.p2_readiness_view, "What is real now, what needs data/model setup, and what not to overclaim."), 1, 1)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    layout.addLayout(grid)
    layout.addStretch(1)
    return widget


def refresh_system_health_page(window) -> None:
    report = build_system_health_report(getattr(window, "project_root"))
    if hasattr(window, "system_health_overview_view"):
        window.system_health_overview_view.setHtml(_render_overview(report))
    if hasattr(window, "system_health_sections_view"):
        window.system_health_sections_view.setHtml(_render_sections(report))
    if hasattr(window, "dependency_check_view"):
        window.dependency_check_view.setPlainText(report.dependency_report.to_text())
    if hasattr(window, "p2_readiness_view"):
        p2 = report.p2_readiness
        lines = [
            "P2 READINESS — TRUTHFUL STATUS",
            "=" * 72,
            f"Local vision model: {p2.get('local_vision_model')}",
            f"Landmark index rows: {p2.get('landmark_index_rows')}",
            f"Offline geocoder rows: {p2.get('offline_geocoder_rows')}",
            f"Visual similarity search: {p2.get('visual_similarity_search')}",
            f"Validation dataset template: {p2.get('validation_dataset_template')}",
            f"Benchmark tool: {p2.get('benchmark_accuracy_tool')}",
            f"ExifTool bridge: {p2.get('exiftool_bridge')}",
            f"QR/barcode detector: {p2.get('qr_barcode_detector')}",
            f"YOLO bridge: {p2.get('yolo_bridge')}",
            "",
            "Do not claim global AI accuracy until you run a real labelled validation dataset.",
            "Recommended commands:",
            r"setup_forensics_stack_windows.bat",
            r"python tools\visual_similarity_search.py query.jpg evidence_folder --threshold 82",
            r"python tools\benchmark_accuracy.py records.json data\validation_ground_truth.real_template.json",
            "",
            "Optional heavy AI:",
            r"pip install -r requirements-ai-heavy.txt",
            r"set GEOTRACE_YOLO_ENABLED=1",
            r"set GEOTRACE_YOLO_MODEL=C:\path\to\yolov8n.pt",
        ]
        window.p2_readiness_view.setPlainText("\n".join(lines))


def run_dependency_check_ui(window) -> str:
    created = ensure_runtime_folders(getattr(window, "project_root"))
    report = run_dependency_check(getattr(window, "project_root"))
    text = report.to_text()
    if created:
        text += "\n\nCreated runtime folders: " + ", ".join(created)
    if hasattr(window, "dependency_check_view"):
        window.dependency_check_view.setPlainText(text)
    return text
