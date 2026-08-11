# Workflow template import (GUI visualization)

GitHub-deployed workflows use **CollatedInput** (`collated_input.json`) and are **not editable** in the Agent Studio visual builder. To visualize and edit the same agents, tasks, and tools in the UI, export them as a **workflow template ZIP** and import it into Agent Studio.

## Quick path

```bash
# 1. Build template ZIP from current collated_input.json + bundled tools
python scripts/collated_to_workflow_template.py

# 2. Upload + import into your Agent Studio project (needs .env credentials)
set -a && source .env && set +a
python scripts/import_workflow_template.py --insecure
```

Then in Agent Studio:

1. Open **Workflows → Templates**
2. Find **Hybrid RAG Agentic Workflow**
3. Click **Create workflow from template**
4. Open the workflow in the visual builder (3 agents, 3 tasks, 11 tools)

## Manual import (UI only)

1. Run step 1 above to create `dist/hybrid_rag_agentic_workflow_template.zip`
2. In the **Agent Studio** CML project file browser, upload the ZIP to the **project root** (same level as `agent-studio/`)
3. In Agent Studio: **Workflows → Templates → Import Template**
4. Enter the relative path: `hybrid_rag_agentic_workflow_template.zip`  
   (the UI prefixes `/home/cdsw/` automatically)

## What the ZIP contains

Mirrors Cloudera’s template format (see `samples/calculator_workflow_template.zip`):

| Path | Purpose |
|------|---------|
| `workflow_template.json` | Workflow, agent, task, and tool template metadata |
| `studio-data/tool_templates/<tool>/` | Full tool source (code + vendored lib + corpus per tool) |

The converter assigns **new UUIDs** on each build so imports do not collide with prior templates.

## GitHub deploy vs UI template

| | GitHub deploy | UI template |
|---|---------------|-------------|
| Source of truth | `collated_input.json` in Git | Agent Studio database after import |
| Edit in UI | No | Yes |
| Production path | Recommended | Use for design/review; redeploy via Git for production |
| Sync | Re-run converter after prompt/tool changes in Git | Re-import or edit in UI separately |

After changing agents, tasks, or tools in Git, regenerate the template:

```bash
python scripts/collated_to_workflow_template.py
python scripts/import_workflow_template.py --insecure
```

## Troubleshooting

- **Import says file not found** — ZIP must live at `/home/cdsw/<filename>.zip` (project root upload), not inside `agent-studio/`.
- **Large ZIP (~4–5 MB)** — expected: 11 tools each vendoring `graph.json` and book slices for sandbox isolation.
- **Template imported but tools fail in UI test** — register `agentstudiomodel` and ensure tool venvs build; same requirements as GitHub deploy.
