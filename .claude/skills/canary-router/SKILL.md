---
name: canary-router
description: Build the external weighted traffic router plus the canary health gate and promote/rollback logic. This is the piece NVCF does NOT provide and is the core of honest canary on NVCF. Use in Phases 5-6 or whenever working on traffic splitting, health checks, or rollback.
---

# Canary router + health gate (the NVCF-missing piece)

NVCF cannot split traffic by percentage (verified). So canary lives in YOUR router. This
is the single most reusable, production-relevant component in the prototype.

## 1. Weighted router (`router/gateway.py`, FastAPI)
- Holds two upstreams: `stable_url` and `canary_url` (the model `/infer` endpoints).
- State: `canary_weight` in [0,100], settable via `POST /__control/weight {pct}`.
- On each request: route to canary with probability `canary_weight/100`, else stable.
  Vary by a per-request random draw (seeded by request count, not wall-clock, for
  reproducible tests). Proxy the body through with `httpx`.
- Record per-request: which upstream, latency, status -> in-memory ring + SQLite.
- Health pass-through: `GET /__control/state` returns weights + rolling metrics.

## 2. Canary health gate (`pipeline/agents/canary_health.py`)
- For `promote_after_seconds`, poll metrics every ~10s. Compute over canary requests:
  **p95 latency**, **error rate (%)**, and **WER delta** (optional; skip for NMT/TTS).
- Compare to `model.yaml` `canary.rollback_on` thresholds. Any breach -> decision=ROLLBACK
  immediately; otherwise after the window -> decision=PROMOTE.
- Borrow the proven progressive-delivery design (Argo Rollouts / Flagger): a check window,
  small step weights, a metric source, and an automatic abort. Don't invent ad-hoc logic.
- **Metrics injector** (`tests/inject_metrics.py`): forces a healthy or degraded run so the
  demo can show both promote and rollback deterministically.

## 3. Promote / Rollback (`pipeline/agents/promote.py`)
- PROMOTE: router weight -> 100 (canary), record `promoted` event, optional Slack webhook.
- ROLLBACK: router weight -> 0 (back to stable) in < 30 s, record `rolled_back` + reason,
  always alert. **Rollback is a pure weight swap — never rebuild or redeploy.**

## Event store (`deployment_events`, SQLite stands in for TimescaleDB)
Columns: ts, model_name, git_sha, image_tag, fn_id, version_id, stage
(`canary_start|promoted|rolled_back`), traffic_pct, rollback_reason, p95_latency_ms,
error_rate, wer_delta. Same shape as the real TimescaleDB table so the swap is trivial.

## Production note to leave in the README
On real NVCF this router becomes a managed gateway (Envoy / Kong / APISIX) in front of two
function IDs. The weighting logic is identical; only the upstreams and ops change.

## Done when
good metrics -> weight 100; injected bad metrics -> weight 0 in < 30 s; one row per
decision in `deployment_events`.
