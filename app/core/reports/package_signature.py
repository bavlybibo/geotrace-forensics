from __future__ import annotations

"""Tamper-evident package signature envelope.

This is not a legal digital signature with a private key. It is a deterministic
root hash over exported artifacts and report assets that makes post-export changes
obvious and gives the verifier a stable handoff receipt.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import hmac
import os
import json
from pathlib import Path
from typing import Any, Iterable

SIGNATURE_FILE = "package_signature.json"
SIGNATURE_SHA256_FILE = "package_signature.sha256"


@dataclass(slots=True)
class PackageSignature:
    generated_at: str
    package_dir: str
    manifest_sha256: str
    entry_count: int
    package_root_sha256: str
    algorithm: str = "sha256(manifest_sha256 + sorted(entry.relative_path:entry.sha256))"
    hmac_sha256: str = ""
    hmac_key_id: str = ""
    entries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _entry_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for section in ("artifacts", "report_assets"):
        for key, entry in (manifest.get(section, {}) or {}).items():
            if not isinstance(entry, dict):
                continue
            relative = str(entry.get("relative_path") or entry.get("file_name") or key)
            digest = str(entry.get("sha256") or "")
            rows.append({"section": section, "key": str(key), "relative_path": relative, "sha256": digest})
    rows.sort(key=lambda item: (item["section"], item["relative_path"], item["key"]))
    return rows


def compute_package_root(manifest_sha256: str, entries: Iterable[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    digest.update(str(manifest_sha256).encode("utf-8"))
    for entry in entries:
        line = f"{entry.get('section','')}|{entry.get('relative_path','')}|{entry.get('sha256','')}\n"
        digest.update(line.encode("utf-8"))
    return digest.hexdigest()


def write_package_signature(package_dir: Path | str) -> dict[str, str]:
    package = Path(package_dir)
    manifest_path = package / "export_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("export_manifest.json is required before package signature can be written")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_sha = _sha256(manifest_path)
    rows = _entry_rows(manifest)
    root = compute_package_root(manifest_sha, rows)
    payload = PackageSignature(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        package_dir=package.name,
        manifest_sha256=manifest_sha,
        entry_count=len(rows),
        package_root_sha256=root,
        entries=rows,
    ).to_dict()
    hmac_key = os.environ.get("GEOTRACE_PACKAGE_SIGNING_KEY", "").encode("utf-8")
    if hmac_key:
        payload["hmac_sha256"] = hmac.new(hmac_key, root.encode("utf-8"), hashlib.sha256).hexdigest()
        payload["hmac_key_id"] = os.environ.get("GEOTRACE_PACKAGE_SIGNING_KEY_ID", "local-hmac-key")
        payload["algorithm"] = payload.get("algorithm", "") + " + optional HMAC-SHA256(package_root)"
    signature_path = package / SIGNATURE_FILE
    signature_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    signature_sha = _sha256(signature_path)
    sha_path = package / SIGNATURE_SHA256_FILE
    sha_path.write_text(f"{signature_sha}  {SIGNATURE_FILE}\n", encoding="utf-8")
    return {"signature": str(signature_path), "signature_sha256": str(sha_path), "package_root_sha256": root}


def verify_package_signature(package_dir: Path | str) -> tuple[bool, str]:
    package = Path(package_dir)
    signature_path = package / SIGNATURE_FILE
    sidecar = package / SIGNATURE_SHA256_FILE
    manifest_path = package / "export_manifest.json"
    if not signature_path.exists():
        return False, "package_signature.json is missing."
    if not sidecar.exists():
        return False, "package_signature.sha256 is missing."
    if not manifest_path.exists():
        return False, "export_manifest.json is missing."
    parts = sidecar.read_text(encoding="utf-8", errors="ignore").strip().split()
    if not parts:
        return False, "package_signature.sha256 is empty."
    sidecar_expected = parts[0]
    if sidecar_expected != _sha256(signature_path):
        return False, "package_signature.sha256 does not match package_signature.json."
    try:
        signature = json.loads(signature_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"Package signature or manifest JSON could not be parsed: {exc}."
    rows = _entry_rows(manifest)
    root = compute_package_root(_sha256(manifest_path), rows)
    if root != signature.get("package_root_sha256"):
        return False, "Package root hash does not match the signature envelope."
    hmac_value = str(signature.get("hmac_sha256") or "")
    if hmac_value:
        hmac_key = os.environ.get("GEOTRACE_PACKAGE_SIGNING_KEY", "").encode("utf-8")
        if not hmac_key:
            return False, "Package has HMAC signature but GEOTRACE_PACKAGE_SIGNING_KEY is not configured for verification."
        expected_hmac = hmac.new(hmac_key, root.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(hmac_value, expected_hmac):
            return False, "Package HMAC signature does not match the configured signing key."
        return True, f"Package signature + HMAC verified; root={root[:16]}… entries={len(rows)}."
    return True, f"Package signature verified; root={root[:16]}… entries={len(rows)}."
