# Instructions for AI coding agents

This file tells automated agents (Cursor, Claude Code, etc.) how to work safely and effectively in this repository.

## Project purpose

**cai-agentstudio-generator** is an Infrastructure-as-Code (IaC) repository that defines a **Hybrid RAG Agentic Workflow** for **Cloudera AI Agent Studio**. It uses the **CollatedInput** format and deploys via the **GitHub target** (Agent Studio clones this repo at the root).

The workflow is a port of the open-source CrewAI project `crew_hybrid` from the *Generative AI Design Patterns* book corpus. All runtime data (knowledge graph + book slices) and all 11 Python tools are **bundled in this repo** under `studio-data/workflows/hybrid_rag_agentic/`.

## Golden rules

1. **Never commit secrets** — `.env`, API keys, `deploy/deployment-config.local.json`.
2. **Deployable files must live at repository root** — `workflow.yaml`, `collated_input.json`, `studio-data/`. Agent Studio's GitHub packaging clones the repo root; subfolder-only layouts fail deploy.
3. **Edit toolkit source in `converters/hybrid_rag_lib/`**, then run `python scripts/bundle_hybrid_data.py` to copy into `studio-data/.../lib/` and regenerate tool entrypoints.
4. **Do not hand-edit generated tool files** unless you also update `scripts/bundle_hybrid_data.py` `TOOL_SPECS` — tools are regenerated from specs.
5. **GitHub-deployed workflows are not editable in the Agent Studio UI** — changes flow through Git → push → redeploy.
6. **CollatedInput ≠ workflow template** — `collated_input.json` cannot be imported as a UI template zip.

## Repository map (what matters)

| Path | Role |
|------|------|
| `workflow.yaml` | Manifest: `type: collated_input`, points to `collated_input.json` |
| `collated_input.json` | Agents (3), tasks (3), tools (11), LLM config, workflow metadata |
| `studio-data/workflows/hybrid_rag_agentic/data/` | Bundled `graph.json` (32 patterns) + 14 book slice markdown files |
| `studio-data/workflows/hybrid_rag_agentic/lib/` | Runtime copy of `converters/hybrid_rag_lib/` |
| `studio-data/workflows/hybrid_rag_agentic/tools/<name>/` | Per-tool `tool.py` + `requirements.txt` |
| `converters/hybrid_rag_lib/hybrid_rag.py` | **Source of truth** for retrieval logic |
| `converters/crew_specs/crew_hybrid_agentic.yaml` | Agent→tool mapping for CrewAI regeneration |
| `scripts/bundle_hybrid_data.py` | Copy lib, optionally refresh corpus, regenerate all 11 tools |
| `scripts/crewai_to_collated.py` | Phase 0: CrewAI YAML → CollatedInput skeleton (needs external config dir) |
| `scripts/validate.py` | Pre-push structural validation |
| `scripts/test_hybrid_tools.py` | Local subprocess smoke test for all 11 tools |
| `scripts/verify_hybrid_mvp.py` | Full deploy-readiness gate |
| `scripts/deploy.py` | Trigger Agent Studio GitHub deploy via gRPC API |
| `deploy/deployment-config.example.json` | Deploy payload template |

## Common tasks

### Validate before any push

```bash
python scripts/validate.py
python scripts/test_hybrid_tools.py
python scripts/verify_hybrid_mvp.py
```

### Change a tool's behavior

1. Edit `converters/hybrid_rag_lib/hybrid_rag.py` (add/fix toolkit method).
2. If tool signature changes, update `TOOL_SPECS` in `scripts/bundle_hybrid_data.py`.
3. Run `python scripts/bundle_hybrid_data.py` (no `--source` needed if corpus unchanged).
4. Run validation scripts above.

### Change agents or tasks

Edit `collated_input.json` directly (prompts, tool assignments). Preserve UUID `id` fields unless intentionally creating new entities.

To regenerate from CrewAI YAML (requires external `crew_hybrid/config/`):

```bash
python scripts/crewai_to_collated.py \
  --config-dir /path/to/crew_hybrid/config \
  --crew-spec converters/crew_specs/crew_hybrid_agentic.yaml
python scripts/bundle_hybrid_data.py
```

### Refresh corpus from upstream

When the upstream docling-graph project produces new `graph.json` or slices:

```bash
export HYBRID_RAG_SOURCE=/path/to/generative_ai_design_patterns
python scripts/bundle_hybrid_data.py --source "$HYBRID_RAG_SOURCE"
```

### Deploy (human or agent with credentials)

Requires `.env` with `CDSW_APIV2_KEY`, `OPENAI_API_KEY`, `AGENT_STUDIO_URL`, `CAI_WORKBENCH_HOST`.

```bash
set -a && source .env && set +a
python scripts/deploy.py --config deploy/deployment-config.example.json --wait 300 --insecure
```

## Workflow runtime

- **Kickoff input:** `{"query": "your question"}` — `{query}` is interpolated in task descriptions.
- **Process:** sequential — Pattern Router → Technical Researcher → Solution Architect.
- **LLM:** `agent_studio_ds_model` (registered in Agent Studio; OpenAI `gpt-4o` still supported via `model_name: gpt-4o` + deploy `llm_config`).

## What NOT to do

- Do not move the workflow into a subfolder (breaks GitHub deploy).
- Do not add heavy dependencies to tool `requirements.txt` without testing venv build on workbench.
- Do not assume CrewAI source is in-repo — only the bundled artifact and converter specs are here.
- Do not force-push `main` without explicit user request.

## Further reading

- [docs/MAINTAINER_GUIDE.md](docs/MAINTAINER_GUIDE.md) — full operational manual
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design and data flow
- [docs/TOOL_REFERENCE.md](docs/TOOL_REFERENCE.md) — all 11 tools documented
- [README.md](README.md) — quick start
