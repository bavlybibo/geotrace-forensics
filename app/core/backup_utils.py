from __future__ import annotations

import zipfile
from pathlib import Path


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_extract_zip(archive: zipfile.ZipFile, target_dir: Path) -> None:
    """Extract a zip archive only if every member stays inside target_dir.

    Prevents Zip Slip payloads such as ../../evil.py or absolute drive paths from
    writing outside the restore preview directory.
    """
    target = Path(target_dir).resolve()
    for member in archive.infolist():
        name = member.filename.replace("\\", "/")
        member_path = (target / name).resolve()
        if Path(name).is_absolute() or not _is_relative_to(member_path, target):
            raise ValueError(f"Unsafe path in backup archive: {member.filename}")
    archive.extractall(target)
