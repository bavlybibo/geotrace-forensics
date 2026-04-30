from __future__ import annotations

"""Digital-risk precision layer for hidden content triage.

This module converts noisy byte/pixel/OCR findings into a short product-style
decision: CLEAR / WATCH / REVIEW / ISOLATE. It intentionally separates:
- risk score: how dangerous the evidence looks;
- confidence score: how reliable the tool is about that decision;
- confirmation level: whether the result is confirmed, strong, medium, weak, or clean.

It does not execute payloads and it does not claim "malware confirmed" from
strings alone. It is an analyst triage layer that points to the exact danger zone.
"""

from pathlib import Path
from typing import Any, Iterable, Mapping
import re


DANGEROUS_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"<\s*script\b", "script tag"),
    (r"javascript\s*:", "javascript URI"),
    (r"\bonerror\s*=", "HTML event handler"),
    (r"\bonload\s*=", "HTML event handler"),
    (r"\beval\s*\(", "eval call"),
    (r"\bFunction\s*\(", "dynamic function constructor"),
    (r"\bpowershell\b", "PowerShell command marker"),
    (r"\bcmd(?:\.exe)?\b", "Windows command marker"),
    (r"\b(?:curl|wget)\s+", "download command marker"),
    (r"\b(?:token|password|passwd|api[_-]?key|secret|bearer)\b", "credential-like keyword"),
    (r"\b(?:base64|atob|fromCharCode)\b", "encoding/obfuscation keyword"),
    (r"flag\{|ctf\{|byuctf\{|umdctf\{", "CTF/hidden-message marker"),
)

ARCHIVE_OR_BINARY_MARKERS: tuple[tuple[str, str], ...] = (
    (r"\bPK\x03\x04\b|zip archive|embedded zip|carved.*zip", "embedded ZIP/archive marker"),
    (r"\bMZ\b|PE executable|portable executable|windows executable", "executable marker"),
    (r"\bELF\b|linux executable", "ELF executable marker"),
    (r"trailing data|appended payload|extra bytes after image end", "appended/trailing bytes"),
    (r"recoverable segment|carved payload", "recoverable/carved payload"),
)

VISIBLE_UI_HINTS = (
    "browser screenshot",
    "code editor",
    "terminal",
    "developer tools",
    "devtools",
    "visual text",
    "ocr line",
)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    return [value]


def _text_join(items: Iterable[Any], *, limit: int = 60) -> str:
    parts: list[str] = []
    for item in items:
        if isinstance(item, Mapping):
            parts.append(" ".join(str(v) for v in item.values()))
        else:
            parts.append(str(item))
        if len(parts) >= limit:
            break
    return "\n".join(parts)


def _dedupe(items: Iterable[str], *, limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = re.sub(r"\s+", " ", str(item or "")).strip(" \t\r\n\x00-•")
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= limit:
            break
    return out


def _pattern_hits(text: str, patterns: tuple[tuple[str, str], ...]) -> list[str]:
    hits: list[str] = []
    for pattern, label in patterns:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
                hits.append(label)
        except re.error:
            continue
    return _dedupe(hits, limit=10)


def _extract_pixel_metrics(pixel_profile: Any) -> dict[str, Any]:
    metrics = dict(getattr(pixel_profile, "metrics", {}) or {})
    channels = metrics.get("channels", {}) if isinstance(metrics.get("channels"), dict) else {}
    composite = metrics.get("composite_streams", {}) if isinstance(metrics.get("composite_streams"), dict) else {}
    high_entropy_channels = 0
    balanced_channels = 0
    readable_streams = 0
    random_streams = 0

    for channel_data in channels.values():
        if not isinstance(channel_data, Mapping):
            continue
        label = str(channel_data.get("label", "")).lower()
        entropy = float(channel_data.get("lsb_entropy", 0) or 0)
        compression = float(channel_data.get("lsb_compression_ratio", 0) or 0)
        pair = float(channel_data.get("even_odd_pair_balance", 1) or 1)
        if "random-like" in label or (entropy >= 7.80 and compression >= 0.94):
            high_entropy_channels += 1
        if pair <= 0.045:
            balanced_channels += 1

    for stream_data in composite.values():
        if not isinstance(stream_data, Mapping):
            continue
        if int(stream_data.get("readable_runs", 0) or 0) > 0:
            readable_streams += 1
        entropy = float(stream_data.get("entropy", 0) or 0)
        compression = float(stream_data.get("compression_ratio", 0) or 0)
        if entropy >= 7.75 and compression >= 0.94:
            random_streams += 1

    return {
        "high_entropy_channels": high_entropy_channels,
        "balanced_channels": balanced_channels,
        "readable_streams": readable_streams,
        "random_composite_streams": random_streams,
    }


def build_digital_risk_verdict(
    *,
    embedded_scan: Mapping[str, Any] | None,
    pixel_profile: Any,
    visible: Mapping[str, Any] | None = None,
    basic: Mapping[str, Any] | None = None,
    file_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create a concise, low-noise digital risk decision.

    Inputs are already-safe scan outputs; this function never reads remote URLs or
    executes anything. It focuses on clear "where is the danger?" answers.
    """

    embedded_scan = embedded_scan or {}
    visible = visible or {}
    basic = basic or {}

    embedded_strings = _as_list(embedded_scan.get("strings"))
    context_strings = _as_list(embedded_scan.get("context_strings"))
    code_indicators = _as_list(embedded_scan.get("code_indicators"))
    suspicious_embeds = _as_list(embedded_scan.get("suspicious_embeds"))
    payload_markers = _as_list(embedded_scan.get("payload_markers"))
    container_findings = _as_list(embedded_scan.get("container_findings"))
    recoverable_segments = _as_list(embedded_scan.get("recoverable_segments"))
    urls = _as_list(embedded_scan.get("urls"))

    lsb_strings = _as_list(getattr(pixel_profile, "lsb_strings", []))
    pixel_indicators = _as_list(getattr(pixel_profile, "indicators", []))
    alpha_findings = _as_list(getattr(pixel_profile, "alpha_findings", []))
    channel_notes = _as_list(getattr(pixel_profile, "channel_notes", []))
    pixel_score = int(getattr(pixel_profile, "score", 0) or 0)

    visible_lines = _as_list(visible.get("lines")) + _as_list(visible.get("ocr_map_labels"))
    visible_text = _text_join(visible_lines, limit=50)
    hidden_text = _text_join(
        [
            *embedded_strings,
            *context_strings,
            *code_indicators,
            *suspicious_embeds,
            *payload_markers,
            *container_findings,
            *urls,
            *lsb_strings,
        ],
        limit=120,
    )

    dangerous_hits = _pattern_hits(hidden_text, DANGEROUS_PATTERNS)
    visible_hits = _pattern_hits(visible_text, DANGEROUS_PATTERNS)
    binary_hits = _pattern_hits(hidden_text + "\n" + _text_join(container_findings) + "\n" + _text_join(suspicious_embeds), ARCHIVE_OR_BINARY_MARKERS)
    pixel_metrics = _extract_pixel_metrics(pixel_profile)

    danger_zones: list[str] = []
    evidence: list[str] = []
    false_positive_guards: list[str] = []
    next_actions: list[str] = []
    score = 0
    confidence = 35

    if dangerous_hits and code_indicators:
        score += 42
        confidence += 22
        danger_zones.append("embedded strings / code-like markers")
        evidence.append("Code/credential-like markers were recovered from embedded/container text, not only visible OCR.")
    elif dangerous_hits:
        score += 26
        confidence += 12
        danger_zones.append("embedded strings")
        evidence.append("High-value keywords or script-like markers were present in recovered strings.")

    if binary_hits or suspicious_embeds or payload_markers or recoverable_segments:
        score += 30
        confidence += 18
        danger_zones.append("container / appended payload area")
        evidence.append("Container-level payload markers, suspicious embeds, or recoverable segments were detected.")

    if lsb_strings:
        score += 34
        confidence += 18
        danger_zones.append("RGB/alpha low-bit planes")
        evidence.append("Readable text was recovered from LSB/composite pixel bitstreams.")
        if _pattern_hits(_text_join(lsb_strings), DANGEROUS_PATTERNS):
            score += 18
            confidence += 8
            evidence.append("The recovered low-bit text contains script/credential/CTF-style high-value markers.")

    if alpha_findings:
        score += 16
        confidence += 10
        danger_zones.append("alpha / transparent-pixel residue")
        evidence.append("Transparent or semi-transparent pixels retain suspicious RGB residue.")

    high_entropy_channels = int(pixel_metrics.get("high_entropy_channels", 0) or 0)
    random_streams = int(pixel_metrics.get("random_composite_streams", 0) or 0)
    if pixel_score >= 40 and not lsb_strings:
        score += 14
        confidence += 6
        danger_zones.append("low-bit statistical anomaly")
        evidence.append("Pixel forensics score is elevated, but no readable payload was decoded.")
    if high_entropy_channels >= 2 or random_streams >= 2:
        score += 8
        confidence += 4
        danger_zones.append("random-like low-bit planes")

    # Visible OCR suppression: code visible in a screenshot is useful context, but
    # it should not be treated as hidden/injected unless container or pixel evidence exists.
    visible_only = bool(visible_hits and not dangerous_hits and not code_indicators and not suspicious_embeds and not payload_markers and not lsb_strings)
    if visible_only:
        score = min(score, 24)
        confidence = max(confidence, 55)
        false_positive_guards.append("Script/code-like text appears in visible OCR only; not treated as hidden payload without container/pixel evidence.")
        danger_zones.append("visible OCR only")
        evidence.append("Visible OCR contains code-like text, but hidden/container evidence did not corroborate it.")

    suffix = Path(str(file_path)).suffix.lower() if file_path else ""
    fmt = str(basic.get("format_name", "") or suffix.replace(".", "").upper() or "Unknown")
    if suffix in {".jpg", ".jpeg"} and pixel_score >= 40 and not lsb_strings:
        false_positive_guards.append("JPEG low-bit noise can be compression artifact; require decoded text or container evidence before escalation.")
        confidence = max(20, confidence - 6)

    score = max(0, min(100, int(score)))
    confidence = max(0, min(100, int(confidence)))

    if score >= 72 and confidence >= 62:
        final_call = "ISOLATE"
        confirmation = "strong"
        one_line = "ISOLATE: strong hidden/container or low-bit payload evidence needs forensic handling."
    elif score >= 45:
        final_call = "REVIEW"
        confirmation = "medium" if confidence >= 55 else "weak"
        one_line = "REVIEW: suspicious digital indicators exist, but manual validation is still required."
    elif score >= 18:
        final_call = "WATCH"
        confirmation = "weak"
        one_line = "WATCH: weak signal only; keep as context unless corroborated."
    else:
        final_call = "CLEAR"
        confirmation = "clean"
        one_line = "CLEAR: no strong hidden payload, injection marker, or color-plane artifact detected."

    if final_call == "ISOLATE":
        next_actions.extend([
            "Do not open recovered payloads directly; preserve the original and analyze a copy.",
            "Export hashes, carved artifacts, and decoded strings into the evidence package.",
            "Validate with a specialist stego/container tool or sandbox before saying malware confirmed.",
        ])
    elif final_call == "REVIEW":
        next_actions.extend([
            "Inspect the listed danger zone first instead of reading the full narrative.",
            "Run targeted manual validation for carved payloads, LSB strings, or trailing bytes.",
            "Escalate only if the recovered artifact executes, decodes, or matches a known payload family.",
        ])
    elif final_call == "WATCH":
        next_actions.extend([
            "Keep the finding as a weak lead.",
            "Do not mark it dangerous unless another source confirms the same artifact.",
        ])
    else:
        next_actions.append("No digital-risk action needed beyond normal evidence preservation.")

    if dangerous_hits:
        evidence.append("Matched marker(s): " + ", ".join(dangerous_hits[:6]))
    if binary_hits:
        evidence.append("Container marker(s): " + ", ".join(binary_hits[:5]))
    if urls and final_call in {"REVIEW", "ISOLATE"}:
        evidence.append(f"{len(urls)} embedded URL/reference item(s) recovered from bytes.")
    if pixel_indicators and final_call in {"REVIEW", "ISOLATE"}:
        evidence.append("Pixel indicators: " + " | ".join(str(x) for x in pixel_indicators[:2]))

    if not danger_zones:
        danger_zones.append("none")

    execution_status = (
        "malware_not_confirmed_payload_present"
        if final_call == "ISOLATE"
        else "malware_not_confirmed_review_required"
        if final_call == "REVIEW"
        else "no_execution_evidence"
    )
    artifact_status = (
        "carved_or_decoded_artifact_present"
        if recoverable_segments or lsb_strings
        else "markers_without_recovered_artifact"
        if dangerous_hits or binary_hits or suspicious_embeds or payload_markers
        else "no_artifact_detected"
    )

    return {
        "final_call": final_call,
        "risk_score": score,
        "confidence_score": confidence,
        "confirmation_level": confirmation,
        "one_line": one_line,
        "danger_zones": _dedupe(danger_zones, limit=8),
        "evidence_brief": _dedupe(evidence, limit=8),
        "artifact_status": artifact_status,
        "execution_status": execution_status,
        "false_positive_guards": _dedupe(false_positive_guards, limit=6),
        "next_actions": _dedupe(next_actions, limit=6),
        "source_balance": {
            "embedded_code_indicators": len(code_indicators),
            "container_findings": len(container_findings),
            "payload_markers": len(payload_markers),
            "carvable_segments": len(recoverable_segments),
            "lsb_strings": len(lsb_strings),
            "alpha_findings": len(alpha_findings),
            "visible_ocr_hits": len(visible_hits),
            "format": fmt,
            **pixel_metrics,
        },
    }
