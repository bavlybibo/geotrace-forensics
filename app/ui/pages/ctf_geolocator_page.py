from __future__ import annotations

"""Compatibility facade for the CTF GeoLocator page."""

from .ctf.geolocator_page import *  # noqa: F401,F403
from .ctf.geolocator_page import build_ctf_geolocator_page, refresh_ctf_geolocator_page

__all__ = ["build_ctf_geolocator_page", "refresh_ctf_geolocator_page"]
