from __future__ import annotations

from src.social_keywords import build_social_queries, load_keyword_terms


def test_load_keyword_terms_from_shared_keyword_maps():
    terms = load_keyword_terms(languages=("en",), max_terms_per_family=1)

    assert terms
    assert terms[0].language == "en"
    assert terms[0].family == "A"
    assert terms[0].term


def test_build_social_queries_adds_country_context():
    queries = build_social_queries("colombia", limit=5, max_terms_per_family=1)

    assert len(queries) == 5
    assert all("query" in item for item in queries)
    assert any("Colombia" in item["query"] for item in queries)
    assert all(item["keyword_family"] for item in queries)
