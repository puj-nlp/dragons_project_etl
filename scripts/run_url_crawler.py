#!/usr/bin/env python3
"""Crawl pending URLs from MongoDB url_queue into url_crawls."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gdelt.common.config import load_crawler_config  # noqa: E402
from src.gdelt.common.exceptions import DragonsDataETLError  # noqa: E402
from src.gdelt.common.logging import configure_logging  # noqa: E402
from src.gdelt.pipelines.url_crawl_pipeline import UrlCrawlPipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl queued URLs from all ETL sources.")
    parser.add_argument("--config", default="config/sources/crawler.yaml")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source", choices=["gdelt", "media_cloud"], default=None)
    parser.add_argument("--strategy", default=None)
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Mantiene el proceso vivo y revisa periodicamente url_queue por URLs nuevas.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=60.0,
        help="Segundos entre revisiones cuando se usa --watch.",
    )
    parser.add_argument(
        "--max-idle-cycles",
        type=int,
        default=None,
        help="Detiene --watch despues de N ciclos sin URLs. Omitir para correr indefinidamente.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    if args.poll_seconds < 0:
        print("--poll-seconds debe ser mayor o igual a cero.", file=sys.stderr)
        return 2
    if args.max_idle_cycles is not None and args.max_idle_cycles < 1:
        print("--max-idle-cycles debe ser un entero positivo.", file=sys.stderr)
        return 2

    crawler_config = load_crawler_config(args.config)
    idle_cycles = 0
    try:
        while True:
            result = UrlCrawlPipeline(crawler_config=crawler_config).run(
                limit=args.limit,
                source=args.source,
                strategy=args.strategy,
            )
            print("\n=== URL crawl summary ===")
            print(json.dumps(result, indent=2, default=str))

            if not args.watch:
                break

            if int(result.get("selected") or 0) == 0:
                idle_cycles += 1
            else:
                idle_cycles = 0
            if args.max_idle_cycles is not None and idle_cycles >= args.max_idle_cycles:
                break
            time.sleep(args.poll_seconds)
    except DragonsDataETLError as exc:
        print(f"\nURL crawl failed at stage='{exc.stage}': {exc}", file=sys.stderr)
        return 1
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
