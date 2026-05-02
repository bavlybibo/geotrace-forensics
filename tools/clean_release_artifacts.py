from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    removed = 0
    for path in ROOT.rglob('*.pyc'):
        path.unlink(missing_ok=True)
        removed += 1
    for folder in list(ROOT.rglob('__pycache__')):
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
    for name in ('.pytest_cache', 'build'):
        target = ROOT / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            removed += 1
    print(f'Cleaned {removed} generated release artifact(s).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
