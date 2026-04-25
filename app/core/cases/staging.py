from __future__ import annotations

from pathlib import Path
import shutil


def stage_evidence_file(source: Path, destination: Path) -> Path:
    """Copy an evidence file into a case-controlled working path using parent-safe creation."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination
