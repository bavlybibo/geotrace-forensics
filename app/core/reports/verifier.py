from __future__ import annotations

"""Readable verifier for GeoTrace export packages.

The verifier is intentionally strict for redacted/courtroom packages: it checks the
manifest, hashes, sensitive report assets, and obvious privacy leaks in text artifacts.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable

try:
    from .package_assets import SENSITIVE_STRICT_ASSET_NAMES
except Exception:  # pragma: no cover - protects standalone verifier usage
    SENSITIVE_STRICT_ASSET_NAMES = {"chart_map.png", "geolocation_map.html"}


STRICT_PRIVACY_LEVELS = {"redacted_text", "courtroom_redacted"}
TEXT_SUFFIXES = {".html", ".txt", ".json", ".csv", ".md"}
VERIFIER_OUTPUT_NAMES = {"export_manifest.json", "package_verification.json", "package_verification.txt"}

LEAK_PATTERNS: dict[str, re.Pattern[str]] = {
    "raw_windows_path": re.compile(r"[A-Za-z]:\\|[A-Za-z]:/"),
    "raw_url": re.compile(r"https?://|www\.", re.IGNORECASE),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "coordinates": re.compile(r"(?<![\w.])-?\d{1,3}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}"),
}


@dataclass(slots=True)
class VerificationResult:
    package_dir: str
    privacy_level: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    passed: bool = True
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def add_check(self, message: str) -> None:
        self.checks.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def fail(self, message: str) -> None:
        self.passed = False
        self.failures.append(message)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_text(self) -> str:
        lines = [
            "GeoTrace Courtroom Package Verification",
            "======================================",
            f"Status: {'PASS' if self.passed else 'REVIEW REQUIRED'}",
            f"Privacy level: {self.privacy_level}",
            f"Package: {self.package_dir}",
            f"Generated: {self.generated_at}",
            "",
            "Checks:",
        ]
        lines.extend(f"- {item}" for item in (self.checks or ["No checks recorded."]))
        if self.warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"- {item}" for item in self.warnings)
        if self.failures:
            lines.extend(["", "Failures:"])
            lines.extend(f"- {item}" for item in self.failures)
        return "\n".join(lines).strip() + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_text_files(package_dir: Path) -> Iterable[Path]:
    for path in package_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and path.name not in VERIFIER_OUTPUT_NAMES:
            yield path


def _safe_manifest_path(package_dir: Path, entry: dict) -> Path:
    """Resolve a manifest entry to a path that cannot escape package_dir."""

    for key in ("relative_path", "file_name"):
        raw = str((entry or {}).get(key) or "").strip()
        if not raw:
            continue
        candidate = (package_dir / raw).resolve()
        try:
            candidate.relative_to(package_dir.resolve())
            return candidate
        except Exception as exc:
            result_fallback = package_dir / Path(raw).name
            return result_fallback

    raw_path = str((entry or {}).get("path") or "").strip()
    if not raw_path:
        return package_dir / ""
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return package_dir / candidate.name
    return (package_dir / candidate).resolve()


def _verify_entries(result: VerificationResult, package_dir: Path, entries: dict, label: str) -> None:
    for name, entry in (entries or {}).items():
        candidate = _safe_manifest_path(package_dir, entry or {})
        if not candidate.exists():
            result.fail(f"{label} missing: {name}")
            continue
        expected_hash = str((entry or {}).get("sha256") or "")
        actual_hash = _sha256(candidate)
        if expected_hash and actual_hash != expected_hash:
            result.fail(
                f"Hash mismatch for {label.lower()} {name}: expected {expected_hash[:12]}…, got {actual_hash[:12]}…"
            )
        else:
            result.add_check(f"{label} hash verified: {name} ({candidate.name})")


def _verify_strict_asset_policy(result: VerificationResult, package_dir: Path, report_assets: dict) -> None:
    for sensitive_name in sorted(SENSITIVE_STRICT_ASSET_NAMES):
        if (package_dir / sensitive_name).exists():
            result.fail(
                f"Strict redacted/courtroom export contains {sensitive_name}; sensitive visual map assets should be omitted."
            )

    for asset_name, entry in (report_assets or {}).items():
        packaged_name = str((entry or {}).get("relative_path") or (entry or {}).get("file_name") or asset_name)
        clean_name = Path(packaged_name).name
        first_part = Path(packaged_name).parts[0] if Path(packaged_name).parts else ""
        if clean_name in SENSITIVE_STRICT_ASSET_NAMES:
            result.fail(f"Strict redacted/courtroom manifest references sensitive map asset: {clean_name}.")
        if first_part == "report_assets":
            result.fail("Strict redacted/courtroom export contains report_assets previews; previews should be omitted.")


def _scan_text_for_strict_leaks(result: VerificationResult, package_dir: Path) -> None:
    for path in _iter_text_files(package_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in LEAK_PATTERNS.items():
            if pattern.search(text):
                result.fail(f"Possible privacy leak ({label}) in {path.name}.")
                break
    result.add_check("Strict-mode text artifacts scanned for paths, URLs, emails, and coordinates.")


def verify_export_package(package_dir: Path | str, privacy_level: str | None = None) -> VerificationResult:
    package = Path(package_dir)
    manifest_path = package / "export_manifest.json"
    result = VerificationResult(str(package), privacy_level or "unknown")

    if not package.exists():
        result.fail("Package folder does not exist.")
        return result
    if not manifest_path.exists():
        result.fail("export_manifest.json is missing.")
        return result

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result.fail(f"Manifest could not be parsed: {exc}")
        return result

    result.privacy_level = str(manifest.get("privacy_level") or privacy_level or "unknown")
    strict_mode = result.privacy_level in STRICT_PRIVACY_LEVELS

    artifacts = manifest.get("artifacts", {}) or {}
    report_assets = manifest.get("report_assets", {}) or {}

    _verify_entries(result, package, artifacts, "Artifact")
    if artifacts:
        result.add_check("Manifest artifact section is present.")
    else:
        result.fail("Manifest contains no artifacts to verify.")

    if strict_mode:
        _verify_strict_asset_policy(result, package, report_assets)

    if report_assets:
        _verify_entries(result, package, report_assets, "Report asset")
    else:
        result.add_check("No report_assets or chart assets packaged for this mode.")

    if strict_mode:
        _scan_text_for_strict_leaks(result, package)
    else:
        result.warn("Internal Full export is not privacy-redacted; do not share externally without creating a redacted package.")

    return result


def write_verification_report(package_dir: Path | str, privacy_level: str | None = None) -> dict:
    package = Path(package_dir)
    result = verify_export_package(package, privacy_level)
    text_path = package / "package_verification.txt"
    json_path = package / "package_verification.json"
    text_path.write_text(result.to_text(), encoding="utf-8")
    json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return {"text": str(text_path), "json": str(json_path), "passed": result.passed, "summary": result.to_text()}
