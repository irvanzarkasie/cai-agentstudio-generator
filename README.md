# cai-agentstudio-generator

Infrastructure-as-code (IaC) for **Cloudera AI Agent Studio** — a self-contained **Hybrid RAG Agentic Workflow** using **CollatedInput** and **GitHub deploy**.

Answers questions about *Generative AI Design Patterns* via a 3-agent pipeline: graph routing → book retrieval → architecture synthesis. Ported from CrewAI `crew_hybrid`.

**Everything needed to run is in this repo:** knowledge graph (32 patterns), book slices (14 files), 11 Python tools, workflow definition, and deploy scripts.

---

## Documentation

| Document | For whom |
|----------|----------|
| **[docs/MAINTAINER_GUIDE.md](docs/MAINTAINER_GUIDE.md)** | Full operational manual — setup, dev, deploy, troubleshoot |
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | System design, data flow, CollatedInput structure |
| **[docs/TOOL_REFERENCE.md](docs/TOOL_REFERENCE.md)** | All 11 tools — parameters, behavior, examples |
| **[AGENTS.md](AGENTS.md)** | Instructions for AI coding agents |
| **[docs/README.md](docs/README.md)** | Documentation index |

---

## What's in the repo

| Component | Location | Size / count |
|-----------|----------|--------------|
| Workflow definition | `workflow.yaml`, `collated_input.json` | 3 agents, 3 tasks |
| Knowledge graph | `studio-data/.../data/graph.json` | 32 patterns, 241 concepts |
| Book corpus | `studio-data/.../data/slices/pages_*.md` | 14 files (~1 MB) |
| Hybrid RAG toolkit | `converters/hybrid_rag_lib/` → copied to `studio-data/.../lib/` | Source of truth |
| Tools (all implemented) | `studio-data/.../tools/` | 11 Python venv tools |
| Deploy scripts | `scripts/deploy.py`, `validate.py`, etc. | |

No external corpus or CrewAI project is required at **deploy or runtime**.

---

## Quick start

### 1. Clone and configure

```bash
git clone git@github.com:irvanzarkasie/cai-agentstudio-generator.git
cd cai-agentstudio-generator

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env: CAI_WORKBENCH_HOST, AGENT_STUDIO_URL, CDSW_APIV2_KEY, OPENAI_API_KEY
set -a && source .env && set +a
```

### 2. Validate locally

```bash
python scripts/validate.py
python scripts/test_hybrid_tools.py
python scripts/verify_hybrid_mvp.py
```

Expected: all pass, `All 11 hybrid RAG tool smoke tests OK`.

### 3. Push and deploy

```bash
git push origin main

python scripts/deploy.py \
  --config deploy/deployment-config.example.json \
  --wait 300 \
  --insecure
```

First deploy takes 5–10 minutes. See [docs/MAINTAINER_GUIDE.md](docs/MAINTAINER_GUIDE.md) for monitoring and testing.

### 4. Test deployed workflow

```bash
curl -X POST "$APP_URL/api/workflow/kickoff" \
  -H "Authorization: Bearer $CDSW_APIV2_KEY" \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"query": "enterprise RAG with reranking"}}'
```

Kickoff input key: **`query`**.

---

## Repository layout

```text
.
├── workflow.yaml                 # CollatedInput manifest (must be at repo root)
├── collated_input.json           # Agents, tasks, tools, LLM config
├── studio-data/workflows/hybrid_rag_agentic/
│   ├── data/                     # graph.json + book slices (bundled corpus)
│   ├── lib/                      # HybridRAGToolkit runtime copy
│   └── tools/                    # 11 tool entrypoints (tool.py + requirements.txt)
├── converters/
│   ├── hybrid_rag_lib/           # Toolkit source of truth
│   └── crew_specs/               # CrewAI → CollatedInput mapping spec
├── scripts/
│   ├── validate.py               # Structural validation
│   ├── test_hybrid_tools.py      # All 11 tools smoke test
│   ├── verify_hybrid_mvp.py      # Deploy readiness gate
│   ├── bundle_hybrid_data.py     # Copy lib + regenerate tools (+ optional corpus refresh)
│   ├── crewai_to_collated.py     # CrewAI YAML → CollatedInput (regeneration)
│   └── deploy.py                 # Agent Studio GitHub deploy
├── deploy/deployment-config.example.json
├── docs/                         # Detailed documentation
├── AGENTS.md                     # AI agent instructions
├── .env.example
└── requirements-dev.txt
```

---

## Workflow overview

**Hybrid RAG Agentic Workflow** — sequential 3-agent pipeline:

| Agent | Role | Tools |
|-------|------|-------|
| Pattern Router | Graph search, neighborhood traversal, workflow stack | 7 graph tools |
| Technical Researcher | Book slice retrieval, validation, Self-RAG reflection | 4 retrieval tools |
| Solution Architect | Final architecture report | None (synthesis only) |

**Hybrid RAG pattern:** structured graph routing (`graph.json`) + section-aware book excerpt retrieval (markdown slices). No external vector DB at runtime.

---

## Common maintainer tasks

| Task | Command |
|------|---------|
| Validate before push | `python scripts/verify_hybrid_mvp.py` |
| Edit retrieval logic | Edit `converters/hybrid_rag_lib/hybrid_rag.py` → `python scripts/bundle_hybrid_data.py` |
| Edit agent prompts | Edit `collated_input.json` |
| Refresh corpus | `python scripts/bundle_hybrid_data.py --source /path/to/generative_ai_design_patterns` |
| Redeploy | `git push` then `python scripts/deploy.py ...` |

Full details: [docs/MAINTAINER_GUIDE.md](docs/MAINTAINER_GUIDE.md).

---

## Environment reference (irz-tstenv04)

| Item | Value |
|------|-------|
| CDP environment | `irz-tstenv04-cdp-env` |
| Workbench URL | `https://ml-1e596f2f-177.irz-tste.a465-9q4k.cloudera.site` |
| Agent Studio | `https://cai-agent-studio-svf4oc.ml-1e596f2f-177.irz-tste.a465-9q4k.cloudera.site` |
| CML project | `Agent Studio - izarkasie` |
| GitHub repo | `git@github.com:irvanzarkasie/cai-agentstudio-generator.git` |

---

## Prerequisites

1. Agent Studio installed in a CML project
2. OpenAI (`gpt-4o`) registered in Agent Studio
3. CML API v2 key (API + Application scope)
4. OpenAI API key for deploy-time `llm_config`
5. Python 3.10+ for local scripts
6. GitHub repo accessible from workbench

---

## CI

GitHub Actions (`.github/workflows/validate.yml`) runs `validate.py`, `test_hybrid_tools.py`, and `verify_hybrid_mvp.py` on every push/PR.

---

## Troubleshooting (quick)

| Symptom | See |
|---------|-----|
| Deploy fails on CML key | [MAINTAINER_GUIDE — internal key](docs/MAINTAINER_GUIDE.md#agent-studio-internal-cml-key) |
| GitHub clone fails | Repo must be accessible from workbench |
| `workflow.yaml not found` | Files must be at **repo root** |
| Workflow not editable in UI | Expected for GitHub deploy — use GitOps |
| Tool stub responses | Redeploy after Phase 2 push |

Full table: [docs/MAINTAINER_GUIDE.md#troubleshooting](docs/MAINTAINER_GUIDE.md#troubleshooting).

---

## Security

- Never commit `.env`, API keys, or `deploy/deployment-config.local.json`
- Rotate keys shared in chat or logs
- Tools read local files only — no tool API keys required

---

## References

- [Cloudera Custom Workflows (CollatedInput)](https://github.com/cloudera/CAI_STUDIO_AGENT/blob/main/docs/user_guide/custom_workflows.md)
- [Cloudera Deployments guide](https://github.com/cloudera/CAI_STUDIO_AGENT/blob/main/docs/user_guide/deployments.md)
