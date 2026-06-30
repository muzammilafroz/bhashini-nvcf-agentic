# Step 0 → Working Claude Code Setup: bhashini-nvcf-agentic

Everything below assumes the plan in `ACTIONABLE_PLAN.md`: $0 budget, CPU-only laptop, compute happens on GitHub Codespaces + Hugging Face Spaces, your laptop only edits and pushes. Follow in order — each section unblocks the next.

---

## 0. Accounts (15–20 min, do this first)

| # | Account | URL | Notes |
|---|---|---|---|
| 1 | GitHub | github.com/join | Free plan is fine. Turn on 2FA (Settings → Password and authentication) — GitHub requires it for most features now. |
| 2 | Hugging Face | huggingface.co/join | Then **Settings → Access Tokens → Create new token**, type "Write" (needed later to push a Space). Copy it somewhere safe — you will *not* hardcode it, see §6. |
| 3 | Claude (for Claude Code) | claude.ai or console.anthropic.com | Claude Code needs a **Pro, Max, Team, Enterprise, or Console (API)** account — the free claude.ai plan does **not** include Claude Code access. If you already have a paid Claude plan you're done; otherwise upgrade or set up API billing at console.anthropic.com. |
| 4 | NGC (NVIDIA) | ngc.nvidia.com | Free, only needed later if you ever pull an `nvcr.io` base image. Day 1–2 use GHCR instead (free, no signup beyond GitHub), so this can wait. |
| 5 | BHASHINI ULCA / Dhruva | bhashini.gov.in/ulca | **Skip for now.** Phase 0–4 use the public Hugging Face IndicTrans2 model directly, not the live Dhruva API. Register only when/if you wire in the real BHASHINI endpoint later. |

Don't create the BHASHINI Dhruva key yet — registering early and then leaving it unused for weeks is how keys go stale or get lost. Do it when Phase 8+ actually needs it.

---

## 1. Install VS Code + extensions

1. Download VS Code: code.visualstudio.com
2. Open it, press **Ctrl+Shift+X** (Cmd+Shift+X on Mac) to open Extensions, install:
   - **Claude Code** (publisher: Anthropic) — the official extension. This gives you a graphical chat panel; it bundles its own copy of the CLI for that panel.
   - **GitHub Codespaces** (publisher: GitHub) — lets you open/manage a cloud Codespace from your local VS Code window instead of the browser.
   - **Python** (ms-python.python)
   - **Ruff** (charliermarsh.ruff) — fast linter/formatter, matches the `ruff` dependency in the plan.
   - **YAML** (redhat.vscode-yaml) — for validating `model.yaml` against your JSON Schema as you type.
   - *(Optional)* **Docker** (ms-azuretools.vscode-docker) — handy for editing the Dockerfile in Phase 3.

You do **not** need the Claude Code CLI installed locally if you're going to do all real work inside a Codespace (recommended, see §3) — the CLI goes inside the Codespace instead. If you also want `claude` to work in your *local* terminal (e.g., for quick edits without spinning up a Codespace), install it locally too using the same command as §4.

---

## 2. Create the repository

Create it as a **new, separate** GitHub repo — not a folder inside your existing BHASHINI research repo, per the earlier decision.

1. github.com/new → name: `bhashini-nvcf-agentic` → Public → check "Add a .gitignore" → template **Python** → Create repository.
2. Don't clone it locally yet — you'll open it directly in a Codespace next.

---

## 3. Open it in a Codespace

This is where the actual compute happens (Docker, Python, model inference) — your laptop just drives VS Code.

1. On the repo page: green **Code** button → **Codespaces** tab → **Create codespace on main**.
   (Or, from local VS Code: Command Palette → `Codespaces: Create New Codespace` → pick the repo.)
2. Use the default **2-core** machine. Free personal-account quota is **120 core-hours/month (≈60 clock-hours on a 2-core box) + 15 GB storage** — comfortably enough for the Day 1–2 build in the plan, but verify current numbers on your account at github.com/settings/billing since GitHub changes these occasionally. Stop (don't just leave idle) the Codespace when you're done for the day — idle ones still burn the storage quota.
3. Once it boots, verify Docker works in the integrated terminal:
   ```
   docker run hello-world
   ```
   That's Phase 0's success check from the plan.

---

## 4. Install Claude Code inside the Codespace

In the Codespace terminal:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

This is the native installer — no Node.js needed, auto-updates in the background, and is what Anthropic currently recommends over the old `npm install -g @anthropic-ai/claude-code` path (that still works if you ever need to pin a specific version).

Then authenticate:

```bash
claude
```

It opens a browser OAuth flow — sign in with the same account from §0.3. Paste the one-time code back if prompted. Verify with:

```bash
claude doctor
```

Back in local VS Code, the **Claude Code** extension will auto-detect this CLI once your local window is connected to the Codespace (Remote indicator bottom-left should say the Codespace name). Click the spark icon in the sidebar to open the panel, or just use `claude` in the integrated terminal — both talk to the same session state.

---

## 5. Project Python environment

Still inside the Codespace, at the repo root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn httpx pydantic jsonschema pyyaml gitpython \
            ctranslate2 transformers sentencepiece pytest ruff pip-audit
```

`pip-audit` isn't in the original dependency list from the plan but you'll want it for the hook in §9 (scans installed packages for known CVEs — relevant given this pulls third-party model-serving libraries).

---

## 6. Secrets — set these up now, never hardcode them

You'll eventually need: `HF_TOKEN` (push to your Space), and later a Dhruva `inferenceApiKey`. Never put these in `model.yaml`, source files, or commit them in any form.

For a Codespace, the clean way is **repo-level Codespaces secrets**:
GitHub repo → **Settings → Secrets and variables → Codespaces → New repository secret** → add `HF_TOKEN`. It's injected as an environment variable into every Codespace for this repo automatically — your code reads `os.environ["HF_TOKEN"]`, nothing touches disk in plaintext.

Add a `.env.example` (committed, no real values) so collaborators know what's expected, and make sure `.env` itself is in `.gitignore` (the Python template you picked in §2 already includes this).

---

## 7. Write CLAUDE.md — before any code

This is the single file Claude Code loads automatically every session, so it's worth getting right before Phase 1 starts. Create `CLAUDE.md` at the repo root:

```markdown
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
```

That's roughly 60 lines — well under the 200-line budget, leaving room to grow as phases land. Keep edits to this file deliberate; it's read on every single turn, so bloat costs tokens every session, not just once.

---

## 8. `.claude/settings.json` — permissions + hooks

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Read",
      "Edit",
      "Bash(git status)",
      "Bash(git diff*)",
      "Bash(git add*)",
      "Bash(git commit*)",
      "Bash(pytest*)",
      "Bash(ruff*)",
      "Bash(python*)",
      "Bash(pip install*)",
      "Bash(pip-audit*)",
      "Bash(uvicorn*)",
      "Bash(docker*)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./**/*token*)",
      "Read(./**/*secret*)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "ruff check --fix $CLAUDE_FILE_PATH 2>/dev/null || true" }
        ]
      }
    ]
  },
  "env": {
    "DISABLE_AUTOUPDATER": "0"
  }
}
```

This is the real security boundary — `.claudeignore` (§9) is *not* a permissions mechanism; Claude Code can still be asked to read a file even if it's listed there. The `deny` block above is what actually blocks reads of anything that looks like a secret. Commit this file; it's meant to be shared.

The `allow` list matters more than it looks: without it, Claude Code prompts you for permission on every single shell command, which is the single biggest source of wasted turns/tokens in a session. Pre-approving your known-safe commands (test, lint, git, docker) lets it move through Phases 1–4 without stopping to ask each time.

---

## 9. `.claudeignore` — context hygiene (not security)

```
.venv/
__pycache__/
*.pyc
node_modules/
*.sqlite
*.db
data/raw/
*.log
.DS_Store
*.bin
*.pt
ct2_model/
```

Purpose: keeps generated/binary artifacts (the CTranslate2 model dirs especially — those can be hundreds of MB) out of automatic file discovery, so Claude isn't spending context budget scanning model weights when you ask it to refactor `pipeline/`. It works like `.gitignore` syntax. Don't rely on it to hide secrets — that's §8's job.

---

## 10. Subagents — delegate the noisy stuff

Create `.claude/agents/test-runner.md`:

```markdown
---
name: test-runner
description: Runs the test suite and reports only failures, summarized
tools: Bash, Read
---

Run `pytest -v`. Do not paste the full passing output back to the main
conversation. If everything passes, report just "N passed" in one line.
If anything fails, report only the failing test names and the relevant
traceback lines (not the full pytest output), with a one-line diagnosis
of likely cause per failure.
```

Create `.claude/agents/log-summarizer.md`:

```markdown
---
name: log-summarizer
description: Summarizes verbose CI/Docker/curl output into a short status
tools: Bash, Read
---

Given a command and its raw output, return at most 5 lines: pass/fail
status, and only the lines a human actually needs to act on. Discard
progress bars, repeated boilerplate, and successful step confirmations.
```

These run in their own context window — the noisy pytest/docker/curl output never lands in your main session, so your main conversation (and its token cost) stays focused on the actual decisions: what to build next, not what scrolled past in a log.

---

## 11. `/code-review` — built-in, no GitHub App needed

`/code-review` ships with Claude Code already; nothing to install. Inside a `claude` session, once you have a diff to check:

```
/code-review
```

It reads your local working diff and reviews it in the terminal — no GitHub App, no PR required, works on an unpushed branch. Use this before pushing, not as a replacement for the eventual GitHub Actions check in Phase 6.

---

## 12. Model + token discipline cheat sheet

| Situation | Do this |
|---|---|
| Default coding (writing agents, tests, fixing bugs) | Leave on **Sonnet** (`/model sonnet`) — it's the default and is enough for Phases 1, 3, 4, 6 |
| Architecture decisions (mock NVCF API shape in Phase 2, router design in Phase 5) | `/model opus` for that one exchange, then switch back |
| Switching to unrelated work (e.g., jumping from the router to the academic econometrics repo) | `/clear` — starts a fresh context, don't let unrelated history ride along |
| Session getting long, Claude losing track of earlier decisions | `/compact`, optionally with focus instructions, e.g. `/compact keep the CLAUDE.md constraints and current phase` |
| Noisy command output (pytest, docker, curl) | Let the `test-runner` / `log-summarizer` subagents handle it instead of dumping raw output into the main thread |
| Before a big multi-file change | Shift+Tab for Plan Mode — review the plan before Claude touches files, cheaper than undoing a wrong multi-file edit |
| Checking spend | `/usage` or `/cost` |

---

## 13. First real command (kicks off Phase 0–1)

Once §0–11 are done, inside the Codespace:

```bash
mkdir -p models/en-hi-indictrans pipeline/schemas
```

Then in a `claude` session:

```
Implement Phase 1 from ACTIONABLE_PLAN.md: write models/en-hi-indictrans/model.yaml
(type: hf-mt), pipeline/schemas/model_yaml_v1.json, and pipeline/validate.py.
Follow CLAUDE.md conventions. Success = valid yaml passes, broken yaml fails
clearly with a useful error.
```

That's the actual Day 1 starting line. Everything in this guide exists to make that one prompt — and the five phases after it — cheap, fast, and hard to get wrong.
