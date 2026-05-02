# Local Vision Setup — GeoTrace v12.10.24

GeoTrace is offline and deterministic by default. Local Vision is optional and only runs when you configure a local command runner.

## Environment variables

```bat
set GEOTRACE_LOCAL_VISION_MODEL=data\local_vision\manifest.example.json
set GEOTRACE_LOCAL_VISION_COMMAND=python tools\local_vision_runner_template.py
set GEOTRACE_LOCAL_VISION_TIMEOUT=12
```

## Runner output schema

The runner receives the image path as the last argument and prints JSON:

```json
{
  "provider": "your-offline-model",
  "caption": "short caption",
  "scene_label": "map/navigation screenshot",
  "confidence": 0.87,
  "objects": [{"label": "road", "confidence": 0.79}],
  "landmarks": [{"label": "Cairo Tower", "confidence": 0.64}],
  "warnings": []
}
```

Recommended local capabilities:

- image captioning for scene summary
- object detection for map pins, roads, route lines, documents, screens
- landmark recognition for POI candidates
- map/screenshot classifier for Map Screenshot Mode
- CLIP/SigLIP-like similarity for offline visual matching

The UI will show `Local Vision: Enabled`, model type, capabilities, timeout, and warnings in Map Workspace and System Health. No evidence is uploaded by GeoTrace.
