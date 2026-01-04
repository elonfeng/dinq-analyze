"""GitHub summary card handler."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class GitHubSummaryHandler(CardHandler):
    """Handle the 'summary' card for GitHub."""
    
    source = "github"
    card_type = "summary"
    version = "3"

    _LEVEL_RE = re.compile(r"^L\s*(\d{1,2})(\+)?$", flags=re.IGNORECASE)

    def _coerce_level(self, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        compact = raw.replace(" ", "").strip()
        m = self._LEVEL_RE.match(compact)
        if m:
            try:
                n = int(m.group(1))
            except Exception:
                return ""
            return f"L{n}{'+' if m.group(2) else ''}"

        lowered = raw.lower()
        if "distinguished" in lowered or "fellow" in lowered:
            return "L8"
        if "principal" in lowered:
            return "L8"
        if "senior staff" in lowered:
            return "L7"
        if "staff" in lowered:
            return "L6"
        if "senior" in lowered:
            return "L5"
        if "mid" in lowered or "intermediate" in lowered:
            return "L4"
        if "junior" in lowered or "entry" in lowered or "intern" in lowered:
            return "L3"
        return ""

    def _parse_salary_range(self, value: Any) -> list[Optional[int]]:
        if isinstance(value, list) and len(value) == 2:
            a_raw, b_raw = value[0], value[1]
            try:
                a = int(a_raw) if a_raw is not None and not isinstance(a_raw, bool) else None
            except Exception:
                a = None
            try:
                b = int(b_raw) if b_raw is not None and not isinstance(b_raw, bool) else None
            except Exception:
                b = None
            if a is not None and b is not None and a > b:
                a, b = b, a
            return [a, b]

        text = str(value or "").strip()
        if not text:
            return [None, None]

        # Extract numbers with optional K/M suffix.
        matches = re.findall(r"(\d[\d,]*\.?\d*)\s*([kKmM]?)", text)
        nums: list[int] = []
        for raw_num, suffix in matches:
            try:
                n = float(raw_num.replace(",", ""))
            except Exception:
                continue
            mult = 1.0
            if suffix.lower() == "k":
                mult = 1000.0
            elif suffix.lower() == "m":
                mult = 1000000.0
            val = int(n * mult)
            if val >= 1000:  # ignore tiny numbers that are likely years/counts
                nums.append(val)

        if len(nums) >= 2:
            a, b = nums[0], nums[1]
            if a > b:
                a, b = b, a
            return [a, b]
        if len(nums) == 1:
            center = nums[0]
            return [int(center * 0.9), int(center * 1.2)]
        return [None, None]

    def _coerce_industry_ranking(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            v = float(value)
        except Exception:
            return None
        if 1.0 < v <= 100.0:
            v = v / 100.0
        if not (0.0 < v <= 1.0):
            return None
        return float(v)

    def _heuristic_level(self, *, overview: Dict[str, Any], user: Dict[str, Any]) -> str:
        years = overview.get("work_experience")
        if years is None:
            created = str(user.get("createdAt") or "").strip()
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                years = max(0, int((datetime.now(timezone.utc) - dt).days / 365))
            except Exception:
                years = 0
        try:
            years_i = int(years or 0)
        except Exception:
            years_i = 0

        try:
            stars = int(overview.get("stars") or 0)
        except Exception:
            stars = 0

        pr_total = None
        prs = user.get("pullRequests") if isinstance(user.get("pullRequests"), dict) else {}
        try:
            pr_total = int(prs.get("totalCount") or 0)
        except Exception:
            pr_total = None
        if pr_total is None:
            try:
                pr_total = int(overview.get("pull_requests") or 0)
            except Exception:
                pr_total = 0

        # Coarse mapping aligned to the upstream prompt bands.
        if years_i >= 15 and stars >= 5000:
            return "L8+"
        if years_i >= 10 and (stars >= 1000 or pr_total >= 200):
            return "L7"
        if years_i >= 7 and (stars >= 500 or pr_total >= 120):
            return "L6"
        if years_i >= 4 and (stars >= 100 or pr_total >= 50):
            return "L5"
        if years_i >= 2:
            return "L4"
        return "L3"

    def _default_salary_for_level(self, level: str, *, overview: Dict[str, Any]) -> list[Optional[int]]:
        base_map = {
            "L3": 194000,
            "L4": 287000,
            "L5": 377000,
            "L6": 562000,
            "L7": 779000,
            "L8": 1111000,
            "L8+": 1111000,
        }
        base = base_map.get(level, 377000)
        try:
            stars = int(overview.get("stars") or 0)
        except Exception:
            stars = 0
        premium = 1.0
        if stars >= 5000:
            premium += 0.4
        elif stars >= 1000:
            premium += 0.25
        elif stars >= 200:
            premium += 0.15
        lo = int(base * 0.9 * premium)
        hi = int(base * 1.3 * premium)
        if lo > hi:
            lo, hi = hi, lo
        return [lo, hi]

    def _default_industry_ranking(self, level: str) -> float:
        # Lower is better (0.05 = top 5%).
        if level.startswith("L8"):
            return 0.03
        if level == "L7":
            return 0.07
        if level == "L6":
            return 0.12
        if level == "L5":
            return 0.25
        if level == "L4":
            return 0.35
        return 0.5

    def _default_growth_potential(self, level: str) -> str:
        if level in ("L3", "L4", "L5"):
            return "High"
        return "Medium"

    def _default_reasoning(self, *, login: str, level: str, salary_range: list[Optional[int]], overview: Dict[str, Any], user: Dict[str, Any]) -> str:
        try:
            stars = int(overview.get("stars") or 0)
        except Exception:
            stars = 0
        repos = overview.get("repositories")
        if repos is None:
            repos_obj = user.get("repositories") if isinstance(user.get("repositories"), dict) else {}
            try:
                repos = int(repos_obj.get("totalCount") or 0)
            except Exception:
                repos = 0
        try:
            repos_i = int(repos or 0)
        except Exception:
            repos_i = 0

        prs_obj = user.get("pullRequests") if isinstance(user.get("pullRequests"), dict) else {}
        try:
            prs_i = int(prs_obj.get("totalCount") or 0)
        except Exception:
            prs_i = int(overview.get("pull_requests") or 0) if isinstance(overview.get("pull_requests"), (int, float, str)) else 0

        years = overview.get("work_experience")
        try:
            years_i = int(years or 0)
        except Exception:
            years_i = 0

        lo = salary_range[0] if salary_range and salary_range[0] is not None else 0
        hi = salary_range[1] if salary_range and salary_range[1] is not None else 0
        # 50-70 words target (best-effort).
        text = (
            f"Based on ~{years_i} years of visible GitHub activity, {prs_i} pull requests, and {stars} stars across {repos_i} repositories, "
            f"{login} maps to a {level} engineering level. The contribution signals consistent shipping and collaboration. "
            f"In today’s competitive market, similar developers often command total compensation around ${lo:,}-${hi:,}, "
            "with premium upside from scarce skills, open-source impact, and sustained execution."
        )
        words = text.split()
        if len(words) < 50:
            text = text + " This estimate assumes strong technical ownership and measurable project outcomes."
        words = text.split()
        if len(words) > 70:
            text = " ".join(words[:70])
        return text.strip()

    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract summary (valuation_and_level + description) from enrich artifact."""
        enrich = ctx.get_artifact("resource.github.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        valuation = enrich.get("valuation_and_level")
        if not isinstance(valuation, dict):
            valuation = {}

        data_art = ctx.get_artifact("resource.github.data", {})
        if not isinstance(data_art, dict):
            data_art = {}
        overview = data_art.get("overview") if isinstance(data_art.get("overview"), dict) else {}
        user = data_art.get("user") if isinstance(data_art.get("user"), dict) else {}

        level = self._coerce_level(valuation.get("level"))
        if not level:
            level = self._heuristic_level(overview=overview, user=user)

        salary_range = self._parse_salary_range(valuation.get("salary_range"))
        if not any(v is not None for v in salary_range):
            salary_range = self._default_salary_for_level(level, overview=overview)

        industry_ranking = self._coerce_industry_ranking(valuation.get("industry_ranking"))
        if industry_ranking is None:
            industry_ranking = self._default_industry_ranking(level)

        growth_potential = str(valuation.get("growth_potential") or "").strip()
        if not growth_potential:
            growth_potential = self._default_growth_potential(level)

        reasoning = str(valuation.get("reasoning") or "").strip()
        if not reasoning:
            login = str(user.get("login") or "").strip() or "this developer"
            reasoning = self._default_reasoning(login=login, level=level, salary_range=salary_range, overview=overview, user=user)
        
        # Normalize valuation schema
        normalized_valuation = {
            "level": level,
            "salary_range": salary_range,
            "industry_ranking": industry_ranking,
            "growth_potential": growth_potential,
            "reasoning": reasoning,
        }
        
        description = str(enrich.get("description") or "").strip()
        if not description:
            login = str(user.get("login") or "").strip()
            description = f"GitHub profile summary{(' for ' + login) if login else ''}."
        
        return CardResult(
            data={
                "valuation_and_level": normalized_valuation,
                "description": description,
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate summary has level."""
        valuation = data.get("valuation_and_level")
        if not isinstance(valuation, dict):
            return False
        level = str(valuation.get("level") or "").strip()
        return bool(level)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback summary."""
        data_artifact = ctx.get_artifact("resource.github.data", {})
        if not isinstance(data_artifact, dict):
            data_artifact = {}
        user = data_artifact.get("user") if isinstance(data_artifact.get("user"), dict) else {}
        overview = data_artifact.get("overview") if isinstance(data_artifact.get("overview"), dict) else {}

        login = str(user.get("login") or "").strip() or "this developer"
        level = self._heuristic_level(overview=overview, user=user)
        salary_range = self._default_salary_for_level(level, overview=overview)
        reasoning = self._default_reasoning(login=login, level=level, salary_range=salary_range, overview=overview, user=user)
        desc = f"GitHub profile summary for {login}."
        
        return CardResult(
            data={
                "valuation_and_level": {
                    "level": level,
                    "salary_range": salary_range,
                    "industry_ranking": self._default_industry_ranking(level),
                    "growth_potential": self._default_growth_potential(level),
                    "reasoning": reasoning,
                },
                "description": desc,
            },
            is_fallback=True,
            meta={"code": "summary_unavailable", "preserve_empty": True}
        )
