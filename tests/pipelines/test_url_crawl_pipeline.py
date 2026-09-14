from __future__ import annotations

from datetime import date

import pytest

from src.gdelt.common.config import CrawlerConfig, MongoDBConfig
from src.gdelt.database.repositories import UrlQueueRepository, initialize_database
from src.gdelt.pipelines.url_crawl_pipeline import UrlCrawlPipeline

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


class _FakeCrawler:
    def crawl(self, targets, run_id=None):
        return {
            "run_id": run_id,
            "attempted": len(targets),
            "succeeded": len(targets),
            "records": [
                {
                    "queue_id": target["id"],
                    "source": target["source"],
                    "strategy": target["strategy"],
                    "source_document_id": target["source_document_id"],
                    "url_hash": target["url_hash"],
                    "document_identifier": target["url"],
                    "source_url": target["url"],
                    "status": "success",
                    "texto_raw": "\nraw article text\n",
                    "texto_raw_length": 18,
                    "text": "article text",
                    "crawled_at": date(2026, 9, 9).isoformat(),
                    "run_id": run_id,
                }
                for target in targets
            ],
        }

    def close(self):
        return None


def test_url_crawl_pipeline_processes_pending_queue(monkeypatch):
    config = _mongo_config()
    fake = _FakeMongo(config)
    monkeypatch.setattr(
        "src.gdelt.pipelines.url_crawl_pipeline.MongoDBConnection",
        lambda config: fake,
    )
    initialize_database(fake, config)
    queue_repo = UrlQueueRepository(fake, config)
    queue_repo.upsert_many(
        [
            {
                "id": "uq_1",
                "source": "media_cloud",
                "strategy": "whitelist",
                "status": "pending",
                "url": "https://example.com/a",
                "url_hash": "hash_1",
                "source_document_id": "mediacloud:es:A:1",
                "queued_at": date(2026, 9, 9).isoformat(),
                "run_id": "load_1",
                "metadata": {"language": "es"},
            }
        ]
    )

    summary = UrlCrawlPipeline(
        crawler_config=CrawlerConfig(
            output_dir="data/crawled",
            limit=10,
            user_agent="test",
            request_timeout_seconds=1,
            delay_seconds=0,
            respect_robots_txt=False,
            max_html_bytes=1000,
        ),
        mongodb_config=config,
        crawler=_FakeCrawler(),
    ).run(limit=10, source="media_cloud")

    assert summary["selected"] == 1
    assert fake.database["url_crawls"].count_documents({"queue_id": "uq_1"}) == 1
    assert fake.database["url_crawls"].find_one({"queue_id": "uq_1"})["texto_raw"]
    assert fake.database["url_queue"].find_one({"id": "uq_1"})["status"] == "crawled"
