"""
Minimal hybrid RAG toolkit for Agent Studio tools (Phase 1).

Vendored from docling-conv-docs generative_ai_design_patterns:
  demo_hybrid_agent.py, hybrid_rag_tools.py
"""

from __future__ import annotations

import json
import re
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


def pattern_brief(pattern: dict[str, Any]) -> dict[str, Any]:
    return {
        "pattern_number": pattern.get("pattern_number"),
        "name": pattern.get("name"),
        "problem": pattern.get("problem"),
        "when_to_use": pattern.get("when_to_use"),
        "tradeoffs": pattern.get("tradeoffs"),
    }


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
        nodes = {n["id"]: n for n in data.get("nodes", [])}
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

    def rag_patterns(self) -> list[dict[str, Any]]:
        ids = sorted(set(self.concept_patterns.get("rag", [])))
        return [self.patterns[i] for i in ids if i in self.patterns]

    def all_patterns(self) -> list[dict[str, Any]]:
        return list(self.patterns.values())

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return search_patterns(self.all_patterns(), query, limit=limit)


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

    return {
        "overview": truncate_text("\n\n".join(sections["overview"]), per_section),
        "problem": truncate_text("\n\n".join(sections["problem"]), per_section),
        "solution": truncate_text("\n\n".join(sections["solution"]), per_section),
        "implementation": truncate_text("\n\n".join(sections["implementation"]), per_section * 2),
        "caveats": truncate_text("\n\n".join(sections["caveats"]), per_section),
        "code_blocks": extract_code_blocks(section_text),
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


def detail_payload(detail: PatternTechnicalDetail, *, max_chars: int | None = None) -> dict[str, Any]:
    return {
        "pattern_number": detail.pattern.get("pattern_number"),
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
        return json.dumps([pattern_brief(p) for p in rows], separators=(",", ":"))

    def retrieve_pattern_technical_context(self, pattern_number: int) -> str:
        pattern = self.router.get_pattern(pattern_number)
        if not pattern:
            return json.dumps({"error": f"Pattern {pattern_number} not found"})
        detail = retrieve_pattern_technical_detail(pattern, self.slices_dir)
        return json.dumps(detail_payload(detail), separators=(",", ":"))
