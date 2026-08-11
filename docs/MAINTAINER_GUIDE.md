# Maintainer guide

Complete operational manual for developers, maintainers, and automated agents working on **cai-agentstudio-generator**.

## Table of contents

1. [What this project is](#what-this-project-is)
2. [First-time setup](#first-time-setup)
3. [Daily development workflow](#daily-development-workflow)
4. [Validation and testing](#validation-and-testing)
5. [Deploying to Agent Studio](#deploying-to-agent-studio)
6. [Testing a deployed workflow](#testing-a-deployed-workflow)
7. [Updating the corpus](#updating-the-corpus)
8. [Regenerating from CrewAI](#regenerating-from-crewai)
9. [Changing agents, tasks, and prompts](#changing-agents-tasks-and-prompts)
10. [Troubleshooting](#troubleshooting)
11. [Security and secrets](#security-and-secrets)
12. [CI/CD](#cicd)
13. [File change checklist](#file-change-checklist)

---

## What this project is

This repository is a **self-contained deploy artifact** for Cloudera AI Agent Studio. It defines one workflow:

**Hybrid RAG Agentic Workflow** — a 3-agent sequential pipeline that answers questions about *Generative AI Design Patterns* using:

- A bundled **knowledge graph** (`graph.json`, 32 patterns)
- Bundled **book slice markdown** (14 files, pages 001–694)
- **11 Python tools** implementing hybrid graph + text retrieval

It was ported from an open-source **CrewAI** project (`crew_hybrid`) using a phased migration:

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | Done | `crewai_to_collated.py` — CrewAI YAML → CollatedInput |
| Phase 1 | Done | Bundle corpus + 2 core tools |
| Phase 2 | Done | All 11 tools + full toolkit |

**Nothing external is required at deploy/runtime** except OpenAI API access and Cloudera credentials.

---

## First-time setup

### 1. Clone the repository

```bash
git clone git@github.com:irvanzarkasie/cai-agentstudio-generator.git
cd cai-agentstudio-generator
```

### 2. Create Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

Dependencies: `PyYAML`, `requests`, `pydantic`.

### 3. Configure secrets

```bash
cp .env.example .env
```

Edit `.env`:

```bash
CAI_WORKBENCH_HOST=https://<your-workbench-host>
AGENT_STUDIO_URL=https://<your-agent-studio-host>
CDSW_APIV2_KEY=<64-char-hex-cml-api-v2-key>
OPENAI_API_KEY=<openai-api-key>
GITHUB_WORKFLOW_URL=https://github.com/irvanzarkasie/cai-agentstudio-generator.git
```

Load in shell:

```bash
set -a && source .env && set +a
```

**Never commit `.env`.**

### 4. Verify local artifact

```bash
python scripts/validate.py
python scripts/test_hybrid_tools.py
python scripts/verify_hybrid_mvp.py
```

All should pass without any external corpus path.

### 5. Verify Agent Studio API (optional, needs live environment)

```bash
python scripts/verify_connection.py
```

---

## Daily development workflow

```text
Edit code → bundle (if toolkit/tools changed) → validate → test → commit → push → deploy
```

### Typical edit: fix retrieval logic

```bash
# 1. Edit source of truth
vim converters/hybrid_rag_lib/hybrid_rag.py

# 2. Copy lib + regenerate tool entrypoints
python scripts/bundle_hybrid_data.py

# 3. Validate
python scripts/validate.py
python scripts/test_hybrid_tools.py

# 4. Commit
git add converters/ studio-data/ scripts/
git commit -m "Fix pattern neighborhood traversal scoring"
git push origin main

# 5. Deploy
python scripts/deploy.py --config deploy/deployment-config.example.json --wait 300 --insecure
```

### Typical edit: change agent prompt

```bash
vim collated_input.json   # edit crew_ai_backstory, task description, etc.
python scripts/validate.py
git commit -am "Clarify Solution Architect output format"
git push && python scripts/deploy.py --config deploy/deployment-config.example.json --wait 300 --insecure
```

No bundle step needed for prompt-only changes.

---

## Validation and testing

### `scripts/validate.py`

Structural validation of the CollatedInput artifact:

- `workflow.yaml` manifest correct
- `collated_input.json` internal ID references consistent
- Tool folders and files exist
- Agent/task/tool cross-references valid

```bash
python scripts/validate.py
python scripts/validate.py --root /path/to/artifact   # custom root
```

### `scripts/test_hybrid_tools.py`

Subprocess smoke test for **all 11 tools** against bundled data:

- Runs each `tool.py` with realistic parameters
- Asserts no `STUB [` responses
- Checks key fields in JSON output

```bash
python scripts/test_hybrid_tools.py
```

### `scripts/verify_hybrid_mvp.py`

Full deploy-readiness gate combining:

- File layout checks
- Corpus presence (graph + slices)
- Stub detection
- `validate.py` + `test_hybrid_tools.py`
- Packaging layout simulation (tar contents)

```bash
python scripts/verify_hybrid_mvp.py
```

### `scripts/package.py` (optional)

Build a local `artifact.tar.gz` identical to what Agent Studio packages:

```bash
python scripts/package.py -o .artifacts/artifact.tar.gz
tar -tzf .artifacts/artifact.tar.gz | head -20
```

---

## Deploying to Agent Studio

### Prerequisites (Cloudera side)

1. **Agent Studio** installed in a CML project
2. **OpenAI** registered as LLM provider in Agent Studio (model: `gpt-4o`)
3. **CML API v2 key** with API (+ Application for gRPC) scope
4. **GitHub repo accessible** from workbench (public repo or deploy keys for private)
5. **Agent Studio internal CML key valid** — check with `cmlApiCheck`

### Deploy command

```bash
set -a && source .env && set +a

python scripts/deploy.py \
  --config deploy/deployment-config.example.json \
  --wait 300 \
  --insecure
```

| Flag | Purpose |
|------|---------|
| `--config` | Deploy payload JSON (use example; secrets from `.env`) |
| `--wait 300` | Poll deployment status up to 300 seconds |
| `--insecure` | Skip TLS verify (common for private CDP environments) |

### What deploy does

1. Reads `deploy/deployment-config.example.json`
2. Injects `OPENAI_API_KEY` into `deployment_config.llm_config`
3. POSTs to `AGENT_STUDIO_URL/api/grpc/deployWorkflow`
4. Agent Studio clones `github_url`, packages artifact, builds tool venvs
5. Creates/updates CML Model + Application

### Critical deploy constraints

| Constraint | Reason |
|------------|--------|
| `workflow.yaml` at **repo root** | GitHub packaging clones root |
| `workflow_target.workflow_name` matches `collated_input.json` → `workflow.name` | Deploy API validation |
| `default_language_model_id` in `llm_config` keys | Runtime LLM auth |
| Push **before** deploy | GitHub target pulls latest commit |

### Monitor deployment

**Agent Studio UI:** Agentic Workflows → deployed workflows list

**API:**

```bash
curl -sS "$AGENT_STUDIO_URL/api/grpc/listDeployedWorkflows" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

Expected terminal state: `application_status: running`

First deploy: **5–10 minutes**. Subsequent redeploys: **3–5 minutes**.

---

## Testing a deployed workflow

### Via Application URL

After deploy, note the `application_url` from deploy output or `listDeployedWorkflows`.

**Kickoff:**

```bash
APP_URL="https://workflow-<deployed-id>.<workbench-domain>"

curl -sS -X POST "$APP_URL/api/workflow/kickoff" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"query": "enterprise RAG with reranking and citations"}}' \
  | python3 -m json.tool
```

Save the `trace_id` from the response.

**Poll events:**

```bash
curl -sS "$APP_URL/api/workflow/events?trace_id=<TRACE_ID>" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

### Via CML Model endpoint

Alternative path using model service URL + `accessKey` from CML model API. See deploy output fields `cml_deployed_model_id` and model `access_key`.

```bash
# Get model access key
curl -sS "$CAI_WORKBENCH_HOST/api/v2/projects/<project-id>/models/<model-id>" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

Kickoff uses base64-encoded inputs in the model API format (see prior session scripts).

### Expected kickoff input

| Key | Type | Example |
|-----|------|---------|
| `query` | string | `"reduce hallucinations in production"` |

The `{query}` placeholder in task descriptions is replaced with this value.

---

## Updating the corpus

The bundled corpus in `studio-data/workflows/hybrid_rag_agentic/data/` is the **runtime source of truth**. Refresh it when the upstream docling-graph project produces new merged graphs or slices.

### Upstream layout expected

```text
/path/to/generative_ai_design_patterns/
├── outputs/merged/graph.json
└── slices/by_50/pages_*.md
```

### Refresh command

```bash
# Option A: CLI flag
python scripts/bundle_hybrid_data.py \
  --source /path/to/generative_ai_design_patterns

# Option B: environment variable
export HYBRID_RAG_SOURCE=/path/to/generative_ai_design_patterns
python scripts/bundle_hybrid_data.py
```

### Refresh lib/tools only (no corpus change)

```bash
python scripts/bundle_hybrid_data.py
```

Omitting `--source` keeps existing `data/graph.json` and `data/slices/` and only copies `converters/hybrid_rag_lib/` + regenerates tools.

### After corpus update

```bash
python scripts/test_hybrid_tools.py
python scripts/verify_hybrid_mvp.py
git add studio-data/workflows/hybrid_rag_agentic/data/
git commit -m "Refresh bundled graph and book slices"
git push
python scripts/deploy.py --config deploy/deployment-config.example.json --wait 300 --insecure
```

---

## Regenerating from CrewAI

Use this when the upstream CrewAI project changes agent definitions, task order, or tool assignments.

### Required external inputs

| Input | Location |
|-------|----------|
| `agents.yaml` | External `crew_hybrid/config/` |
| `tasks.yaml` | External `crew_hybrid/config/` |
| Crew spec | `converters/crew_specs/crew_hybrid_agentic.yaml` (in this repo) |

### Regeneration steps

```bash
python scripts/crewai_to_collated.py \
  --config-dir /path/to/crew_hybrid/config \
  --crew-spec converters/crew_specs/crew_hybrid_agentic.yaml

python scripts/bundle_hybrid_data.py

python scripts/validate.py
python scripts/verify_hybrid_mvp.py
```

**Warning:** `crewai_to_collated.py` regenerates UUIDs and writes stub tools. After running it, you must run `bundle_hybrid_data.py` to restore real tool implementations.

To preserve existing UUIDs (avoid breaking deployed references), merge changes manually into `collated_input.json` instead of full regeneration.

---

## Changing agents, tasks, and prompts

Edit `collated_input.json` directly.

### Agent fields

| Field | Purpose |
|-------|---------|
| `crew_ai_role` | Agent role string |
| `crew_ai_goal` | Goal (supports `{query}`) |
| `crew_ai_backstory` | System context |
| `crew_ai_temperature` | LLM temperature |
| `crew_ai_max_iter` | Max tool-use iterations |
| `tool_instance_ids` | List of tool UUIDs |

### Task fields

| Field | Purpose |
|-------|---------|
| `description` | Task instructions (supports `{query}`) |
| `expected_output` | Format/quality guidance |
| `assigned_agent_id` | Agent UUID |

### Do not change unless intentional

- Entity `id` UUIDs — changing breaks cross-references and may confuse redeploy
- `workflow.name` — must match `deploy/deployment-config.example.json` → `workflow_name`
- `default_language_model_id` — must match an entry in deploy `llm_config`

---

## Troubleshooting

### Deploy failures

| Symptom | Fix |
|---------|-----|
| GitHub clone fails | Ensure repo is public or workbench has deploy keys |
| `workflow.yaml not found` | Files must be at repo root, not subfolder |
| LLM errors at runtime | Check `OPENAI_API_KEY` in `.env`; verify `gpt-4o` registered in Agent Studio |
| `CML API v2 key validation has failed` | Run `cmlApiCheck`; if invalid, `rotateCmlApi` |
| `401` / `malformed apikey` | Recreate CML API v2 key with API + Application scope |
| Tool venv build fails | Check tool `requirements.txt`; test locally with `test_hybrid_tools.py` |
| Login HTML instead of JSON | Wrong/expired API key or missing Authorization header |

### Agent Studio internal CML key

Deploy uses Agent Studio's **internal** key, not your personal `.env` key.

```bash
curl -sS "$AGENT_STUDIO_URL/api/grpc/cmlApiCheck" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

If `message` is non-empty:

```bash
curl -sS "$AGENT_STUDIO_URL/api/grpc/rotateCmlApi" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

Then redeploy.

### Runtime / agent behavior

| Symptom | Likely cause |
|---------|--------------|
| Agent returns generic ChromaDB advice | Prompt drift — verify Solution Architect backstory mentions Agent Studio stack |
| Tool returns empty results | Check bundled `data/graph.json` and slices present in deployed artifact |
| All tools fail instantly (0s) with agent generic fallback | **Missing module:** Agent Studio sandboxes mount only each tool directory at `/tool`; shared `lib/` is not visible. Run `python scripts/bundle_hybrid_data.py` so each tool vendors `hybrid_rag.py`, `paths.py`, `tool_runtime.py`, and `data/` alongside `tool.py`. |
| Tool returns `ModuleNotFoundError: tool_runtime` | Same as above — redeploy after rebundling; confirm with `python scripts/test_hybrid_tools.py` (includes isolated tool-dir test). |
| Tool returns `FileNotFoundError: Graph not found` with cwd `/workspace` | Corpus not reachable from sandbox — rebundle so each tool directory includes `data/graph.json` and `data/slices/` (see `bundle_hybrid_data.py`). |
| Workflow slow | 3 sequential LLM agents + multiple tool calls; normal for complex queries |
| Stub tool output | Old deployment — ensure Phase 2 pushed and redeployed |

### GitHub-deployed workflow not editable in UI

**Expected behavior.** GitHub-target workflows are read-only in Agent Studio UI. Edit via Git and redeploy.

---

## Security and secrets

| File | Commit? |
|------|---------|
| `.env` | **Never** |
| `.env.example` | Yes (template only) |
| `deploy/deployment-config.local.json` | **Never** (gitignored) |
| `deploy/deployment-config.example.json` | Yes (no secrets) |

Rotate any API key that was shared in chat, logs, or tickets.

Tools do not require API keys — they read local bundled files only. LLM calls use OpenAI key injected at deploy.

---

## CI/CD

GitHub Actions workflow `.github/workflows/validate.yml` runs on push/PR to `main`/`master`:

1. `python scripts/validate.py`
2. `python scripts/test_hybrid_tools.py`
3. `python scripts/verify_hybrid_mvp.py`

Deploy is **manual** (requires Cloudera credentials). CI validates artifact integrity only.

---

## File change checklist

Use this before every push:

- [ ] `python scripts/validate.py` passes
- [ ] `python scripts/test_hybrid_tools.py` passes
- [ ] `python scripts/verify_hybrid_mvp.py` passes
- [ ] No secrets in diff (`git diff`)
- [ ] If toolkit changed: ran `bundle_hybrid_data.py`
- [ ] If `workflow.name` changed: updated `deploy/deployment-config.example.json`
- [ ] README/docs updated if behavior or layout changed

---

## Related documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design and data flow
- [TOOL_REFERENCE.md](TOOL_REFERENCE.md) — all 11 tools
- [../AGENTS.md](../AGENTS.md) — instructions for AI coding agents
- [../README.md](../README.md) — quick start

## External references

- [Cloudera CAI Custom Workflows (CollatedInput)](https://github.com/cloudera/CAI_STUDIO_AGENT/blob/main/docs/user_guide/custom_workflows.md)
- [Cloudera CAI Deployments guide](https://github.com/cloudera/CAI_STUDIO_AGENT/blob/main/docs/user_guide/deployments.md)
