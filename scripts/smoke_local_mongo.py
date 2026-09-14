#!/usr/bin/env python3
"""Check local NLP MongoDB collections and document counts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gdelt.common.config import load_mongodb_config  # noqa: E402
from src.gdelt.database.export_sample import configured_collection_names  # noqa: E402
from src.gdelt.database.mongodb import MongoDBConnection  # noqa: E402
from src.gdelt.database.repositories import initialize_database  # noqa: E402


def main() -> int:
    config = load_mongodb_config()
    connection = MongoDBConnection(config)
    try:
        initialize_database(connection, config)
        names = configured_collection_names(config)
        counts = {
            name: connection.database[name].count_documents({})
            for name in names
        }
        print(json.dumps({"database": config.database, "counts": counts}, indent=2))
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
