"""
90-day rolling duplicate detection for construction investment leads.
Uses SQLite with a normalized fingerprint per investment.
"""

import sqlite3
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
from rapidfuzz import fuzz

from src.llm_extractor import ExtractionResult


@dataclass
class DedupResult:
    is_duplicate: bool
    last_seen: Optional[str]  # ISO datetime string
    matched_email_id: Optional[str]
    similarity_score: Optional[float]


class DedupChecker:
    WINDOW_DAYS = 90

    def __init__(self, db_path: str = ".tmp/dedup.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                address_normalized TEXT,
                company_normalized TEXT,
                investment_type TEXT,
                processed_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fingerprint ON leads(fingerprint)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_at ON leads(processed_at)")
        conn.commit()
        conn.close()

    def check(self, email_id: str, extraction: ExtractionResult) -> DedupResult:
        """Check if this investment has been processed in the last 90 days."""
        inv = extraction.investment
        address_norm = self._normalize(inv.address or inv.city or "")
        company_norm = self._normalize(inv.investor_name or extraction.contact.company or "")
        fingerprint = self._fingerprint(address_norm, company_norm, inv.type or "")

        conn = sqlite3.connect(self.db_path)
        cutoff = (datetime.utcnow() - timedelta(days=self.WINDOW_DAYS)).isoformat()

        # Exact fingerprint match
        row = conn.execute(
            "SELECT email_id, processed_at FROM leads WHERE fingerprint = ? AND processed_at > ?",
            (fingerprint, cutoff)
        ).fetchone()

        if row:
            conn.close()
            return DedupResult(is_duplicate=True, last_seen=row[1],
                               matched_email_id=row[0], similarity_score=1.0)

        # Fuzzy match on address + company for near-duplicates
        recent = conn.execute(
            "SELECT email_id, address_normalized, company_normalized, processed_at FROM leads WHERE processed_at > ?",
            (cutoff,)
        ).fetchall()

        for r_email_id, r_addr, r_company, r_date in recent:
            addr_sim = fuzz.token_sort_ratio(address_norm, r_addr or "") / 100
            comp_sim = fuzz.token_sort_ratio(company_norm, r_company or "") / 100
            combined = (addr_sim * 0.6) + (comp_sim * 0.4)
            if combined >= 0.85 and address_norm:  # only fuzzy-match if we have an address
                conn.close()
                return DedupResult(is_duplicate=True, last_seen=r_date,
                                   matched_email_id=r_email_id, similarity_score=combined)

        conn.close()
        return DedupResult(is_duplicate=False, last_seen=None,
                           matched_email_id=None, similarity_score=None)

    def register(self, email_id: str, extraction: ExtractionResult):
        """Store this lead so future emails can be checked against it."""
        inv = extraction.investment
        address_norm = self._normalize(inv.address or inv.city or "")
        company_norm = self._normalize(inv.investor_name or extraction.contact.company or "")
        fingerprint = self._fingerprint(address_norm, company_norm, inv.type or "")

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO leads (email_id, fingerprint, address_normalized, company_normalized, investment_type, processed_at) VALUES (?,?,?,?,?,?)",
            (email_id, fingerprint, address_norm, company_norm, inv.type, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().strip().split())

    @staticmethod
    def _fingerprint(address: str, company: str, inv_type: str) -> str:
        raw = f"{address}|{company}|{inv_type}"
        return hashlib.sha256(raw.encode()).hexdigest()
