# Hybrid RAG Agentic Workflow (Phase 0 export)

Generated from [crew_hybrid](https://github.com/) CrewAI config via `scripts/crewai_to_collated.py`.

## Source

| CrewAI file | Role |
|-------------|------|
| `crew_hybrid/config/agents.yaml` | Agent personas |
| `crew_hybrid/config/tasks.yaml` | Task descriptions |
| `converters/crew_specs/crew_hybrid_agentic.yaml` | Tool assignments + workflow metadata |

Mode: **agentic** (3 agents, 3 tasks — no quality evaluator).

## Contents

- `collated_input.json` — 3 agents, 3 tasks, 11 stub tools
- `studio-data/workflows/hybrid_rag_agentic/tools/*` — Phase 0 stub `tool.py` files

Kickoff input placeholder: **`{query}`** (matches CrewAI `kickoff({"query": ...})`).

## Regenerate

```bash
python scripts/crewai_to_collated.py \
  --config-dir /path/to/crew_hybrid/config \
  --crew-spec converters/crew_specs/crew_hybrid_agentic.yaml \
  -o examples/crew_hybrid_agentic

python scripts/validate.py --root examples/crew_hybrid_agentic
```

## Phase 0 limitations

- Tools return stub responses — port `hybrid_rag_tools.py` in Phase 1
- No bundled `graph.json` / book slices yet
- Not deploy-ready until tools and data are implemented
