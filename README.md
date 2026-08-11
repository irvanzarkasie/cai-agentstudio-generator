# cai-agentstudio-generator

Infrastructure-as-code (IaC) workflow for **Cloudera AI Agent Studio** using the **CollatedInput** format and **GitHub deploy target**.

This repository defines a sample **Calculator Workflow** (single agent + calculator tool + OpenAI) at the **repository root**, which is required for Agent Studio's GitHub packaging (`workflow.yaml` must live at the clone root).

## Environment reference (irz-tstenv04)

| Item | Value |
|------|-------|
| CDP environment | `irz-tstenv04-cdp-env` |
| ML workbench | `irz-ai-workbench` |
| Workbench URL | `https://ml-1e596f2f-177.irz-tste.a465-9q4k.cloudera.site` |
| Agent Studio app | `https://cai-agent-studio-svf4oc.ml-1e596f2f-177.irz-tste.a465-9q4k.cloudera.site` |
| CML project | `Agent Studio - izarkasie` |
| GitHub repo | `git@github.com:irvanzarkasie/cai-agentstudio-generator.git` |

---

## Repository layout

```text
.
├── workflow.yaml                 # Artifact manifest (type: collated_input)
├── collated_input.json           # Full workflow definition (agents, tasks, tools, LLMs)
├── studio-data/                  # Tool source code referenced by collated_input.json
│   └── workflows/calculator/tools/calculator_tool/
│       ├── tool.py
│       └── requirements.txt
├── deploy/
│   └── deployment-config.example.json
├── scripts/
│   ├── validate.py               # Validate artifact before push/deploy
│   ├── package.py                # Build artifact.tar.gz locally (optional)
│   └── deploy.py                 # Trigger GitHub-target deploy via Agent Studio API
├── .env.example                  # Local secrets template (copy to .env)
└── requirements-dev.txt
```

---

## Prerequisites

1. **Agent Studio** installed and running in project `Agent Studio - izarkasie`.
2. **OpenAI** registered in Agent Studio (Models / LLM providers).
3. **CML API v2 key** with API scope (Workbench → User Settings → API Keys).
4. **OpenAI API key** for runtime LLM calls (passed at deploy time via `llm_config`).
5. **Python 3.10+** locally for validation scripts.
6. **Git + SSH** access to GitHub (`ssh -T git@github.com`).

Verify CDP / workbench from CLI:

```bash
cdp environments describe-environment --environment-name irz-tstenv04-cdp-env
cdp ml describe-workspace --environment-name irz-tstenv04-cdp-env --workspace-name irz-ai-workbench
```

---

## Step-by-step manual guide

### Step 1 — Clone and configure secrets

```bash
git clone git@github.com:irvanzarkasie/cai-agentstudio-generator.git
cd cai-agentstudio-generator

cp .env.example .env
```

Edit `.env` (never commit this file):

```bash
CAI_WORKBENCH_HOST=https://ml-1e596f2f-177.irz-tste.a465-9q4k.cloudera.site
AGENT_STUDIO_URL=https://cai-agent-studio-svf4oc.ml-1e596f2f-177.irz-tste.a465-9q4k.cloudera.site
CDSW_APIV2_KEY=<your-cml-api-v2-key>
OPENAI_API_KEY=<your-openai-api-key>
GITHUB_WORKFLOW_URL=https://github.com/irvanzarkasie/cai-agentstudio-generator.git
```

Load env in your shell:

```bash
set -a && source .env && set +a
```

### Step 2 — Install dev dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Step 3 — Validate workflow artifact

```bash
python scripts/validate.py
```

Expected output: `Validation OK`

This checks:

- `workflow.yaml` declares `type: collated_input`
- `collated_input.json` has consistent agent/task/tool references
- Tool files exist under `studio-data/...`

### Step 4 — (Optional) Package artifact locally

```bash
python scripts/package.py -o .artifacts/artifact.tar.gz
tar -tzf .artifacts/artifact.tar.gz | head
```

You should see `workflow.yaml`, `collated_input.json`, and `studio-data/...` at the archive root.

### Step 5 — Push workflow to GitHub

Agent Studio's GitHub deploy target **clones the repo**; the deployable files must be at the **repository root**.

```bash
git status
git add .
git commit -m "Add Calculator Workflow CollatedInput artifact and deploy scripts"
git push -u origin main
```

If your default branch is `master`, use that instead of `main`.

### Step 6 — Verify Agent Studio API access

```bash
curl -sS "$AGENT_STUDIO_URL/api/grpc/listWorkflows" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

```bash
curl -sS "$AGENT_STUDIO_URL/api/grpc/getStudioDefaultModel" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

A JSON response (not a login redirect) confirms the API key works.

List CML projects (find project ID):

```bash
curl -sS "$CAI_WORKBENCH_HOST/api/v2/projects?search_filter=izarkasie" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

### Step 7 — Deploy via GitHub target

Copy example config (optional — deploy script uses example + env overrides):

```bash
cp deploy/deployment-config.example.json deploy/deployment-config.local.json
# Edit github_url if needed; keep secrets out of this file — use .env
```

Run deploy:

```bash
python scripts/deploy.py \
  --config deploy/deployment-config.example.json \
  --wait 30
```

What happens internally:

1. POST `{ "deployment_payload": "<JSON>" }` to `/api/grpc/deployWorkflow`
2. Agent Studio clones `github_url` from the payload
3. Packages `workflow.yaml` + `collated_input.json` + `studio-data/` into `artifact.tar.gz`
4. Creates/updates CML Model + Application for the workflow
5. Injects `deployment_config.llm_config` (OpenAI key) at runtime

First deploy typically takes **5–10 minutes**.

### Step 8 — Monitor deployment

In the Agent Studio UI:

- **Agentic Workflows** → deployed workflows list

Or via API:

```bash
curl -sS "$AGENT_STUDIO_URL/api/grpc/listDeployedWorkflows" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

In CML project **Agent Studio - izarkasie**:

- Check **Models** and **Applications** for new resources

### Step 9 — Test the deployed workflow

After deployment completes, open the deployed workflow's **Application** URL in the workbench.

Kick off via application API:

```bash
APP_URL="https://<deployed-app-subdomain>.ml-1e596f2f-177.irz-tste.a465-9q4k.cloudera.site"

curl -sS -X POST "$APP_URL/api/workflow/kickoff" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"expression": "25 * 4 + 10"}}' | python3 -m json.tool
```

Note the `trace_id` in the response, then poll events:

```bash
curl -sS "$APP_URL/api/workflow/events?trace_id=<TRACE_ID>" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" | python3 -m json.tool
```

Task input key **`expression`** matches the `{expression}` placeholder in `collated_input.json` tasks.

### Step 10 — Iterate (GitOps loop)

1. Edit `collated_input.json`, tools, or tasks locally
2. `python scripts/validate.py`
3. `git commit && git push`
4. Re-run `python scripts/deploy.py ...`

---

## Deployment payload reference

`deploy/deployment-config.example.json`:

| Section | Purpose |
|---------|---------|
| `workflow_target.type: github` | Clone repo and package as artifact |
| `workflow_target.github_url` | Public/accessible Git URL |
| `deployment_target.type: workbench_model` | Deploy as CML Model + App |
| `deployment_config.generation_config` | LLM generation defaults |
| `deployment_config.llm_config` | Injected by `deploy.py` from `OPENAI_API_KEY` |
| `deployment_config.tool_config` | Tool user params (API keys for tools) |

The `default_language_model_id` in `collated_input.json` must match a key in `llm_config` when passing credentials at deploy time.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| GitHub clone fails during deploy | Private repo without credentials on workbench; use public repo or deploy keys |
| `workflow.yaml not found` | Files not at **repo root** — fix layout and push |
| Deploy job fails on LLM | Missing `OPENAI_API_KEY` in `.env` / `llm_config` |
| 302 / login HTML from API | Invalid or expired `CDSW_APIV2_KEY` |
| Tool venv build fails | Check `requirements.txt` in tool folder |

---

## Security notes

- **Never commit** `.env`, API keys, or `deploy/deployment-config.local.json`
- Rotate any API key that was shared in chat or logs
- Use CML project environment variables for shared team secrets where appropriate

---

## References

- [Custom Workflows (CollatedInput)](https://github.com/cloudera/CAI_STUDIO_AGENT/blob/main/docs/user_guide/custom_workflows.md)
- [Deployments guide](https://github.com/cloudera/CAI_STUDIO_AGENT/blob/main/docs/user_guide/deployments.md)
- Agent Studio deploy engine: `studio/deployments/entry.py` in CAI_STUDIO_AGENT
