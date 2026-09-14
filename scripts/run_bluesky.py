#!/usr/bin/env python3
"""Run Bluesky biodiversity collection into MongoDB."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bluesky.collector import COUNTRIES, BlueskyPublicClient  # noqa: E402
from src.bluesky.pipeline import BlueskyPipeline  # noqa: E402
from src.gdelt.common.logging import configure_logging  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect public Bluesky biodiversity posts into MongoDB.")
    parser.add_argument("--countries", nargs="+", choices=list(COUNTRIES), default=["colombia", "united_kingdom", "hungary"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--since", default="2024-01-01")
    parser.add_argument("--until", default="2026-09-11")
    parser.add_argument("--max-pages-per-query", type=int, default=1)
    parser.add_argument("--min-delay", type=float, default=0.6)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument(
        "--legacy-queries",
        action="store_true",
        help="Usa las consultas internas antiguas en lugar de src/mediacloud/resources/keyword_maps.",
    )
    parser.add_argument(
        "--offline-sample",
        action="store_true",
        help="Usa posts de muestra locales para validar la integracion Mongo sin llamar la API de Bluesky.",
    )
    return parser.parse_args()


class _OfflineSampleClient:
    def search_page(self, **kwargs):
        limit = int(kwargs.get("limit") or 10)
        query = kwargs.get("query") or "biodiversidad Colombia"
        posts = []
        for index in range(1, limit + 1):
            posts.append(
                {
                    "uri": f"at://did:plc:offline/app.bsky.feed.post/sample{index:02d}",
                    "cid": f"offline-cid-{index:02d}",
                    "record": {
                        "text": (
                            f"Post de muestra {index} sobre biodiversidad Colombia "
                            f"conservacion #Biodiversidad https://example.com/{index}"
                        ),
                        "createdAt": "2026-09-01T00:00:00Z",
                        "langs": ["es"],
                    },
                    "indexedAt": "2026-09-01T00:00:01Z",
                    "author": {
                        "did": "did:plc:offline",
                        "handle": "offline-sample.bsky.social",
                        "displayName": "Offline Sample",
                    },
                    "replyCount": index,
                    "repostCount": index + 1,
                    "likeCount": index + 2,
                    "quoteCount": 0,
                }
            )
        return {"posts": posts}, 200


def main() -> int:
    configure_logging()
    args = parse_args()
    if args.limit < 1:
        print("--limit debe ser un entero positivo.", file=sys.stderr)
        return 2
    if args.max_pages_per_query < 1:
        print("--max-pages-per-query debe ser un entero positivo.", file=sys.stderr)
        return 2

    client = (
        _OfflineSampleClient()
        if args.offline_sample
        else BlueskyPublicClient(
            min_delay=args.min_delay,
            max_retries=args.max_retries,
            identifier=os.environ.get("BLUESKY_IDENTIFIER"),
            app_password=os.environ.get("BLUESKY_APP_PASSWORD"),
        )
    )
    result = BlueskyPipeline(client=client).run(
        countries=args.countries,
        limit=args.limit,
        since=args.since,
        until=args.until,
        max_pages_per_query=args.max_pages_per_query,
        use_keyword_maps=not args.legacy_queries,
    )
    print("\n=== Bluesky run summary ===")
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
