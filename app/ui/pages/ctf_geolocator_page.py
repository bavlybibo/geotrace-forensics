from __future__ import annotations

"""Compatibility facade for the legacy CTF GeoLocator import path.

The real implementation lives in :mod:`app.ui.pages.ctf.geolocator_page`.
Keep private helper exports explicit because wildcard imports intentionally skip
underscore-prefixed names, while regression tests import those helpers directly.
"""

from .ctf.geolocator_page import *  # noqa: F401,F403
from .ctf.geolocator_page import (
    _candidate_key,
    _iter_candidates,
    _render_writeup,
    _update_candidate_status_by_key,
    build_ctf_geolocator_page,
    refresh_ctf_geolocator_page,
)

__all__ = [
    "_candidate_key",
    "_iter_candidates",
    "_render_writeup",
    "_update_candidate_status_by_key",
    "build_ctf_geolocator_page",
    "refresh_ctf_geolocator_page",
]
