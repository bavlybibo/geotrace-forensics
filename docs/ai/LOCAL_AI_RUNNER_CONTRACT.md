# Local AI Runner Contract

GeoTrace does **not** bundle a heavy model and does **not** call remote AI providers by default. The AI layer can call a local runner that you control.

## Local LLM runner

Enable:

```powershell
$env:GEOTRACE_AGENT_PROVIDER="local_llm"
$env:GEOTRACE_LOCAL_LLM_COMMAND="python tools/local_llm_runner_template.py"
```

The command receives compact evidence JSON on `stdin` and must print JSON:

```json
{
  "provider": "my-local-llm",
  "summary": "Conservative forensic summary based only on supplied evidence.",
  "recommended_actions": ["Validate GPS against timeline."],
  "caveats": ["Derived map signals are leads, not proof."],
  "confidence": 68
}
```

## Local vision runner

Enable:

```powershell
$env:GEOTRACE_LOCAL_VISION_COMMAND="python tools/local_vision_runner_template.py"
```

The command receives the image path as the final argument and must print JSON:

```json
{
  "provider": "my-local-vision-model",
  "caption": "A screenshot-like image with possible map context.",
  "scene_label": "map_screenshot",
  "confidence": 0.72,
  "objects": [{"label": "map", "confidence": 0.81}],
  "landmarks": [{"label": "possible Cairo landmark", "confidence": 0.44}],
  "warnings": []
}
```

## Guardrails

- Runners must be local/offline unless your evidence policy explicitly allows otherwise.
- Do not return identity claims about people.
- Do not claim a confirmed location unless GPS or independently corroborated evidence supports it.
- GeoTrace will still treat model output as advisory and blend it with deterministic safeguards.
