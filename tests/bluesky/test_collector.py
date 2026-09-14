from __future__ import annotations

from datetime import datetime, timezone

from src.bluesky.collector import clean_social_text, post_to_document


def test_clean_social_text_removes_urls_mentions_and_keeps_hashtag_text():
    cleaned = clean_social_text("@user Biodiversidad #Colombia https://example.com/a\n nueva")

    assert cleaned == "Biodiversidad Colombia nueva"


def test_post_to_document_preserves_raw_and_clean_text():
    post = {
        "uri": "at://did:plc:abc/app.bsky.feed.post/123",
        "cid": "cid1",
        "record": {
            "text": "@org Biodiversidad #Colombia https://example.com/a",
            "createdAt": "2026-09-01T00:00:00Z",
            "langs": ["es"],
        },
        "indexedAt": "2026-09-01T00:00:01Z",
        "author": {"did": "did:plc:abc", "handle": "user.bsky.social"},
        "likeCount": 2,
    }

    document = post_to_document(
        post,
        requested_country="Colombia",
        country_key="colombia",
        query="biodiversidad Colombia",
        run_id="run_1",
        collected_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )

    assert document is not None
    assert document["source"] == "bluesky"
    assert document["source_type"] == "social_post"
    assert document["texto_raw"] == "@org Biodiversidad #Colombia https://example.com/a"
    assert document["text"] == "Biodiversidad Colombia"
    assert document["web_url"] == "https://bsky.app/profile/user.bsky.social/post/123"
