from __future__ import annotations

"""Machine-readable failure logging for forensic transparency."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Iterator

@dataclass(slots=True)
class FailureEvent:
    timestamp: str
    context: str
    operation: str
    message: str
    evidence_id: str = ''
    path: str = ''
    exception_type: str = ''
    exception: str = ''
    severity: str = 'error'
    user_visible: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not payload.get('extra'):
            payload.pop('extra', None)
        return payload

def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(v) for v in value]
        return str(value)


def _safe_path(path: str | Path | None) -> str:
    if path is None:
        return ''
    try:
        return str(Path(path))
    except Exception:
        return str(path)

def log_failure(
    logger: logging.Logger | None,
    *,
    context: str,
    message: str,
    evidence_id: str = '',
    operation: str = '',
    path: str | Path | None = None,
    exc: BaseException | None = None,
    log_dir: str | Path | None = None,
    extra: dict[str, Any] | None = None,
    severity: str = 'error',
    user_visible: bool = True,
) -> dict[str, Any]:
    event = FailureEvent(
        timestamp=datetime.now().isoformat(timespec='seconds'),
        context=str(context or 'failure'),
        operation=str(operation or context or 'operation'),
        message=str(message or ''),
        evidence_id=str(evidence_id or ''),
        path=_safe_path(path),
        exception_type=type(exc).__name__ if exc else '',
        exception=str(exc) if exc else '',
        severity=str(severity or 'error'),
        user_visible=bool(user_visible),
        extra=_json_safe(dict(extra or {})),
    )
    payload = event.to_dict()
    try:
        target_dir = Path(log_dir or Path.cwd() / 'logs')
        target_dir.mkdir(parents=True, exist_ok=True)
        with (target_dir / 'structured_failures.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + '\n')
    except Exception as log_exc:
        if logger:
            logger.error('Structured failure log write failed: %s', log_exc)
    if logger:
        logger.error('%s | %s | evidence=%s path=%s', payload['context'], payload['message'], payload.get('evidence_id',''), payload.get('path',''))
    return payload

def tail_failures(log_dir: str | Path, limit: int = 80) -> list[dict[str, Any]]:
    path = Path(log_dir) / 'structured_failures.jsonl'
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding='utf-8', errors='ignore').splitlines()[-max(1, int(limit)):]:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return rows

@contextmanager
def failure_scope(
    logger: logging.Logger | None,
    *,
    context: str,
    operation: str = '',
    evidence_id: str = '',
    path: str | Path | None = None,
    log_dir: str | Path | None = None,
    extra: dict[str, Any] | None = None,
    severity: str = 'error',
    user_visible: bool = True,
) -> Iterator[None]:
    try:
        yield
    except Exception as exc:
        log_failure(
            logger,
            context=context,
            operation=operation or context,
            evidence_id=evidence_id,
            path=path,
            exc=exc,
            log_dir=log_dir,
            extra=extra,
            severity=severity,
            user_visible=user_visible,
            message=f"{operation or context} failed: {exc}",
        )
        raise
