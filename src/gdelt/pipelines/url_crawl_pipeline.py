from __future__ import annotations

from typing import Any

from src.gdelt.common.config import (
    CrawlerConfig,
    MongoDBConfig,
    load_crawler_config,
    load_mongodb_config,
)
from src.gdelt.common.utils import new_run_id, utcnow
from src.gdelt.database.mongodb import MongoDBConnection
from src.gdelt.database.repositories import (
    PipelineRunsRepository,
    UrlCrawlsRepository,
    UrlQueueRepository,
    initialize_database,
)

_LOCAL_ONLY_FIELDS = {"html_path", "text_path", "metadata_path"}


class UrlCrawlPipeline:
    """Crawl pending URL queue records from any source strategy."""

    def __init__(
        self,
        crawler_config: CrawlerConfig | None = None,
        mongodb_config: MongoDBConfig | None = None,
        crawler: ArticleCrawler | None = None,
    ) -> None:
        self.crawler_config = crawler_config or load_crawler_config()
        self._mongodb_config = mongodb_config
        self._crawler = crawler

    def run(
        self,
        *,
        limit: int | None = None,
        source: str | None = None,
        strategy: str | None = None,
    ) -> dict[str, Any]:
        run_id = new_run_id("url_crawl")
        crawl_limit = limit if limit is not None else self.crawler_config.limit
        mongodb_config = self._mongodb_config or load_mongodb_config()
        connection = MongoDBConnection(mongodb_config)
        if self._crawler is None:
            from src.gdelt.collectors.web.crawler import ArticleCrawler

            crawler = ArticleCrawler(self.crawler_config)
        else:
            crawler = self._crawler
        try:
            initialize_database(connection, mongodb_config)
            queue_repo = UrlQueueRepository(connection, mongodb_config)
            crawls_repo = UrlCrawlsRepository(connection, mongodb_config)
            runs_repo = PipelineRunsRepository(connection, mongodb_config)
            targets = queue_repo.list_pending(limit=crawl_limit, source=source, strategy=strategy)
            now = utcnow()
            for target in targets:
                queue_repo.mark_processing(target["id"], run_id, now)
                target["run_id"] = run_id
            summary = crawler.crawl(targets, run_id=run_id) if targets else {"records": []}
            records = summary.pop("records", [])
            inserted = 0
            for record in records:
                crawl_id = f"crawl_{record.get('queue_id')}"
                mongo_record = {
                    "id": crawl_id,
                    **{key: value for key, value in record.items() if key not in _LOCAL_ONLY_FIELDS},
                    "html_path": record.get("html_path"),
                    "text_path": record.get("text_path"),
                    "metadata_path": record.get("metadata_path"),
                }
                crawls_repo.save(mongo_record)
                status = "crawled" if record.get("status") == "success" else "crawl_failed"
                queue_repo.mark_finished(
                    str(record.get("queue_id")),
                    status=status,
                    crawl_id=crawl_id,
                    error=record.get("error"),
                    now=utcnow(),
                )
                inserted += 1
            run_summary = {
                "run_id": run_id,
                "pipeline": "url_crawl",
                "status": "success",
                "source": source,
                "strategy": strategy,
                "requested_limit": crawl_limit,
                "selected": len(targets),
                "crawls_saved": inserted,
                **{key: value for key, value in summary.items() if key != "run_id"},
                "finished_at": utcnow(),
            }
            runs_repo.save(run_summary)
            return run_summary
        finally:
            crawler.close()
            connection.close()
