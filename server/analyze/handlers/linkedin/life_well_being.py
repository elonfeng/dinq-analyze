"""LinkedIn life_well_being card handler."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from server.analyze.handlers.base import CardHandler, CardResult, ExecutionContext


class LinkedInLifeWellBeingHandler(CardHandler):
    """Handle the 'life_well_being' card for LinkedIn."""
    
    source = "linkedin"
    card_type = "life_well_being"
    version = "3"

    def _normalize_phrase(self, value: Any) -> str:
        phrase = str(value or "").strip()
        if not phrase:
            return ""
        phrase = " ".join(phrase.split())
        # Enforce "MAXIMUM 3 WORDS" rule (best-effort).
        words = phrase.split()
        if len(words) > 3:
            phrase = " ".join(words[:3])
        return phrase

    def _simplified_advice(self, advice: str) -> str:
        text = str(advice or "").strip()
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text).strip()
        words = text.split()
        if not words:
            return ""
        # Under 10 words per upstream prompt.
        return " ".join(words[:9])

    def _normalize_actions(self, value: Any, *, kind: str) -> list[Dict[str, str]]:
        actions = value if isinstance(value, list) else []
        out: list[Dict[str, str]] = []
        for a in actions:
            if not isinstance(a, dict):
                continue
            emoji = str(a.get("emoji") or "").strip()
            phrase = self._normalize_phrase(a.get("phrase"))
            if not phrase:
                continue
            out.append({"emoji": emoji, "phrase": phrase})
        if out:
            return out[:3]

        # Upstream-style deterministic fallback actions.
        if kind == "health":
            return [
                {"emoji": "🏃", "phrase": "Move Daily"},
                {"emoji": "😴", "phrase": "Sleep Well"},
                {"emoji": "🧘", "phrase": "Manage Stress"},
            ]
        return [
            {"emoji": "📏", "phrase": "Set Boundaries"},
            {"emoji": "👥", "phrase": "Build Network"},
            {"emoji": "🎯", "phrase": "Focus Time"},
        ]

    def _normalize_block(self, value: Any, *, kind: str) -> Dict[str, Any]:
        if isinstance(value, str):
            value = {"advice": value}
        block = value if isinstance(value, dict) else {}
        advice = str(block.get("advice") or "").strip()
        simplified = str(block.get("simplified_advice") or "").strip()
        if not simplified:
            simplified = self._simplified_advice(advice)
        return {
            "advice": advice,
            "simplified_advice": simplified,
            "actions": self._normalize_actions(block.get("actions"), kind=kind),
        }
    
    def execute(self, ctx: ExecutionContext) -> CardResult:
        """Extract life_well_being from enrich artifact."""
        enrich = ctx.get_artifact("resource.linkedin.enrich", {})
        
        if not isinstance(enrich, dict):
            enrich = {}
        
        life_well_being = enrich.get("life_well_being")
        if not isinstance(life_well_being, dict):
            life_well_being = {}

        life_suggestion = self._normalize_block(life_well_being.get("life_suggestion"), kind="life")
        health = self._normalize_block(life_well_being.get("health"), kind="health")

        return CardResult(
            data={
                "life_suggestion": life_suggestion,
                "health": health,
            }
        )
    
    def validate(self, data: Dict[str, Any], ctx: ExecutionContext) -> bool:
        """Validate life_well_being has at least one non-empty advice field."""
        life = data.get("life_suggestion") if isinstance(data.get("life_suggestion"), dict) else {}
        health = data.get("health") if isinstance(data.get("health"), dict) else {}
        life_advice = str(life.get("advice") or "").strip()
        health_advice = str(health.get("advice") or "").strip()
        return bool(life_advice or health_advice)
    
    def fallback(self, ctx: ExecutionContext, error: Optional[Exception] = None) -> CardResult:
        """Generate fallback life_well_being."""
        raw_art = ctx.get_artifact("resource.linkedin.raw_profile", {})
        profile = raw_art.get("profile_data") if isinstance(raw_art, dict) else None
        raw_profile = (profile.get("raw_profile") or {}) if isinstance(profile, dict) else {}

        fallback_payload: Dict[str, Any] = {}
        try:
            from server.linkedin_analyzer.life_well_being_service import create_default_life_well_being

            fallback_payload = create_default_life_well_being(raw_profile if isinstance(raw_profile, dict) else {}, str((profile or {}).get("name") or "").strip() or "Unknown")
        except Exception:
            fallback_payload = {}

        life = self._normalize_block((fallback_payload or {}).get("life_suggestion"), kind="life")
        health = self._normalize_block((fallback_payload or {}).get("health"), kind="health")
        return CardResult(
            data={
                "life_suggestion": life,
                "health": health,
            },
            is_fallback=True,
            meta={"code": "life_well_being_unavailable", "preserve_empty": True}
        )
