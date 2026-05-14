"""
Priority scoring engine for construction investment leads.
Rules are loaded from config/priority_rules.yaml - no code changes needed.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Literal

from src.llm_extractor import ExtractionResult


PriorityLevel = Literal["HIGH", "MEDIUM", "LOW"]


@dataclass
class ScoringResult:
    priority: PriorityLevel
    score: int  # 0-100
    matched_rules: list[str]


class PriorityScorer:
    def __init__(self, config_path: str = "config/priority_rules.yaml"):
        with open(config_path) as f:
            self.rules = yaml.safe_load(f)

    def score(self, extraction: ExtractionResult, is_duplicate: bool = False) -> ScoringResult:
        if is_duplicate and self.rules.get("low", {}).get("auto_downgrade_if_duplicate"):
            return ScoringResult(priority="LOW", score=5, matched_rules=["duplicate_detected"])

        score = 0
        matched = []
        inv = extraction.investment
        contact = extraction.contact

        high_rules = self.rules.get("high", {})

        # Scale scoring
        if inv.scale_m2 and inv.scale_m2 >= high_rules.get("min_scale_m2", 5000):
            score += 30
            matched.append(f"scale_m2>={high_rules['min_scale_m2']}")
        elif inv.scale_units and inv.scale_units >= high_rules.get("min_units", 50):
            score += 25
            matched.append(f"units>={high_rules['min_units']}")

        # Stage scoring
        high_stages = [s.lower() for s in high_rules.get("stages", [])]
        if inv.stage and any(s in inv.stage.lower() for s in high_stages):
            score += 25
            matched.append(f"stage_match:{inv.stage}")

        # Investment type scoring
        high_types = [t.lower() for t in high_rules.get("investment_types", [])]
        if inv.type and any(t in inv.type.lower() for t in high_types):
            score += 15
            matched.append(f"type_match:{inv.type}")

        # Keyword scoring
        high_keywords = [k.lower() for k in high_rules.get("keywords", [])]
        keyword_hits = [k for k in inv.keywords if any(h in k.lower() for h in high_keywords)]
        if keyword_hits:
            score += min(15, len(keyword_hits) * 5)
            matched.append(f"keywords:{keyword_hits}")

        # Contact completeness bonus
        contact_fields = [contact.company, contact.person, contact.phone, contact.email]
        contact_score = sum(5 for f in contact_fields if f)
        score += contact_score
        if contact_score >= 15:
            matched.append("full_contact")

        # Determine priority
        if score >= 65:
            priority = "HIGH"
        elif score >= 35:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Auto-downgrade if no contact and rule set
        if not any([contact.person, contact.phone, contact.email]):
            if self.rules.get("low", {}).get("auto_downgrade_if_no_contact") and priority == "HIGH":
                priority = "MEDIUM"
                matched.append("downgraded_no_contact")

        return ScoringResult(priority=priority, score=min(score, 100), matched_rules=matched)
