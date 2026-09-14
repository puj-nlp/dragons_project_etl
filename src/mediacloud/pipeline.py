from __future__ import annotations

from pathlib import Path
from typing import Any

from src.gdelt.common.config import MongoDBConfig, load_mongodb_config
from src.gdelt.common.utils import new_run_id, utcnow
from src.gdelt.database.mongodb import MongoDBConnection
from src.gdelt.database.repositories import (
    MediaCloudSourcesRepository,
    PipelineRunsRepository,
    UrlQueueRepository,
    initialize_database,
)
from src.mediacloud.loader import build_queue_documents, iter_source_documents, load_mediacloud_settings


class MediaCloudLoadPipeline:
    def __init__(self, mongodb_config: MongoDBConfig | None = None) -> None:
        self._mongodb_config = mongodb_config

    def run(
        self,
        *,
        config_path: str | Path = "config/sources/mediacloud.yaml",
        root_dir: str | Path | None = None,
        limit: int | None = None,
        strategy: str | None = None,
    ) -> dict[str, Any]:
        settings = load_mediacloud_settings(config_path)
        run_id = new_run_id("mediacloud_load")
        documents = iter_source_documents(
            root_dir or settings["root_dir"],
            language_folders=settings["language_folders"],
            strategy=strategy or settings["default_strategy"],
            limit=limit if limit is not None else settings["limit"],
        )
        mongodb_config = self._mongodb_config or load_mongodb_config()
        connection = MongoDBConnection(mongodb_config)
        try:
            initialize_database(connection, mongodb_config)
            sources = MediaCloudSourcesRepository(connection, mongodb_config)
            queue = UrlQueueRepository(connection, mongodb_config)
            runs = PipelineRunsRepository(connection, mongodb_config)
            source_result = sources.upsert_many(documents)
            queue_documents = build_queue_documents(documents, run_id=run_id)
            queue_result = queue.upsert_many(queue_documents)
            sources.mark_queued([document["source_uid"] for document in documents])
            summary = {
                "run_id": run_id,
                "pipeline": "media_cloud_load",
                "status": "success" if not source_result.failed and not queue_result.failed else "partial",
                "source_documents": source_result.inserted,
                "queue_documents": queue_result.inserted,
                "failed": source_result.failed + queue_result.failed,
                "finished_at": utcnow(),
            }
            runs.save(summary)
            return summary
        finally:
            connection.close()
