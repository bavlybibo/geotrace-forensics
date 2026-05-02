from __future__ import annotations

"""Compatibility facade for the CTF GeoLocator page.

This module preserves the old import path:
    app.ui.pages.ctf_geolocator_page

The real implementation lives in:
    app.ui.pages.ctf.geolocator_page

Keep this facade explicit because wildcard imports do not export private
helpers whose names start with an underscore. Several regression tests import
these helpers directly to validate CTF UI hardening behavior.
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
