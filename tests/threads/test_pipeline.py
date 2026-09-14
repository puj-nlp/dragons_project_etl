from __future__ import annotations

import pytest

from src.gdelt.common.config import MongoDBConfig
from src.gdelt.database.repositories import initialize_database
from src.threads.pipeline import ThreadsPipeline

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
    def search(self, **kwargs):
        return {
            "data": [
                {
                    "id": f"post_{index}",
                    "permalink": f"https://threads.net/@u/post/{index}",
                    "username": "u",
                    "text": f"Post {index} biodiversidad Colombia https://example.com/{index}",
                    "timestamp": "2026-09-01T00:00:00+0000",
                    "has_replies": index == 1,
                }
                for index in range(1, 4)
            ]
        }, 200

    def conversation(self, **kwargs):
        post_id = kwargs["post_id"]
        return {
            "data": [
                {
                    "id": "reply_1",
                    "text": "Respuesta biodiversidad https://example.com/r",
                    "root_post": {"id": post_id},
                    "replied_to": {"id": post_id},
                }
            ]
        }, 200


def test_threads_pipeline_writes_posts_replies_and_run(monkeypatch):
    config = _mongo_config()
    fake = _FakeMongo(config)
    monkeypatch.setattr("src.threads.pipeline.MongoDBConnection", lambda config: fake)
    initialize_database(fake, config)

    summary = ThreadsPipeline(client=_FakeClient(), mongodb_config=config).run(
        countries=["colombia"],
        limit=3,
        since="2026-09-01",
        until="2026-09-11",
        download_replies=True,
        max_conversation_posts=1,
        use_keyword_maps=True,
    )

    assert summary["documents_saved"] == 3
    assert summary["replies_saved"] == 1
    assert fake.database[config.threads_posts_collection].count_documents({}) == 3
    assert fake.database[config.threads_replies_collection].count_documents({}) == 1
    stored = fake.database[config.threads_posts_collection].find_one({"id": "post_1"})
    assert stored["source"] == "threads"
    assert stored["keyword_metadata"]["keyword_family"]
    assert stored["texto_raw"].startswith("Post 1")
    assert "https://example.com" not in stored["text"]
    assert fake.database[config.pipeline_runs_collection].count_documents({"pipeline": "threads"}) == 1
