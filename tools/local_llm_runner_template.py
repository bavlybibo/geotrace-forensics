"""Template local LLM runner for GeoTrace.

Replace the simple rules below with your local model call. This file is safe to
run as-is for testing the adapter contract:

PowerShell:
  $env:GEOTRACE_AGENT_PROVIDER="local_llm"
  $env:GEOTRACE_LOCAL_LLM_COMMAND="python tools/local_llm_runner_template.py"
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    record = payload.get("selected_record", {})
    gps = record.get("gps", {})
    derived = record.get("derived_geo", {})
    map_data = record.get("map", {})
    actions = ["Check claim-to-evidence rows before exporting the final report."]
    caveats = ["Template runner only; replace with a real local model for production."]
    if gps.get("has_gps"):
        summary = f"{record.get('evidence_id')} has a native GPS anchor and should be timeline-corroborated."
        actions.insert(0, "Verify GPS against the source device and nearby evidence timestamps.")
        confidence = 70
    elif derived.get("display") and derived.get("display") != "Unavailable":
        summary = f"{record.get('evidence_id')} has a derived geo/map lead but no native GPS proof."
        actions.insert(0, "Label the location as a lead until an independent source confirms it.")
        caveats.append("Derived map/OCR content can represent a searched place or destination.")
        confidence = 58
    elif map_data.get("confidence", 0):
        summary = f"{record.get('evidence_id')} contains map-like context that deserves OCR and route review."
        actions.insert(0, "Decide whether the map is current location, searched place, route origin, or destination.")
        confidence = 52
    else:
        summary = f"{record.get('evidence_id')} should be reviewed mainly through integrity, timeline, OCR, and hidden-content signals."
        confidence = 45
    print(json.dumps({
        "provider": "geotrace-template-local-llm",
        "summary": summary,
        "recommended_actions": actions,
        "caveats": caveats,
        "confidence": confidence,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
