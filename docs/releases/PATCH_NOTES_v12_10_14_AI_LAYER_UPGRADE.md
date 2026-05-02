# GeoTrace v12.10.14 — AI Layer Upgrade Patch

## What changed

This patch upgrades the AI layer from a mostly deterministic rules layer into a safer extension-ready AI architecture while keeping the product offline-first and forensic-safe.

### Added

- **Local LLM command adapter**
  - New `GEOTRACE_AGENT_PROVIDER=local_llm` mode.
  - New `GEOTRACE_LOCAL_LLM_COMMAND` runner hook.
  - Sends a compact, evidence-only JSON payload to a local command.
  - Requires schema-guarded JSON output.
  - Falls back to deterministic rules if the model is missing, slow, invalid, or unsafe.

- **Optional local vision model runner**
  - New `GEOTRACE_LOCAL_VISION_COMMAND` hook.
  - Supports JSON outputs for caption, scene label, objects, landmarks, confidence, and warnings.
  - Has safe timeout and schema normalization.
  - Never makes remote calls.

- **Semantic image fingerprinting**
  - New dependency-free `semantic_embeddings.py` profile.
  - Adds offline vector/fingerprint, visual-family tags, and near-duplicate triage support.
  - Designed as a safe fallback before a real CLIP/SigLIP runner is configured.

- **Evidence Fusion Guard**
  - New claim-to-evidence fusion module.
  - Adds conservative claims with evidence, limitations, contradictions, and next actions.
  - Prevents AI wording from outrunning GPS/OCR/map/custody evidence.
  - Injects fused claims into the AI corroboration matrix.

- **Validation expansion**
  - Added support for validating:
    - image detail generation
    - semantic fingerprint generation
    - local vision execution
    - route/map detection
    - OCR minimum confidence thresholds

- **Plugin registry update**
  - Added explicit registry entries for local LLM, local vision, semantic fingerprinting, and evidence-fusion guard.

## Safety model

- Remote LLMs remain blocked by default.
- Local LLM and local vision are opt-in only.
- AI output is advisory and blended with deterministic safeguards.
- The report pipeline receives new AI metrics through existing evidence fields, avoiding risky schema churn.

## Environment examples

```powershell
$env:GEOTRACE_AGENT_PROVIDER="local_llm"
$env:GEOTRACE_LOCAL_LLM_COMMAND="python local_llm_runner.py"
$env:GEOTRACE_LOCAL_LLM_TIMEOUT="12"

$env:GEOTRACE_LOCAL_VISION_COMMAND="python local_vision_runner.py"
$env:GEOTRACE_LOCAL_VISION_TIMEOUT="8"
```

Both runners must print JSON to stdout. If they fail, GeoTrace keeps the deterministic pipeline active.
