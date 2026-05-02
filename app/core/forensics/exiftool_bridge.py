from __future__ import annotations

"""Safe optional ExifTool bridge.

GeoTrace never requires ExifTool to run. When available, this helper enriches
metadata extraction with a bounded, local-only subprocess call using shell=False.
It accepts either:
- GEOTRACE_EXIFTOOL_CMD
- tools/bin/exiftool/exiftool.exe inside the project
- exiftool/exiftool.exe on PATH
"""

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any


@dataclass(slots=True)
class ExifToolResult:
    available: bool = False
    executed: bool = False
    binary: str = ""
    timeout_seconds: float = 5.0
    metadata: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _project_root_from_file(path: Path) -> Path:
    for parent in [path, *path.parents]:
        if (parent / "VERSION").exists() and (parent / "app").exists():
            return parent
    return Path.cwd()


def resolve_exiftool_binary(project_root: Path | str | None = None) -> str:
    candidates: list[str] = []
    env = os.getenv("GEOTRACE_EXIFTOOL_CMD", "").strip()
    if env:
        candidates.append(env)
    if project_root is not None:
        root = Path(project_root)
        candidates.extend([
            str(root / "tools" / "bin" / "exiftool" / "exiftool.exe"),
            str(root / "tools" / "bin" / "exiftool" / "exiftool"),
        ])
    for name in ("exiftool", "exiftool.exe"):
        resolved = shutil.which(name)
        if resolved:
            candidates.append(resolved)
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and path.is_file():
            return str(path)
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return ""


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)[:500]
        except Exception:
            return str(value)[:500]
    return str(value).strip()


def _put_alias(aliases: dict[str, str], key: str, value: Any) -> None:
    rendered = _stringify(value)
    if rendered:
        aliases.setdefault(key, rendered)


def _build_aliases(raw: dict[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}

    def pick(*names: str) -> Any:
        for name in names:
            if name in raw and raw[name] not in (None, ""):
                return raw[name]
        return ""

    for target, names in {
        "Make": ("EXIF:Make", "IFD0:Make", "Make"),
        "Model": ("EXIF:Model", "IFD0:Model", "Model"),
        "Software": ("EXIF:Software", "IFD0:Software", "Software"),
        "DateTimeOriginal": ("EXIF:DateTimeOriginal", "Composite:SubSecDateTimeOriginal", "DateTimeOriginal"),
        "DateTimeDigitized": ("EXIF:CreateDate", "CreateDate", "DateTimeDigitized"),
        "DateTime": ("EXIF:ModifyDate", "IFD0:ModifyDate", "ModifyDate", "DateTime"),
        "Orientation": ("EXIF:Orientation", "IFD0:Orientation", "Orientation"),
        "LensModel": ("EXIF:LensModel", "Composite:LensID", "LensModel"),
        "ISO": ("EXIF:ISO", "ISO"),
        "ExposureTime": ("EXIF:ExposureTime", "ExposureTime"),
        "FNumber": ("EXIF:FNumber", "FNumber"),
        "FocalLength": ("EXIF:FocalLength", "FocalLength"),
        "Artist": ("EXIF:Artist", "IFD0:Artist", "Artist"),
        "Copyright": ("EXIF:Copyright", "IFD0:Copyright", "Copyright"),
    }.items():
        _put_alias(aliases, target, pick(*names))

    lat = pick("Composite:GPSLatitude", "EXIF:GPSLatitude", "GPS:GPSLatitude", "GPSLatitude")
    lon = pick("Composite:GPSLongitude", "EXIF:GPSLongitude", "GPS:GPSLongitude", "GPSLongitude")
    alt = pick("Composite:GPSAltitude", "EXIF:GPSAltitude", "GPS:GPSAltitude", "GPSAltitude")
    if lat not in (None, "") and lon not in (None, ""):
        _put_alias(aliases, "GPS GPSLatitude", lat)
        _put_alias(aliases, "GPS GPSLongitude", lon)
        try:
            _put_alias(aliases, "GPS GPSLatitudeRef", "S" if float(lat) < 0 else "N")
            _put_alias(aliases, "GPS GPSLongitudeRef", "W" if float(lon) < 0 else "E")
        except Exception:
            pass
    if alt not in (None, ""):
        _put_alias(aliases, "GPS GPSAltitude", alt)
    return aliases


def extract_exiftool_metadata(file_path: Path | str, project_root: Path | str | None = None) -> ExifToolResult:
    path = Path(file_path)
    result = ExifToolResult()
    if project_root is None:
        project_root = _project_root_from_file(path.resolve())
    binary = resolve_exiftool_binary(project_root)
    result.binary = binary
    result.available = bool(binary)
    if not binary:
        result.warnings.append("ExifTool binary not found; using Python metadata parsers only.")
        return result
    try:
        result.timeout_seconds = max(1.0, float(os.getenv("GEOTRACE_EXIFTOOL_TIMEOUT", "5.0")))
    except Exception:
        result.timeout_seconds = 5.0
    try:
        completed = subprocess.run(
            [binary, "-json", "-n", "-G1", "-s", str(path)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=result.timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        result.warnings.append(f"ExifTool timed out after {result.timeout_seconds:.1f}s.")
        return result
    except Exception as exc:
        result.warnings.append(f"ExifTool execution failed: {exc.__class__.__name__}.")
        return result
    result.executed = True
    if completed.returncode not in (0, 1):
        result.warnings.append(f"ExifTool returned code {completed.returncode}.")
    stderr = (completed.stderr or "").strip()
    if stderr:
        result.warnings.append(stderr[:300])
    try:
        parsed = json.loads(completed.stdout or "[]")
        row = parsed[0] if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict) else {}
    except Exception as exc:
        result.warnings.append(f"ExifTool JSON parse failed: {exc.__class__.__name__}.")
        row = {}
    metadata: dict[str, str] = {}
    for key, value in row.items():
        if key == "SourceFile":
            continue
        rendered = _stringify(value)
        if rendered:
            metadata[f"ExifTool {key.replace(':', ' ')}"] = rendered[:500]
    result.metadata = metadata
    result.aliases = _build_aliases(row)
    return result
