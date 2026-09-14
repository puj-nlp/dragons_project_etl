#!/usr/bin/env python3
"""Run the 10-document URL extraction proof of concept.

This local exercise avoids BigQuery credentials: Media Cloud URLs come from the
local whitelist files, and GDELT-like URLs are seeded into the shared queue with
source=gdelt so the same queue crawler path is tested for both sources.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gdelt.common.config import load_crawler_config, load_mongodb_config  # noqa: E402
from src.gdelt.common.logging import configure_logging  # noqa: E402
from src.gdelt.common.utils import hash_identifier, new_run_id, utcnow  # noqa: E402
from src.gdelt.database.export_sample import configured_collection_names, export_collection_samples  # noqa: E402
from src.gdelt.database.mongodb import MongoDBConnection  # noqa: E402
from src.gdelt.database.repositories import PipelineRunsRepository, UrlQueueRepository, initialize_database  # noqa: E402
from src.gdelt.pipelines.url_crawl_pipeline import UrlCrawlPipeline  # noqa: E402
from src.mediacloud.loader import iter_source_documents, load_mediacloud_settings  # noqa: E402
from src.mediacloud.pipeline import MediaCloudLoadPipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a 10-document URL queue/crawl/export PoC.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--mediacloud-config", default="config/sources/mediacloud.yaml")
    parser.add_argument("--crawler-config", default="config/sources/crawler.yaml")
    parser.add_argument("--export-dir", default="data/mongo_exports/poc_10")
    parser.add_argument(
        "--skip-crawl",
        action="store_true",
        help="Solo carga/encola URLs y exporta muestras, sin descargar HTML.",
    )
    return parser.parse_args()


def seed_gdelt_sample_queue(limit: int, mediacloud_config: str) -> dict[str, Any]:
    settings = load_mediacloud_settings(mediacloud_config)
    run_id = new_run_id("gdelt_sample_queue")
    source_documents = iter_source_documents(
        settings["root_dir"],
        language_folders=settings["language_folders"],
        strategy="event_query_sample",
        limit=limit,
    )
    queued_at = utcnow()
    queue_documents = []
    for index, document in enumerate(source_documents, start=1):
        url_hash = hash_identifier(document["url"])
        queue_documents.append(
            {
                "id": f"uq_{url_hash[:24]}_gdelt_event_query_sample",
                "source": "gdelt",
                "strategy": "event_query_sample",
                "status": "pending",
                "url": document["url"],
                "url_hash": url_hash,
                "source_document_id": f"gdelt:sample:{index}",
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
    with MongoDBConnection(config) as connection:
        initialize_database(connection, config)
        result = UrlQueueRepository(connection, config).upsert_many(queue_documents)
        summary = {
            "run_id": run_id,
            "pipeline": "gdelt_sample_url_queue",
            "status": "success" if result.failed == 0 else "partial",
            "source": "gdelt",
            "strategy": "event_query_sample",
            "queue_documents": result.inserted,
            "failed": result.failed,
            "finished_at": utcnow(),
        }
        PipelineRunsRepository(connection, config).save(summary)
        return summary


def collection_counts() -> dict[str, int]:
    config = load_mongodb_config()
    with MongoDBConnection(config) as connection:
        initialize_database(connection, config)
        return {
            name: connection.database[name].count_documents({})
            for name in configured_collection_names(config)
        }


def export_samples(limit: int, output_dir: str) -> dict[str, Any]:
    config = load_mongodb_config()
    with MongoDBConnection(config) as connection:
        initialize_database(connection, config)
        return export_collection_samples(
            connection.database,
            output_dir=Path(output_dir),
            limit=limit,
            formats=("csv", "xlsx"),
            collection_names=configured_collection_names(config),
        )


def main() -> int:
    configure_logging()
    args = parse_args()
    if args.limit < 1:
        print("--limit debe ser un entero positivo.", file=sys.stderr)
        return 2

    media_cloud = MediaCloudLoadPipeline().run(
        config_path=args.mediacloud_config,
        limit=args.limit,
    )
    gdelt_sample = seed_gdelt_sample_queue(args.limit, args.mediacloud_config)

    crawls: list[dict[str, Any]] = []
    if not args.skip_crawl:
        crawler_config = load_crawler_config(args.crawler_config)
        crawler = UrlCrawlPipeline(crawler_config=crawler_config)
        crawls.append(crawler.run(limit=args.limit, source="media_cloud", strategy="whitelist"))
        crawls.append(crawler.run(limit=args.limit, source="gdelt", strategy="event_query_sample"))

    export = export_samples(args.limit, args.export_dir)
    summary = {
        "status": "success",
        "limit": args.limit,
        "media_cloud_load": media_cloud,
        "gdelt_sample_queue": gdelt_sample,
        "url_crawls": crawls,
        "collection_counts": collection_counts(),
        "export": export,
    }
    print("\n=== URL PoC 10 summary ===")
    print(json.dumps(summary, indent=2, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
