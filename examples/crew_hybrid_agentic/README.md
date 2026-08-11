# Hybrid RAG Agentic Workflow (Phase 0 export)

Generated from CrewAI `crew_hybrid` via `scripts/crewai_to_collated.py` + Phase 1 data bundling.

## Source

| CrewAI file | Role |
|-------------|------|
| `crew_hybrid/config/agents.yaml` | Agent personas |
| `crew_hybrid/config/tasks.yaml` | Task descriptions |
| `converters/crew_specs/crew_hybrid_agentic.yaml` | Tool assignments + workflow metadata |
| `generative_ai_design_patterns/outputs/merged/graph.json` | Knowledge graph (bundled) |
| `generative_ai_design_patterns/slices/by_50/*.md` | Book slices (bundled) |

Mode: **agentic** (3 agents, 3 tasks — no quality evaluator).

## Phase 1 status

| Tool | Status |
|------|--------|
| `search_design_patterns` | **Implemented** — graph search |
| `retrieve_pattern_technical_context` | **Implemented** — slice retrieval |
| All other tools | Phase 0 stub |

Shared library: `studio-data/workflows/hybrid_rag_agentic/lib/`

## Regenerate

```bash
# CollatedInput skeleton from CrewAI YAML
python scripts/crewai_to_collated.py \
  --config-dir /path/to/crew_hybrid/config \
  --crew-spec converters/crew_specs/crew_hybrid_agentic.yaml \
  -o examples/crew_hybrid_agentic

# Bundle graph, slices, lib, and Phase 1 tool implementations
python scripts/bundle_hybrid_data.py \
  --source /path/to/generative_ai_design_patterns

python scripts/validate.py --root examples/crew_hybrid_agentic
python scripts/test_hybrid_tools.py
```

Kickoff input: **`{query}`**

## Deploy note

Deploy from a Git repo whose root contains this artifact tree (or copy `examples/crew_hybrid_agentic/*` to repo root). Set `workflow_name` to **Hybrid RAG Agentic Workflow** in deploy config.

Remaining Phase 2 work: port remaining 9 tools, optional pre-crew pipeline wrapper.
