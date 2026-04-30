from __future__ import annotations

"""Single runtime-folder contract used by startup, health checks, and tests."""

from pathlib import Path

# Keep both ``case_data`` and ``cases`` for backwards compatibility: earlier
# builds used case_data while newer health tooling expects cases.
RUNTIME_DIRS: tuple[str, ...] = (
    "case_data",
    "cases",
    "exports",
    "logs",
    "cache",
    "reports",
    "tmp",
    "data/validation",
    "data/validation_cases",
)


def ensure_project_runtime_dirs(project_root: Path | str) -> list[str]:
    """Create runtime folders and return the relative names newly created."""
    root = Path(project_root)
    created: list[str] = []
    for name in RUNTIME_DIRS:
        folder = root / name
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            created.append(name)
    return created


def runtime_dir_paths(project_root: Path | str) -> list[Path]:
    root = Path(project_root)
    return [root / name for name in RUNTIME_DIRS]
