from __future__ import annotations

"""Pixel-level hidden-content and low-bit-plane heuristics.

The detector is intentionally offline, deterministic, and explainable. It does
**not** claim that a clean result proves the absence of steganography; it only
surfaces analyst-friendly signals such as readable LSB text, suspicious
transparent-pixel color data, unusual low-bit statistics, composite RGB/BGR bit
streams, and alpha-channel anomalies.
"""

from dataclasses import dataclass, field
from math import log2
from pathlib import Path
import re
import zlib
from typing import Any, Iterable, Sequence

from PIL import Image, ImageStat


_PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{8,}")
_HIGH_VALUE_CONTEXT_RE = re.compile(
    r"(flag\{|ctf\{|byuctf\{|umdctf\{|secret|token|password|api[_-]?key|https?://|<script|javascript:)",
    re.IGNORECASE,
)
_LOSSLESS_SUFFIXES = {".png", ".bmp", ".tif", ".tiff", ".webp"}
_CHANNEL_INDEX = {"R": 0, "G": 1, "B": 2, "A": 3}


@dataclass(slots=True)
class PixelForensicsProfile:
    available: bool = False
    score: int = 0
    verdict: str = "Pixel scan not evaluated"
    summary: str = "Pixel-level hidden-content scan has not run yet."
    indicators: list[str] = field(default_factory=list)
    lsb_strings: list[str] = field(default_factory=list)
    alpha_findings: list[str] = field(default_factory=list)
    channel_notes: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "score": self.score,
            "verdict": self.verdict,
            "summary": self.summary,
            "indicators": list(self.indicators),
            "lsb_strings": list(self.lsb_strings),
            "alpha_findings": list(self.alpha_findings),
            "channel_notes": list(self.channel_notes),
            "metrics": dict(self.metrics),
            "limitations": list(self.limitations),
            "next_actions": list(self.next_actions),
        }


def _entropy(values: bytes) -> float:
    if not values:
        return 0.0
    counts = [0] * 256
    for value in values:
        counts[value] += 1
    total = len(values)
    return -sum((count / total) * log2(count / total) for count in counts if count)


def _dedupe(items: Iterable[str], limit: int = 10) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = re.sub(r"\s+", " ", str(item or "")).strip(" \t\r\n\x00")
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


def _bits_to_bytes(bits: Sequence[int], *, msb_first: bool = True) -> bytes:
    if len(bits) < 8:
        return b""
    out = bytearray()
    usable = len(bits) - (len(bits) % 8)
    for index in range(0, usable, 8):
        chunk = bits[index:index + 8]
        value = 0
        if msb_first:
            for bit in chunk:
                value = (value << 1) | int(bit)
        else:
            for offset, bit in enumerate(chunk):
                value |= int(bit) << offset
        out.append(value)
    return bytes(out)


def _printable_runs(payload: bytes, *, limit: int = 6) -> list[str]:
    runs: list[str] = []
    for match in _PRINTABLE_RE.finditer(payload):
        text = match.group(0).decode("ascii", errors="ignore")
        # Very common all-identical runs are usually flat image artifacts, not hidden messages.
        if len(set(text)) <= 2 and not _HIGH_VALUE_CONTEXT_RE.search(text):
            continue
        runs.append(text[:180])
        if len(runs) >= limit:
            break
    return _dedupe(runs, limit=limit)


def _channel_quality_label(ones_ratio: float, entropy: float, compression_ratio: float, pair_balance: float) -> str:
    bits: list[str] = []
    if abs(ones_ratio - 0.5) <= 0.025 and entropy >= 7.65:
        bits.append("random-like low bit plane")
    elif ones_ratio <= 0.08 or ones_ratio >= 0.92:
        bits.append("flat low bit plane")
    if compression_ratio <= 0.45:
        bits.append("highly compressible low bit plane")
    elif compression_ratio >= 0.92 and entropy >= 7.3:
        bits.append("poorly compressible/noisy low bit plane")
    if pair_balance <= 0.045 and 0.45 <= ones_ratio <= 0.55:
        bits.append("even/odd pairs unusually balanced")
    return ", ".join(bits) if bits else "ordinary low-bit distribution"


def _pair_balance_score(values: Sequence[int]) -> float:
    """Return a rough 0..1 even/odd pair imbalance score for a byte channel.

    Very low values mean even/odd counts are unusually balanced across many value
    pairs. This can happen naturally, so it is only a weak supporting signal.
    """
    if not values:
        return 1.0
    counts = [0] * 256
    for value in values:
        counts[int(value) & 0xFF] += 1
    total = max(1, len(values))
    imbalance = 0
    participating_pairs = 0
    for base in range(0, 256, 2):
        pair_total = counts[base] + counts[base + 1]
        if pair_total:
            participating_pairs += 1
            imbalance += abs(counts[base] - counts[base + 1])
    if participating_pairs < 8:
        return 1.0
    return imbalance / total


def _bits_for_stream(
    pixels: Sequence[tuple[int, int, int, int]],
    order: str,
    *,
    bit_index: int = 0,
    limit_bits: int = 1_600_000,
) -> list[int]:
    bits: list[int] = []
    shift = max(0, min(7, int(bit_index)))
    for pixel in pixels:
        for channel_name in order:
            channel_index = _CHANNEL_INDEX.get(channel_name)
            if channel_index is None:
                continue
            bits.append((pixel[channel_index] >> shift) & 1)
            if len(bits) >= limit_bits:
                return bits
    return bits


def _extract_strings_from_bitstream(bits: Sequence[int], *, label: str, limit: int = 4) -> list[str]:
    strings: list[str] = []
    for endian in ("MSB", "LSB"):
        raw = _bits_to_bytes(bits, msb_first=(endian == "MSB"))
        for text in _printable_runs(raw, limit=limit):
            strings.append(f"{label}-{endian}: {text}")
    return _dedupe(strings, limit=limit)


def _scan_lsb_channels(pixels: list[tuple[int, int, int, int]], *, include_alpha: bool) -> tuple[list[str], list[str], dict[str, Any]]:
    channel_names = ["R", "G", "B", "A"] if include_alpha else ["R", "G", "B"]
    strings: list[str] = []
    notes: list[str] = []
    metrics: dict[str, Any] = {"channels": {}}

    for channel_index, channel_name in enumerate(channel_names):
        values = [pixel[channel_index] for pixel in pixels]
        bits = [value & 1 for value in values]
        if not bits:
            continue
        raw_msb = _bits_to_bytes(bits, msb_first=True)
        raw_lsb = _bits_to_bytes(bits, msb_first=False)
        combined_strings = _printable_runs(raw_msb) + _printable_runs(raw_lsb)
        for text in combined_strings:
            strings.append(f"{channel_name}-LSB: {text}")

        ones_ratio = sum(bits) / max(1, len(bits))
        entropy = max(_entropy(raw_msb), _entropy(raw_lsb))
        compressed = len(zlib.compress(raw_msb, level=6)) if raw_msb else 0
        compression_ratio = compressed / max(1, len(raw_msb))
        pair_balance = _pair_balance_score(values)
        label = _channel_quality_label(ones_ratio, entropy, compression_ratio, pair_balance)
        metrics["channels"][channel_name] = {
            "lsb_ones_ratio": round(ones_ratio, 4),
            "lsb_entropy": round(entropy, 4),
            "lsb_compression_ratio": round(compression_ratio, 4),
            "even_odd_pair_balance": round(pair_balance, 4),
            "sampled_bits": len(bits),
            "label": label,
        }
        notes.append(
            f"{channel_name}: {label} "
            f"(ones={ones_ratio:.2%}, entropy={entropy:.2f}, zlib={compression_ratio:.2f}, pair={pair_balance:.3f})"
        )
    return _dedupe(strings, limit=12), _dedupe(notes, limit=10), metrics


def _scan_composite_bitstreams(
    pixels: list[tuple[int, int, int, int]],
    *,
    include_alpha: bool,
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Search common RGB/BGR/RGBA packed bitstream layouts.

    CTF images often encode one message bit per color component, not one message
    stream per isolated channel. This pass checks the common composite orders and
    the second-lowest bit plane as a deeper but still bounded triage layer.
    """
    orders = ["RGB", "BGR", "RBG", "GBR"]
    if include_alpha:
        orders.extend(["RGBA", "ARGB", "A"])
    strings: list[str] = []
    notes: list[str] = []
    metrics: dict[str, Any] = {"composite_streams": {}}
    streams_checked = 0

    for order in orders:
        for bit_index in (0, 1):
            bits = _bits_for_stream(pixels, order, bit_index=bit_index)
            if len(bits) < 64:
                continue
            streams_checked += 1
            label = f"{order}-bit{bit_index}"
            raw = _bits_to_bytes(bits, msb_first=True)
            entropy = _entropy(raw)
            compression_ratio = len(zlib.compress(raw, level=6)) / max(1, len(raw)) if raw else 0.0
            ones_ratio = sum(bits) / max(1, len(bits))
            extracted = _extract_strings_from_bitstream(bits, label=label, limit=4)
            strings.extend(extracted)
            metrics["composite_streams"][label] = {
                "bits": len(bits),
                "ones_ratio": round(ones_ratio, 4),
                "entropy": round(entropy, 4),
                "compression_ratio": round(compression_ratio, 4),
                "readable_runs": len(extracted),
            }
            if extracted:
                notes.append(f"{label}: readable ASCII run recovered from packed component stream.")
            elif bit_index == 0 and abs(ones_ratio - 0.5) <= 0.018 and entropy >= 7.75 and compression_ratio >= 0.94:
                notes.append(f"{label}: high-entropy random-like packed stream without decoded text.")
    metrics["streams_checked"] = streams_checked
    return _dedupe(strings, limit=12), _dedupe(notes, limit=10), metrics


def _scan_row_column_bias(pixels: Sequence[tuple[int, int, int, int]], width: int) -> dict[str, Any]:
    if width <= 1 or not pixels:
        return {}
    rows = max(1, min(len(pixels) // width, 300))
    usable = min(len(pixels), rows * width)
    if usable < width * 2:
        return {}
    row_ones: list[float] = []
    for row_index in range(rows):
        row = pixels[row_index * width:(row_index + 1) * width]
        bits = [(r & 1) for r, _g, _b, _a in row]
        row_ones.append(sum(bits) / max(1, len(bits)))
    mean = sum(row_ones) / max(1, len(row_ones))
    variance = sum((item - mean) ** 2 for item in row_ones) / max(1, len(row_ones))
    spike_rows = sum(1 for item in row_ones if abs(item - mean) >= 0.18)
    return {
        "sampled_rows": rows,
        "red_lsb_row_mean": round(mean, 4),
        "red_lsb_row_variance": round(variance, 6),
        "red_lsb_spike_rows": spike_rows,
    }


def _alpha_hidden_findings(pixels: list[tuple[int, int, int, int]]) -> tuple[list[str], dict[str, Any]]:
    transparent = 0
    colored_transparent = 0
    vivid_transparent = 0
    semi_transparent = 0
    for red, green, blue, alpha in pixels:
        if alpha < 255:
            semi_transparent += 1
        if alpha <= 5:
            transparent += 1
            if max(red, green, blue) >= 12:
                colored_transparent += 1
            if max(red, green, blue) - min(red, green, blue) >= 24 or max(red, green, blue) >= 48:
                vivid_transparent += 1
    total = max(1, len(pixels))
    transparent_ratio = transparent / total
    colored_ratio = colored_transparent / max(1, transparent)
    vivid_ratio = vivid_transparent / max(1, transparent)
    semi_ratio = semi_transparent / total
    findings: list[str] = []
    if transparent_ratio >= 0.02 and colored_ratio >= 0.30:
        findings.append(
            f"Transparent-pixel RGB data is not blank: {colored_ratio:.1%} of fully transparent pixels retain color values."
        )
    if transparent_ratio >= 0.01 and vivid_ratio >= 0.12:
        findings.append(
            f"Vivid RGB residue exists under transparent pixels ({vivid_ratio:.1%} of transparent pixels)."
        )
    if semi_ratio >= 0.20 and transparent_ratio < 0.02:
        findings.append("Large semi-transparent alpha region detected; inspect alpha plane if the image is expected to be opaque.")
    return findings, {
        "transparent_pixel_ratio": round(transparent_ratio, 4),
        "colored_transparent_ratio": round(colored_ratio, 4),
        "vivid_transparent_ratio": round(vivid_ratio, 4),
        "non_opaque_pixel_ratio": round(semi_ratio, 4),
    }


def _thumbnail_texture_metrics(image: Image.Image) -> dict[str, Any]:
    work = image.convert("RGB")
    work.thumbnail((256, 256))
    stat = ImageStat.Stat(work)
    pixels = list(work.getdata())
    total = max(1, len(pixels))
    light = sum(1 for red, green, blue in pixels if (red + green + blue) / 3 >= 190) / total
    dark = sum(1 for red, green, blue in pixels if (red + green + blue) / 3 <= 45) / total
    saturated = sum(1 for red, green, blue in pixels if max(red, green, blue) - min(red, green, blue) >= 60) / total
    return {
        "thumbnail_pixels": total,
        "mean_brightness": round(sum(stat.mean) / max(1, len(stat.mean)), 2),
        "mean_stddev": round(sum(stat.stddev) / max(1, len(stat.stddev)), 2),
        "light_pixel_ratio": round(light, 4),
        "dark_pixel_ratio": round(dark, 4),
        "saturated_pixel_ratio": round(saturated, 4),
    }


def analyze_pixel_forensics(file_path: Path, *, max_scan_pixels: int = 1_200_000) -> PixelForensicsProfile:
    """Analyze pixel-level low-bit and transparency hiding signals.

    The function scans original pixel order up to ``max_scan_pixels``. It avoids
    network calls and avoids expensive exhaustive stego brute force, making it safe
    for import-time triage and repeatable tests.
    """
    profile = PixelForensicsProfile(
        limitations=[
            "A clean pixel scan does not prove that steganography is absent; it only means these offline heuristics did not find strong evidence.",
            "JPEG compression can randomize low bits; LSB findings are strongest on PNG/BMP/lossless screenshots.",
            "Composite RGB/BGR stream checks are CTF/stego triage aids; decoded strings still require manual validation.",
        ],
        next_actions=[
            "If score is elevated, preserve the original file and run specialist stego tools on a copy.",
            "Corroborate pixel findings with container-level strings, appended payload scans, and source-app history.",
        ],
    )
    try:
        with Image.open(file_path) as image:
            image.load()
            width, height = image.size
            mode = image.mode
            fmt = image.format or file_path.suffix.upper().lstrip(".") or "Unknown"
            has_alpha = "A" in image.getbands() or mode in {"LA", "RGBA", "PA"}
            rgba = image.convert("RGBA")
            iterator = rgba.getdata()
            pixels: list[tuple[int, int, int, int]] = []
            for index, pixel in enumerate(iterator):
                if index >= max_scan_pixels:
                    break
                pixels.append(tuple(int(part) for part in pixel))
            if not pixels:
                raise ValueError("image contains no readable pixels")
            texture = _thumbnail_texture_metrics(image)
    except Exception as exc:
        profile.available = False
        profile.verdict = "Pixel scan unavailable"
        profile.summary = f"Pixel-level scan could not be completed: {exc}"
        profile.limitations.append("The image decoder could not provide a stable pixel buffer for low-bit analysis.")
        return profile

    lsb_strings, channel_notes, channel_metrics = _scan_lsb_channels(pixels, include_alpha=has_alpha)
    composite_strings, composite_notes, composite_metrics = _scan_composite_bitstreams(pixels, include_alpha=has_alpha)
    alpha_findings, alpha_metrics = _alpha_hidden_findings(pixels) if has_alpha else ([], {})
    row_bias = _scan_row_column_bias(pixels, width)

    all_strings = _dedupe([*lsb_strings, *composite_strings], limit=14)
    score = 0
    indicators: list[str] = []
    if all_strings:
        valuable = [item for item in all_strings if _HIGH_VALUE_CONTEXT_RE.search(item)]
        composite_hit = any("bit" in item and any(order in item for order in ("RGB", "BGR", "RGBA", "ARGB")) for item in all_strings)
        score += 62 if valuable else 42 if composite_hit else 35
        indicators.append(f"Readable low-bit text recovered from {len(all_strings)} LSB/composite stream(s).")
        if composite_hit:
            indicators.append("Packed RGB/BGR component stream produced readable text; this is common in CTF-style stego tasks.")
        if valuable:
            indicators.append("High-value keyword was recovered from LSB text (flag/token/script/URL style marker).")
    if alpha_findings:
        score += 28 if any("Transparent-pixel" in item for item in alpha_findings) else 16
        indicators.extend(alpha_findings[:3])

    noisy_channels = 0
    flat_channels = 0
    balanced_pairs = 0
    for channel_name, metrics in channel_metrics.get("channels", {}).items():
        label = str(metrics.get("label", ""))
        entropy = float(metrics.get("lsb_entropy", 0.0))
        compression_ratio = float(metrics.get("lsb_compression_ratio", 0.0))
        ones_ratio = float(metrics.get("lsb_ones_ratio", 0.0))
        pair_balance = float(metrics.get("even_odd_pair_balance", 1.0))
        if "random-like" in label and compression_ratio >= 0.92:
            noisy_channels += 1
        if ones_ratio <= 0.03 or ones_ratio >= 0.97:
            flat_channels += 1
        if pair_balance <= 0.045 and channel_name != "A":
            balanced_pairs += 1
        if entropy >= 7.85 and compression_ratio >= 0.97 and channel_name != "A":
            indicators.append(f"{channel_name} low-bit plane is extremely high entropy and poorly compressible.")
    suffix = Path(file_path).suffix.lower()
    if noisy_channels >= 2 and suffix in _LOSSLESS_SUFFIXES:
        score += 14
        indicators.append("Multiple lossless color-channel LSB planes look random-like; this is a weak stego triage cue without decoded payload.")
    if balanced_pairs >= 2 and suffix in _LOSSLESS_SUFFIXES:
        score += 8
        indicators.append("Multiple even/odd channel pairs are unusually balanced, which can support LSB replacement triage.")
    if flat_channels >= 3 and texture.get("mean_stddev", 0) >= 25:
        score += 8
        indicators.append("Most color-channel LSB planes are unexpectedly flat while visible texture is non-trivial.")
    if row_bias.get("red_lsb_spike_rows", 0) >= 4:
        score += 5
        indicators.append("Row-level LSB distribution contains spike rows; inspect for barcode/striped payload layouts.")
    if composite_notes and not all_strings:
        score += 8
        indicators.extend(composite_notes[:2])

    score = max(0, min(100, score))
    if score >= 70:
        verdict = "Strong pixel-hidden-content lead"
    elif score >= 40:
        verdict = "Review pixel-level anomaly"
    elif score >= 15:
        verdict = "Weak pixel-level lead"
    else:
        verdict = "No strong pixel-level hidden-content indicator"

    profile.available = True
    profile.score = score
    profile.verdict = verdict
    profile.indicators = _dedupe(indicators, limit=12)
    profile.lsb_strings = _dedupe(all_strings, limit=10)
    profile.alpha_findings = _dedupe(alpha_findings, limit=6)
    profile.channel_notes = _dedupe([*channel_notes, *composite_notes], limit=12)
    profile.metrics = {
        "format": fmt,
        "mode": mode,
        "dimensions": f"{width}x{height}",
        "scanned_pixels": len(pixels),
        "scan_truncated": (width * height) > len(pixels),
        "has_alpha": has_alpha,
        "alpha": alpha_metrics,
        "texture": texture,
        "row_bias": row_bias,
        **channel_metrics,
        **composite_metrics,
        "analysis_depth": "channel LSB + composite RGB/BGR/RGBA bit0/bit1 + alpha residue + row-bias triage",
    }
    if profile.indicators:
        profile.summary = (
            f"Pixel-level scan scored {score}/100 ({verdict}). Key indicators: "
            + "; ".join(profile.indicators[:3])
        )
    else:
        profile.summary = (
            f"Pixel-level scan scored {score}/100. No readable LSB payload, packed RGB/BGR payload, "
            "transparent-pixel residue, or strong low-bit anomaly was detected by the offline heuristics."
        )
    return profile
