"""
Main pipeline orchestrator - processes emails end-to-end and returns structured JSON.
"""

import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.llm_extractor import LLMExtractor
from src.priority_scorer import PriorityScorer
from src.geo_router import GeoRouter
from src.dedup_checker import DedupChecker


def process_email(email_id: str, email_subject: str, email_body: str,
                  attachment_text: str = "") -> dict:
    """
    Full pipeline: extract -> score -> route -> dedup -> return JSON.
    """
    extractor = LLMExtractor(api_key=os.environ["OPENAI_API_KEY"])
    scorer = PriorityScorer()
    router = GeoRouter()
    dedup = DedupChecker(db_path=os.getenv("DEDUP_DB_PATH", ".tmp/dedup.db"))

    # 1. LLM extraction
    full_text = f"Temat: {email_subject}\n\n{email_body}"
    extraction = extractor.extract(full_text, attachment_text)
    inv = extraction.investment

    # 2. Duplicate check
    dedup_result = dedup.check(email_id, extraction)

    # 3. Priority scoring
    scoring = scorer.score(extraction, is_duplicate=dedup_result.is_duplicate)

    # 4. Geographic routing
    routing = router.route(
        voivodeship=inv.voivodeship,
        address=inv.address,
        city=inv.city,
        postal_code=inv.postal_code,
    )

    # 5. Register in dedup store (only if not duplicate)
    if not dedup_result.is_duplicate:
        dedup.register(email_id, extraction)

    # 6. Build output JSON
    output = {
        "email_id": email_id,
        "processed_at": datetime.utcnow().isoformat() + "Z",
        "investment": {
            "type": inv.type,
            "stage": inv.stage,
            "scale": inv.scale_description or (f"{inv.scale_m2} m2" if inv.scale_m2 else None),
            "address": inv.address,
            "city": inv.city,
            "voivodeship": inv.voivodeship,
            "investor_name": inv.investor_name,
            "keywords": inv.keywords,
        },
        "contact": {
            "company": extraction.contact.company,
            "person": extraction.contact.person,
            "title": extraction.contact.title,
            "phone": extraction.contact.phone,
            "email": extraction.contact.email,
        },
        "priority": scoring.priority,
        "priority_score": scoring.score,
        "priority_rules_matched": scoring.matched_rules,
        "assigned_region": routing.region,
        "assigned_rep": routing.rep_name,
        "assigned_rep_email": routing.rep_email,
        "geo_match_method": routing.match_method,
        "duplicate_check": {
            "is_duplicate": dedup_result.is_duplicate,
            "last_seen": dedup_result.last_seen,
            "matched_email_id": dedup_result.matched_email_id,
        },
        "extraction_confidence": extraction.extraction_confidence,
    }

    return output


if __name__ == "__main__":
    # Quick test with sample email
    sample_subject = "Inwestycja mieszkaniowa - Poznan ul. Pozanska 14"
    sample_body = """
    Dzien dobry,

    Przekazujemy informacje o nowej inwestycji mieszkaniowej wielorodzinnej w Poznaniu.

    Lokalizacja: ul. Pozanska 14, 60-850 Poznan
    Inwestor: Budimex Nieruchomosci Sp. z o.o.
    Skala: 120 mieszkan, ok. 7500 m2
    Etap: Pozwolenie na budowe wydane, przetarg otwarty
    Planowany start: Q3 2026

    Kontakt:
    Marek Kowalski - Kierownik Projektu
    Tel: +48 601 234 567
    Email: m.kowalski@budimex.pl
    """

    result = process_email("test_001", sample_subject, sample_body)
    print(json.dumps(result, ensure_ascii=False, indent=2))
