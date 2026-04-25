from __future__ import annotations

"""Compatibility wrapper.

The old module name implied neural embeddings. v12.9 uses the clearer
`image_fingerprint` name unless an optional local CLIP backend is explicitly enabled.
"""

from .image_fingerprint import fingerprint_image

__all__ = ["fingerprint_image"]
