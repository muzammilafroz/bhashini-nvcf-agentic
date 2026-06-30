---
name: model-yaml-contract
description: Define and validate the declarative model.yaml that is the single source of truth for a model deployment, plus the JSON Schema and validate.py, and the config-only-vs-rebuild change rule. Use in Phase 1 and whenever touching model config or the change detector. Runs locally on the laptop.
---

# model.yaml — the single source of truth

The NVCF UI is never authoritative. Every model dir `models/<lang>-<task>-<arch>/` has a
`model.yaml`. The pipeline reads it; if reality differs, the pipeline wins. All of this is
light Python that runs locally.

## Canonical fields (prototype uses `type: hf-mt` for the CPU model)
```yaml
schema_version: "1.0"
name: en-hi-indictrans            # MUST match the (mock) NVCF function name
type: hf-mt                       # prototype CPU type; real types: triton | vllm | sglang
image: ghcr.io/<owner>/en-hi-indictrans:${GIT_SHA}
gpu: { type: CPU, count: 0 }      # CPU for the prototype
ports: { http: 8000 }
scaling: { min_instances: 1, max_instances: 2, concurrency: 4 }
canary:
  enabled: true
  initial_traffic_pct: 10         # enforced by the external router, NOT by NVCF
  promote_after_seconds: 120
  rollback_on:
    p95_latency_ms: 1500
    error_rate_pct: 2.0
    wer_delta_pct: 5.0            # ASR only; omit for NMT/TTS
smoke_test: { input_fixture: tests/fixtures/hello.txt, max_latency_ms: 2000 }
```

## Deliverables
- `pipeline/schemas/model_yaml_v1.json` — JSON Schema (draft 2020-12). Required:
  schema_version, name, type, image, gpu, ports, scaling. `type` is an enum.
- `pipeline/validate.py` — loads yaml (`pyyaml`), validates (`jsonschema`), prints a clear
  pass/fail with the failing JSON path. Run: `python pipeline/validate.py models/<name>/model.yaml`.

## The change rule (feeds the change detector)
- Only `models/<name>/model.yaml` changed AND only scaling/canary numbers differ ->
  **config-only** (skip build; on real NVCF this is the PUT-deployment fast path).
- `Dockerfile`, model repo, or any other file changed -> **rebuild required**.
- Only `pipeline/` or `.github/` changed -> CI change, no model deploy.

## Done when
a valid file passes, a broken file fails with a readable message, and a scaling-only edit
is classified config-only.
