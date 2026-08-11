# Tool reference

All 11 hybrid RAG tools shipped with the **Hybrid RAG Agentic Workflow**. Each tool is a Python venv tool under `studio-data/workflows/hybrid_rag_agentic/tools/<name>/`.

Tools return **JSON strings** (compact, no pretty-print) for agent consumption.

## Tool → agent assignment

| Tool | Agent |
|------|-------|
| `search_design_patterns` | Pattern Router |
| `get_design_pattern` | Pattern Router |
| `patterns_using_concept` | Pattern Router |
| `related_design_patterns` | Pattern Router |
| `traverse_pattern_neighborhood` | Pattern Router |
| `recommend_hybrid_agentic_workflow` | Pattern Router |
| `expand_design_patterns` | Pattern Router |
| `retrieve_pattern_technical_context` | Technical Researcher |
| `build_hybrid_context_bundle` | Technical Researcher |
| `validate_hybrid_retrieval` | Technical Researcher |
| `reflect_on_hybrid_retrieval` | Technical Researcher |

---

## Graph routing tools (Pattern Router)

### `search_design_patterns`

Search the knowledge graph for patterns matching a user question.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | — | User question |
| `limit` | int | 5 | Max patterns to return |

**Behavior:** If query contains "rag" (case-insensitive), returns RAG-linked patterns from the graph. Otherwise keyword-scores patterns on name, problem, solution, when_to_use, tradeoffs.

**Returns:** JSON array of pattern briefs: `{pattern_number, name, problem, when_to_use, tradeoffs}`.

**Example local test:**

```bash
python studio-data/workflows/hybrid_rag_agentic/tools/search_design_patterns/tool.py \
  --user-params '{}' \
  --tool-params '{"query": "enterprise RAG", "limit": 3}'
```

---

### `get_design_pattern`

Fetch full graph metadata for one pattern.

| Parameter | Type | Description |
|-----------|------|-------------|
| `pattern_number` | int | Pattern number 1–32 |

**Returns:** Pattern brief plus `solution`, `implementation_notes`, `related_patterns`. Error JSON if not found.

---

### `patterns_using_concept`

List patterns linked to a concept node in the graph.

| Parameter | Type | Description |
|-----------|------|-------------|
| `concept_name` | str | Concept name (e.g. `rag`, `reflection`) |

**Returns:** JSON array of pattern briefs.

---

### `related_design_patterns`

Find related patterns via `related_patterns` links and shared concepts.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern_number` | int | — | Anchor pattern |
| `limit` | int | 5 | Max related patterns |

**Returns:** De-duplicated JSON array of pattern briefs (excludes anchor).

---

### `traverse_pattern_neighborhood`

BFS traversal of the pattern graph (Index-Aware / graph-augmented retrieval — Pattern 9).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern_number` | int | — | Starting pattern |
| `max_depth` | int | 2 | Traversal depth (clamped 1–3) |

**Returns:** JSON with `start_pattern`, `max_depth`, `layers[]` (each layer has `depth` and `patterns[]`).

---

### `recommend_hybrid_agentic_workflow`

Return the canonical hybrid KG + text agentic workflow stack.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | User question for contextual pattern matching |

**Returns:** JSON with:

- `query`
- `domain`: `"generative_ai_design_patterns"`
- `recommended_stack`: 9-step agentic stack (Patterns 7, 9, 21, 13, 12, 23, 10, 17, 8)
- `query_matched_patterns`: top matching patterns for the query

---

### `expand_design_patterns`

Expand context with supplementary patterns (safety, production, excerpt refs, graph links).

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | User question driving expansion |

**Returns:** JSON with `primary_patterns`, `expanded_patterns`, `expansion_reasons` (map of pattern number → reason string).

Runs the full deterministic expansion pipeline without returning full technical text.

---

## Book retrieval tools (Technical Researcher)

### `retrieve_pattern_technical_context`

Retrieve book technical sections and code examples for one pattern.

| Parameter | Type | Description |
|-----------|------|-------------|
| `pattern_number` | int | Pattern number 1–32 |

**Returns:** JSON with:

- `pattern_number`, `name`, `slice` (source markdown file)
- `overview`, `problem`, `solution`, `implementation`, `caveats`
- `graph_implementation_notes`
- `code_blocks[]`
- `technical_text` (formatted LLM-ready summary)

Uses section-aware parsing of slice markdown. Locates best slice via heading anchors and excerpt scoring.

---

### `build_hybrid_context_bundle`

Run the full deterministic hybrid pipeline and return structured JSON context.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | User question |

**Returns:** JSON with:

- `query`
- `primary_patterns`, `expanded_patterns`, `expansion_reasons`
- `evidence[]` — top-k technical detail payloads (max 4000 chars each)
- `expanded_technical[]` — expanded pattern technical payloads (max 2500 chars each)

This is the most comprehensive single-shot retrieval tool.

---

### `validate_hybrid_retrieval`

Validate whether hybrid retrieval has sufficient graph + book coverage.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | User question |

**Returns:** JSON with:

- `passed` (bool) — true if at most one warning
- `warnings[]` — human-readable issues
- `metrics`: `{pattern_count, technical_sections, code_blocks, graph_and_text}`

Builds hybrid context, fuses/reranks, then validates.

---

### `reflect_on_hybrid_retrieval`

Self-RAG-style reflection: decide if retrieval is sufficient or needs expansion (Pattern 13).

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | User question |

**Returns:** JSON with:

- `action`: `"sufficient"` or `"expand"`
- `reason`: explanation
- `validation`: full validation payload

**Expansion triggers:**

- Validation failed (too many warnings)
- No code blocks retrieved
- Query mentions "agentic" but fewer than 5 patterns in bundle

---

## User parameters (all tools)

All tools accept optional **user parameters** via `HybridUserParameters`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `graph_path` | `data/graph.json` | Path to graph JSON (relative to workflow data root) |
| `slices_dir` | `data/slices` | Directory of slice markdown files |

These defaults work out of the box in the deployed artifact. Override only if relocating data files.

## Regenerating tools

Tools are generated from `TOOL_SPECS` in `scripts/bundle_hybrid_data.py`. After changing specs or toolkit methods:

```bash
python scripts/bundle_hybrid_data.py
python scripts/test_hybrid_tools.py
```

## Adding a new tool

1. Add method to `HybridRAGToolkit` in `converters/hybrid_rag_lib/hybrid_rag.py`.
2. Add entry to `TOOL_SPECS` in `scripts/bundle_hybrid_data.py`.
3. Add tool instance to `collated_input.json` and assign to an agent (or regenerate via `crewai_to_collated.py` + manual merge).
4. Run bundle + validation scripts.
