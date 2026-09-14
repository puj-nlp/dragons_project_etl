from __future__ import annotations

from typing import Any

import requests

from src.bluesky.collector import (
    COUNTRIES,
    MAX_PAGE_SIZE,
    BlueskyPublicClient,
    CountryConfig,
    end_of_day_if_date,
    parse_date,
    post_to_document,
    to_iso_z,
)
from src.gdelt.common.config import MongoDBConfig, load_mongodb_config
from src.gdelt.common.utils import new_run_id, utcnow
from src.gdelt.database.mongodb import MongoDBConnection
from src.gdelt.database.repositories import BlueskyPostsRepository, PipelineRunsRepository, initialize_database
from src.social_keywords import build_social_queries


class BlueskyPipeline:
    def __init__(
        self,
        *,
        client: BlueskyPublicClient | None = None,
        mongodb_config: MongoDBConfig | None = None,
        country_configs: dict[str, CountryConfig] | None = None,
    ) -> None:
        self.client = client or BlueskyPublicClient()
        self._mongodb_config = mongodb_config
        self.country_configs = country_configs or COUNTRIES

    def run(
        self,
        *,
        countries: list[str] | None = None,
        limit: int = 10,
        since: str = "2024-01-01",
        until: str = "2026-09-11",
        max_pages_per_query: int = 1,
        use_keyword_maps: bool = True,
    ) -> dict[str, Any]:
        if limit < 1:
            raise ValueError("limit must be positive")
        if max_pages_per_query < 1:
            raise ValueError("max_pages_per_query must be positive")

        selected = countries or list(self.country_configs)
        for country in selected:
            if country not in self.country_configs:
                raise ValueError(f"Unknown Bluesky country: {country}")

        run_id = new_run_id("bluesky")
        since_ts = to_iso_z(parse_date(since))
        until_ts = to_iso_z(end_of_day_if_date(until))
        config = self._mongodb_config or load_mongodb_config()
        collected_at = utcnow()

        connection = MongoDBConnection(config)
        try:
            initialize_database(connection, config)
            posts_repo = BlueskyPostsRepository(connection, config)
            runs_repo = PipelineRunsRepository(connection, config)

            summary: dict[str, Any] = {
                "run_id": run_id,
                "pipeline": "bluesky",
                "status": "success",
                "source": "bluesky",
                "source_type": "social_post",
                "countries": selected,
                "requested_limit": limit,
                "since": since_ts,
                "until": until_ts,
                "fetched": 0,
                "documents_saved": 0,
                "failed": 0,
                "query_results": [],
            }

            saved = 0
            for country_key in selected:
                cfg = self.country_configs[country_key]
                query_specs = (
                    build_social_queries(country_key, limit=max(30, limit * 3))
                    if use_keyword_maps
                    else [{"query": query} for query in cfg.queries]
                )
                for query_spec in query_specs:
                    if saved >= limit:
                        break
                    query = query_spec["query"]
                    cursor = None
                    for page in range(1, max_pages_per_query + 1):
                        if saved >= limit:
                            break
                        try:
                            payload, status = self.client.search_page(
                                query=query,
                                since=since_ts,
                                until=until_ts,
                                cursor=cursor,
                                limit=min(MAX_PAGE_SIZE, limit - saved),
                            )
                        except requests.HTTPError as exc:
                            response = exc.response
                            summary["status"] = "failed"
                            summary["error"] = {
                                "type": type(exc).__name__,
                                "message": str(exc),
                                "http_status": response.status_code if response is not None else None,
                                "query": query,
                                "country": country_key,
                            }
                            summary["finished_at"] = utcnow()
                            runs_repo.save(summary)
                            return summary
                        except requests.RequestException as exc:
                            summary["status"] = "failed"
                            summary["error"] = {
                                "type": type(exc).__name__,
                                "message": str(exc),
                                "query": query,
                                "country": country_key,
                            }
                            summary["finished_at"] = utcnow()
                            runs_repo.save(summary)
                            return summary
                        raw_posts = payload.get("posts") or []
                        documents = [
                            document
                            for post in raw_posts
                            if (
                                document := post_to_document(
                                    post,
                                    requested_country=cfg.name,
                                    country_key=country_key,
                                    query=query,
                                    run_id=run_id,
                                    collected_at=collected_at,
                                )
                            )
                        ]
                        for document in documents:
                            document["keyword_metadata"] = {
                                key: value
                                for key, value in query_spec.items()
                                if key != "query"
                            }
                        result = posts_repo.upsert_many(documents)
                        saved += result.inserted
                        summary["fetched"] += len(raw_posts)
                        summary["documents_saved"] += result.inserted
                        summary["failed"] += result.failed
                        summary["query_results"].append(
                            {
                                "country": country_key,
                                "query": query,
                                "page": page,
                                "http_status": status,
                                "fetched": len(raw_posts),
                                "saved": result.inserted,
                                "failed": result.failed,
                            }
                        )
                        if result.quota_exceeded:
                            summary["status"] = "quota_exceeded"
                            break
                        cursor = payload.get("cursor")
                        if not raw_posts or not cursor:
                            break
                    if summary["status"] == "quota_exceeded":
                        break
                if saved >= limit or summary["status"] == "quota_exceeded":
                    break

            if summary["failed"] and summary["status"] == "success":
                summary["status"] = "partial"
            summary["finished_at"] = utcnow()
            runs_repo.save(summary)
            return summary
        finally:
            connection.close()
