from __future__ import annotations

"""Offline local LLM command adapter.

A real LLM can be connected without changing UI code by setting
GEOTRACE_LOCAL_LLM_COMMAND.  The command receives a compact JSON request on
stdin and must print a JSON object containing summary/actions/caveats/confidence.
Remote APIs are intentionally not supported here.
"""

from dataclasses import asdict, dataclass, field
import json
import os
import shlex
import subprocess
from typing import Any

from .contracts import AgentRequest, AgentResponse


@dataclass(slots=True)
class LocalLLMRunResult:
    executed: bool = False
    response: AgentResponse | None = None
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.response is not None:
            data["response"] = {
                "summary": self.response.summary,
                "recommended_actions": self.response.recommended_actions,
                "caveats": self.response.caveats,
                "confidence": self.response.confidence,
                "provider": self.response.provider,
            }
        return data


def _safe_int(value: Any, default: int = 12) -> int:
    try:
        return max(1, min(90, int(value)))
    except Exception:
        return default


def _clean_list(value: Any, limit: int = 8) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value[:limit]:
        clean = " ".join(str(item or "").split()).strip()
        if clean:
            out.append(clean[:500])
    return out


def _compact_record(record: Any) -> dict[str, Any]:
    """Evidence-only prompt payload: no image bytes, no full raw OCR dump."""
    return {
        "evidence_id": getattr(record, "evidence_id", ""),
        "file_name": getattr(record, "file_name", ""),
        "source_type": getattr(record, "source_type", ""),
        "parser_status": getattr(record, "parser_status", ""),
        "risk_level": getattr(record, "risk_level", ""),
        "confidence_score": getattr(record, "confidence_score", 0),
        "timestamp": getattr(record, "timestamp", ""),
        "timestamp_source": getattr(record, "timestamp_source", ""),
        "gps": {
            "has_gps": bool(getattr(record, "has_gps", False)),
            "display": getattr(record, "gps_display", ""),
            "confidence": getattr(record, "gps_confidence", 0),
        },
        "derived_geo": {
            "display": getattr(record, "derived_geo_display", ""),
            "source": getattr(record, "derived_geo_source", ""),
            "confidence": getattr(record, "derived_geo_confidence", 0),
        },
        "map": {
            "app": getattr(record, "map_app_detected", ""),
            "type": getattr(record, "map_type", ""),
            "confidence": getattr(record, "map_intelligence_confidence", 0),
            "basis": list(getattr(record, "map_evidence_basis", []) or [])[:8],
            "limitations": list(getattr(record, "map_limitations", []) or [])[:6],
        },
        "ocr": {
            "confidence": getattr(record, "ocr_confidence", 0),
            "map_labels": list(getattr(record, "ocr_map_labels", []) or [])[:10],
            "locations": list(getattr(record, "ocr_location_entities", []) or [])[:10],
            "urls": list(getattr(record, "ocr_url_entities", []) or [])[:6],
            "excerpt": str(getattr(record, "visible_text_excerpt", ""))[:1200],
        },
        "image": {
            "label": getattr(record, "image_detail_label", ""),
            "confidence": getattr(record, "image_detail_confidence", 0),
            "cues": list(getattr(record, "image_detail_cues", []) or [])[:8],
            "objects": list(getattr(record, "image_object_hints", []) or [])[:8],
            "quality": list(getattr(record, "image_quality_flags", []) or [])[:8],
            "metrics": dict(getattr(record, "image_detail_metrics", {}) or {}),
        },
        "hidden_content": {
            "indicators": list(getattr(record, "hidden_code_indicators", []) or [])[:8],
            "pixel_score": getattr(record, "pixel_hidden_score", 0),
            "pixel_verdict": getattr(record, "pixel_hidden_verdict", ""),
        },
        "existing_ai": {
            "flags": list(getattr(record, "ai_flags", []) or [])[:8],
            "summary": getattr(record, "ai_summary", ""),
            "matrix": list(getattr(record, "ai_corroboration_matrix", []) or [])[:8],
        },
    }


def build_local_llm_payload(request: AgentRequest) -> dict[str, Any]:
    peers = list(request.case_records or [])
    return {
        "task": "Return conservative forensic triage. Use only supplied evidence. Never invent locations, identities, or timestamps.",
        "case": {"case_id": request.case_id, "case_name": request.case_name, "record_count": len(peers)},
        "selected_record": _compact_record(request.selected_record),
        "case_context": {
            "gps_count": sum(1 for r in peers if getattr(r, "has_gps", False)),
            "derived_geo_count": sum(1 for r in peers if getattr(r, "derived_geo_display", "Unavailable") != "Unavailable"),
            "high_risk_count": sum(1 for r in peers if getattr(r, "risk_level", "") == "High"),
            "ai_flagged_count": sum(1 for r in peers if getattr(r, "ai_flags", [])),
        },
        "analyst_context": str(request.analyst_context or "")[:1000],
        "required_json_schema": {
            "summary": "string <= 700 chars",
            "recommended_actions": "list of strings",
            "caveats": "list of strings",
            "confidence": "integer 0..100",
        },
    }


def run_local_llm_command(request: AgentRequest) -> LocalLLMRunResult:
    command = os.environ.get("GEOTRACE_LOCAL_LLM_COMMAND", "").strip()
    if not command:
        return LocalLLMRunResult(False, warnings=["GEOTRACE_LOCAL_LLM_COMMAND is not configured; using deterministic agent."])

    payload = build_local_llm_payload(request)
    timeout = _safe_int(os.environ.get("GEOTRACE_LOCAL_LLM_TIMEOUT", "12"), 12)
    try:
        completed = subprocess.run(
            shlex.split(command),
            input=json.dumps(payload, ensure_ascii=False),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return LocalLLMRunResult(False, warnings=[f"Local LLM command timed out after {timeout}s."])
    except Exception as exc:
        return LocalLLMRunResult(False, warnings=[f"Local LLM command could not start: {exc}"])

    if completed.returncode != 0:
        return LocalLLMRunResult(
            False,
            warnings=[f"Local LLM exited with code {completed.returncode}.", (completed.stderr or "")[:500]],
        )

    try:
        data = json.loads((completed.stdout or "")[:200_000])
    except Exception as exc:
        return LocalLLMRunResult(True, warnings=[f"Local LLM output was not valid JSON: {exc}"])
    if not isinstance(data, dict):
        return LocalLLMRunResult(True, warnings=["Local LLM JSON must be an object."])

    summary = " ".join(str(data.get("summary") or "").split())[:700]
    actions = _clean_list(data.get("recommended_actions") or data.get("actions"), 8)
    caveats = _clean_list(data.get("caveats") or data.get("limitations"), 8)
    confidence = _safe_int(data.get("confidence", 45), 45)
    if not summary:
        return LocalLLMRunResult(True, warnings=["Local LLM returned no summary; deterministic fallback kept."])
    if not caveats:
        caveats = ["Local LLM output is advisory; final claims must remain tied to evidence rows."]
    caveats.append("Schema-guarded local LLM output; no remote provider was used by GeoTrace.")
    response = AgentResponse(
        summary=summary,
        recommended_actions=actions or ["Validate the model summary against claim-to-evidence rows before reporting."],
        caveats=caveats[:8],
        confidence=max(0, min(100, confidence)),
        provider=str(data.get("provider") or "local-llm-command")[:80],
    )
    return LocalLLMRunResult(True, response=response, raw={k: v for k, v in data.items() if k != "prompt"})
