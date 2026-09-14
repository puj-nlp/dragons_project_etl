#!/usr/bin/env python3
"""Load Media Cloud whitelist CSV/XLSX rows into MongoDB and enqueue URLs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gdelt.common.exceptions import DragonsDataETLError  # noqa: E402
from src.gdelt.common.logging import configure_logging  # noqa: E402
from src.mediacloud.pipeline import MediaCloudLoadPipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Media Cloud source listings into MongoDB.")
    parser.add_argument("--config", default="config/sources/mediacloud.yaml")
    parser.add_argument("--root-dir", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--strategy", default=None)
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    try:
        result = MediaCloudLoadPipeline().run(
            config_path=args.config,
            root_dir=args.root_dir,
            limit=args.limit,
            strategy=args.strategy,
        )
    except (DragonsDataETLError, RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"\nMedia Cloud load failed: {exc}", file=sys.stderr)
        return 1
    print("\n=== Media Cloud load summary ===")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
