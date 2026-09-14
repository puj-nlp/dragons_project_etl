from __future__ import annotations

from typing import Any

from src.gdelt.common.utils import hash_identifier, utcnow


def queue_document_from_gdelt_whitelist(
    document: dict[str, Any],
    *,
    run_id: str,
) -> dict[str, Any] | None:
    url = str(document.get("url") or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return None
    url_hash = hash_identifier(url)
    source_document_id = str(document.get("id") or document.get("gkg_record_id"))
    return {
        "id": f"uq_{url_hash[:24]}_gdelt_event",
        "source": "gdelt",
        "strategy": "event_query",
        "status": "pending",
        "url": url,
        "url_hash": url_hash,
        "source_document_id": source_document_id,
        "queued_at": utcnow(),
        "run_id": run_id,
        "metadata": {
            "gkg_record_id": document.get("gkg_record_id"),
            "gkg_date": document.get("date"),
            "source_common_name": document.get("source_common_name"),
            "id_query": document.get("id_query"),
            "id_metric": document.get("id_metric"),
            "themes": document.get("themes"),
            "locations": document.get("locations"),
            "persons": document.get("persons"),
            "organizations": document.get("organizations"),
            "tone": document.get("tone"),
        },
    }


def queue_documents_from_gdelt_whitelist(
    documents: list[dict[str, Any]],
    *,
    run_id: str,
) -> list[dict[str, Any]]:
    queued = []
    for document in documents:
        queue_document = queue_document_from_gdelt_whitelist(document, run_id=run_id)
        if queue_document is not None:
            queued.append(queue_document)
    return queued
