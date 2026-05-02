from pathlib import Path

from app.core.dependency_check import ensure_runtime_folders, run_dependency_check
from app.core.runtime_paths import RUNTIME_DIRS
from app.core.system_health import build_system_health_report
from app.core.osint.local_landmarks import load_local_landmarks
from app.core.osint.offline_geocoder import match_offline_places


def test_system_health_assets_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / 'app/core/dependency_check.py').exists()
    assert (root / 'app/core/system_health.py').exists()
    assert (root / 'app/ui/pages/system_health_page.py').exists()
    assert (root / 'tools/visual_similarity_search.py').exists()
    assert (root / 'data/validation_ground_truth.real_template.json').exists()
    assert (root / 'data/osint/local_geocoder_places.json').exists()


def test_system_health_report_is_structured():
    root = Path(__file__).resolve().parents[1]
    report = build_system_health_report(root)
    payload = report.to_dict()
    assert payload['score'] >= 0
    assert payload['dependency_report']['required_total'] >= 1
    assert payload['p2_readiness']['visual_similarity_search'] == 'available'
    assert payload['p2_readiness']['validation_dataset_template'] == 'available'


def test_landmark_and_geocoder_seed_expanded():
    landmarks = load_local_landmarks()
    assert len(landmarks) >= 80
    hits = match_offline_places(['route from Cairo Tower to Khan el-Khalili'])
    names = {hit['name'] for hit in hits}
    assert 'Cairo Tower' in names
    assert 'Khan el-Khalili' in names


def test_dependency_check_runtime_folders(tmp_path):
    created = ensure_runtime_folders(tmp_path)
    assert 'cases' in created
    assert 'case_data' in created
    for folder in RUNTIME_DIRS:
        assert (tmp_path / folder).exists()
    report = run_dependency_check(tmp_path)
    assert report.required_total >= 1
    assert isinstance(report.to_text(), str)
