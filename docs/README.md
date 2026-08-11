# Documentation index

Detailed documentation for **cai-agentstudio-generator**.

## Start here

| Audience | Document |
|----------|----------|
| New user / quick deploy | [../README.md](../README.md) |
| Maintainer / operator | [MAINTAINER_GUIDE.md](MAINTAINER_GUIDE.md) |
| AI coding agent | [../AGENTS.md](../AGENTS.md) |
| System design | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Tool API reference | [TOOL_REFERENCE.md](TOOL_REFERENCE.md) |

## Document summaries

### [MAINTAINER_GUIDE.md](MAINTAINER_GUIDE.md)

Complete operational manual: setup, daily workflow, validation, deploy, testing deployed workflows, corpus updates, CrewAI regeneration, troubleshooting, security, CI, and pre-push checklist.

### [ARCHITECTURE.md](ARCHITECTURE.md)

Technical deep dive: CollatedInput structure, agent pipeline, bundled data, toolkit modules, tool execution model, hybrid context pipeline, deploy architecture, GitHub vs UI builder, CrewAI migration lineage, extension points.

### [TOOL_REFERENCE.md](TOOL_REFERENCE.md)

All 11 tools: parameters, behavior, return shapes, agent assignments, local test examples, and how to add new tools.

### [../AGENTS.md](../AGENTS.md)

Concise instructions for automated coding agents: golden rules, repo map, common tasks, anti-patterns.

## Quick command reference

```bash
# Setup
cp .env.example .env && pip install -r requirements-dev.txt

# Validate (run before every push)
python scripts/validate.py
python scripts/test_hybrid_tools.py
python scripts/verify_hybrid_mvp.py

# Refresh toolkit/tools after editing converters/hybrid_rag_lib/
python scripts/bundle_hybrid_data.py

# Refresh corpus from upstream (optional)
python scripts/bundle_hybrid_data.py --source /path/to/generative_ai_design_patterns

# Deploy
python scripts/deploy.py --config deploy/deployment-config.example.json --wait 300 --insecure
```
