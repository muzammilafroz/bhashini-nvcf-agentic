---
name: nvcf-mock
description: Build or extend the faithful Mock NVCF control-plane API (FastAPI) for the bhashini-nvcf-agentic prototype. Use when creating the mock server, its endpoints, polling behavior, or the deploy client that talks to it. Encodes the REAL NVCF object model so mock->real is a base-URL + auth-header swap. Runs locally on the laptop.
---

# Mock NVCF — faithful to the real control plane

Goal: a small FastAPI server that behaves like real NVCF so the deploy agent code is real.
**Do not invent endpoints.** Mirror the verified NVCF surface below. This runs locally
(no GPU, no cloud) — it is pure control-plane simulation.

## The REAL object model (3 layers)
1. **Function** — logical workload, stable function ID, single invocation endpoint.
2. **Version** — immutable config under a function (image, health URI, GPU/backend).
   A version exists but serves **zero traffic** until it is *deployed*.
3. **Deployment** — allocates GPU instances (min/max, backend, gpu type) to a version.
   Lives on a SEPARATE API path.

## Endpoints the mock MUST expose (real control plane host = api.ngc.nvidia.com)
| Action | Method + path |
|---|---|
| Create function | `POST /v2/nvcf/functions` |
| List functions | `GET /v2/nvcf/functions?visibility=private` |
| Create version | `POST /v2/nvcf/functions/{functionId}/versions` |
| Deploy a version | `POST /v2/nvcf/deployments/functions/{functionId}/versions/{versionId}` |
| Get deployment | `GET /v2/nvcf/deployments/functions/{functionId}/versions/{versionId}` |
| Update deployment | `PUT /v2/nvcf/deployments/functions/{functionId}/versions/{versionId}` |
| Delete deployment | `DELETE /v2/nvcf/deployments/functions/{functionId}/versions/{versionId}` |

Deploy body uses a `deploymentSpecifications` array:
`[{ "backend": "GFN", "gpu": "L40G", "minInstances": 1, "maxInstances": 1, "maxRequestConcurrency": 4 }]`

## CRITICAL — the constraint that shapes the whole project
**There is NO traffic-weight / percentage field anywhere.** `deploymentSpecifications`
fields are: gpu, instanceType, backend, minInstances, maxInstances, maxRequestConcurrency,
regions, clusters, configuration, attributes. **None is a weight.** Real NVCF multi-version
routing is "based on instance availability," not a settable percent. So the mock must
**deliberately NOT** expose a traffic-split endpoint. Canary is done by the external
`canary-router` skill, never by the mock.

## Behavior to simulate
- After `POST deployment`, status starts `DEPLOYING`; flip to `ACTIVE` after N seconds
  (config, e.g. 5s) so the deploy agent practices polling. Support an `ERROR` path.
- Poll = `GET deployment` returns `{ "deployment": { "functionVersionId": ..., "status": "ACTIVE" } }`.
- Invoke semantics to imitate if you add an /exec route: blocks ~5s then returns **202 +
  invocation request-id** to poll; **302** = result too large (Location header). Auth header
  carries a bearer/api-key; scopes are `deploy_function` (manage) vs `invoke_function`
  (call). For the mock, accept any non-empty `Authorization`.

## Implementation notes
- In-memory dicts keyed by id; generate ids with `uuid4`. Pydantic models for bodies.
- Keep a `mock=True` flag in the deploy client so the ONLY difference vs real is `BASE_URL`
  + the `Authorization` header. Document this in the file header.
- Add a `/__admin/advance` test hook to force a version to ACTIVE/ERROR instantly for CI.
- Run locally: `uvicorn mock_nvcf.app:app --reload --port 8000`.

## Done when
create fn -> create version -> deploy -> poll ACTIVE -> undeploy all return correct JSON,
and there is no traffic-percentage endpoint anywhere.
