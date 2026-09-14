from __future__ import annotations

from src.mediacloud.loader import build_queue_documents, iter_source_documents


def test_iter_source_documents_reads_real_media_cloud_sample():
    documents = iter_source_documents(
        "data/media-cloud/White lists",
        language_folders={
            "white list español": "es",
            "white list ingles": "en",
            "white list hungaro": "hu",
            "spanish": "es",
            "english": "en",
            "hungarian": "hu",
        },
        limit=10,
    )

    assert len(documents) == 10
    assert documents[0]["source"] == "media_cloud"
    assert documents[0]["strategy"] == "whitelist"
    assert documents[0]["url"].startswith("http")
    assert documents[0]["source_uid"]
    assert documents[0]["url_hash"]


def test_build_queue_documents_preserves_metadata():
    source_documents = [
        {
            "source_uid": "mediacloud:es:A:1",
            "source": "media_cloud",
            "strategy": "whitelist",
            "url": "https://example.com/a",
            "url_hash": "abc",
            "eid": "1",
            "language": "es",
            "keyword_family": "A",
            "title": "Title",
        }
    ]

    queue = build_queue_documents(source_documents, run_id="run_1")

    assert queue[0]["source_document_id"] == "mediacloud:es:A:1"
    assert queue[0]["metadata"]["keyword_family"] == "A"
    assert queue[0]["status"] == "pending"
