"""Rule-driven card planning for unified analysis."""
from __future__ import annotations

from typing import Dict, List, Optional

CARD_MATRIX: Dict[str, List[Dict[str, object]]] = {
    "scholar": [
        # Phase 0: base fetch (page0) for fast-first UX.
        {"card_type": "resource.scholar.page0", "depends_on": [], "priority": 100},
        # Phase 1: full base report (heavier compute); used by most formatted blocks.
        {"card_type": "resource.scholar.full", "depends_on": [], "priority": 90},
        # Phase 2: shared fast JSON LLM (used by estimatedSalary + researcherCharacter).
        {"card_type": "resource.scholar.level", "depends_on": ["resource.scholar.full"], "priority": 80, "concurrency_group": "llm"},
        # Phase 2: formatted UI blocks (match origin/main contract).
        {"card_type": "researcherInfo", "depends_on": ["resource.scholar.page0"], "priority": 80},
        {"card_type": "publicationStats", "depends_on": ["resource.scholar.full"], "priority": 70},
        {"card_type": "publicationInsight", "depends_on": ["resource.scholar.full"], "priority": 60},
        {"card_type": "roleModel", "depends_on": ["resource.scholar.full"], "priority": 50},
        {"card_type": "closestCollaborator", "depends_on": ["resource.scholar.full"], "priority": 40},
        {"card_type": "estimatedSalary", "depends_on": ["resource.scholar.level"], "priority": 35},
        {"card_type": "researcherCharacter", "depends_on": ["resource.scholar.level"], "priority": 34},
        {"card_type": "paperOfYear", "depends_on": ["resource.scholar.full"], "priority": 30},
        {"card_type": "representativePaper", "depends_on": ["resource.scholar.full"], "priority": 20},
        # Kick off criticalReview early to overlap LLM tail with deterministic blocks.
        {"card_type": "criticalReview", "depends_on": ["resource.scholar.full"], "priority": 75, "concurrency_group": "llm"},
    ],
    "github": [
        # Phase 0 (fast-first): profile-only (REST preferred). Guarantees profile UX even if full data is slow.
        {"card_type": "resource.github.profile", "depends_on": [], "priority": 100},
        # Phase 1: full GitHub data bundle (GraphQL) used by downstream AI/enrich.
        # Runs in parallel with profile to avoid extra preview requests and reduce critical-path latency.
        {"card_type": "resource.github.data", "depends_on": [], "priority": 90},
        # Phase 3: fused LLM enrich (single call for role_model/summary/roast/best_pr/tags).
        {"card_type": "resource.github.enrich", "depends_on": ["resource.github.data"], "priority": 5, "concurrency_group": "llm"},
        # Phase 4: data-only cards.
        {"card_type": "profile", "depends_on": ["resource.github.profile"], "priority": 30},
        {"card_type": "activity", "depends_on": ["resource.github.data"], "priority": 20},
        # Phase 5: UI cards derived from the fused enrich artifact (repos may receive preview card.append earlier).
        {"card_type": "repos", "depends_on": ["resource.github.enrich"], "priority": 10, "concurrency_group": "default"},
        {"card_type": "role_model", "depends_on": ["resource.github.enrich"], "priority": 40, "concurrency_group": "default"},
        {"card_type": "roast", "depends_on": ["resource.github.enrich"], "priority": 50, "concurrency_group": "default"},
        {"card_type": "summary", "depends_on": ["resource.github.enrich"], "priority": 60, "concurrency_group": "default"},
    ],
    "linkedin": [
        # Fast-first: resolve URL + emit degraded profile immediately (does not scrape).
        {"card_type": "resource.linkedin.preview", "depends_on": [], "priority": 100, "concurrency_group": "default"},
        # Long-tail: actual LinkedIn scraping (Apify/etc).
        {"card_type": "resource.linkedin.raw_profile", "depends_on": ["resource.linkedin.preview"], "priority": 0},
        # Fused enrich bundle (single LLM call) for all non-roast cards.
        {"card_type": "resource.linkedin.enrich", "depends_on": ["resource.linkedin.raw_profile"], "priority": 5, "concurrency_group": "llm"},
        # Phase 1: complete profile after enrich so UI-only sections (e.g. colleagues_view/life_well_being) are present.
        {"card_type": "profile", "depends_on": ["resource.linkedin.enrich"], "priority": 10},
        # Phase 2: UI cards derived from the fused enrich artifact (no per-card LLM calls).
        {"card_type": "skills", "depends_on": ["resource.linkedin.enrich"], "priority": 20, "concurrency_group": "default"},
        {"card_type": "career", "depends_on": ["resource.linkedin.enrich"], "priority": 30, "concurrency_group": "default"},
        {"card_type": "role_model", "depends_on": ["resource.linkedin.enrich"], "priority": 40, "concurrency_group": "default"},
        {"card_type": "money", "depends_on": ["resource.linkedin.enrich"], "priority": 50, "concurrency_group": "default"},
        {"card_type": "roast", "depends_on": ["profile"], "priority": 60},
        {"card_type": "summary", "depends_on": ["resource.linkedin.enrich"], "priority": 70, "concurrency_group": "default"},
    ],
    "huggingface": [
        {"card_type": "full_report", "depends_on": [], "priority": 0},
        {"card_type": "profile", "depends_on": ["full_report"], "priority": 10},
        {"card_type": "summary", "depends_on": ["full_report"], "priority": 20},
    ],
    "twitter": [
        {"card_type": "full_report", "depends_on": [], "priority": 0},
        {"card_type": "profile", "depends_on": ["full_report"], "priority": 10},
        {"card_type": "stats", "depends_on": ["full_report"], "priority": 20},
        {"card_type": "network", "depends_on": ["full_report"], "priority": 30},
        {"card_type": "summary", "depends_on": ["full_report"], "priority": 40},
    ],
    "openreview": [
        {"card_type": "full_report", "depends_on": [], "priority": 0},
        {"card_type": "profile", "depends_on": ["full_report"], "priority": 10},
        {"card_type": "papers", "depends_on": ["full_report"], "priority": 20},
        {"card_type": "summary", "depends_on": ["full_report"], "priority": 30},
    ],
    "youtube": [
        {"card_type": "full_report", "depends_on": [], "priority": 0},
        {"card_type": "profile", "depends_on": ["full_report"], "priority": 10},
        {"card_type": "summary", "depends_on": ["full_report"], "priority": 20},
    ],
}


def _fallback_defs() -> List[Dict[str, object]]:
    return [
        {"card_type": "full_report", "depends_on": [], "priority": 0},
        {"card_type": "summary", "depends_on": ["full_report"], "priority": 100},
    ]


def card_defs_for_source(source: str) -> List[Dict[str, object]]:
    defs = CARD_MATRIX.get(source)
    if not defs:
        return _fallback_defs()
    return sorted(defs, key=lambda d: int(d.get("priority", 0)))


def normalize_cards(source: str, requested: Optional[List[str]] = None) -> List[str]:
    defs = card_defs_for_source(source)
    available = {d["card_type"]: d for d in defs}
    if not requested:
        return [d["card_type"] for d in defs]

    requested_clean = [c for c in requested if isinstance(c, str) and c.strip()]

    include: set[str] = set()

    def add_card(card_type: str) -> None:
        if card_type in include:
            return
        include.add(card_type)
        deps = available.get(card_type, {}).get("depends_on", [])
        for dep in deps:
            add_card(dep)

    for card in requested_clean:
        add_card(card)

    ordered = [d["card_type"] for d in defs if d["card_type"] in include]
    extras = [c for c in requested_clean if c not in available]
    for extra in extras:
        if extra not in ordered:
            ordered.append(extra)
    return ordered


def build_plan(source: str, requested: Optional[List[str]] = None) -> List[Dict[str, object]]:
    defs = card_defs_for_source(source)
    lookup = {d["card_type"]: d for d in defs}
    cards = normalize_cards(source, requested)

    def _default_concurrency_group(src: str, card_type: str) -> str:
        ct = str(card_type or "")
        s = str(src or "").strip().lower()
        if ct.startswith("resource."):
            if s == "github":
                return "github_api"
            if s == "scholar":
                return "crawlbase"
            if s == "linkedin":
                return "apify"
            return "resource"
        ai_cards = {"repos", "role_model", "roast", "summary", "news", "level", "skills", "career", "money"}
        if ct in ai_cards:
            return "llm"
        return "default"

    def _default_deadline_ms(src: str, card_type: str) -> Optional[int]:
        # Deadlines are disabled: cards should not be skipped due to job age.
        return None

    plan: List[Dict[str, object]] = []
    for card in cards:
        spec = lookup.get(card, {}) or {}
        depends_on = spec.get("depends_on", ["full_report"])
        priority = int(spec.get("priority", 0) or 0)
        concurrency_group = str(spec.get("concurrency_group") or _default_concurrency_group(source, card))
        deadline_ms = spec.get("deadline_ms")
        if deadline_ms is None:
            deadline_ms = _default_deadline_ms(source, card)
        # Always start cards in pending state; release_ready_cards() promotes runnable cards to "ready".
        # This avoids a race where the scheduler claims a "ready" card before cache-hit completion logic runs.
        rec: Dict[str, object] = {
            "card_type": card,
            "status": "pending",
            "depends_on": depends_on,
            "priority": priority,
            "concurrency_group": concurrency_group,
        }
        if deadline_ms is not None:
            try:
                rec["deadline_ms"] = int(deadline_ms)
            except Exception:
                pass
        plan.append(rec)
    return plan


def dependent_cards(source: str) -> List[str]:
    cards = normalize_cards(source)
    return [c for c in cards if c != "full_report" and not str(c).startswith("resource.")]
