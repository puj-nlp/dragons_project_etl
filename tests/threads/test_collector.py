from __future__ import annotations

from datetime import datetime, timezone

from src.threads.collector import clean_social_text, post_to_document, reply_to_document


def test_clean_social_text_removes_urls_mentions_and_keeps_hashtag_text():
    assert clean_social_text("@user Biodiversidad #Colombia https://example.com/a") == "Biodiversidad Colombia"


def test_post_to_document_preserves_raw_and_clean_text():
    document = post_to_document(
        {
            "id": "post_1",
            "permalink": "https://threads.net/@u/post/1",
            "username": "u",
            "text": "@u Biodiversidad #Colombia https://example.com/a",
            "timestamp": "2026-09-01T00:00:00+0000",
            "has_replies": True,
        },
        requested_country="Colombia",
        country_key="colombia",
        query="biodiversidad Colombia",
        search_type="RECENT",
        run_id="run_1",
        collected_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )

    assert document is not None
    assert document["source"] == "threads"
    assert document["source_type"] == "social_post"
    assert document["texto_raw"] == "@u Biodiversidad #Colombia https://example.com/a"
    assert document["text"] == "Biodiversidad Colombia"
    assert document["has_replies"] is True


def test_reply_to_document_preserves_relationship_and_texts():
    document = reply_to_document(
        {
            "id": "reply_1",
            "text": "Respuesta #Biodiversidad https://example.com/r",
            "root_post": {"id": "post_1"},
            "replied_to": {"id": "post_1"},
        },
        post_id="post_1",
        requested_country="Colombia",
        run_id="run_1",
        collected_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )

    assert document is not None
    assert document["source_type"] == "social_reply"
    assert document["post_id"] == "post_1"
    assert document["text"] == "Respuesta Biodiversidad"
