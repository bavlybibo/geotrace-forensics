from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'VERSION',
    'main.py', 'requirements.txt', 'requirements-dev.txt',
    'setup_windows.bat', 'run_windows.bat', 'make_release.bat',
    'geotrace_forensics_x.spec', 'geotrace_forensics_x_demo.spec',
    'README.md', 'LICENSE', 'PRIVACY.md', 'SECURITY.md', 'DISCLAIMER.md',
    'tests/test_release_files.py', 'tests/test_map_false_positive_guard.py',
    'tests/test_system_health_p2.py', 'tests/test_visual_similarity.py',
    'app/config.py', 'app/core/runtime_paths.py',
    'app/core/dependency_check.py', 'app/core/system_health.py',
    'app/core/vision/local_vision_model.py',
    'tests/test_local_vision_runner_hardening.py',
    'tools/clean_release_artifacts.py',
    'app/ui/pages/system_health_page.py', 'tools/visual_similarity_search.py', 'tools/build_offline_geocoder_index.py', 'docs/GEO_DATA_SOURCES.md',
    'data/validation_ground_truth.real_template.json', 'data/osint/local_geocoder_places.json', 'data/osint/geo_aliases.json',
]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8', errors='ignore')


def _config_version() -> str:
    text = read('app/config.py') if (ROOT / 'app/config.py').exists() else ''
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ''
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'APP_VERSION':
                    if isinstance(node.value, ast.Constant):
                        return str(node.value.value)
    return ''


def main() -> int:
    failures: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            failures.append(f'missing required file: {rel}')

    version_file = read('VERSION').strip() if (ROOT / 'VERSION').exists() else ''
    config_version = _config_version()
    readme = read('README.md') if (ROOT / 'README.md').exists() else ''
    make_release = read('make_release.bat') if (ROOT / 'make_release.bat').exists() else ''

    if not version_file:
        failures.append('VERSION file is empty or missing')
    if config_version != version_file:
        failures.append(f'APP_VERSION ({config_version or "missing"}) does not match VERSION ({version_file or "missing"})')
    if version_file and f'v{version_file}' not in readme and version_file not in readme:
        failures.append(f'README does not identify version {version_file}')
    if version_file and version_file not in make_release and 'VERSION' not in make_release:
        failures.append('make_release.bat does not consume the VERSION file')

    pyc = list(ROOT.rglob('*.pyc'))
    caches = [p for p in ROOT.rglob('__pycache__') if p.is_dir()]
    pytest_cache = ROOT / '.pytest_cache'
    if pyc:
        failures.append(f'compiled .pyc files present: {len(pyc)}')
    if caches:
        failures.append(f'__pycache__ folders present: {len(caches)}')
    if pytest_cache.exists():
        failures.append('.pytest_cache folder present')

    if 'tools\audit_release.py' not in readme and 'tools/audit_release.py' not in readme:
        failures.append('README does not document audit_release.py')

    if failures:
        print('GeoTrace release audit FAILED:')
        for item in failures:
            print(f' - {item}')
        return 1
    print(f'GeoTrace release audit passed for v{version_file}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
