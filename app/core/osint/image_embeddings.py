from __future__ import annotations

"""Local image embedding helpers.

This module preserves the old import path while exposing the v12.10.1 local
embedding/search functions.
"""

from .image_fingerprint import fingerprint_image
from .local_clip import (
    classify_offline_scene,
    compute_local_image_embedding,
    cosine_similarity,
    describe_local_embedding_backend,
    search_similar_images,
)

__all__ = [
    "fingerprint_image",
    "classify_offline_scene",
    "compute_local_image_embedding",
    "cosine_similarity",
    "describe_local_embedding_backend",
    "search_similar_images",
]
