from __future__ import annotations

"""Optional local CLIP/embedding backend descriptor.

GeoTrace does not bundle a model by default. This keeps the online/AI promise honest:
local embeddings are available only when the analyst installs and enables a backend.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LocalEmbeddingStatus:
    enabled: bool
    provider: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "provider": self.provider, "note": self.note}


def describe_local_embedding_backend(model_path: str | Path | None = None) -> LocalEmbeddingStatus:
    if not model_path:
        return LocalEmbeddingStatus(
            enabled=False,
            provider="none",
            note="Optional local CLIP/embedding backend is not configured. GeoTrace remains deterministic/offline.",
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
