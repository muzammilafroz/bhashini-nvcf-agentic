# Skills for the bhashini-nvcf-agentic prototype

These are Claude Code **skills**: small instruction files the agent loads on demand while
building. Each encodes the *verified* facts for one hard part of the Actionable Plan, so
generated code is grounded instead of guessed.

> Why this matters: the source spec assumed an NVCF traffic-split API that **does not
> exist**. These skills bake in the corrected reality (and the model/serving details I
> verified) so every piece of code is built on solid ground.

## Where they run (read this first)
You edit and run Claude Code **on your local laptop**. These skills are used by your local
Claude Code session. They describe code that mostly runs locally too (mock, router, agents,
tests). Only the genuinely heavy / Linux-only steps (CTranslate2 conversion + model
inference, Docker builds) run on a **Codespace** — see `indictrans2-cpu-serving` and
`free-tier-ops` for which is which.

## The skills (mapped to plan phases)
| Skill | Phase | Runs where | What it gives the agent |
|-------|-------|-----------|--------------------------|
| `free-tier-ops` | 0, 6 | local + cloud | Codespaces / HF Spaces / GHCR / Actions setup, limits, gotchas |
| `model-yaml-contract` | 1 | local | Declarative config + JSON Schema + validate.py + config-vs-rebuild rule |
| `nvcf-mock` | 2 | local | The **real** NVCF object model, exact endpoints, polling, auth scopes |
| `indictrans2-cpu-serving` | 3 | **Codespace** | IndicTrans2-dist-200M on CPU (CT2 int8), FastAPI, Docker, HF Space |
| `canary-router` | 5–6 | local | External weighted router + health gate + promote/rollback |

Build order matches the plan: `free-tier-ops` → `model-yaml-contract` → `nvcf-mock` →
`indictrans2-cpu-serving` → `canary-router`.
