from __future__ import annotations

"""Lazy exports for vision helpers.

The previous eager imports pulled Pillow-backed modules during lightweight
readiness checks.  Lazy loading keeps System Health/Dependency Check fast and
lets the app report missing optional imaging dependencies cleanly.
"""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ImageDetailProfile": ("image_intelligence", "ImageDetailProfile"),
    "analyze_image_details": ("image_intelligence", "analyze_image_details"),
    "LocalVisionInferenceResult": ("local_vision_model", "LocalVisionInferenceResult"),
    "LocalVisionModelStatus": ("local_vision_model", "LocalVisionModelStatus"),
    "detect_local_vision_model": ("local_vision_model", "detect_local_vision_model"),
    "run_optional_local_vision": ("local_vision_model", "run_optional_local_vision"),
    "self_test_local_vision": ("local_vision_model", "self_test_local_vision"),
    "score_visual_map_and_route": ("map_visuals", "score_visual_map_and_route"),
    "summarize_visual_map_signals": ("map_visuals", "summarize_visual_map_signals"),
    "PixelForensicsProfile": ("pixel_stego", "PixelForensicsProfile"),
    "analyze_pixel_forensics": ("pixel_stego", "analyze_pixel_forensics"),
    "SemanticImageProfile": ("semantic_embeddings", "SemanticImageProfile"),
    "build_semantic_image_profile": ("semantic_embeddings", "build_semantic_image_profile"),
    "compare_semantic_profiles": ("semantic_embeddings", "compare_semantic_profiles"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attr = _EXPORTS[name]
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, attr)
    globals()[name] = value
    return value
