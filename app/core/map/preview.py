from __future__ import annotations

"""Internal offline map preview for coordinate anchors.

This is intentionally not a live third-party map. It renders an SVG scatter map
with confidence circles so the analyst can compare anchors locally first.
"""

from html import escape
from typing import Any, Iterable


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def render_internal_map_preview_html(anchors: Iterable[dict[str, Any]]) -> str:
    pts = [a for a in anchors if isinstance(a, dict) and a.get("latitude") is not None and a.get("longitude") is not None]
    if not pts:
        return (
            "<div style='padding:16px;border:1px dashed #27506c;border-radius:14px;background:#09131d;color:#9fb2c7;'>"
            "No internal map preview yet. Import evidence with Native GPS, visible coordinates, map URL coordinates, or offline geocoder hits."
            "</div>"
        )
    w, h = 720, 320
    pad = 42
    lats = [_f(p.get("latitude")) for p in pts]
    lons = [_f(p.get("longitude")) for p in pts]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    lat_span = max(0.0001, max_lat - min_lat)
    lon_span = max(0.0001, max_lon - min_lon)

    def xy(lat: float, lon: float) -> tuple[float, float]:
        x = pad + ((lon - min_lon) / lon_span) * (w - 2 * pad)
        y = h - pad - ((lat - min_lat) / lat_span) * (h - 2 * pad)
        return x, y

    circles: list[str] = []
    labels: list[str] = []
    for idx, point in enumerate(pts, start=1):
        lat = _f(point.get("latitude"))
        lon = _f(point.get("longitude"))
        x, y = xy(lat, lon)
        native = str(point.get("source", "")).lower() == "native-gps"
        stroke = "#67f5c2" if native else "#ffd166"
        fill = "#12372d" if native else "#33260e"
        confidence = int(_f(point.get("confidence"), 0))
        radius = max(8, min(40, 8 + confidence / 4))
        eid = escape(str(point.get("evidence_id", f"EV-{idx}")))
        circles.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{radius:.1f}' fill='{fill}' opacity='0.34' stroke='{stroke}' stroke-width='1.4'/>")
        circles.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='5.5' fill='{stroke}'/>")
        labels.append(f"<text x='{x+9:.1f}' y='{y-8:.1f}' fill='#eaf8ff' font-size='12' font-weight='700'>{eid}</text>")
    grid = []
    for i in range(1, 5):
        gx = pad + i * (w - 2 * pad) / 5
        gy = pad + i * (h - 2 * pad) / 5
        grid.append(f"<line x1='{gx:.1f}' y1='{pad}' x2='{gx:.1f}' y2='{h-pad}' stroke='#173247' stroke-width='1'/>")
        grid.append(f"<line x1='{pad}' y1='{gy:.1f}' x2='{w-pad}' y2='{gy:.1f}' stroke='#173247' stroke-width='1'/>")
    legend = "Native GPS = green; Derived Geo Anchor = amber; circles show relative confidence, not exact meters."
    bbox = f"lat {min_lat:.5f} → {max_lat:.5f} | lon {min_lon:.5f} → {max_lon:.5f}"
    svg = (
        f"<svg viewBox='0 0 {w} {h}' width='100%' height='320' role='img' aria-label='Internal GeoTrace anchor preview'>"
        f"<rect x='0' y='0' width='{w}' height='{h}' rx='18' fill='#07111b' stroke='#20435b'/>"
        + "".join(grid)
        + f"<text x='{pad}' y='26' fill='#8de9ff' font-size='13' font-weight='800'>Internal Map Preview — offline anchor comparison</text>"
        + f"<text x='{pad}' y='{h-14}' fill='#8fa7ba' font-size='11'>{escape(bbox)}</text>"
        + "".join(circles)
        + "".join(labels)
        + "</svg>"
    )
    rows = []
    for point in pts[:8]:
        source = "Native GPS" if str(point.get("source", "")).lower() == "native-gps" else "Derived Geo Anchor"
        rows.append(
            "<div style='border:1px solid #1d3850;border-radius:10px;padding:8px;margin-top:6px;background:#0a1520;'>"
            f"<b>{escape(str(point.get('evidence_id','EV')))}</b> • {escape(source)} • {escape(str(point.get('latitude')))}, {escape(str(point.get('longitude')))} • confidence {escape(str(point.get('confidence',0)))}%"
            "</div>"
        )
    return (
        "<div style='padding:10px;border:1px solid #1e4865;border-radius:16px;background:#081520;'>"
        + svg
        + f"<div style='color:#9fb2c7;margin-top:8px;'>{escape(legend)}</div>"
        + "".join(rows)
        + "</div>"
    )
