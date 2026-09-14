from __future__ import annotations

import pytest

from src.bluesky.pipeline import BlueskyPipeline
from src.gdelt.common.config import MongoDBConfig
from src.gdelt.database.repositories import initialize_database

mongomock = pytest.importorskip("mongomock")


def _mongo_config() -> MongoDBConfig:
    return MongoDBConfig(
        uri="mongodb://localhost:27017",
        database="test_db",
        gkg_records_collection="gkg_records",
        execution_metrics_collection="execution_metrics",
        crawled_data_collection="crawled_data",
        eventos_collection="eventos",
        queries_collection="queries",
        whitelist_collection="whitelist",
        scrapper_collection="scrapper",
        metrics_collection="metrics",
        connect_timeout_ms=1000,
        server_selection_timeout_ms=1000,
        ordered_inserts=False,
        ensure_indexes_on_startup=True,
    )


class _FakeMongo:
    def __init__(self, config: MongoDBConfig) -> None:
        self.config = config
        self._client = mongomock.MongoClient()

    @property
    def client(self):
        return self._client

    @property
    def database(self):
        return self._client[self.config.database]

    def close(self) -> None:
        return None


class _FakeClient:
    def search_page(self, **kwargs):
        return {
            "posts": [
                {
                    "uri": f"at://did:plc:abc/app.bsky.feed.post/{index}",
                    "cid": f"cid{index}",
                    "record": {
                        "text": f"Post {index} sobre biodiversidad Colombia https://example.com/{index}",
                        "createdAt": "2026-09-01T00:00:00Z",
                        "langs": ["es"],
                    },
                    "indexedAt": "2026-09-01T00:00:01Z",
                    "author": {"did": "did:plc:abc", "handle": "user.bsky.social"},
                }
                for index in range(1, 4)
            ]
        }, 200


def test_bluesky_pipeline_writes_posts_and_run(monkeypatch):
    config = _mongo_config()
    fake = _FakeMongo(config)
    monkeypatch.setattr(
        "src.bluesky.pipeline.MongoDBConnection",
        lambda config: fake,
    )
    initialize_database(fake, config)

    summary = BlueskyPipeline(client=_FakeClient(), mongodb_config=config).run(
        countries=["colombia"],
        limit=3,
        since="2026-09-01",
        until="2026-09-11",
        use_keyword_maps=True,
    )

    assert summary["documents_saved"] == 3
    assert fake.database[config.bluesky_posts_collection].count_documents({}) == 3
    stored = fake.database[config.bluesky_posts_collection].find_one({"uri": "at://did:plc:abc/app.bsky.feed.post/1"})
    assert stored["source"] == "bluesky"
    assert stored["keyword_metadata"]["keyword_family"]
    assert stored["texto_raw"].startswith("Post 1")
    assert "https://example.com" not in stored["text"]
    assert fake.database[config.pipeline_runs_collection].count_documents({"pipeline": "bluesky"}) == 1
