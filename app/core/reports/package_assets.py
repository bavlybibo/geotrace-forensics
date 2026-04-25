from __future__ import annotations

import shutil
from pathlib import Path

STRICT_PRIVACY_LEVELS = {"redacted_text", "courtroom_redacted"}
SENSITIVE_STRICT_ASSET_NAMES = {"chart_map.png", "geolocation_map.html"}


def is_strict_privacy_level(privacy_level: str | None) -> bool:
    return str(privacy_level or "").strip().lower() in STRICT_PRIVACY_LEVELS


def should_package_asset(asset_name: str, privacy_level: str | None) -> bool:
    """Return whether a generated report asset is safe to include in this export package."""
    clean_name = Path(asset_name).name
    if is_strict_privacy_level(privacy_level) and clean_name in SENSITIVE_STRICT_ASSET_NAMES:
        return False
    return True


def copy_package_assets(source_dir: Path, package_dir: Path, privacy_level: str | None) -> list[Path]:
    """Copy safe, already-generated visual/report assets into a package folder.

    Strict redacted/courtroom exports must not include visual map artifacts because those can
    reveal coordinates or travel paths even when the textual reports are redacted.
    """
    source_dir = Path(source_dir)
    package_dir = Path(package_dir)
    copied: list[Path] = []
    patterns = ("chart_*.png", "geolocation_map.html")
    for pattern in patterns:
        for source in source_dir.glob(pattern):
            if not source.is_file() or not should_package_asset(source.name, privacy_level):
                continue
            destination = package_dir / source.name
            shutil.copy2(source, destination)
            copied.append(destination)
    return copied
