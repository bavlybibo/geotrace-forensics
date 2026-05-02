from pathlib import Path
import ast


def _config_version(root: Path) -> str:
    tree = ast.parse((root / 'app/config.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'APP_VERSION':
                    if isinstance(node.value, ast.Constant):
                        return str(node.value.value)
    raise AssertionError('APP_VERSION not found')


def test_release_files_exist():
    root = Path(__file__).resolve().parents[1]
    required = [
        'VERSION', 'main.py', 'requirements.txt', 'requirements-dev.txt', 'setup_windows.bat',
        'run_windows.bat', 'make_release.bat', 'geotrace_forensics_x.spec',
        'geotrace_forensics_x_demo.spec', 'tools/audit_release.py', 'tools/visual_similarity_search.py',
        'app/core/runtime_paths.py', 'app/core/dependency_check.py', 'app/core/system_health.py',
        'app/ui/pages/system_health_page.py', 'data/validation_ground_truth.real_template.json',
        'data/osint/local_geocoder_places.json',
        'data/osint/geo_aliases.json', 'tools/build_offline_geocoder_index.py',
        'docs/GEO_DATA_SOURCES.md',
    ]
    missing = [item for item in required if not (root / item).exists()]
    assert not missing, missing


def test_version_aligned():
    root = Path(__file__).resolve().parents[1]
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    assert version == _config_version(root)
    assert f'v{version}' in (root / 'README.md').read_text(encoding='utf-8')
    make_release = (root / 'make_release.bat').read_text(encoding='utf-8')
    assert 'VERSION' in make_release


def test_release_cleaner_covers_generated_python_cache_artifacts():
    """Keep pytest compatible with release hygiene.

    pytest/compileall legitimately create __pycache__ and .pyc files while the
    test suite is running, so the live test tree cannot be required to stay
    cache-free. The release gate enforces a clean tree through
    tools/audit_release.py after tools/clean_release_artifacts.py.
    """
    root = Path(__file__).resolve().parents[1]
    cleaner = (root / 'tools/clean_release_artifacts.py').read_text(encoding='utf-8')
    audit = (root / 'tools/audit_release.py').read_text(encoding='utf-8')
    for token in ('*.pyc', '__pycache__', '.pytest_cache'):
        assert token in cleaner
        assert token in audit
