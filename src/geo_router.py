"""
Geographic routing of leads to regional sales representatives.
Supports full address, city, postal code, or voivodeship name.
Falls back to geocoding for ambiguous/incomplete location data.
"""

import yaml
import re
from dataclasses import dataclass
from typing import Optional
from rapidfuzz import process, fuzz


@dataclass
class RoutingResult:
    region: str
    rep_name: str
    rep_email: str
    matched_voivodeship: Optional[str]
    match_method: str  # exact | fuzzy | geocode | fallback


VOIVODESHIP_ALIASES = {
    "mazowieckie": ["mazowsze", "warszawa", "warsaw", "mazovian"],
    "malopolskie": ["malopolska", "krakow", "cracow", "lesser poland"],
    "slaskie": ["silesia", "katowice", "slask"],
    "wielkopolskie": ["wielkopolska", "poznan", "greater poland"],
    "dolnoslaskie": ["dolny slask", "wroclaw", "lower silesia"],
    "pomorskie": ["gdansk", "trojmiasto", "pomerania"],
    "lodzkie": ["lodz", "lodz voivodeship"],
    "kujawsko-pomorskie": ["bydgoszcz", "torun"],
    "lubelskie": ["lublin"],
    "podkarpackie": ["rzeszow", "subcarpathian"],
    "podlaskie": ["bialystok"],
    "swietokrzyskie": ["kielce"],
    "warminsko-mazurskie": ["olsztyn", "warmia"],
    "zachodniopomorskie": ["szczecin", "west pomerania"],
    "lubuskie": ["zielona gora", "gorzow"],
    "opolskie": ["opole"],
}

# Postal code prefix to voivodeship mapping (partial)
POSTAL_PREFIXES = {
    "00": "mazowieckie", "01": "mazowieckie", "02": "mazowieckie", "03": "mazowieckie",
    "04": "mazowieckie", "05": "mazowieckie",
    "30": "malopolskie", "31": "malopolskie", "32": "malopolskie",
    "40": "slaskie", "41": "slaskie", "42": "slaskie", "43": "slaskie", "44": "slaskie",
    "60": "wielkopolskie", "61": "wielkopolskie", "62": "wielkopolskie", "63": "wielkopolskie",
    "50": "dolnoslaskie", "51": "dolnoslaskie", "52": "dolnoslaskie", "53": "dolnoslaskie",
    "80": "pomorskie", "81": "pomorskie", "82": "pomorskie", "83": "pomorskie",
    "90": "lodzkie", "91": "lodzkie", "92": "lodzkie", "93": "lodzkie",
}


class GeoRouter:
    def __init__(self, config_path: str = "config/region_mapping.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.regions = self.config["regions"]
        self.fallback = self.config.get("fallback_region", "A")
        self._build_lookup()

    def _build_lookup(self):
        self.voivodeship_to_region = {}
        for region_id, region_data in self.regions.items():
            for v in region_data.get("voivodeships", []):
                self.voivodeship_to_region[v.lower()] = region_id

    def route(self, voivodeship: str = None, address: str = None,
              city: str = None, postal_code: str = None) -> RoutingResult:

        # 1. Direct voivodeship match
        if voivodeship:
            region_id = self._match_voivodeship(voivodeship)
            if region_id:
                return self._build_result(region_id, voivodeship, "exact")

        # 2. Postal code prefix
        if postal_code:
            prefix = re.sub(r"[^0-9]", "", postal_code)[:2]
            v = POSTAL_PREFIXES.get(prefix)
            if v:
                region_id = self._match_voivodeship(v)
                if region_id:
                    return self._build_result(region_id, v, "postal_code")

        # 3. Fuzzy match on address/city text
        for text in [city, address]:
            if text:
                region_id, matched_v = self._fuzzy_match(text)
                if region_id:
                    return self._build_result(region_id, matched_v, "fuzzy")

        # 4. Fallback
        return self._build_result(self.fallback, None, "fallback")

    def _match_voivodeship(self, text: str) -> Optional[str]:
        t = text.lower().strip()
        if t in self.voivodeship_to_region:
            return self.voivodeship_to_region[t]
        for canonical, aliases in VOIVODESHIP_ALIASES.items():
            if t == canonical or t in aliases:
                return self.voivodeship_to_region.get(canonical)
        return None

    def _fuzzy_match(self, text: str):
        all_voivodeships = list(self.voivodeship_to_region.keys())
        all_voivodeships += [a for aliases in VOIVODESHIP_ALIASES.values() for a in aliases]
        match, score, _ = process.extractOne(text.lower(), all_voivodeships, scorer=fuzz.partial_ratio)
        if score >= 75:
            region_id = self._match_voivodeship(match)
            return region_id, match
        return None, None

    def _build_result(self, region_id: str, voivodeship: str, method: str) -> RoutingResult:
        region = self.regions.get(region_id, self.regions[self.fallback])
        return RoutingResult(
            region=region_id,
            rep_name=region["rep_name"],
            rep_email=region["rep_email"],
            matched_voivodeship=voivodeship,
            match_method=method,
        )
