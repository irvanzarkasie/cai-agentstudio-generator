"""
Hybrid RAG toolkit for Agent Studio tools (Phase 2).

Vendored from docling-conv-docs generative_ai_design_patterns:
  demo_hybrid_agent.py, hybrid_rag_tools.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SECTION_HEADING_PREFIX = "Pattern"
ENTITY_ID_FIELD = "pattern_number"
ENTITY_GRAPH_LABEL = "DesignPattern"
CONCEPT_GRAPH_LABEL = "Concept"
USES_CONCEPT_EDGE = "USES_CONCEPT"
SLICE_GLOB = "pages_*.md"
LOW_QUALITY_SLICE_PREFIXES = ("pages_001-050",)
SEARCH_FIELDS = ("name", "problem", "solution", "when_to_use", "tradeoffs")
SUMMARY_FIELDS = ("problem", "solution", "when_to_use", "tradeoffs")
PRODUCTION_SAFETY_TERMS = {
    "production", "hallucin", "guardrail", "safeguard", "validate", "validation",
    "safety", "reliable", "fact", "deploy",
}
PRODUCTION_SAFETY_PATTERNS = (31, 32, 17, 18, 10)

AGENTIC_STACK: list[dict[str, Any]] = [
    {
        "order": 1,
        "pattern_number": 7,
        "name": "Semantic Indexing",
        "implementation_in_our_stack": "Merged graph.json + slices/by_50/ as dual indexes (structured + text).",
    },
    {
        "order": 2,
        "pattern_number": 9,
        "name": "Index-Aware Retrieval",
        "implementation_in_our_stack": "Graph search → pattern neighborhood traversal → slice excerpt retrieval.",
    },
    {
        "order": 3,
        "pattern_number": 21,
        "name": "Tool Calling",
        "implementation_in_our_stack": "Agent Studio tools: search, traverse, retrieve_pattern_technical_context.",
    },
    {
        "order": 4,
        "pattern_number": 13,
        "name": "Self-RAG (Reflection in RAG)",
        "implementation_in_our_stack": "Reflection gate: validate bundle → expand if insufficient.",
    },
    {
        "order": 5,
        "pattern_number": 12,
        "name": "Corrective RAG (CRAG)",
        "implementation_in_our_stack": "One corrective re-retrieval pass when validation warns.",
    },
    {
        "order": 6,
        "pattern_number": 23,
        "name": "Multiagent Collaboration",
        "implementation_in_our_stack": "Agent Studio router + researcher + architect agents.",
    },
    {
        "order": 7,
        "pattern_number": 10,
        "name": "Node Postprocessing",
        "implementation_in_our_stack": "Deterministic fuse_and_rerank_context() before synthesis.",
    },
    {
        "order": 8,
        "pattern_number": 17,
        "name": "LLM-as-Judge",
        "implementation_in_our_stack": "Optional quality evaluation on final answer.",
    },
    {
        "order": 9,
        "pattern_number": 8,
        "name": "Indexing at Scale",
        "implementation_in_our_stack": "Offline graph merge + slice maintenance pipeline.",
    },
]
TECHNICAL_SECTION_KEYS = ("overview", "problem", "solution", "implementation", "caveats")
TECHNICAL_HEADING_RULES: tuple[tuple[str, str], ...] = (
    ("problem", "problem"),
    ("solution", "solution"),
    ("implementation", "implementation"),
    ("example", "implementation"),
    ("how ", "implementation"),
    ("step ", "implementation"),
    ("caveat", "caveats"),
    ("consideration", "caveats"),
    ("tradeoff", "caveats"),
)
CODE_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "by", "for", "in", "is", "of", "on",
    "or", "the", "to", "with",
}
CHAPTER_GRAPH_LABEL = "Chapter"
BELONGS_TO_EDGE = "BELONGS_TO"
CHAPTER_REF_RE = re.compile(r"\bchapter\s+(\d+)\b", re.IGNORECASE)
PATTERN_REF_RE = re.compile(r"Pattern\s+(?:\[)?(\d+)(?:\])?", re.IGNORECASE)


def query_terms(query: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9]+", query.casefold()))
    return {t for t in terms if t not in STOPWORDS and len(t) >= 3}


def score_pattern(pattern: dict[str, Any], terms: set[str]) -> float:
    if not terms:
        return 0.0
    blob = " ".join(str(pattern.get(k) or "") for k in SEARCH_FIELDS).casefold()
    return sum(1 for term in terms if term in blob) / len(terms)


def search_patterns(patterns: list[dict[str, Any]], query: str, limit: int = 5) -> list[dict[str, Any]]:
    terms = query_terms(query)
    scored = [(score_pattern(p, terms), p) for p in patterns]
    scored = [(s, p) for s, p in scored if s > 0]
    scored.sort(key=lambda x: (-x[0], x[1].get("pattern_number", 0)))
    return [p for _, p in scored[:limit]]


def infer_chapter_from_notes(pattern: dict[str, Any]) -> int | None:
    for field in ("implementation_notes", "solution", "when_to_use", "problem"):
        text = str(pattern.get(field) or "")
        match = CHAPTER_REF_RE.search(text)
        if match:
            return int(match.group(1))
    return None


def pattern_brief(
    pattern: dict[str, Any],
    *,
    chapter_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brief: dict[str, Any] = {
        "pattern_number": pattern.get("pattern_number"),
        "name": pattern.get("name"),
        "problem": pattern.get("problem"),
        "when_to_use": pattern.get("when_to_use"),
        "tradeoffs": pattern.get("tradeoffs"),
    }
    chapter_number = None
    chapter_title = None
    if chapter_info:
        chapter_number = chapter_info.get("chapter_number")
        chapter_title = chapter_info.get("chapter_title") or chapter_info.get("chapter_theme")
    elif pattern.get("chapter") is not None:
        chapter_number = pattern.get("chapter")
    else:
        chapter_number = infer_chapter_from_notes(pattern)
    if chapter_number is not None:
        brief["chapter_number"] = chapter_number
    if chapter_title:
        brief["chapter_title"] = chapter_title
    return brief


class PatternGraphIndex:
    def __init__(self, graph_path: Path) -> None:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        self.patterns = {
            int(n[ENTITY_ID_FIELD]): n
            for n in data.get("nodes", [])
            if n.get("label") == ENTITY_GRAPH_LABEL and n.get(ENTITY_ID_FIELD) is not None
        }
        self.concept_patterns: dict[str, list[int]] = {}
        self.pattern_concepts: dict[int, set[str]] = {}
        self.pattern_chapters: dict[int, dict[str, Any]] = {}
        nodes = {n["id"]: n for n in data.get("nodes", [])}
        for edge in data.get("edges", []):
            if edge.get("label") == BELONGS_TO_EDGE:
                src = nodes.get(edge["source"], {})
                tgt = nodes.get(edge["target"], {})
                if (
                    src.get("label") == ENTITY_GRAPH_LABEL
                    and tgt.get("label") == CHAPTER_GRAPH_LABEL
                    and src.get(ENTITY_ID_FIELD) is not None
                ):
                    pn = int(src[ENTITY_ID_FIELD])
                    self.pattern_chapters[pn] = {
                        "chapter_number": tgt.get("number"),
                        "chapter_title": tgt.get("title"),
                        "chapter_theme": tgt.get("theme"),
                    }
        for edge in data.get("edges", []):
            if edge.get("label") != USES_CONCEPT_EDGE:
                continue
            src = nodes.get(edge["source"], {})
            tgt = nodes.get(edge["target"], {})
            if src.get("label") == ENTITY_GRAPH_LABEL and tgt.get("label") == CONCEPT_GRAPH_LABEL:
                pn = int(src[ENTITY_ID_FIELD])
                concept = tgt["name"].casefold()
                self.concept_patterns.setdefault(concept, []).append(pn)
                self.pattern_concepts.setdefault(pn, set()).add(concept)

    def get_pattern(self, pattern_number: int) -> dict[str, Any] | None:
        return self.patterns.get(pattern_number)

    def chapter_for(self, pattern_number: int) -> dict[str, Any] | None:
        return self.pattern_chapters.get(pattern_number)

    def brief(self, pattern: dict[str, Any]) -> dict[str, Any]:
        pn = int(pattern[ENTITY_ID_FIELD])
        return pattern_brief(pattern, chapter_info=self.chapter_for(pn))

    def rag_patterns(self) -> list[dict[str, Any]]:
        ids = sorted(set(self.concept_patterns.get("rag", [])))
        return [self.patterns[i] for i in ids if i in self.patterns]

    def all_patterns(self) -> list[dict[str, Any]]:
        return list(self.patterns.values())

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return search_patterns(self.all_patterns(), query, limit=limit)

    def get_related_patterns(self, pattern_number: int, limit: int = 4) -> list[dict[str, Any]]:
        pattern = self.get_pattern(pattern_number)
        if not pattern:
            return []
        related: list[dict[str, Any]] = []
        seen = {pattern_number}
        for rel in pattern.get("related_patterns") or []:
            pn = rel.get("pattern_number")
            if pn is None or pn in seen:
                continue
            row = self.get_pattern(int(pn))
            if row:
                related.append(row)
                seen.add(int(pn))
            if len(related) >= limit:
                break
        return related

    def patterns_sharing_concepts(self, pattern_number: int, limit: int = 3) -> list[dict[str, Any]]:
        concepts = self.pattern_concepts.get(pattern_number, set())
        if not concepts:
            return []
        overlap: Counter[int] = Counter()
        for concept in concepts:
            for pn in self.concept_patterns.get(concept, []):
                if pn != pattern_number:
                    overlap[pn] += 1
        related: list[dict[str, Any]] = []
        for pn, _ in overlap.most_common(limit):
            row = self.get_pattern(pn)
            if row:
                related.append(row)
        return related

    def patterns_using_concept(self, concept_name: str) -> list[dict[str, Any]]:
        ids = self.concept_patterns.get(concept_name.casefold(), [])
        return [self.patterns[i] for i in ids if i in self.patterns]


def normalize_slice_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\t", " ", text)
    text = re.sub(r"<!-- image -->", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_text(text: str, max_chars: int) -> str:
    text = normalize_slice_text(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def classify_technical_heading(heading: str) -> str | None:
    normalized = re.sub(r"\s+", " ", heading.casefold().strip())
    for needle, bucket in TECHNICAL_HEADING_RULES:
        if needle in normalized:
            return bucket
    return None


def extract_code_blocks(section_text: str, *, max_blocks: int = 4, max_block_chars: int = 1200) -> list[str]:
    blocks: list[str] = []
    for match in CODE_BLOCK_RE.finditer(section_text):
        block = normalize_slice_text(match.group(1))
        if not block or len(block) < 8:
            continue
        blocks.append(truncate_text(block, max_block_chars))
        if len(blocks) >= max_blocks:
            break
    return blocks


def parse_pattern_section(section_text: str, *, section_budget: int) -> dict[str, Any]:
    section_text = normalize_slice_text(section_text)
    per_section = max(400, section_budget // 5)
    sections: dict[str, list[str]] = {key: [] for key in TECHNICAL_SECTION_KEYS}
    current_key = "overview"

    for part in re.split(r"(?m)^##\s+", section_text):
        part = part.strip()
        if not part:
            continue
        heading, _, body = part.partition("\n")
        bucket = classify_technical_heading(heading)
        if bucket:
            current_key = bucket
        elif re.match(r"^pattern\s+\d+\s*:", heading, re.IGNORECASE):
            current_key = "overview"
            body = part
        if body.strip():
            sections[current_key].append(body.strip())

    overview = truncate_text("\n\n".join(sections["overview"]), per_section)
    problem = truncate_text("\n\n".join(sections["problem"]), per_section)
    solution = truncate_text("\n\n".join(sections["solution"]), per_section)
    implementation = truncate_text("\n\n".join(sections["implementation"]), per_section * 2)
    caveats = truncate_text("\n\n".join(sections["caveats"]), per_section)
    code_blocks = extract_code_blocks(section_text)
    if not implementation and code_blocks:
        implementation = "See code examples below for concrete API usage and processing steps."

    return {
        "overview": overview,
        "problem": problem,
        "solution": solution,
        "implementation": implementation,
        "caveats": caveats,
        "code_blocks": code_blocks,
    }


def find_pattern_section_bounds(
    text: str,
    pattern_number: int,
    *,
    pattern_name: str = "",
) -> tuple[int, int] | None:
    prefix = SECTION_HEADING_PREFIX
    anchors: list[re.Pattern[str]] = [
        re.compile(rf"^#+\s*{prefix}\s+{pattern_number}\s*:", re.MULTILINE | re.IGNORECASE),
    ]
    if pattern_name:
        name_pattern = re.escape(pattern_name).replace(r"\ ", r"\s+")
        anchors.insert(
            0,
            re.compile(
                rf"^#+\s*{prefix}\s+{pattern_number}\s*:\s*{name_pattern}",
                re.MULTILINE | re.IGNORECASE,
            ),
        )
    next_pattern = re.compile(rf"^#+\s*{prefix}\s+\d+\s*:", re.MULTILINE | re.IGNORECASE)

    best_start: int | None = None
    for anchor in anchors:
        match = anchor.search(text)
        if match:
            best_start = match.start()
            break
    if best_start is None:
        return None

    next_match = next_pattern.search(text, best_start + 1)
    end = next_match.start() if next_match else len(text)
    return best_start, end


def extract_pattern_refs(text: str) -> set[int]:
    return {int(match) for match in PATTERN_REF_RE.findall(text)}


def score_excerpt_match(md_path: Path, text: str, match: re.Match[str], pattern_number: int) -> float:
    score = 0.0
    line_start = text.rfind("\n", 0, match.start()) + 1
    line = text[line_start : match.start() + 80]
    if re.match(rf"^#+\s*{SECTION_HEADING_PREFIX}\s+", line, re.IGNORECASE):
        score += 100.0
    window = text[max(0, match.start() - 100) : match.end() + 800]
    if len(extract_pattern_refs(window)) > 8:
        score -= 50.0
    if any(md_path.name.startswith(prefix) for prefix in LOW_QUALITY_SLICE_PREFIXES) and score < 100.0:
        score -= 30.0
    if match.start() > 5000:
        score += 5.0
    return score


def locate_best_pattern_slice(
    slices_dir: Path,
    pattern_number: int,
    *,
    pattern_name: str = "",
) -> tuple[str, str] | None:
    best: tuple[str, str, float] | None = None
    fallback = re.compile(rf"{SECTION_HEADING_PREFIX}\s+{pattern_number}\b", re.IGNORECASE)

    for md_path in sorted(slices_dir.glob(SLICE_GLOB)):
        text = md_path.read_text(encoding="utf-8")
        bounds = find_pattern_section_bounds(text, pattern_number, pattern_name=pattern_name)
        if bounds:
            start, end = bounds
            score = 100.0 + (start / 10000.0)
            if any(md_path.name.startswith(prefix) for prefix in LOW_QUALITY_SLICE_PREFIXES):
                score -= 20.0
            if score > (best[2] if best else -1.0):
                best = (md_path.name, text[start:end], score)
            continue

        match = fallback.search(text)
        if not match:
            continue
        score = score_excerpt_match(md_path, text, match, pattern_number) - 20.0
        if score <= (best[2] if best else -1.0):
            continue
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 3000)
        best = (md_path.name, text[start:end], score)

    if not best:
        return None
    return best[0], best[1]


@dataclass
class PatternTechnicalDetail:
    pattern: dict[str, Any]
    slice_name: str
    overview: str = ""
    problem: str = ""
    solution: str = ""
    implementation: str = ""
    caveats: str = ""
    code_blocks: list[str] = field(default_factory=list)
    graph_implementation_notes: str = ""

    @property
    def excerpt(self) -> str:
        return self.as_technical_text()

    def as_technical_text(self, *, max_chars: int | None = None) -> str:
        parts = [f"Source: {self.slice_name}"]
        pn = self.pattern.get(ENTITY_ID_FIELD)
        parts.append(f"{SECTION_HEADING_PREFIX} {pn}: {self.pattern.get('name')}")
        for label, value in (
            ("Overview", self.overview),
            ("Problem (book)", self.problem),
            ("Solution (book)", self.solution),
            ("Implementation (book)", self.implementation),
            ("Graph implementation notes", self.graph_implementation_notes),
            ("Caveats / considerations", self.caveats),
        ):
            if value:
                parts.append(f"\n{label}:\n{value}")
        if self.code_blocks:
            parts.append("\nCode examples from the book:")
            for idx, block in enumerate(self.code_blocks, start=1):
                parts.append(f"\n--- Example {idx} ---\n{block}")
        text = "\n".join(parts).strip()
        if max_chars and len(text) > max_chars:
            return text[: max_chars - 3].rstrip() + "..."
        return text


def retrieve_pattern_technical_detail(
    pattern: dict[str, Any],
    slices_dir: Path,
    *,
    section_budget: int = 4000,
    include_graph_notes: bool = True,
) -> PatternTechnicalDetail:
    pn = int(pattern[ENTITY_ID_FIELD])
    pattern_name = str(pattern.get("name") or "")
    located = locate_best_pattern_slice(slices_dir, pn, pattern_name=pattern_name)
    if not located:
        return PatternTechnicalDetail(
            pattern=pattern,
            slice_name="(not found)",
            overview=f"No technical section found for {SECTION_HEADING_PREFIX} {pn}.",
            graph_implementation_notes=str(pattern.get("implementation_notes") or "")
            if include_graph_notes
            else "",
        )

    slice_name, section_text = located
    parsed = parse_pattern_section(section_text, section_budget=section_budget)
    graph_notes = str(pattern.get("implementation_notes") or "").strip() if include_graph_notes else ""

    return PatternTechnicalDetail(
        pattern=pattern,
        slice_name=slice_name,
        overview=parsed["overview"],
        problem=parsed["problem"] or str(pattern.get("problem") or ""),
        solution=parsed["solution"] or str(pattern.get("solution") or ""),
        implementation=parsed["implementation"],
        caveats=parsed["caveats"] or str(pattern.get("tradeoffs") or ""),
        code_blocks=parsed["code_blocks"],
        graph_implementation_notes=graph_notes,
    )


def query_implies_production_safety(query: str) -> bool:
    terms = query_terms(query)
    return bool(terms & PRODUCTION_SAFETY_TERMS)


def format_pattern_summary(pattern: dict[str, Any], *, heading: bool = True) -> str:
    pn = pattern.get("pattern_number")
    name = pattern.get("name")
    lines = [f"## Pattern {pn}: {name}"] if heading else []
    for field_name in SUMMARY_FIELDS:
        value = pattern.get(field_name)
        if value:
            label = field_name.replace("_", " ").title()
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def collect_evidence(
    rows: list[dict[str, Any]],
    slices_dir: Path,
    top_k: int,
    *,
    tech_chars: int,
) -> list[PatternTechnicalDetail]:
    evidence: list[PatternTechnicalDetail] = []
    for row in rows[:top_k]:
        evidence.append(
            retrieve_pattern_technical_detail(row, slices_dir, section_budget=tech_chars)
        )
    return evidence


def collect_expanded_technical(
    expanded_patterns: list[dict[str, Any]],
    slices_dir: Path,
    *,
    tech_chars: int,
) -> list[PatternTechnicalDetail]:
    return [
        retrieve_pattern_technical_detail(pattern, slices_dir, section_budget=tech_chars)
        for pattern in expanded_patterns
    ]


def expand_context_patterns(
    router: PatternGraphIndex,
    slices_dir: Path,
    primary_patterns: list[dict[str, Any]],
    evidence: list[PatternTechnicalDetail],
    query: str,
    *,
    max_expanded: int = 6,
    expand_related: bool = True,
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    seen = {int(p["pattern_number"]) for p in primary_patterns}
    candidates: dict[int, tuple[float, str]] = {}

    def add_candidate(pn: int, score: float, reason: str) -> None:
        if pn in seen or pn in candidates:
            return
        candidates[pn] = (score, reason)

    for item in evidence:
        source_pn = int(item.pattern["pattern_number"])
        for pn in extract_pattern_refs(item.excerpt):
            add_candidate(
                pn,
                50.0,
                f"referenced in excerpt for Pattern {source_pn}",
            )

    if query_implies_production_safety(query):
        for pn in PRODUCTION_SAFETY_PATTERNS:
            add_candidate(pn, 45.0, "query mentions production, safety, or hallucination")

    if expand_related:
        for pattern in primary_patterns[:3]:
            pn = int(pattern["pattern_number"])
            for related in router.get_related_patterns(pn, limit=4):
                rpn = int(related["pattern_number"])
                add_candidate(rpn, 35.0, f"graph neighbor of Pattern {pn}")
            for related in router.patterns_sharing_concepts(pn, limit=3):
                rpn = int(related["pattern_number"])
                add_candidate(rpn, 30.0, f"shares concepts with Pattern {pn}")

    ranked = sorted(candidates.items(), key=lambda item: (-item[1][0], item[0]))
    expanded: list[dict[str, Any]] = []
    reasons: dict[int, str] = {}
    for pn, (_, reason) in ranked[:max_expanded]:
        pattern = router.get_pattern(pn)
        if not pattern:
            continue
        expanded.append(pattern)
        reasons[pn] = reason
    return expanded, reasons


@dataclass
class HybridContextBundle:
    query: str
    primary_patterns: list[dict[str, Any]]
    expanded_patterns: list[dict[str, Any]]
    expansion_reasons: dict[int, str]
    evidence: list[PatternTechnicalDetail]
    expanded_technical: list[PatternTechnicalDetail]

    def to_llm_context(self) -> str:
        parts = [
            f"User question:\n{self.query}\n",
            "MAIN CONTEXT — Book technical implementations:\n",
        ]
        for detail in self.evidence:
            pn = detail.pattern.get("pattern_number")
            parts.append(f"### Pattern {pn}: {detail.pattern.get('name')}")
            parts.append(detail.as_technical_text(max_chars=6000))
            parts.append("")
        for detail in self.expanded_technical:
            pn = int(detail.pattern["pattern_number"])
            reason = self.expansion_reasons.get(pn, "graph expansion")
            parts.append(f"### Pattern {pn}: {detail.pattern.get('name')} [{reason}]")
            parts.append(detail.as_technical_text(max_chars=3500))
            parts.append("")
        parts.append("Supporting graph summaries:\n")
        for pattern in self.primary_patterns:
            parts.append(format_pattern_summary(pattern))
            parts.append("")
        return "\n".join(parts)


def detail_payload(detail: PatternTechnicalDetail, *, max_chars: int | None = None) -> dict[str, Any]:
    pn = detail.pattern.get("pattern_number")
    chapter_info = None
    if pn is not None:
        chapter_info = infer_chapter_from_notes(detail.pattern)
    payload: dict[str, Any] = {
        "pattern_number": pn,
        "name": detail.pattern.get("name"),
        "slice": detail.slice_name,
        "overview": detail.overview,
        "problem": detail.problem,
        "solution": detail.solution,
        "implementation": detail.implementation,
        "graph_implementation_notes": detail.graph_implementation_notes,
        "caveats": detail.caveats,
        "code_blocks": detail.code_blocks,
        "technical_text": detail.as_technical_text(max_chars=max_chars),
    }
    if chapter_info is not None:
        payload["chapter_number"] = chapter_info
    return payload


class HybridRAGToolkit:
    """Graph + slice retrieval for Agent Studio hybrid RAG tools."""

    def __init__(self, graph_path: Path, slices_dir: Path) -> None:
        self.graph_path = graph_path
        self.slices_dir = slices_dir
        self.router = PatternGraphIndex(graph_path)

    def search_design_patterns(self, query: str, limit: int = 5) -> str:
        if "rag" in query.casefold():
            rows = self.router.rag_patterns()[:limit]
        else:
            rows = self.router.search(query, limit=limit)
        return json.dumps([self.router.brief(p) for p in rows], separators=(",", ":"))

    def retrieve_pattern_technical_context(self, pattern_number: int) -> str:
        pattern = self.router.get_pattern(pattern_number)
        if not pattern:
            return json.dumps({"error": f"Pattern {pattern_number} not found"})
        detail = retrieve_pattern_technical_detail(pattern, self.slices_dir)
        payload = detail_payload(detail)
        chapter = self.router.chapter_for(pattern_number)
        if chapter and chapter.get("chapter_number") is not None:
            payload["chapter_number"] = chapter["chapter_number"]
            title = chapter.get("chapter_title") or chapter.get("chapter_theme")
            if title:
                payload["chapter_title"] = title
        return json.dumps(payload, separators=(",", ":"))

    def get_design_pattern(self, pattern_number: int) -> str:
        pattern = self.router.get_pattern(pattern_number)
        if not pattern:
            return json.dumps({"error": f"Pattern {pattern_number} not found"})
        payload = self.router.brief(pattern)
        payload["solution"] = pattern.get("solution")
        payload["implementation_notes"] = pattern.get("implementation_notes")
        payload["related_patterns"] = pattern.get("related_patterns") or []
        return json.dumps(payload, separators=(",", ":"))

    def patterns_using_concept(self, concept_name: str) -> str:
        rows = self.router.patterns_using_concept(concept_name)
        return json.dumps([self.router.brief(p) for p in rows], separators=(",", ":"))

    def related_design_patterns(self, pattern_number: int, limit: int = 5) -> str:
        related = self.router.get_related_patterns(pattern_number, limit=limit)
        shared = self.router.patterns_sharing_concepts(pattern_number, limit=limit)
        seen = {pattern_number}
        merged: list[dict[str, Any]] = []
        for row in related + shared:
            pn = int(row["pattern_number"])
            if pn in seen:
                continue
            seen.add(pn)
            merged.append(self.router.brief(row))
        return json.dumps(merged, separators=(",", ":"))

    def traverse_pattern_neighborhood(self, pattern_number: int, max_depth: int = 2) -> str:
        max_depth = max(1, min(max_depth, 3))
        start = self.router.get_pattern(pattern_number)
        if not start:
            return json.dumps({"error": f"Pattern {pattern_number} not found"})

        seen = {pattern_number}
        frontier = [pattern_number]
        layers: list[dict[str, Any]] = []
        for depth in range(max_depth):
            next_frontier: list[int] = []
            layer_patterns: list[dict[str, Any]] = []
            for pn in frontier:
                for row in self.router.get_related_patterns(pn, limit=6):
                    rpn = int(row["pattern_number"])
                    if rpn in seen:
                        continue
                    seen.add(rpn)
                    next_frontier.append(rpn)
                    layer_patterns.append(self.router.brief(row))
                for row in self.router.patterns_sharing_concepts(pn, limit=4):
                    rpn = int(row["pattern_number"])
                    if rpn in seen:
                        continue
                    seen.add(rpn)
                    next_frontier.append(rpn)
                    layer_patterns.append(self.router.brief(row))
            if layer_patterns:
                layers.append({"depth": depth + 1, "patterns": layer_patterns})
            frontier = next_frontier
            if not frontier:
                break

        return json.dumps(
            {
                "start_pattern": self.router.brief(start),
                "max_depth": max_depth,
                "linked_slice_hint": "Use retrieve_pattern_technical_context for each discovered pattern.",
                "layers": layers,
            },
            separators=(",", ":"),
        )

    def recommend_hybrid_agentic_workflow(self, query: str) -> str:
        matched = (
            self.router.search(query, limit=5)
            if "rag" not in query.casefold()
            else self.router.rag_patterns()[:5]
        )
        return json.dumps(
            {
                "query": query,
                "domain": "generative_ai_design_patterns",
                "recommended_stack": AGENTIC_STACK,
                "query_matched_patterns": [self.router.brief(p) for p in matched],
            },
            separators=(",", ":"),
        )

    def build_hybrid_context(
        self,
        query: str,
        *,
        top_k: int = 3,
        tech_chars: int = 4000,
        expanded_tech_chars: int = 2500,
        max_expanded: int = 6,
    ) -> HybridContextBundle:
        if "rag" in query.casefold():
            primary = self.router.rag_patterns()[:6]
        else:
            primary = self.router.search(query, limit=5)

        evidence = collect_evidence(primary, self.slices_dir, top_k=top_k, tech_chars=tech_chars)
        expanded, reasons = expand_context_patterns(
            self.router,
            self.slices_dir,
            primary,
            evidence,
            query,
            max_expanded=max_expanded,
            expand_related=True,
        )
        expanded_technical = collect_expanded_technical(
            expanded,
            self.slices_dir,
            tech_chars=expanded_tech_chars,
        )
        return HybridContextBundle(
            query=query,
            primary_patterns=primary,
            expanded_patterns=expanded,
            expansion_reasons=reasons,
            evidence=evidence,
            expanded_technical=expanded_technical,
        )

    def build_hybrid_context_json(self, query: str, **kwargs: Any) -> str:
        bundle = self.build_hybrid_context(query, **kwargs)
        return json.dumps(
            {
                "query": bundle.query,
                "primary_patterns": [self.router.brief(p) for p in bundle.primary_patterns],
                "expanded_patterns": [self.router.brief(p) for p in bundle.expanded_patterns],
                "expansion_reasons": bundle.expansion_reasons,
                "evidence": [detail_payload(d, max_chars=4000) for d in bundle.evidence],
                "expanded_technical": [
                    detail_payload(d, max_chars=2500) for d in bundle.expanded_technical
                ],
            },
            separators=(",", ":"),
        )

    def expand_design_patterns(self, query: str) -> str:
        bundle = self.build_hybrid_context(query)
        return json.dumps(
            {
                "primary_patterns": [self.router.brief(p) for p in bundle.primary_patterns[:5]],
                "expanded_patterns": [self.router.brief(p) for p in bundle.expanded_patterns],
                "expansion_reasons": {str(k): v for k, v in bundle.expansion_reasons.items()},
            },
            separators=(",", ":"),
        )

    def _score_technical_detail(self, detail: PatternTechnicalDetail, terms: set[str]) -> float:
        blob = detail.as_technical_text(max_chars=4000).casefold()
        term_score = sum(1 for t in terms if t in blob) / max(len(terms), 1)
        code_bonus = 0.15 if detail.code_blocks else 0.0
        impl_bonus = 0.1 if detail.implementation else 0.0
        return term_score + code_bonus + impl_bonus

    def fuse_and_rerank_context(self, bundle: HybridContextBundle, query: str) -> HybridContextBundle:
        terms = query_terms(query)
        evidence = sorted(
            bundle.evidence,
            key=lambda d: self._score_technical_detail(d, terms),
            reverse=True,
        )
        expanded_technical = sorted(
            bundle.expanded_technical,
            key=lambda d: self._score_technical_detail(d, terms),
            reverse=True,
        )
        seen: set[int] = set()
        primary: list[dict[str, Any]] = []
        for row in bundle.primary_patterns + bundle.expanded_patterns:
            pn = int(row["pattern_number"])
            if pn in seen:
                continue
            seen.add(pn)
            primary.append(row)
        return HybridContextBundle(
            query=bundle.query,
            primary_patterns=primary,
            expanded_patterns=bundle.expanded_patterns,
            expansion_reasons=bundle.expansion_reasons,
            evidence=evidence,
            expanded_technical=expanded_technical,
        )

    def validate_retrieval_bundle(
        self,
        bundle: HybridContextBundle,
        query: str,
        *,
        min_patterns: int = 2,
    ) -> str:
        warnings: list[str] = []
        pattern_ids = {
            int(p["pattern_number"])
            for p in bundle.primary_patterns + bundle.expanded_patterns
        }
        technical_sections = len(bundle.evidence) + len(bundle.expanded_technical)
        code_blocks = sum(len(d.code_blocks) for d in bundle.evidence + bundle.expanded_technical)
        graph_only = len(bundle.primary_patterns) > 0 and technical_sections == 0
        text_only = technical_sections > 0 and len(bundle.primary_patterns) == 0

        if len(pattern_ids) < min_patterns:
            warnings.append(f"Fewer than {min_patterns} distinct patterns in bundle.")
        if code_blocks < 1:
            warnings.append("No code examples retrieved from book slices.")
        if graph_only:
            warnings.append("Graph patterns present but no book technical sections retrieved.")
        if text_only:
            warnings.append("Book excerpts present but weak graph routing metadata.")

        passed = len(warnings) <= 1
        return json.dumps(
            {
                "passed": passed,
                "warnings": warnings,
                "metrics": {
                    "pattern_count": len(pattern_ids),
                    "technical_sections": technical_sections,
                    "code_blocks": code_blocks,
                    "graph_and_text": not graph_only and not text_only,
                },
            },
            separators=(",", ":"),
        )

    def reflection_decision(self, bundle: HybridContextBundle, query: str) -> str:
        validation = json.loads(self.validate_retrieval_bundle(bundle, query))
        metrics = validation.get("metrics", {})
        action = "sufficient"
        reason = "Retrieval bundle meets minimum hybrid graph+text thresholds."

        if not validation.get("passed"):
            action = "expand"
            reason = "Validation warnings indicate insufficient hybrid context; expand patterns/sections."
        elif metrics.get("code_blocks", 0) < 1:
            action = "expand"
            reason = "Missing book code examples; expand technical retrieval."
        elif "agentic" in query.casefold() and metrics.get("pattern_count", 0) < 5:
            action = "expand"
            reason = "Agentic workflow queries benefit from broader pattern stack coverage."

        return json.dumps(
            {"action": action, "reason": reason, "validation": validation},
            separators=(",", ":"),
        )

    def validate_hybrid_retrieval(self, query: str) -> str:
        bundle = self.build_hybrid_context(query)
        bundle = self.fuse_and_rerank_context(bundle, query)
        return self.validate_retrieval_bundle(bundle, query)

    def reflect_on_hybrid_retrieval(self, query: str) -> str:
        bundle = self.build_hybrid_context(query)
        bundle = self.fuse_and_rerank_context(bundle, query)
        return self.reflection_decision(bundle, query)
