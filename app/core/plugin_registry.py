from __future__ import annotations

"""Lightweight plugin/engine registry for world-readiness expansion.

The registry is intentionally dependency-free.  It gives OCR, map, vision, AI,
privacy, validation, and exporter engines a stable contract before heavier
enterprise plugins are introduced.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable


@dataclass(slots=True)
class EnginePlugin:
    name: str
    family: str
    version: str = "1.0"
    enabled: bool = True
    capabilities: list[str] = field(default_factory=list)
    notes: str = ""
    handler: Callable[..., Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("handler", None)
        return payload


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, EnginePlugin] = {}

    def register(self, plugin: EnginePlugin) -> EnginePlugin:
        key = plugin.name.strip().lower()
        if not key:
            raise ValueError("Plugin name cannot be empty")
        self._plugins[key] = plugin
        return plugin

    def get(self, name: str) -> EnginePlugin | None:
        return self._plugins.get(name.strip().lower())

    def list(self, family: str | None = None, *, enabled_only: bool = False) -> list[EnginePlugin]:
        items = list(self._plugins.values())
        if family:
            fam = family.strip().lower()
            items = [item for item in items if item.family.lower() == fam]
        if enabled_only:
            items = [item for item in items if item.enabled]
        return sorted(items, key=lambda item: (item.family.lower(), item.name.lower()))

    def to_manifest(self) -> dict[str, Any]:
        return {plugin.name: plugin.to_dict() for plugin in self.list()}


def default_registry() -> PluginRegistry:
    registry = PluginRegistry()
    for plugin in [
        EnginePlugin("tesseract_ocr", "ocr", capabilities=["quick_ocr", "deep_ocr", "manual_crop_ocr", "map_label_ocr"], notes="Local OCR only; no remote calls."),
        EnginePlugin("map_label_extractor", "map", capabilities=["map_screenshot_detection", "route_signal", "candidate_place_labels"], notes="Conservative extraction; visual-only claims stay as leads."),
        EnginePlugin("claim_evidence_linker", "forensics", capabilities=["claim_matrix", "source_family", "confidence", "limitations"]),
        EnginePlugin("timeline_confidence", "timeline", capabilities=["time_anchor_scoring", "single_item_warning", "corroboration_actions"]),
        EnginePlugin("privacy_redaction", "privacy", capabilities=["redacted_text", "path_only", "courtroom_redacted", "full"]),
        EnginePlugin("package_verifier", "export", capabilities=["manifest", "sha256_sidecar", "artifact_verification"]),
        EnginePlugin("local_ai_optional", "ai", enabled=False, capabilities=["local_llm_command", "schema_guard", "evidence_only_prompt", "deterministic_fallback"], notes="Disabled by default; set GEOTRACE_AGENT_PROVIDER=local_llm and GEOTRACE_LOCAL_LLM_COMMAND to use an offline runner."),
        EnginePlugin("local_vision_optional", "vision", enabled=False, capabilities=["local_vision_command", "object_candidates", "landmark_candidates", "caption_schema", "safe_timeout"], notes="Optional offline runner via GEOTRACE_LOCAL_VISION_COMMAND; deterministic image intelligence remains the default."),
        EnginePlugin("semantic_fingerprint", "vision", capabilities=["near_duplicate_triage", "visual_family_tags", "offline_vector", "no_network"], notes="Dependency-free fallback vector; use local CLIP/SigLIP runner for stronger semantic identity."),
        EnginePlugin("evidence_fusion_guard", "ai", capabilities=["claim_to_evidence", "contradiction_guard", "limitations", "next_best_action"], notes="Prevents AI language from outrunning recovered evidence."),
        EnginePlugin("package_signature", "export", capabilities=["package_root_hash", "signature_sidecar", "verifier_hook"], notes="Tamper-evident envelope; not a legal PKI signature."),
        EnginePlugin("multi_case_comparison", "enterprise", capabilities=["shared_hashes", "shared_places", "shared_devices", "timeline_overlap"]),
        EnginePlugin("enterprise_audit", "enterprise", capabilities=["blockers", "controls", "handoff_readiness"]),
        EnginePlugin("launch_readiness_gate", "export", capabilities=["handoff_blockers", "privacy_gate", "validation_gate", "courtroom_threshold"], notes="Conservative release/handoff gate for demo, external, and courtroom packages."),
        EnginePlugin("validation_template", "validation", capabilities=["ground_truth_template", "accuracy_dataset_bootstrap"], notes="Generates validation_ground_truth_template.json for measurable test sets."),
    ]:
        registry.register(plugin)
    return registry


def registry_manifest_text(registry: PluginRegistry | None = None) -> str:
    registry = registry or default_registry()
    lines = ["GeoTrace Engine Plugin Registry", "==============================="]
    for plugin in registry.list():
        state = "enabled" if plugin.enabled else "optional/off"
        caps = ", ".join(plugin.capabilities) or "no declared capabilities"
        lines.append(f"- {plugin.name} [{plugin.family}] {plugin.version} — {state}; {caps}")
        if plugin.notes:
            lines.append(f"  note: {plugin.notes}")
    return "\n".join(lines).strip() + "\n"
