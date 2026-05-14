"""
LLM-based extraction of construction investment fields from Polish email text.
Uses OpenAI structured outputs for reliable JSON field extraction.
"""

import json
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional


EXTRACTION_PROMPT = """
Jesteś asystentem analizującym wiadomości e-mail dotyczące inwestycji budowlanych w Polsce.

Przeanalizuj poniższą wiadomość e-mail i wyodrebnij nastepujące informacje w formacie JSON.
Jezeli jakaś informacja nie jest dostepna, ustaw wartość na null.

Wiadomosc e-mail:
{email_text}

Wyodrebnij:
- typ inwestycji (np. mieszkalny wielorodzinny, komercyjny, przemyslowy, biurowy)
- etap inwestycji (np. koncepcja, projekt budowlany, pozwolenie na budowe, realizacja)
- adres/lokalizacja placu budowy
- nazwa inwestora lub firmy
- skala projektu (powierzchnia m2 lub liczba jednostek)
- slowa kluczowe definiujace priorytety
- dane kontaktowe (nazwa firmy, osoba kontaktowa, stanowisko, telefon, e-mail)

Odpowiedz wylacznie w formacie JSON.
"""


class ContactDetails(BaseModel):
    company: Optional[str] = None
    person: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class InvestmentDetails(BaseModel):
    type: Optional[str] = None
    stage: Optional[str] = None
    address: Optional[str] = None
    voivodeship: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    investor_name: Optional[str] = None
    scale_m2: Optional[float] = None
    scale_units: Optional[int] = None
    scale_description: Optional[str] = None
    keywords: list[str] = []


class ExtractionResult(BaseModel):
    investment: InvestmentDetails
    contact: ContactDetails
    raw_text_length: int
    extraction_confidence: str  # high | medium | low


class LLMExtractor:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def extract(self, email_text: str, attachment_text: str = "") -> ExtractionResult:
        """Extract structured fields from Polish email + optional attachment text."""
        combined_text = email_text
        if attachment_text:
            combined_text += f"\n\n--- ZALACZNIK ---\n{attachment_text}"

        prompt = EXTRACTION_PROMPT.format(email_text=combined_text[:8000])

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )

        raw = json.loads(response.choices[0].message.content)
        return self._parse_response(raw, len(combined_text))

    def _parse_response(self, raw: dict, text_length: int) -> ExtractionResult:
        inv = raw.get("inwestycja", raw.get("investment", {}))
        contact = raw.get("kontakt", raw.get("contact", {}))

        investment = InvestmentDetails(
            type=inv.get("typ") or inv.get("type"),
            stage=inv.get("etap") or inv.get("stage"),
            address=inv.get("adres") or inv.get("address"),
            voivodeship=inv.get("wojewodztwo") or inv.get("voivodeship"),
            city=inv.get("miasto") or inv.get("city"),
            postal_code=inv.get("kod_pocztowy") or inv.get("postal_code"),
            investor_name=inv.get("inwestor") or inv.get("investor_name"),
            scale_m2=inv.get("powierzchnia_m2") or inv.get("scale_m2"),
            scale_units=inv.get("liczba_jednostek") or inv.get("scale_units"),
            scale_description=inv.get("skala") or inv.get("scale_description"),
            keywords=inv.get("slowa_kluczowe") or inv.get("keywords") or [],
        )

        contact_details = ContactDetails(
            company=contact.get("firma") or contact.get("company"),
            person=contact.get("osoba") or contact.get("person"),
            title=contact.get("stanowisko") or contact.get("title"),
            phone=contact.get("telefon") or contact.get("phone"),
            email=contact.get("email"),
            address=contact.get("adres") or contact.get("address"),
        )

        filled = sum(1 for f in [investment.type, investment.stage, investment.address,
                                  contact_details.company, contact_details.phone] if f)
        confidence = "high" if filled >= 4 else "medium" if filled >= 2 else "low"

        return ExtractionResult(
            investment=investment,
            contact=contact_details,
            raw_text_length=text_length,
            extraction_confidence=confidence,
        )
