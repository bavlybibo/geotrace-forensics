from __future__ import annotations

"""Optional local CLIP/embedding backend descriptor + deterministic fallback.

GeoTrace does not bundle neural weights. When a local model path is configured, the
status advertises that policy decision. Without a model, this module still provides a
privacy-safe perceptual embedding fallback for similarity search and CTF triage; it is
not marketed as neural CLIP recognition.
"""

from dataclasses import dataclass
from pathlib import Path
import math
from typing import Any, Iterable

from PIL import Image, ImageFilter, ImageStat


@dataclass(slots=True)
class LocalEmbeddingStatus:
    enabled: bool
    provider: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "provider": self.provider, "note": self.note}


@dataclass(slots=True)
class ImageSimilarityResult:
    path: str
    score: int
    method: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "score": self.score,
            "method": self.method,
            "explanation": self.explanation,
        }


def describe_local_embedding_backend(model_path: str | Path | None = None) -> LocalEmbeddingStatus:
    if not model_path:
        return LocalEmbeddingStatus(
            enabled=False,
            provider="deterministic-perceptual-fallback",
            note="No neural CLIP model is configured. Similarity search uses local color/luma/edge fingerprints only.",
        )
    path = Path(model_path)
    if not path.exists():
        return LocalEmbeddingStatus(
            enabled=False,
            provider="local-clip",
            note=f"Configured model path does not exist: {path}",
        )
    return LocalEmbeddingStatus(
        enabled=True,
        provider="local-clip",
        note="A local embedding backend path is configured. Ensure case policy permits model-assisted matching.",
    )


def _safe_open(path: str | Path) -> Image.Image | None:
    try:
        image = Image.open(path).convert("RGB")
        image.load()
        return image
    except Exception:
        return None


def compute_local_image_embedding(path: str | Path, *, size: int = 32) -> list[float]:
    """Return a compact local-only image vector.

    The vector contains normalized low-resolution luma, RGB means/stddevs, and simple
    edge-density hints. It is deterministic and works without downloading models.
    """
    image = _safe_open(path)
    if image is None:
        return []
    thumb = image.resize((size, size))
    gray = thumb.convert("L")
    pixels = [v / 255.0 for v in gray.getdata()]
    stat = ImageStat.Stat(thumb)
    means = [x / 255.0 for x in stat.mean[:3]]
    stddev = [x / 255.0 for x in stat.stddev[:3]]
    edge = gray.filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edge)
    edge_density = (edge_stat.mean[0] / 255.0) if edge_stat.mean else 0.0
    # Downsample luma vector further to keep storage light.
    sampled = pixels[:: max(1, len(pixels) // 192)][:192]
    return sampled + means + stddev + [edge_density]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    a = list(left)
    b = list(right)
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def search_similar_images(query_path: str | Path, candidate_paths: Iterable[str | Path], *, limit: int = 8) -> list[dict[str, Any]]:
    query_vec = compute_local_image_embedding(query_path)
    results: list[ImageSimilarityResult] = []
    for candidate in candidate_paths:
        candidate_vec = compute_local_image_embedding(candidate)
        score = int(round(cosine_similarity(query_vec, candidate_vec) * 100))
        if score <= 0:
            continue
        explanation = "Local deterministic embedding similarity. Treat as grouping support, not identity proof."
        results.append(ImageSimilarityResult(str(candidate), score, "local-perceptual-embedding", explanation))
    results.sort(key=lambda row: (-row.score, row.path.lower()))
    return [row.to_dict() for row in results[:limit]]


def classify_offline_scene(path: str | Path) -> dict[str, Any]:
    image = _safe_open(path)
    if image is None:
        return {"label": "Unavailable", "confidence": 0, "objects": [], "location_hints": [], "limitations": ["Image could not be opened."]}
    w, h = image.size
    stat = ImageStat.Stat(image.resize((64, 64)))
    r, g, b = [float(x) for x in stat.mean[:3]]
    brightness = (r + g + b) / 3
    tags: list[str] = []
    location_hints: list[str] = []
    if g > r * 1.08 and g > b * 1.05:
        tags.append("outdoor/green-region cue")
        location_hints.append("parks, fields, satellite/terrain map regions")
    if b > r * 1.08 and b > g * 1.02:
        tags.append("water/blue-region cue")
        location_hints.append("coastline, river, sea, route overlay, or map water body")
    if brightness > 210:
        tags.append("bright UI/document/map canvas")
    if min(w, h) < 720:
        tags.append("low-resolution evidence; OCR may miss small labels")
    aspect = w / h if h else 1
    if aspect > 1.6:
        tags.append("wide screenshot/layout")
    label = "Map/OSINT visual candidate" if any("map" in hint or "coastline" in hint or "route" in hint for hint in location_hints) else "General image"
    confidence = min(82, 38 + len(tags) * 12)
    return {
        "label": label,
        "confidence": confidence,
        "objects": tags,
        "location_hints": location_hints,
        "limitations": ["Deterministic offline scene classifier; does not replace a trained vision model."],
    }
