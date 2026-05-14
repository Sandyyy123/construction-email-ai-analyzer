# Construction Email AI Analyzer

AI-powered module for automatic analysis of incoming email reports related to construction investments (Polish language).

Extracts structured lead data, scores priority, routes to regional sales representatives, and eliminates duplicate leads across sources.

## What It Does

1. **Fetches emails** from IMAP / Gmail API / Microsoft 365
2. **Parses attachments** - PDF and DOCX
3. **Extracts key fields** via LLM (Polish NLP) - investment type, stage, location, investor, contact details
4. **Scores priority** - HIGH / MEDIUM / LOW based on configurable rules
5. **Routes geographically** - assigns lead to regional rep based on Polish voivodeship
6. **Deduplicates** - 90-day rolling window to eliminate repeat leads from different sources
7. **Returns JSON** - structured output for downstream system integration

## Sample Output

```json
{
  "email_id": "msg_20260514_0047",
  "processed_at": "2026-05-14T10:23:41Z",
  "investment": {
    "type": "Budynek mieszkalny wielorodzinny",
    "stage": "Pozwolenie na budowe - wydane",
    "scale": "Duzy (pow. 5000 m2)",
    "address": "ul. Pozanska 14, 60-850 Poznan",
    "voivodeship": "Wielkopolskie",
    "keywords": ["prefabrykaty", "termin Q3 2026", "przetarg otwarty"]
  },
  "contact": {
    "company": "Budimex Nieruchomosci Sp. z o.o.",
    "person": "Marek Kowalski",
    "title": "Kierownik Projektu",
    "phone": "+48 601 234 567",
    "email": "m.kowalski@budimex.pl"
  },
  "priority": "HIGH",
  "priority_score": 87,
  "assigned_region": "Region A",
  "assigned_rep": "Jan Nowak (Wielkopolska / Slaskie)",
  "duplicate_check": {
    "is_duplicate": false,
    "last_seen": null
  },
  "source_attachment": "raport_inwestycja_poznan.pdf"
}
```

## Architecture

```
Email Source (IMAP/Gmail/M365)
        |
        v
  EmailFetcher
        |
        v
  AttachmentParser  <-- PDF / DOCX
        |
        v
  LLMExtractor  <-- GPT-4o + Polish prompt
        |
        v
  PriorityScorer  <-- configurable YAML rules
        |
        v
  GeoRouter  <-- 16 Polish voivodeships
        |
        v
  DedupChecker  <-- 90-day SQLite fingerprint store
        |
        v
  JSON Output  <-- API / webhook / file
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python src/main.py
```

## Configuration

Priority rules and region mappings are fully configurable in `config/` - no code changes needed.

```yaml
# config/priority_rules.yaml
high:
  min_scale_m2: 5000
  stages: ["pozwolenie wydane", "przetarg", "realizacja"]
  keywords: ["pilne", "termin", "przetarg otwarty"]
```

## Tech Stack

- Python 3.11+
- OpenAI GPT-4o (structured outputs)
- LangChain
- PyMuPDF (PDF parsing)
- python-docx (DOCX parsing)
- Gmail API / imaplib
- FastAPI (optional REST wrapper)
- SQLite (dedup store)

## License

CC BY-NC 4.0 - Dr. Sandeep Grover
