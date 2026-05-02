from __future__ import annotations

"""Deterministic local Image Threat AI.

The goal is to answer the analyst's practical question: *is this image dangerous
or just context/privacy-sensitive?*  The module intentionally separates
malicious/technical danger from privacy/location exposure and keeps visible OCR
from being over-escalated unless hidden/container evidence corroborates it.

v12.10.20 further calibrates this layer with production triage metadata:
- independent-sensor corroboration instead of one flat score;
- explicit threat family and decision lane for UI/reporting;
- weighted contributors so the analyst can see exactly why the score moved;
- stronger false-positive caps for map/GPS/visible-text-only images;
- evidence grade, review priority, risk temperature, missing-evidence notes,
  safe-handling profile, and export policy for UI/reporting.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping
import re


VISIBLE_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:api[_-]?key|secret|bearer|authorization|token|password|passwd|jwt|sessionid|cookie)\b", "visible credential keyword"),
    (r"AKIA[0-9A-Z]{16}", "AWS access-key shaped text"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "private-key block"),
    (r"\b(?:sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b", "API/chat-token shaped text"),
    (r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "JWT-shaped token"),
)

VISIBLE_CODE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"<\s*script\b", "visible script tag"),
    (r"javascript\s*:", "visible javascript URI"),
    (r"\bon(?:error|load|click)\s*=", "visible HTML event handler"),
    (r"\b(?:powershell|cmd(?:\.exe)?|curl|wget|bash|nc\s+-|python\s+-c)\b", "visible command/code text"),
    (r"\b(?:eval\s*\(|base64_decode\s*\(|atob\s*\(|document\.cookie|localStorage)\b", "visible exploit-code keyword"),
)

PRIVACY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b\+?\d[\d\s().-]{7,}\d\b", "phone-like visible text"),
    (r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "email address"),
    (r"\b(?:street|st\.|avenue|ave\.|road|rd\.|building|apartment|floor|flat|unit)\b", "address-like wording"),
    (r"\b\d{1,3}\.\d{3,},\s*-?\d{1,3}\.\d{3,}\b", "coordinate-like visible text"),
)

SENSITIVE_DOCUMENT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:passport|national\s+id|identity\s+card|driver'?s?\s+license|residence\s+permit)\b", "identity-document wording"),
    (r"\b(?:credit\s*card|debit\s*card|iban|swift|routing\s+number|bank\s+account)\b", "financial-document wording"),
    (r"\b(?:ssn|social\s+security|tax\s+id|national\s+number)\b", "government-id wording"),
    (r"\b(?:qr\s*code|barcode|2fa|mfa|otp|recovery\s+code)\b", "machine-readable or auth-code wording"),
)

HIDDEN_PAYLOAD_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"<\s*script\b|javascript\s*:|onerror\s*=|document\.cookie", "hidden browser payload marker"),
    (r"\b(?:powershell|cmd\.exe|bash|/bin/sh|curl|wget|nc\s+-|python\s+-c)\b", "hidden command/execution marker"),
    (r"\b(?:api[_-]?key|secret|bearer|authorization|token|password|passwd|jwt)\b", "hidden credential/secret marker"),
    (r"(?:eval\s*\(|base64_decode\s*\(|atob\s*\(|fromCharCode\s*\()", "hidden obfuscation/execution marker"),
    (r"MZ\x00|PK\x03\x04|ELF|%PDF-", "embedded file signature marker"),
)

SUSPICIOUS_URL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"https?://(?:\d{1,3}\.){3}\d{1,3}\b", "IP-address URL in recovered content"),
    (r"https?://[^\s/$.?#].*?(?:token|key|auth|callback|redirect|cmd|payload)=", "sensitive URL parameter"),
    (r"(?:pastebin|gist\.github|raw\.githubusercontent|discord(?:app)?\.com/api/webhooks|ngrok|trycloudflare|requestbin)", "high-risk external pivot URL"),
)


@dataclass(slots=True)
class WeightedSignal:
    name: str
    weight: int
    category: str
    confidence_delta: int = 0
    note: str = ""

    def to_text(self) -> str:
        suffix = f" — {self.note}" if self.note else ""
        sign = "+" if self.weight >= 0 else ""
        return f"{self.category}: {self.name} ({sign}{self.weight}){suffix}"


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


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _join(items: Iterable[Any], *, limit: int = 80) -> str:
    parts: list[str] = []
    for item in items:
        if isinstance(item, Mapping):
            parts.append(" ".join(str(v) for v in item.values()))
        else:
            parts.append(str(item))
        if len(parts) >= limit:
            break
    return "\n".join(parts)


def _hits(text: str, patterns: tuple[tuple[str, str], ...]) -> list[str]:
    out: list[str] = []
    for pattern, label in patterns:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
                out.append(label)
        except re.error:
            continue
    return _dedupe(out, limit=8)


def _segment_text(items: Iterable[Any], *, limit: int = 40) -> str:
    chunks: list[str] = []
    for item in list(items)[:limit]:
        if isinstance(item, Mapping):
            chunks.append(" ".join(str(v) for v in item.values()))
        else:
            chunks.append(str(item))
    return "\n".join(chunks)


@dataclass(slots=True)
class ImageThreatAssessment:
    label: str = "SAFE"  # SAFE / LOW / MEDIUM / HIGH / CRITICAL
    score: int = 0
    confidence: int = 45
    is_dangerous: bool = False
    summary: str = "SAFE: no technical danger indicators were detected."
    primary_reason: str = "No hidden/container/pixel payload evidence detected."
    danger_zones: list[str] = field(default_factory=list)
    evidence_matrix: list[str] = field(default_factory=list)
    false_positive_guards: list[str] = field(default_factory=list)
    privacy_findings: list[str] = field(default_factory=list)
    manipulation_findings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    decision_path: list[str] = field(default_factory=list)
    badge: str = "SAFE"
    threat_family: str = "clean"
    decision_lane: str = "benign_or_normal_preservation"
    technical_signal_count: int = 0
    contributor_matrix: list[str] = field(default_factory=list)
    analyst_verdict_hint: str = "No danger-handling escalation needed."
    evidence_grade: str = "D"
    review_priority: str = "P3"
    risk_temperature: str = "COOL"
    calibration_notes: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    safe_handling_profile: str = "normal_evidence_preservation"
    export_policy: str = "Shareable after standard case redaction."
    technical_threat: str = "Low"
    privacy_exposure: str = "Low"
    geo_sensitivity: str = "Low"
    manipulation_suspicion: str = "Low"
    geo_evidence_posture: str = "No location claim generated."
    risk_split_cards: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _label_from_score(score: int) -> str:
    if score >= 85:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 38:
        return "MEDIUM"
    if score >= 15:
        return "LOW"
    return "SAFE"


def _append_signal(
    signals: list[WeightedSignal],
    evidence: list[str],
    *,
    name: str,
    weight: int,
    category: str,
    confidence_delta: int = 0,
    note: str = "",
    evidence_line: str | None = None,
) -> None:
    sig = WeightedSignal(name=name, weight=weight, category=category, confidence_delta=confidence_delta, note=note)
    signals.append(sig)
    if evidence_line:
        evidence.append(evidence_line)


def assess_image_threat(
    *,
    embedded_scan: Mapping[str, Any] | None,
    pixel_profile: Any,
    visible: Mapping[str, Any] | None,
    basic: Mapping[str, Any] | None,
    digital_verdict: Mapping[str, Any] | None,
    image_profile: Any | None = None,
    map_intel: Any | None = None,
    context: Mapping[str, Any] | None = None,
) -> ImageThreatAssessment:
    """Return a direct image-danger decision with explainable evidence.

    The model is intentionally local/deterministic. It uses several independent
    sensors (digital-risk verdict, container scan, parser/signature state,
    low-bit pixel/stego scan, visible OCR, map/GPS context) and only labels an
    image as *dangerous* when strong technical evidence exists. Privacy-only or
    location-only evidence stays reviewable but not malicious.
    """

    embedded_scan = embedded_scan or {}
    visible = visible or {}
    basic = basic or {}
    digital_verdict = digital_verdict or {}
    context = context or {}

    score = 0
    confidence = 44
    zones: list[str] = []
    evidence: list[str] = []
    guards: list[str] = []
    privacy: list[str] = []
    manipulation: list[str] = []
    next_actions: list[str] = []
    path: list[str] = []
    signals: list[WeightedSignal] = []
    technical_sensors: set[str] = set()

    digital_call = str(digital_verdict.get("final_call", "CLEAR") or "CLEAR").upper()
    digital_score = int(digital_verdict.get("risk_score", 0) or 0)
    digital_conf = int(digital_verdict.get("confidence_score", 0) or 0)
    artifact_status = str(digital_verdict.get("artifact_status", "no_artifact_detected") or "")
    digital_zones = [str(x) for x in _as_list(digital_verdict.get("danger_zones"))]

    if digital_call == "ISOLATE":
        w = max(58, min(76, digital_score))
        score += w
        confidence += 22
        zones.extend(digital_zones or ["hidden/container payload area"])
        technical_sensors.add("digital-risk")
        _append_signal(
            signals,
            evidence,
            name="ISOLATE verdict from digital-risk engine",
            weight=w,
            category="technical",
            confidence_delta=22,
            note=f"engine confidence {digital_conf}%",
            evidence_line=f"Digital-risk engine returned ISOLATE with score {digital_score}% and confidence {digital_conf}%.",
        )
        path.append("digital_call=ISOLATE -> technical danger escalated")
    elif digital_call == "REVIEW":
        w = max(32, min(50, digital_score))
        score += w
        confidence += 13
        zones.extend(digital_zones or ["suspicious hidden-content signal"])
        technical_sensors.add("digital-risk")
        _append_signal(signals, evidence, name="REVIEW verdict from digital-risk engine", weight=w, category="technical", confidence_delta=13, note=f"engine score {digital_score}%", evidence_line=f"Digital-risk engine returned REVIEW with score {digital_score}%.")
        path.append("digital_call=REVIEW -> analyst validation required")
    elif digital_call == "WATCH":
        w = max(10, min(22, digital_score))
        score += w
        confidence += 4
        _append_signal(signals, evidence, name="WATCH weak digital-risk lead", weight=w, category="weak technical", confidence_delta=4, evidence_line="Digital-risk engine returned WATCH; weak signal retained without over-escalation.")
        path.append("digital_call=WATCH -> weak lead only")
    else:
        path.append("digital_call=CLEAR -> no hidden payload baseline")

    code_indicators = _as_list(embedded_scan.get("code_indicators"))
    suspicious_embeds = _as_list(embedded_scan.get("suspicious_embeds"))
    payload_markers = _as_list(embedded_scan.get("payload_markers"))
    container_findings = _as_list(embedded_scan.get("container_findings"))
    recoverable_segments = _as_list(embedded_scan.get("recoverable_segments"))
    urls = _as_list(embedded_scan.get("urls"))
    context_strings = _as_list(embedded_scan.get("context_strings"))
    hidden_text = _segment_text([*code_indicators, *payload_markers, *container_findings, *recoverable_segments, *context_strings, *urls])
    hidden_payload_hits = _hits(hidden_text, HIDDEN_PAYLOAD_PATTERNS)
    hidden_url_hits = _hits("\n".join(str(x) for x in urls), SUSPICIOUS_URL_PATTERNS)

    if recoverable_segments:
        score += 28
        confidence += 12
        zones.append("carved/recoverable payload segment")
        technical_sensors.add("container-carving")
        _append_signal(signals, evidence, name="recoverable hidden segment", weight=28, category="technical", confidence_delta=12, note=f"segments={len(recoverable_segments)}", evidence_line=f"{len(recoverable_segments)} recoverable payload segment(s) were reported by the container scanner.")
    if code_indicators or hidden_payload_hits:
        weight = 24 if hidden_payload_hits else 20
        score += weight
        confidence += 9
        zones.append("embedded code/credential markers")
        technical_sensors.add("container-content")
        detail = ", ".join(hidden_payload_hits[:3]) or "code-like recovered content"
        _append_signal(signals, evidence, name="embedded code/credential marker", weight=weight, category="technical", confidence_delta=9, note=detail, evidence_line="Embedded code-like, credential-like, or executable indicators were recovered from the file container.")
    if suspicious_embeds or payload_markers or container_findings:
        weight = 18
        score += weight
        confidence += 7
        zones.append("container structure / appended-data area")
        technical_sensors.add("container-structure")
        _append_signal(signals, evidence, name="structural hidden-content warning", weight=weight, category="technical", confidence_delta=7, note="trailing bytes / encoded blobs / suspicious embeds", evidence_line="Structural hidden-content warnings exist: trailing bytes, encoded blobs, payload markers, or suspicious embeds.")
    if hidden_url_hits:
        score += 12
        confidence += 4
        zones.append("recovered hidden URL/reference")
        technical_sensors.add("hidden-url")
        _append_signal(signals, evidence, name="suspicious URL recovered from hidden content", weight=12, category="technical", confidence_delta=4, note="; ".join(hidden_url_hits[:3]), evidence_line=f"{len(hidden_url_hits)} suspicious URL pattern(s) were recovered from hidden/container content.")

    lsb_strings = _as_list(getattr(pixel_profile, "lsb_strings", []))
    alpha_findings = _as_list(getattr(pixel_profile, "alpha_findings", []))
    pixel_score = int(getattr(pixel_profile, "score", 0) or 0)
    pixel_indicators = _as_list(getattr(pixel_profile, "indicators", []))
    lsb_hits = _hits(_segment_text(lsb_strings), HIDDEN_PAYLOAD_PATTERNS)
    if lsb_strings:
        weight = 30 if lsb_hits else 24
        score += weight
        confidence += 12
        zones.append("RGB/alpha low-bit planes")
        technical_sensors.add("pixel-lsb")
        _append_signal(signals, evidence, name="decoded low-bit pixel text", weight=weight, category="technical", confidence_delta=12, note=", ".join(lsb_hits[:3]) or "readable strings", evidence_line="Readable strings were recovered from low-bit pixel streams.")
    elif pixel_score >= 70:
        score += 14
        confidence += 4
        zones.append("high pixel/stego statistical anomaly")
        technical_sensors.add("pixel-statistics")
        _append_signal(signals, evidence, name="high pixel/stego statistical anomaly", weight=14, category="weak technical", confidence_delta=4, note=f"pixel score {pixel_score}%", evidence_line=f"Pixel hidden-content score is high ({pixel_score}%), but no decoded payload text was confirmed.")
    elif pixel_score >= 40:
        score += 8
        zones.append("weak pixel/stego anomaly")
        guards.append("Pixel entropy without decoded text is treated as a weak lead, especially for JPEG/compressed images.")
        _append_signal(signals, evidence, name="weak pixel/stego anomaly", weight=8, category="weak technical", note=f"pixel score {pixel_score}%")
    if alpha_findings:
        score += 10
        confidence += 4
        zones.append("transparent/alpha-channel residue")
        technical_sensors.add("alpha-channel")
        _append_signal(signals, evidence, name="alpha-channel residue", weight=10, category="technical", confidence_delta=4, note=f"findings={len(alpha_findings)}", evidence_line="Transparent or alpha-channel RGB residue may contain hidden visual/pixel data.")

    visible_text = _join([
        *_as_list(visible.get("lines")),
        *_as_list(visible.get("ocr_map_labels")),
        *_as_list(visible.get("visible_urls")),
        str(visible.get("raw_text", "")),
    ])
    visible_secret_hits = _hits(visible_text, VISIBLE_SECRET_PATTERNS)
    visible_code_hits = _hits(visible_text, VISIBLE_CODE_PATTERNS)
    visible_privacy_hits = _hits(visible_text, PRIVACY_PATTERNS)
    sensitive_doc_hits = _hits(visible_text, SENSITIVE_DOCUMENT_PATTERNS)

    hidden_or_structural = bool(code_indicators or suspicious_embeds or payload_markers or container_findings or recoverable_segments or lsb_strings or digital_call in {"ISOLATE", "REVIEW"})
    if visible_secret_hits:
        w = 18 if hidden_or_structural else 10
        score += w
        confidence += 5
        zones.append("visible sensitive text")
        privacy.extend(visible_secret_hits)
        _append_signal(signals, evidence, name="visible credential/secret-like text", weight=w, category="privacy", confidence_delta=5, note=", ".join(visible_secret_hits[:3]), evidence_line="Visible OCR contains credential-like or secret-like text; review before sharing/export.")
        if not hidden_or_structural:
            guards.append("Visible secret-like OCR is a privacy/exposure concern, not proof of hidden malware.")
    if visible_code_hits:
        w = 8 if hidden_or_structural else 3
        score += w
        zones.append("visible code/shell text")
        _append_signal(signals, evidence, name="visible code/command text", weight=w, category="visible content", note=", ".join(visible_code_hits[:3]), evidence_line="Visible OCR contains code/command-like text.")
        if not hidden_or_structural:
            guards.append("Visible code in a screenshot is not treated as an injected payload unless container/pixel evidence corroborates it.")
    if visible_privacy_hits:
        score += 6
        privacy.extend(visible_privacy_hits)
        _append_signal(signals, evidence, name="visible personal/location data", weight=6, category="privacy", note=", ".join(visible_privacy_hits[:3]), evidence_line="Visible OCR may expose personal/contact/location data.")
    if sensitive_doc_hits:
        score += 9
        privacy.extend(sensitive_doc_hits)
        zones.append("visible sensitive-document/auth-code area")
        _append_signal(
            signals,
            evidence,
            name="visible sensitive document/auth-code clue",
            weight=9,
            category="privacy",
            note=", ".join(sensitive_doc_hits[:3]),
            evidence_line="Visible OCR suggests identity, financial, QR/barcode, or auth-code material; redact and restrict sharing.",
        )
        guards.append("Sensitive visible documents/codes are handled as exposure risk, not malware, unless hidden technical evidence also exists.")

    parser_status = str(basic.get("parser_status", "Valid") or "Valid")
    signature_status = str(basic.get("signature_status", "Unknown") or "Unknown")
    format_trust = str(basic.get("format_trust", "Unverified") or "Unverified")
    if parser_status != "Valid":
        score += 20
        confidence += 8
        zones.append("decoder/parser failure")
        manipulation.append("parser did not fully validate the media")
        technical_sensors.add("parser")
        _append_signal(signals, evidence, name="decoder/parser failure", weight=20, category="authenticity", confidence_delta=8, note=parser_status, evidence_line="The media parser could not fully validate this file, so the container should be handled cautiously.")
    if signature_status == "Mismatch":
        score += 24
        confidence += 10
        zones.append("file signature mismatch")
        manipulation.append("extension and binary signature disagree")
        technical_sensors.add("signature")
        _append_signal(signals, evidence, name="file signature mismatch", weight=24, category="authenticity", confidence_delta=10, evidence_line="File extension/signature mismatch can indicate masquerading or container manipulation.")
    elif format_trust in {"Weak", "Header-only"}:
        score += 6
        manipulation.append(f"format trust is {format_trust}")
        _append_signal(signals, evidence, name="weak format trust", weight=6, category="authenticity", note=format_trust)

    if bool(context.get("has_gps")):
        privacy.append("native GPS coordinates present")
        score += 7
        _append_signal(signals, evidence, name="native GPS coordinates", weight=7, category="privacy", note=str(context.get("gps_display", "")), evidence_line="Native GPS exists; this is privacy-sensitive during export even if the image is not malicious.")
    if getattr(map_intel, "detected", False) or int(getattr(map_intel, "confidence", 0) or 0) >= 55:
        privacy.append("map/navigation screenshot context")
        score += 5
        _append_signal(signals, evidence, name="map/navigation context", weight=5, category="privacy", note=f"confidence={getattr(map_intel, 'confidence', 0)}")
        if getattr(map_intel, "route_overlay_detected", False):
            privacy.append("route overlay / movement path visible")
            score += 4
            _append_signal(signals, evidence, name="route overlay visible", weight=4, category="privacy", note="movement path may be exposed")

    quality_flags = [str(x) for x in _as_list(getattr(image_profile, "quality_flags", []))]
    object_hints = [str(x) for x in _as_list(getattr(image_profile, "object_hints", []))]
    detail_metrics = dict(getattr(image_profile, "metrics", {}) or {}) if image_profile is not None else {}
    barcode_scan = dict(detail_metrics.get("barcode_scan", {}) or {})
    barcode_findings = list(barcode_scan.get("findings", []) or [])
    if barcode_findings or any(("qr" in hint.lower() or "barcode" in hint.lower() or "machine-readable" in hint.lower()) for hint in object_hints):
        score += 8
        privacy.append("machine-readable QR/barcode content present")
        zones.append("QR/barcode region")
        _append_signal(
            signals,
            evidence,
            name="machine-readable QR/barcode detected",
            weight=8,
            category="privacy",
            confidence_delta=4,
            note=f"items={len(barcode_findings)}",
            evidence_line="A QR/barcode detector or object-hint layer found machine-readable content; redact/review payloads before export.",
        )
        guards.append("QR/barcode content is treated as privacy/exposure evidence unless hidden payload or executable content corroborates technical danger.")
    hidden_priority = int(detail_metrics.get("hidden_content_priority_score", 0) or 0)
    if hidden_priority >= 55 and not hidden_or_structural:
        score += 5
        guards.append("Image-detail hidden-content priority is only a review hint until byte/pixel scanners corroborate it.")
        _append_signal(signals, evidence, name="image-detail hidden-content review hint", weight=5, category="weak technical", note=f"priority={hidden_priority}")
    for flag in quality_flags[:4]:
        lowered = flag.lower()
        if any(term in lowered for term in ("very dark", "blur", "low resolution", "occlusion")):
            guards.append("Image quality may reduce OCR/vision confidence: " + flag)
            confidence = max(25, confidence - 3)
        elif any(term in lowered for term in ("alpha", "transparent", "hidden")):
            zones.append("image quality/alpha review area")

    if urls and hidden_or_structural:
        evidence.append(f"{len(urls)} URL/reference item(s) were recovered from hidden/container scanning.")
    if pixel_indicators and hidden_or_structural:
        evidence.append("Pixel indicators: " + " | ".join(str(x) for x in pixel_indicators[:2]))

    # Sensor fusion: a single weak anomaly should rarely become dangerous. Multiple
    # independent technical sensors strengthen confidence and severity.
    sensor_count = len(technical_sensors)
    if sensor_count >= 3:
        score += 10
        confidence += 8
        path.append(f"sensor_fusion={sensor_count} independent technical sensors -> confidence boost")
        _append_signal(signals, evidence, name="multi-sensor corroboration", weight=10, category="fusion", confidence_delta=8, note=f"sensors={', '.join(sorted(technical_sensors))}")
    elif sensor_count == 2:
        score += 5
        confidence += 4
        path.append("sensor_fusion=2 independent technical sensors -> moderate boost")
        _append_signal(signals, evidence, name="two-sensor corroboration", weight=5, category="fusion", confidence_delta=4, note=f"sensors={', '.join(sorted(technical_sensors))}")

    technical_signal = bool(
        hidden_or_structural
        or parser_status != "Valid"
        or signature_status == "Mismatch"
        or lsb_strings
        or recoverable_segments
        or pixel_score >= 70
        or hidden_payload_hits
        or hidden_url_hits
    )
    strong_payload_signal = bool(
        digital_call == "ISOLATE"
        or recoverable_segments
        or hidden_payload_hits
        or (lsb_strings and lsb_hits)
        or (code_indicators and (suspicious_embeds or payload_markers or container_findings))
    )

    # Avoid saying a location/privacy image is technically dangerous when there is
    # no hidden payload, parser anomaly, or executable/container evidence.
    if not technical_signal and score > 32:
        score = 32
        guards.append("Score capped: only privacy/visible-content signals were present, not technical payload evidence.")
        path.append("false_positive_cap=privacy_visible_only -> max MEDIUM review")
    elif technical_signal and not strong_payload_signal and score > 64 and sensor_count <= 1:
        score = 64
        guards.append("Score capped below HIGH: one technical anomaly needs corroboration before dangerous classification.")
        path.append("false_positive_cap=single_technical_sensor -> max MEDIUM review")

    critical_cap_applied = False
    confidence_cap_applied = False
    score = max(0, min(100, int(score)))
    confidence = max(0, min(100, int(confidence)))

    # v12.10.24 calibration: CRITICAL/100 must be rare and corroborated.
    # A single ISOLATE or parser anomaly can be serious, but it should not become
    # CRITICAL 100% without independent payload/container/pixel corroboration.
    critical_ready = bool(score >= 92 and sensor_count >= 3 and strong_payload_signal)
    if score >= 85 and not critical_ready:
        score = 84
        critical_cap_applied = True
        guards.append("CRITICAL blocked: needs score >=92 plus at least three independent technical sensors and a strong payload signal.")
        path.append("critical_cap=not_enough_independent_corrob -> max HIGH")
    max_confidence = 96 if critical_ready and (recoverable_segments or hidden_payload_hits or lsb_strings) else 94
    if privacy and not technical_signal:
        max_confidence = min(max_confidence, 82)
    elif technical_signal and sensor_count <= 1:
        max_confidence = min(max_confidence, 88)
    elif technical_signal and sensor_count == 2:
        max_confidence = min(max_confidence, 92)
    if confidence > max_confidence:
        confidence = max_confidence
        confidence_cap_applied = True
        path.append(f"confidence_cap={max_confidence}%")

    label = _label_from_score(score)
    if label == "SAFE" and privacy:
        # Privacy/location-only evidence should be visible to the analyst without
        # becoming a malicious-image verdict.
        label = "LOW"
        score = max(score, 15)
        path.append("privacy_floor=visible/location data -> LOW non-danger review")
    is_dangerous = bool(label in {"HIGH", "CRITICAL"} and technical_signal and (strong_payload_signal or sensor_count >= 2))
    if label in {"HIGH", "CRITICAL"} and not is_dangerous:
        label = "MEDIUM"
        is_dangerous = False

    if is_dangerous:
        if recoverable_segments or hidden_payload_hits:
            threat_family = "hidden_payload_or_embedded_artifact"
        elif lsb_strings:
            threat_family = "steganographic_payload"
        elif signature_status == "Mismatch":
            threat_family = "masqueraded_or_tampered_media"
        else:
            threat_family = "technical_payload_risk"
        decision_lane = "isolate_and_validate"
        primary = evidence[0] if evidence else "Strong technical image-risk indicators were detected."
        summary = f"{label}: dangerous technical image indicators detected — isolate and validate before opening recovered artifacts."
        badge = "DANGEROUS"
        analyst_hint = "Treat as dangerous until the recovered artifact/payload is manually validated in a safe lab."
        next_actions.extend([
            "Keep the original isolated; analyze only a working copy.",
            "Review the first danger zone before reading the full narrative.",
            "Export hashes, scanner evidence, and any carved artifacts for manual validation.",
            "Never execute recovered content on the analyst workstation.",
        ])
    elif label == "MEDIUM":
        if technical_signal:
            threat_family = "technical_review_needed"
            decision_lane = "controlled_manual_review"
        elif privacy:
            threat_family = "privacy_or_location_exposure"
            decision_lane = "redact_before_share"
        else:
            threat_family = "contextual_review_needed"
            decision_lane = "manual_triage"
        primary = evidence[0] if evidence else "Mixed technical/privacy signals require analyst review."
        summary = "MEDIUM: review required, but the image is not confirmed dangerous from current evidence."
        badge = "REVIEW"
        analyst_hint = "Do not call it malicious yet; validate the listed zone or redact sensitive data depending on the lane."
        next_actions.extend([
            "Manually verify the listed danger/privacy zones.",
            "Do not mark as malicious unless a payload is decoded, carved, or executed in a safe lab.",
        ])
    elif label == "LOW":
        threat_family = "privacy_or_weak_context_signal" if privacy else "weak_technical_lead"
        decision_lane = "normal_preservation_with_redaction" if privacy else "normal_preservation"
        primary = privacy[0] if privacy else evidence[0] if evidence else "Weak contextual signals only."
        summary = "LOW: weak or privacy-only signal; not dangerous unless corroborated."
        badge = "LOW RISK"
        analyst_hint = "Safe for normal preservation; redact visible/private clues before sharing."
        next_actions.append("Preserve normally and redact sensitive visible/location data before sharing.")
    else:
        threat_family = "clean"
        decision_lane = "benign_or_normal_preservation"
        primary = "No hidden payload, parser mismatch, or strong pixel-stego indicator was detected."
        summary = "SAFE: no current evidence that the image is dangerous."
        badge = "SAFE"
        analyst_hint = "No danger-handling escalation needed beyond normal evidence preservation."
        next_actions.append("No extra danger-handling step needed beyond normal evidence preservation.")

    contributor_matrix = _dedupe([s.to_text() for s in sorted(signals, key=lambda item: abs(item.weight), reverse=True)], limit=12)
    if contributor_matrix:
        path.append("top_contributors=" + " | ".join(contributor_matrix[:3]))

    privacy_only = bool(privacy and not technical_signal)
    if is_dangerous and sensor_count >= 3 and confidence >= 75:
        evidence_grade = "A"
        review_priority = "P0"
        risk_temperature = "HOT"
        safe_handling_profile = "isolated_lab_only"
        export_policy = "Do not share raw artifact; export hashes, redacted report, and carved-artifact notes only."
    elif is_dangerous:
        evidence_grade = "B"
        review_priority = "P0"
        risk_temperature = "HOT"
        safe_handling_profile = "isolated_lab_only"
        export_policy = "Quarantine original and share only a redacted technical appendix until manual validation completes."
    elif technical_signal and label == "MEDIUM":
        evidence_grade = "C"
        review_priority = "P1"
        risk_temperature = "WARM"
        safe_handling_profile = "controlled_manual_review"
        export_policy = "Share redacted report; do not attach raw media outside the case workspace until the weak technical lead is resolved."
    elif privacy_only:
        evidence_grade = "P"
        review_priority = "P2"
        risk_temperature = "WARM"
        safe_handling_profile = "normal_preservation_with_privacy_redaction"
        export_policy = "Shareable only after location, identity, contact, credential, QR/barcode, and document clues are redacted."
    elif label == "LOW":
        evidence_grade = "D"
        review_priority = "P3"
        risk_temperature = "COOL"
        safe_handling_profile = "normal_preservation"
        export_policy = "Shareable after standard redaction and analyst spot-check."
    else:
        evidence_grade = "D"
        review_priority = "P3"
        risk_temperature = "COOL"
        safe_handling_profile = "normal_evidence_preservation"
        export_policy = "Shareable after standard case redaction."

    if is_dangerous and label == "CRITICAL":
        technical_threat = "Critical"
    elif is_dangerous or label == "HIGH":
        technical_threat = "High"
    elif technical_signal or label == "MEDIUM":
        technical_threat = "Medium"
    else:
        technical_threat = "Low"

    if len(privacy) >= 3 or any("native GPS" in item for item in privacy):
        privacy_exposure = "High"
    elif privacy:
        privacy_exposure = "Medium"
    else:
        privacy_exposure = "Low"

    has_geo_context = bool(context.get("has_gps") or context.get("gps_display") or getattr(map_intel, "detected", False) or int(getattr(map_intel, "confidence", 0) or 0) >= 55)
    if context.get("has_gps"):
        geo_sensitivity = "High"
    elif has_geo_context or any("coordinate" in item.lower() or "location" in item.lower() for item in privacy):
        geo_sensitivity = "Medium"
    else:
        geo_sensitivity = "Low"

    if context.get("has_gps"):
        geo_evidence_posture = "Native GPS exposure: privacy-sensitive metadata, not a malware indicator."
    elif getattr(map_intel, "detected", False) or int(getattr(map_intel, "confidence", 0) or 0) >= 55:
        geo_evidence_posture = "Map/route screenshot exposure: derived context only unless coordinates or source URL corroborate it."
    elif any("coordinate" in item.lower() or "location" in item.lower() for item in privacy):
        geo_evidence_posture = "Visible coordinate/location text: redact before sharing; not native GPS by itself."
    else:
        geo_evidence_posture = "No meaningful location exposure was detected."


    if signature_status == "Mismatch" or parser_status != "Valid":
        manipulation_suspicion = "High"
    elif manipulation or pixel_score >= 70 or hidden_or_structural:
        manipulation_suspicion = "Medium"
    else:
        manipulation_suspicion = "Low"


    risk_split_cards = [
        {"dimension": "Technical payload", "level": technical_threat, "basis": f"{sensor_count} technical sensor(s); strong_payload={str(strong_payload_signal).lower()}"},
        {"dimension": "Privacy exposure", "level": privacy_exposure, "basis": ", ".join(_dedupe(privacy, limit=3)) or "no visible private data"},
        {"dimension": "Geo sensitivity", "level": geo_sensitivity, "basis": geo_evidence_posture},
        {"dimension": "Manipulation suspicion", "level": manipulation_suspicion, "basis": ", ".join(_dedupe(manipulation, limit=3)) or "parser/signature did not add suspicion"},
    ]
    calibration_notes = [
        f"sensor_count={sensor_count}",
        f"strong_payload_signal={str(strong_payload_signal).lower()}",
        f"technical_signal={str(technical_signal).lower()}",
        f"privacy_only={str(privacy_only).lower()}",
        f"score={score}% confidence={confidence}%",
        f"technical_threat={technical_threat}",
        f"privacy_exposure={privacy_exposure}",
        f"geo_sensitivity={geo_sensitivity}",
        f"manipulation_suspicion={manipulation_suspicion}",
        f"geo_evidence_posture={geo_evidence_posture}",
    ]
    if critical_cap_applied:
        calibration_notes.append("critical cap applied")
    if confidence_cap_applied:
        calibration_notes.append("confidence cap applied")
    if any("false_positive_cap" in item for item in path):
        calibration_notes.append("false-positive cap applied")
    if visible_code_hits and not hidden_or_structural:
        calibration_notes.append("visible code screenshot kept below technical-danger threshold")
    if sensitive_doc_hits:
        calibration_notes.append("sensitive document/auth-code clue treated as privacy exposure")

    missing_evidence: list[str] = []
    if technical_signal and not recoverable_segments:
        missing_evidence.append("No carved/recoverable artifact has been confirmed yet.")
    if technical_signal and not lsb_strings and pixel_score >= 40:
        missing_evidence.append("Pixel anomaly exists but no decoded low-bit string was confirmed.")
    if technical_signal and sensor_count <= 1:
        missing_evidence.append("Only one technical sensor is active; corroborate with container, pixel, parser, or manual artifact review.")
    if privacy_only:
        missing_evidence.append("No hidden/container/pixel payload corroborates danger; current risk is exposure/redaction.")
    if not visible_text.strip():
        missing_evidence.append("No OCR text was available; run crop OCR/manual review for text-heavy screenshots.")
    if not evidence:
        missing_evidence.append("No direct image-threat evidence line was generated.")

    return ImageThreatAssessment(
        label=label,
        score=score,
        confidence=confidence,
        is_dangerous=is_dangerous,
        summary=summary,
        primary_reason=primary,
        danger_zones=_dedupe(zones or ["none"], limit=10),
        evidence_matrix=_dedupe(evidence, limit=10),
        false_positive_guards=_dedupe(guards, limit=8),
        privacy_findings=_dedupe(privacy, limit=8),
        manipulation_findings=_dedupe(manipulation, limit=8),
        next_actions=_dedupe(next_actions, limit=8),
        decision_path=_dedupe(path, limit=10),
        badge=badge,
        threat_family=threat_family,
        decision_lane=decision_lane,
        technical_signal_count=sensor_count,
        contributor_matrix=contributor_matrix,
        analyst_verdict_hint=analyst_hint,
        evidence_grade=evidence_grade,
        review_priority=review_priority,
        risk_temperature=risk_temperature,
        calibration_notes=_dedupe(calibration_notes, limit=14),
        missing_evidence=_dedupe(missing_evidence, limit=8),
        safe_handling_profile=safe_handling_profile,
        export_policy=export_policy,
        technical_threat=technical_threat,
        privacy_exposure=privacy_exposure,
        geo_sensitivity=geo_sensitivity,
        manipulation_suspicion=manipulation_suspicion,
        geo_evidence_posture=geo_evidence_posture,
        risk_split_cards=risk_split_cards,
    )
