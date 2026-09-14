from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.gdelt.common.config import PROJECT_ROOT, load_yaml
from src.gdelt.common.utils import utcnow

HEADER_ALIASES = {
    "id": "eid",
    "eid": "eid",
    "indexed date": "indexed_date",
    "indexed_date": "indexed_date",
    "media name": "media_name",
    "media_name": "media_name",
    "media url": "media_url",
    "media_url": "media_url",
    "publish date": "publish_date",
    "publish_date": "publish_date",
    "title": "title",
    "url": "url",
    "language": "language",
}


def normalize_header(value: str | None) -> str:
    if value is None:
        return ""
    return HEADER_ALIASES.get(value.replace("\ufeff", "").strip().lower(), value.strip())


def hash_url(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def load_mediacloud_settings(path: str | Path = "config/sources/mediacloud.yaml") -> dict[str, Any]:
    raw = load_yaml(path)
    raw["root_dir"] = str(_resolve_path(raw.get("root_dir", "data/media-cloud/White lists")))
    raw["limit"] = int(raw.get("limit", 10))
    raw["default_strategy"] = raw.get("default_strategy", "whitelist")
    raw["language_folders"] = {
        str(key).lower(): value for key, value in raw.get("language_folders", {}).items()
    }
    return raw


def _language_from_path(path: Path, root: Path, language_folders: dict[str, str]) -> str:
    relative = path.relative_to(root)
    folder = relative.parts[0].lower() if relative.parts else ""
    language = language_folders.get(folder)
    if not language:
        raise ValueError(f"No language mapping for Media Cloud folder '{folder}'")
    return language


def _keyword_family_from_path(path: Path) -> str:
    return path.stem.strip()


def _detect_dialect(path: Path) -> csv.Dialect:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    dialect = _detect_dialect(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, dialect=dialect)
        rows: list[dict[str, Any]] = []
        for raw in reader:
            if raw.get(None):
                continue
            row = {normalize_header(key): value for key, value in raw.items() if normalize_header(key)}
            rows.append(row)
        return rows


def _read_xlsx_rows(path: Path) -> list[dict[str, Any]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required to load .xlsx Media Cloud files") from exc

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    iterator = sheet.iter_rows(values_only=True)
    headers = [normalize_header(str(value or "")) for value in next(iterator)]
    rows = []
    for values in iterator:
        rows.append({headers[index]: value for index, value in enumerate(values) if index < len(headers)})
    workbook.close()
    return rows


def iter_source_documents(
    root_dir: str | Path,
    *,
    language_folders: dict[str, str],
    strategy: str = "whitelist",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    root = _resolve_path(root_dir)
    if not root.exists():
        raise FileNotFoundError(f"Media Cloud root not found: {root}")

    loaded_at = utcnow()
    documents: list[dict[str, Any]] = []
    files = sorted([*root.rglob("*.csv"), *root.rglob("*.xlsx")])
    for path in files:
        language = _language_from_path(path, root, language_folders)
        keyword_family = _keyword_family_from_path(path)
        rows = _read_xlsx_rows(path) if path.suffix.lower() == ".xlsx" else _read_csv_rows(path)
        for row_number, row in enumerate(rows, start=2):
            url = str(row.get("url") or "").strip()
            if not is_http_url(url):
                continue
            eid = str(row.get("eid") or row.get("id") or hash_url(url)).strip()
            source_uid = f"mediacloud:{language}:{keyword_family}:{eid}"
            document = {
                "source_uid": source_uid,
                "source": "media_cloud",
                "strategy": strategy,
                "status": "loaded",
                "eid": eid,
                "url": url,
                "url_hash": hash_url(url),
                "language": str(row.get("language") or language).strip() or language,
                "keyword_family": keyword_family,
                "indexed_date": row.get("indexed_date"),
                "media_name": row.get("media_name"),
                "media_url": row.get("media_url"),
                "publish_date": row.get("publish_date"),
                "title": row.get("title"),
                "source_file": str(path),
                "source_row": row_number,
                "loaded_at": loaded_at,
                "raw": row,
            }
            documents.append(document)
            if limit is not None and len(documents) >= limit:
                return documents
    return documents


def build_queue_documents(
    source_documents: list[dict[str, Any]],
    *,
    run_id: str,
) -> list[dict[str, Any]]:
    queued_at = utcnow()
    queue_documents = []
    for document in source_documents:
        queue_documents.append(
            {
                "id": f"uq_{document['url_hash'][:24]}_{document['source']}_{document['strategy']}",
                "source": document["source"],
                "strategy": document["strategy"],
                "status": "pending",
                "url": document["url"],
                "url_hash": document["url_hash"],
                "source_document_id": document["source_uid"],
                "queued_at": queued_at,
                "run_id": run_id,
                "metadata": {
                    key: document.get(key)
                    for key in (
                        "eid",
                        "language",
                        "keyword_family",
                        "indexed_date",
                        "media_name",
                        "media_url",
                        "publish_date",
                        "title",
                        "source_file",
                        "source_row",
                    )
                },
            }
        )
    return queue_documents
