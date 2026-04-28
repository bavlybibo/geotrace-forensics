from __future__ import annotations

"""Compatibility facade for anomaly detection helpers.

This module is intentionally kept as a compatibility facade so older imports keep
working after the v12.10.2 codebase organization pass.
"""

from .anomaly_detection.service import *  # noqa: F401,F403
from .anomaly_detection import service as _impl

__all__ = []
for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)
        __all__.append(_name)

del _impl
