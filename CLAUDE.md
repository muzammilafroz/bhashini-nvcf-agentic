# bhashini-nvcf-agentic

CPU-only, $0 prototype of a GitOps-style deployment pipeline for BHASHINI
models on NVCF. See ACTIONABLE_PLAN.md for full context — this file is the
condensed, always-loaded version.

## The one thing to never forget
NVCF has NO native weighted/percentage traffic-split field. Canary routing
must be built as an external FastAPI gateway (`router/gateway.py`) that
holds old+new endpoints and splits by a settable weight. Do not write code
that calls a fictional `trafficPercentage` field on the NVCF API.

## Stack
- Python 3.11, FastAPI, httpx, pydantic, pytest, ruff
- CTranslate2 (int8 CPU inference) for IndicTrans2-dist-200M
- SQLite standing in for TimescaleDB (`deployment_events` table)
- Mock NVCF: 3-layer Function→Version→Deployment model, NO traffic field

## Conventions
- Type hints everywhere; ruff handles lint + format (`ruff check .`, `ruff format .`)
- pytest for all new logic; mock external calls with `httpx.MockTransport`
- Async for I/O-bound agent steps (git diff, HTTP calls), sync for pure logic
- Never hardcode API keys, tokens, or secrets — read from environment only

## Architecture (6 stages — see ACTIONABLE_PLAN.md §1.3 for the diagram)
1. Change Detector — git diff → config-only vs rebuild
2. Build + CPU smoke test → push image to GHCR
3. Planner — model.yaml → resolved deploy spec
4. Deploy Agent — create fn/version/deployment on mock NVCF, poll ACTIVE
5. Router + Canary Health — weighted gateway, poll p95/error-rate metrics
6. Promote/Rollback — reweight router, write deployment_events row

## Commands
- `pytest` — run all tests
- `ruff check . && ruff format .` — lint + format
- `pip-audit` — dependency vulnerability scan
- `uvicorn router.gateway:app --reload --port 8001` — run the router locally
- `python pipeline/validate.py models/en-hi-indictrans/model.yaml` — validate a model config

## File map
- `models/<name>/model.yaml` — declarative config per model (source of truth)
- `pipeline/` — change_detector.py, deployment_planner.py, nvcf_deploy.py, schemas/
- `mock_nvcf/` — FastAPI app mimicking the real 3-layer NVCF API
- `router/` — gateway.py (weighted canary router), canary_health.py
- `tests/` — mirrors the structure above

## Out of scope for the prototype (don't build these)
- Real GPU/Triton serving — CTranslate2 CPU int8 only
- TimescaleDB/OTel — SQLite + injected metrics
- LLM rollback-triage agent — deterministic controller only, unless told otherwise
