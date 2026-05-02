from __future__ import annotations

"""Optional local vision model readiness + execution hooks.

GeoTrace stays offline and deterministic by default.  This module adds a real
adapter layer without bundling a model or making network calls:

Environment options
-------------------
GEOTRACE_LOCAL_VISION_MODEL
    Folder or manifest JSON.  A manifest may contain model_type, capabilities,
    command, timeout_seconds, and input_mode.
GEOTRACE_LOCAL_VISION_COMMAND
    Command used to execute a local model runner.  The command receives the
    image path as its final argument and should print JSON to stdout.
GEOTRACE_LOCAL_VISION_TIMEOUT
    Max seconds for the model runner.  Default: 8.

Expected runner JSON
--------------------
{
  "caption": "...",
  "scene_label": "...",
  "confidence": 0.0-1.0 or 0-100,
  "objects": [{"label":"map", "confidence":0.82}],
  "landmarks": [{"label":"Cairo Tower", "confidence":0.63}],
  "warnings": ["..."]
}

If the runner is absent or fails, callers get a structured disabled/error result
and the deterministic pipeline continues safely.
"""

from dataclasses import asdict, dataclass, field
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
from typing import Any


_BLOCKED_COMMAND_TOKENS = {"&&", "||", "|", ";", "<", ">", ">>", "2>", "`"}
_BLOCKED_SHELL_EXECUTABLES = {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe", "bash", "bash.exe", "sh", "sh.exe"}
_DEFAULT_MAX_OUTPUT_BYTES = 200_000


@dataclass(slots=True)
class LocalVisionModelStatus:
    enabled: bool
    path: str = ""
    model_type: str = "not_configured"
    capabilities: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    command_configured: bool = False
    timeout_seconds: int = 8
    runner_sha256: str = ""
    policy_status: str = "safe_or_not_configured"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LocalVisionInferenceResult:
    available: bool = False
    executed: bool = False
    provider: str = "local-vision-disabled"
    caption: str = ""
    scene_label: str = ""
    confidence: int = 0
    objects: list[dict[str, Any]] = field(default_factory=list)
    landmarks: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_int(value: Any, default: int = 8) -> int:
    try:
        return max(1, min(60, int(value)))
    except Exception:
        return default


def _split_command(command: str) -> list[str]:
    """Split a direct runner command safely on Linux/macOS and Windows.

    Python's POSIX shlex mode strips backslashes from Windows paths such as
    C:\\hostedtoolcache\\windows\\Python\\python.exe. Using posix=False on
    Windows preserves those paths so CI/self-test commands execute correctly.
    """
    return shlex.split(command, posix=(os.name != "nt"))


def _load_manifest(path: Path) -> dict[str, Any]:
    manifest_path = path if path.is_file() else path / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # caller adds user-facing warning too
        return {"__manifest_error__": str(exc)}


def _resolve_status() -> tuple[LocalVisionModelStatus, dict[str, Any]]:
    raw = os.environ.get("GEOTRACE_LOCAL_VISION_MODEL", "").strip()
    env_command = os.environ.get("GEOTRACE_LOCAL_VISION_COMMAND", "").strip()
    env_timeout = _safe_int(os.environ.get("GEOTRACE_LOCAL_VISION_TIMEOUT", "8"), 8)
    if not raw and not env_command:
        return (
            LocalVisionModelStatus(
                False,
                capabilities=["deterministic-map-classifier", "map-ocr-zone-planner", "no-remote-ai"],
                warnings=["No local vision runner configured. Deterministic heuristics only. Attach a real offline model with GEOTRACE_LOCAL_VISION_COMMAND and a JSON manifest when needed."],
                command_configured=False,
                timeout_seconds=env_timeout,
            ),
            {},
        )

    manifest: dict[str, Any] = {}
    warnings: list[str] = []
    model_type = "command" if env_command else "folder"
    capabilities = ["offline-adapter", "json-schema-guard", "safe-timeout", "image-captioning-schema", "object-detection-schema", "landmark-candidate-schema", "map-screenshot-classifier-schema", "clip-similarity-schema"]
    path_str = ""

    if raw:
        path = Path(raw)
        path_str = str(path)
        if not path.exists():
            return (
                LocalVisionModelStatus(
                    False,
                    path=path_str,
                    model_type="missing_path",
                    warnings=["Configured local vision model path does not exist."],
                    command_configured=bool(env_command),
                    timeout_seconds=env_timeout,
                ),
                {},
            )
        manifest = _load_manifest(path)
        if manifest.get("__manifest_error__"):
            warnings.append("Manifest could not be parsed: " + str(manifest["__manifest_error__"]))
        model_type = str(manifest.get("model_type") or manifest.get("type") or model_type)
        for cap in manifest.get("capabilities", []) or []:
            clean = str(cap).strip()
            if clean:
                capabilities.append(clean)

    command = env_command or str(manifest.get("command") or "").strip()
    timeout = _safe_int(manifest.get("timeout_seconds", env_timeout), env_timeout)
    runner_sha256 = ""
    policy_status = "safe_or_not_configured"
    if command:
        capabilities.append("local-model-execution")
        try:
            args = _split_command(command)
        except Exception as exc:
            args = []
            warnings.append(f"Local vision command cannot be parsed safely: {exc}")
            policy_status = "blocked"
        policy_error = _command_policy_error(args)
        if policy_error:
            warnings.append(policy_error)
            policy_status = "blocked"
        runner_file = _find_runner_file(args) if args else None
        if runner_file is not None:
            runner_sha256 = _sha256_file(runner_file if runner_file.is_absolute() else Path.cwd() / runner_file)
            expected_sha = str(manifest.get("runner_sha256") or "").strip().lower()
            if expected_sha and runner_sha256 and expected_sha != runner_sha256.lower():
                warnings.append("Local vision runner SHA256 does not match manifest runner_sha256; inference will be blocked until reviewed.")
                policy_status = "blocked"
        warnings.append("Local vision execution is enabled through a real offline command runner; verify model license, hardware fit, and that the runner makes no network calls.")
    else:
        warnings.append("Local model path is configured, but no command is set; inference remains deterministic until GEOTRACE_LOCAL_VISION_COMMAND is set.")

    return (
        LocalVisionModelStatus(
            bool(command or raw),
            path=path_str,
            model_type=model_type,
            capabilities=sorted(set(capabilities)),
            warnings=warnings,
            command_configured=bool(command) and policy_status != "blocked",
            timeout_seconds=timeout,
            runner_sha256=runner_sha256,
            policy_status=policy_status,
        ),
        {**manifest, "command": command, "timeout_seconds": timeout, "policy_status": policy_status},
    )



def _safe_max_output() -> int:
    try:
        value = int(os.environ.get("GEOTRACE_LOCAL_VISION_MAX_OUTPUT", str(_DEFAULT_MAX_OUTPUT_BYTES)))
        return max(16_384, min(1_000_000, value))
    except Exception:
        return _DEFAULT_MAX_OUTPUT_BYTES


def _command_policy_error(args: list[str]) -> str:
    if not args:
        return "Local vision command is empty."
    if any(token in _BLOCKED_COMMAND_TOKENS for token in args):
        return "Local vision command contains shell-control tokens; use a direct runner command such as: python tools/local_vision_runner_template.py"
    executable = Path(args[0]).name.lower()
    if executable in _BLOCKED_SHELL_EXECUTABLES and os.environ.get("GEOTRACE_LOCAL_VISION_ALLOW_SHELL", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return "Local vision command starts a shell interpreter. This is blocked by default; use a direct Python runner or explicitly set GEOTRACE_LOCAL_VISION_ALLOW_SHELL=1 after review."
    return ""


def _find_runner_file(args: list[str]) -> Path | None:
    for token in args[1:4]:
        if token.startswith('-'):
            continue
        candidate = Path(token)
        if candidate.suffix.lower() in {'.py', '.exe', '.bat', '.cmd', '.ps1'}:
            return candidate
    first = Path(args[0])
    if first.suffix.lower() in {'.py', '.exe', '.bat', '.cmd', '.ps1'}:
        return first
    return None


def _sha256_file(path: Path) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _write_tiny_png() -> Path:
    # 1x1 transparent PNG used only for local-runner self-tests.
    raw = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII='
    )
    tmp = tempfile.NamedTemporaryFile(prefix='geotrace_local_vision_selftest_', suffix='.png', delete=False)
    try:
        tmp.write(raw)
        return Path(tmp.name)
    finally:
        tmp.close()

def detect_local_vision_model() -> LocalVisionModelStatus:
    status, _manifest = _resolve_status()
    return status


def _confidence_to_int(value: Any) -> int:
    try:
        score = float(value)
        if 0 <= score <= 1:
            score *= 100
        return max(0, min(100, int(round(score))))
    except Exception:
        return 0


def _normalize_items(items: Any, *, limit: int = 12) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return normalized
    for item in items[:limit]:
        if isinstance(item, str):
            label = item.strip()
            if label:
                normalized.append({"label": label, "confidence": 0})
            continue
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("name") or item.get("class") or "").strip()
        if not label:
            continue
        normalized.append(
            {
                "label": label[:120],
                "confidence": _confidence_to_int(item.get("confidence", item.get("score", 0))),
                "source": str(item.get("source") or "local_vision_runner")[:80],
            }
        )
    return normalized


def run_optional_local_vision(image_path: Path | str) -> LocalVisionInferenceResult:
    """Run a configured local vision adapter and normalize its JSON output.

    The function never calls the network and never raises to the caller.  It is
    safe to call from imports/rescans because timeouts and output sizes are
    bounded.
    """
    status, manifest = _resolve_status()
    if not status.command_configured:
        return LocalVisionInferenceResult(
            available=status.enabled,
            executed=False,
            provider="local-vision-not-executed",
            warnings=list(status.warnings),
            raw={"status": status.to_dict()},
        )

    command = str(manifest.get("command") or "").strip()
    if not command:
        return LocalVisionInferenceResult(available=False, warnings=["No local vision command configured."])

    path = Path(image_path)
    if not path.exists():
        return LocalVisionInferenceResult(available=False, warnings=["Image path does not exist for local vision inference."])

    timeout = _safe_int(manifest.get("timeout_seconds", status.timeout_seconds), status.timeout_seconds)
    try:
        args = _split_command(command)
    except Exception as exc:
        return LocalVisionInferenceResult(
            available=True,
            executed=False,
            provider="local-vision-command-parse-error",
            warnings=[f"Local vision command cannot be parsed safely: {exc}"],
        )
    policy_error = _command_policy_error(args)
    if policy_error or manifest.get("policy_status") == "blocked":
        return LocalVisionInferenceResult(
            available=True,
            executed=False,
            provider="local-vision-policy-blocked",
            warnings=[policy_error or "Local vision runner policy blocked execution."],
        )

    try:
        args = args + [str(path)]
        completed = subprocess.run(
            args,
            input="",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return LocalVisionInferenceResult(
            available=True,
            executed=False,
            provider="local-vision-timeout",
            warnings=[f"Local vision runner timed out after {timeout}s."],
        )
    except Exception as exc:
        return LocalVisionInferenceResult(
            available=True,
            executed=False,
            provider="local-vision-error",
            warnings=[f"Local vision runner could not start: {exc}"],
        )

    max_output = _safe_max_output()
    raw_stdout = completed.stdout or ""
    stdout = raw_stdout[:max_output]
    stderr = (completed.stderr or "")[:4_000]
    if len(raw_stdout) > max_output:
        return LocalVisionInferenceResult(
            available=True,
            executed=False,
            provider="local-vision-output-too-large",
            warnings=[f"Local vision runner output exceeded {max_output} bytes and was rejected."],
        )

    if completed.returncode != 0:
        return LocalVisionInferenceResult(
            available=True,
            executed=False,
            provider="local-vision-nonzero-exit",
            warnings=[f"Local vision runner exited with code {completed.returncode}.", stderr.strip()[:500]],
        )

    try:
        data = json.loads(stdout)
    except Exception as exc:
        return LocalVisionInferenceResult(
            available=True,
            executed=True,
            provider="local-vision-invalid-json",
            warnings=[f"Local vision runner output was not valid JSON: {exc}"],
        )
    if not isinstance(data, dict):
        return LocalVisionInferenceResult(
            available=True,
            executed=True,
            provider="local-vision-invalid-schema",
            warnings=["Local vision JSON must be an object."],
        )

    warnings = [str(x)[:300] for x in data.get("warnings", []) or [] if str(x).strip()]
    if stderr.strip():
        warnings.append("runner stderr: " + stderr.strip()[:300])

    return LocalVisionInferenceResult(
        available=True,
        executed=True,
        provider=str(data.get("provider") or manifest.get("model_type") or "local-vision-runner")[:80],
        caption=str(data.get("caption") or data.get("summary") or "")[:600],
        scene_label=str(data.get("scene_label") or data.get("label") or "")[:120],
        confidence=_confidence_to_int(data.get("confidence", data.get("score", 0))),
        objects=_normalize_items(data.get("objects") or data.get("detections") or [], limit=16),
        landmarks=_normalize_items(data.get("landmarks") or data.get("places") or [], limit=10),
        raw={k: v for k, v in data.items() if k not in {"image_bytes", "pixels", "embedding"}},
        warnings=warnings,
    )



def self_test_local_vision(image_path: Path | str | None = None) -> dict[str, Any]:
    """Run a bounded local-vision self-test for System Health / Setup Wizard."""
    status = detect_local_vision_model()
    if not status.command_configured:
        return {
            "ready": False,
            "executed": False,
            "status": status.to_dict(),
            "message": "No approved local vision command is configured.",
        }

    temp_path: Path | None = None
    try:
        target = Path(image_path) if image_path is not None else _write_tiny_png()
        if image_path is None:
            temp_path = target
        result = run_optional_local_vision(target)
        return {
            "ready": bool(result.available and result.executed and result.provider not in {"local-vision-invalid-json", "local-vision-invalid-schema"}),
            "executed": result.executed,
            "provider": result.provider,
            "confidence": result.confidence,
            "objects": result.objects[:5],
            "landmarks": result.landmarks[:5],
            "warnings": result.warnings,
            "status": status.to_dict(),
        }
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
