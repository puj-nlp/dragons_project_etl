#!/usr/bin/env python3
"""Run Threads biodiversity collection into MongoDB."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gdelt.common.logging import configure_logging  # noqa: E402
from src.threads.collector import COUNTRIES, ThreadsClient  # noqa: E402
from src.threads.pipeline import ThreadsPipeline  # noqa: E402


class _OfflineSampleClient:
    def search(self, **kwargs):
        limit = min(int(kwargs.get("limit") or 10), 50)
        posts = []
        for index in range(1, limit + 1):
            posts.append(
                {
                    "id": f"threads_sample_{index:02d}",
                    "media_product_type": "THREADS",
                    "media_type": "TEXT_POST",
                    "permalink": f"https://www.threads.net/@offline/post/sample{index:02d}",
                    "username": "offline",
                    "text": (
                        f"Post de muestra {index} sobre biodiversidad Colombia "
                        f"conservacion #Biodiversidad https://example.com/{index}"
                    ),
                    "timestamp": "2026-09-01T00:00:00+0000",
                    "shortcode": f"sample{index:02d}",
                    "is_quote_post": False,
                    "has_replies": index <= 2,
                }
            )
        return {"data": posts}, 200

    def conversation(self, **kwargs):
        post_id = kwargs["post_id"]
        replies = [
            {
                "id": f"{post_id}_reply_01",
                "media_product_type": "THREADS",
                "media_type": "TEXT_POST",
                "permalink": f"https://www.threads.net/@offline/post/{post_id}_reply_01",
                "username": "offline_reply",
                "text": f"Respuesta sobre biodiversidad para {post_id} https://example.com/reply",
                "timestamp": "2026-09-01T00:01:00+0000",
                "shortcode": f"{post_id}_r01",
                "has_replies": False,
                "is_reply": True,
                "root_post": {"id": post_id},
                "replied_to": {"id": post_id},
            }
        ]
        return {"data": replies}, 200


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect public Threads biodiversity posts into MongoDB.")
    parser.add_argument("--countries", nargs="+", choices=list(COUNTRIES), default=["colombia", "united_kingdom", "hungary"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--since", default="2025-01-01")
    parser.add_argument("--until", default="2026-09-11")
    parser.add_argument("--search-types", nargs="+", choices=["RECENT", "TOP"], default=["RECENT"])
    parser.add_argument("--max-pages-per-query", type=int, default=1)
    parser.add_argument("--download-replies", action="store_true")
    parser.add_argument("--max-conversation-posts", type=int, default=None)
    parser.add_argument("--max-pages-per-conversation", type=int, default=1)
    parser.add_argument("--min-delay", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument(
        "--legacy-queries",
        action="store_true",
        help="Usa las consultas internas antiguas en lugar de src/mediacloud/resources/keyword_maps.",
    )
    parser.add_argument(
        "--offline-sample",
        action="store_true",
        help="Usa posts de muestra locales para validar la integracion Mongo sin llamar la API de Threads.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    if args.limit < 1:
        print("--limit debe ser un entero positivo.", file=sys.stderr)
        return 2

    try:
        client = (
            _OfflineSampleClient()
            if args.offline_sample
            else ThreadsClient(
                os.environ.get("THREADS_ACCESS_TOKEN"),
                min_delay=args.min_delay,
                max_retries=args.max_retries,
            )
        )
    except ValueError as exc:
        print(f"Threads config failed: {exc}", file=sys.stderr)
        return 1

    result = ThreadsPipeline(client=client).run(
        countries=args.countries,
        limit=args.limit,
        since=args.since,
        until=args.until,
        search_types=args.search_types,
        max_pages_per_query=args.max_pages_per_query,
        download_replies=args.download_replies,
        max_conversation_posts=args.max_conversation_posts,
        max_pages_per_conversation=args.max_pages_per_conversation,
        use_keyword_maps=not args.legacy_queries,
    )
    print("\n=== Threads run summary ===")
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
