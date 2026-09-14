from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.gdelt.common.config import PROJECT_ROOT

KEYWORD_MAP_DIR = PROJECT_ROOT / "src" / "mediacloud" / "resources" / "keyword_maps"

LANGUAGE_FILES = {
    "es": "keywords_es.txt",
    "en": "keywords_en.txt",
    "hu": "keywords_hu.txt",
}

COUNTRY_LANGUAGE_MAP = {
    "colombia": ("es", "en"),
    "united_kingdom": ("en",),
    "hungary": ("hu", "en"),
}

COUNTRY_SEARCH_TERMS = {
    "colombia": ("Colombia",),
    "united_kingdom": ("UK", "United Kingdom"),
    "hungary": ("Hungary", "Magyarorszag"),
}

COUNTRY_NAMES = {
    "colombia": "Colombia",
    "united_kingdom": "United Kingdom",
    "hungary": "Hungary",
}

_SECTION_RE = re.compile(r"^===\s*(?P<family>[A-Z][A-Z0-9]*)\.\s*(?P<label>.*?)\s*\(", re.MULTILINE)
_TERM_RE = re.compile(r"\([^()]+?\s+AND\s+(?P<term>\"[^\"]+\"|#[\wÁÉÍÓÚÜÑáéíóúüñŐőŰűÄÖÜäöü-]+|[\wÁÉÍÓÚÜÑáéíóúüñŐőŰűÄÖÜäöü-]+)\)")


@dataclass(frozen=True)
class KeywordTerm:
    language: str
    family: str
    label: str
    term: str


def _clean_term(raw: str) -> str:
    return raw.strip().strip('"').strip()


def load_keyword_terms(
    *,
    languages: tuple[str, ...],
    keyword_dir: Path = KEYWORD_MAP_DIR,
    max_terms_per_family: int = 3,
) -> list[KeywordTerm]:
    terms: list[KeywordTerm] = []
    for language in languages:
        path = keyword_dir / LANGUAGE_FILES[language]
        content = path.read_text(encoding="utf-8", errors="replace")
        matches = list(_SECTION_RE.finditer(content))
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            section = content[start:end]
            seen: set[str] = set()
            added = 0
            for term_match in _TERM_RE.finditer(section):
                term = _clean_term(term_match.group("term"))
                if not term or term.lower() in seen:
                    continue
                seen.add(term.lower())
                terms.append(
                    KeywordTerm(
                        language=language,
                        family=match.group("family"),
                        label=match.group("label").strip(),
                        term=term,
                    )
                )
                added += 1
                if added >= max_terms_per_family:
                    break
    return terms


def build_social_queries(
    country_key: str,
    *,
    limit: int = 30,
    max_terms_per_family: int = 3,
) -> list[dict[str, str]]:
    languages = COUNTRY_LANGUAGE_MAP[country_key]
    country_terms = COUNTRY_SEARCH_TERMS[country_key]
    keyword_terms = load_keyword_terms(languages=languages, max_terms_per_family=max_terms_per_family)
    queries: list[dict[str, str]] = []
    seen: set[str] = set()
    for keyword in keyword_terms:
        for country_term in country_terms:
            query = f"{keyword.term} {country_term}".strip()
            key = query.lower()
            if key in seen:
                continue
            seen.add(key)
            queries.append(
                {
                    "query": query,
                    "keyword": keyword.term,
                    "keyword_family": keyword.family,
                    "keyword_label": keyword.label,
                    "keyword_language": keyword.language,
                    "country_term": country_term,
                }
            )
            if len(queries) >= limit:
                return queries
    return queries
