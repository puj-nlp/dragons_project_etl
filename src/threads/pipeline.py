from __future__ import annotations

from typing import Any

import requests

from src.gdelt.common.config import MongoDBConfig, load_mongodb_config
from src.gdelt.common.utils import new_run_id, utcnow
from src.gdelt.database.mongodb import MongoDBConnection
from src.gdelt.database.repositories import (
    PipelineRunsRepository,
    ThreadsPostsRepository,
    ThreadsRepliesRepository,
    initialize_database,
)
from src.social_keywords import build_social_queries
from src.threads.collector import (
    COUNTRIES,
    ThreadsClient,
    after_cursor,
    end_of_day_if_date,
    parse_date,
    post_to_document,
    reply_to_document,
    to_threads_date,
)


class ThreadsPipeline:
    def __init__(
        self,
        *,
        client: ThreadsClient,
        mongodb_config: MongoDBConfig | None = None,
    ) -> None:
        self.client = client
        self._mongodb_config = mongodb_config

    def run(
        self,
        *,
        countries: list[str] | None = None,
        limit: int = 10,
        since: str = "2025-01-01",
        until: str = "2026-09-11",
        search_types: list[str] | None = None,
        max_pages_per_query: int = 1,
        download_replies: bool = False,
        max_conversation_posts: int | None = None,
        max_pages_per_conversation: int = 1,
        use_keyword_maps: bool = True,
    ) -> dict[str, Any]:
        if limit < 1:
            raise ValueError("limit must be positive")
        if max_pages_per_query < 1:
            raise ValueError("max_pages_per_query must be positive")
        if max_pages_per_conversation < 1:
            raise ValueError("max_pages_per_conversation must be positive")

        selected = countries or list(COUNTRIES)
        for country in selected:
            if country not in COUNTRIES:
                raise ValueError(f"Unknown Threads country: {country}")
        requested_search_types = search_types or ["RECENT"]

        run_id = new_run_id("threads")
        since_date = to_threads_date(parse_date(since))
        until_date = to_threads_date(end_of_day_if_date(until))
        config = self._mongodb_config or load_mongodb_config()
        collected_at = utcnow()

        connection = MongoDBConnection(config)
        try:
            initialize_database(connection, config)
            posts_repo = ThreadsPostsRepository(connection, config)
            replies_repo = ThreadsRepliesRepository(connection, config)
            runs_repo = PipelineRunsRepository(connection, config)
            summary: dict[str, Any] = {
                "run_id": run_id,
                "pipeline": "threads",
                "status": "success",
                "source": "threads",
                "source_type": "social_post",
                "countries": selected,
                "requested_limit": limit,
                "since": since_date,
                "until": until_date,
                "search_types": requested_search_types,
                "download_replies": download_replies,
                "fetched": 0,
                "documents_saved": 0,
                "replies_fetched": 0,
                "replies_saved": 0,
                "failed": 0,
                "query_results": [],
                "conversation_results": [],
            }

            saved = 0
            posts_for_replies: list[dict[str, Any]] = []
            for country_key in selected:
                cfg = COUNTRIES[country_key]
                query_specs = (
                    build_social_queries(country_key, limit=max(30, limit * 3))
                    if use_keyword_maps
                    else [{"query": query} for query in cfg.queries]
                )
                for query_spec in query_specs:
                    if saved >= limit:
                        break
                    query = query_spec["query"]
                    for search_type in requested_search_types:
                        if saved >= limit:
                            break
                        after = None
                        for page in range(1, max_pages_per_query + 1):
                            if saved >= limit:
                                break
                            try:
                                payload, status = self.client.search(
                                    query=query,
                                    since=since_date,
                                    until=until_date,
                                    search_type=search_type,
                                    after=after,
                                    limit=limit - saved,
                                )
                            except requests.HTTPError as exc:
                                return self._save_failed_run(
                                    runs_repo,
                                    summary,
                                    exc,
                                    query=query,
                                    country=country_key,
                                )
                            except (requests.RequestException, RuntimeError, ValueError) as exc:
                                return self._save_failed_run(
                                    runs_repo,
                                    summary,
                                    exc,
                                    query=query,
                                    country=country_key,
                                )

                            raw_posts = payload.get("data") or []
                            documents = [
                                document
                                for raw_post in raw_posts
                                if (
                                    document := post_to_document(
                                        raw_post,
                                        requested_country=cfg.name,
                                        country_key=country_key,
                                        query=query,
                                        search_type=search_type,
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
                            posts_for_replies.extend(
                                document
                                for document in documents
                                if document.get("has_replies")
                            )
                            summary["fetched"] += len(raw_posts)
                            summary["documents_saved"] += result.inserted
                            summary["failed"] += result.failed
                            summary["query_results"].append(
                                {
                                    "country": country_key,
                                    "query": query,
                                    "search_type": search_type,
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
                            next_after = after_cursor(payload)
                            if not raw_posts or not next_after or next_after == after:
                                break
                            after = next_after
                        if summary["status"] == "quota_exceeded":
                            break
                    if summary["status"] == "quota_exceeded":
                        break
                if saved >= limit or summary["status"] == "quota_exceeded":
                    break

            if download_replies and summary["status"] == "success":
                self._download_replies(
                    replies_repo,
                    summary,
                    posts_for_replies,
                    run_id=run_id,
                    collected_at=collected_at,
                    max_posts=max_conversation_posts,
                    max_pages=max_pages_per_conversation,
                )

            if summary["failed"] and summary["status"] == "success":
                summary["status"] = "partial"
            summary["finished_at"] = utcnow()
            runs_repo.save(summary)
            return summary
        finally:
            connection.close()

    def _download_replies(
        self,
        replies_repo: ThreadsRepliesRepository,
        summary: dict[str, Any],
        posts: list[dict[str, Any]],
        *,
        run_id: str,
        collected_at,
        max_posts: int | None,
        max_pages: int,
    ) -> None:
        selected_posts = posts[:max_posts] if max_posts else posts
        for post in selected_posts:
            after = None
            for page in range(1, max_pages + 1):
                payload, status = self.client.conversation(
                    post_id=post["id"],
                    after=after,
                )
                raw_replies = payload.get("data") or []
                documents = [
                    document
                    for raw_reply in raw_replies
                    if (
                        document := reply_to_document(
                            raw_reply,
                            post_id=post["id"],
                            requested_country=post["country_requested"],
                            run_id=run_id,
                            collected_at=collected_at,
                        )
                    )
                ]
                result = replies_repo.upsert_many(documents)
                summary["replies_fetched"] += len(raw_replies)
                summary["replies_saved"] += result.inserted
                summary["failed"] += result.failed
                summary["conversation_results"].append(
                    {
                        "post_id": post["id"],
                        "page": page,
                        "http_status": status,
                        "fetched": len(raw_replies),
                        "saved": result.inserted,
                        "failed": result.failed,
                    }
                )
                next_after = after_cursor(payload)
                if not raw_replies or not next_after or next_after == after:
                    break
                after = next_after

    @staticmethod
    def _save_failed_run(
        runs_repo: PipelineRunsRepository,
        summary: dict[str, Any],
        exc: BaseException,
        *,
        query: str,
        country: str,
    ) -> dict[str, Any]:
        response = getattr(exc, "response", None)
        summary["status"] = "failed"
        summary["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "http_status": response.status_code if response is not None else None,
            "query": query,
            "country": country,
        }
        summary["finished_at"] = utcnow()
        runs_repo.save(summary)
        return summary
