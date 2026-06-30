---
name: free-tier-ops
description: Set up and operate the $0 cloud stack for the prototype - GitHub Codespaces, Hugging Face Spaces, GHCR, and GitHub Actions - including current limits and gotchas. Use in Phase 0 and when wiring CI/CD or hosting.
---

# Free-tier ops ($0 stack)

The laptop only edits code and pushes. All compute is free cloud. Re-check limits at
signup (they change) — values below marked *verify*.

## Build/run box: GitHub Codespaces
- Free personal tier ~120 core-hours + ~15 GB-month storage *(verify)*. Docker works
  inside a Codespace, so build/run/test the mock, router, and model image there.
- Stop the Codespace when idle to save hours.

## Model hosting: Hugging Face Spaces
- Free **CPU Basic** ~2 vCPU / 16 GB, **Docker SDK** supported. **Sleeps when idle** ->
  first hit is a cold start (note it in the demo). Limited persistence — treat as stateless.
- The Space public URL = the model "function" the router targets.

## Image registry: GHCR (ghcr.io)
- Free image hosting for public repos. Push with `GITHUB_TOKEN` in Actions. This stands in
  for `nvcr.io`; the swap to nvcr.io is a one-line registry + token change.

## CI: GitHub Actions
- **Unlimited minutes for public repos**; private repos get ~2000 min/month *(verify)*.
- `deploy.yml`: `on: push: paths: ['models/**']`, `actions/checkout@v4` with
  `fetch-depth: 0` (needed for the change-detector git diff). Steps run the orchestrator
  stages; the mock + router + injector run as background steps inside the job.
- `hotfix_deploy.yml`: `on: workflow_dispatch` with inputs `model_name`, `image_tag`,
  `skip_canary` (boolean; true bypasses gates — emergency only, warn loudly).

## Secrets (use repo Actions secrets; never hardcode)
`GHCR` uses built-in `GITHUB_TOKEN`. Later/real: `NVCF_API_KEY`, `NVCR_TOKEN`,
`TIMESCALE_DSN`, `SLACK_WEBHOOK`. For the prototype, mock/SQLite need none.

## NVIDIA accounts (free, for realism only)
- **NGC** free = pull `nvcr.io/nvidia/...` base images. **build.nvidia.com** free credits =
  only *call* hosted NIMs. **Neither lets you create/deploy your own NVCF function** —
  that's why the control plane is mocked.

## Gotchas
- IndicTransToolkit is Linux-only -> always in Codespaces, never native Windows.
- HF Space cold start; Codespaces auto-stops; both fine for a 2-day demo.
