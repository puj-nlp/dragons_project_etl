#!/usr/bin/env python3
"""Seed url_queue with local sample URLs for integration testing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gdelt.common.config import load_mongodb_config  # noqa: E402
from src.gdelt.common.utils import hash_identifier, new_run_id, utcnow  # noqa: E402
from src.gdelt.database.mongodb import MongoDBConnection  # noqa: E402
from src.gdelt.database.repositories import PipelineRunsRepository, UrlQueueRepository, initialize_database  # noqa: E402
from src.mediacloud.loader import iter_source_documents, load_mediacloud_settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed sample GDELT-like URL queue records.")
    parser.add_argument("--source", default="gdelt")
    parser.add_argument("--strategy", default="event_query_sample")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--mediacloud-config", default="config/sources/mediacloud.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_mediacloud_settings(args.mediacloud_config)
    run_id = new_run_id("sample_queue")
    source_documents = iter_source_documents(
        settings["root_dir"],
        language_folders=settings["language_folders"],
        strategy=args.strategy,
        limit=args.limit,
    )
    queued_at = utcnow()
    queue_documents = []
    for index, document in enumerate(source_documents, start=1):
        url_hash = hash_identifier(document["url"])
        queue_documents.append(
            {
                "id": f"uq_{url_hash[:24]}_{args.source}_{args.strategy}",
                "source": args.source,
                "strategy": args.strategy,
                "status": "pending",
                "url": document["url"],
                "url_hash": url_hash,
                "source_document_id": f"{args.source}:sample:{index}",
                "queued_at": queued_at,
                "run_id": run_id,
                "metadata": {
                    "sample": True,
                    "event_id": "SAMPLE-01",
                    "media_name": document.get("media_name"),
                    "title": document.get("title"),
                    "language": document.get("language"),
                    "source_from": "media_cloud_local_listing",
                },
            }
        )

    config = load_mongodb_config()
    connection = MongoDBConnection(config)
    try:
        initialize_database(connection, config)
        result = UrlQueueRepository(connection, config).upsert_many(queue_documents)
        summary = {
            "run_id": run_id,
            "pipeline": "sample_url_queue",
            "status": "success" if result.failed == 0 else "partial",
            "source": args.source,
            "strategy": args.strategy,
            "queue_documents": result.inserted,
            "failed": result.failed,
            "finished_at": utcnow(),
        }
        PipelineRunsRepository(connection, config).save(summary)
        print(json.dumps(summary, indent=2, default=str))
        return 0 if summary["status"] == "success" else 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
