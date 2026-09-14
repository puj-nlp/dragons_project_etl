from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

GRAPH_BASE = "https://graph.threads.net"
SEARCH_ENDPOINT = f"{GRAPH_BASE}/keyword_search"

POST_FIELDS = ",".join(
    [
        "id",
        "media_product_type",
        "media_type",
        "permalink",
        "username",
        "text",
        "timestamp",
        "shortcode",
        "is_quote_post",
        "has_replies",
    ]
)

REPLY_FIELDS = ",".join(
    [
        "id",
        "media_product_type",
        "media_type",
        "permalink",
        "username",
        "text",
        "timestamp",
        "shortcode",
        "is_quote_post",
        "has_replies",
        "is_reply",
        "is_reply_owned_by_me",
        "root_post",
        "replied_to",
    ]
)


@dataclass(frozen=True)
class CountryConfig:
    key: str
    name: str
    queries: tuple[str, ...]


COUNTRIES: dict[str, CountryConfig] = {
    "colombia": CountryConfig(
        "colombia",
        "Colombia",
        (
            "biodiversidad Colombia",
            "biodiversity Colombia",
            "conservacion Colombia",
            "conservation Colombia",
            "deforestacion Colombia",
            "deforestation Colombia",
            "Amazonia Colombia",
            "Colombian Amazon",
            "wildlife Colombia",
            "COP16 biodiversity Cali",
        ),
    ),
    "united_kingdom": CountryConfig(
        "united_kingdom",
        "United Kingdom",
        (
            "biodiversity UK",
            "UK biodiversity loss",
            "British biodiversity",
            "nature recovery UK",
            "wildlife UK",
            "rewilding UK",
            "RSPB biodiversity",
        ),
    ),
    "hungary": CountryConfig(
        "hungary",
        "Hungary",
        (
            "biodiversity Hungary",
            "Hungarian biodiversity",
            "conservation Hungary",
            "wildlife Hungary",
            "Danube biodiversity Hungary",
        ),
    ),
}

_URL_RE = re.compile(r"https?://\S+")
_MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_.-]+")
_HASHTAG_RE = re.compile(r"(?<!\w)#(\w+)")


def parse_date(value: str) -> datetime:
    value = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def end_of_day_if_date(value: str) -> datetime:
    parsed = parse_date(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return parsed + timedelta(days=1) - timedelta(microseconds=1)
    return parsed


def to_threads_date(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def clean_social_text(text: str) -> str:
    text = text or ""
    text = _URL_RE.sub(" ", text)
    text = _MENTION_RE.sub(" ", text)
    text = _HASHTAG_RE.sub(r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def after_cursor(payload: dict[str, Any]) -> str | None:
    return ((payload.get("paging") or {}).get("cursors") or {}).get("after")


class ThreadsClient:
    def __init__(
        self,
        access_token: str | None,
        *,
        min_delay: float = 1.0,
        max_retries: int = 4,
        timeout: float = 30,
        session: requests.Session | None = None,
    ) -> None:
        if not access_token:
            raise ValueError("Set THREADS_ACCESS_TOKEN in .env")
        self.access_token = access_token
        self.min_delay = min_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = session or requests.Session()

    def _get(self, url: str, params: dict[str, Any]) -> tuple[dict[str, Any], int]:
        request_params = {**params, "access_token": self.access_token}
        for attempt in range(self.max_retries + 1):
            if self.min_delay > 0:
                time.sleep(self.min_delay + random.uniform(0, 0.25))
            response = self.session.get(url, params=request_params, timeout=self.timeout)
            if response.status_code == 200:
                return response.json(), response.status_code
            if response.status_code == 429 or 500 <= response.status_code <= 599:
                if attempt >= self.max_retries:
                    response.raise_for_status()
                raw_retry_after = response.headers.get("Retry-After")
                try:
                    wait = float(raw_retry_after) if raw_retry_after else None
                except ValueError:
                    wait = None
                time.sleep(wait if wait is not None else min(120.0, 2**attempt + random.uniform(0, 2)))
                continue
            response.raise_for_status()
        raise RuntimeError("Threads request did not return a response")

    def search(
        self,
        *,
        query: str,
        since: str,
        until: str,
        search_type: str = "RECENT",
        after: str | None = None,
        limit: int = 50,
    ) -> tuple[dict[str, Any], int]:
        params: dict[str, Any] = {
            "q": query,
            "search_type": search_type,
            "search_mode": "KEYWORD",
            "fields": POST_FIELDS,
            "limit": min(int(limit), 50),
            "since": since,
            "until": until,
        }
        if after:
            params["after"] = after
        return self._get(SEARCH_ENDPOINT, params)

    def conversation(
        self,
        *,
        post_id: str,
        after: str | None = None,
        limit: int = 50,
    ) -> tuple[dict[str, Any], int]:
        params: dict[str, Any] = {
            "fields": REPLY_FIELDS,
            "reverse": "false",
            "limit": min(int(limit), 50),
        }
        if after:
            params["after"] = after
        return self._get(f"{GRAPH_BASE}/{post_id}/conversation", params)


def post_to_document(
    post: dict[str, Any],
    *,
    requested_country: str,
    country_key: str,
    query: str,
    search_type: str,
    run_id: str,
    collected_at: datetime,
) -> dict[str, Any] | None:
    post_id = post.get("id")
    if not post_id:
        return None
    texto_raw = post.get("text") or ""
    text = clean_social_text(texto_raw)
    return {
        "id": str(post_id),
        "source": "threads",
        "source_type": "social_post",
        "origin_platform": "threads",
        "permalink": post.get("permalink"),
        "username": post.get("username"),
        "texto_raw": texto_raw,
        "texto_raw_length": len(texto_raw),
        "text": text,
        "text_length": len(text),
        "timestamp": post.get("timestamp"),
        "shortcode": post.get("shortcode"),
        "media_product_type": post.get("media_product_type"),
        "media_type": post.get("media_type"),
        "is_quote_post": bool(post.get("is_quote_post")),
        "has_replies": bool(post.get("has_replies")),
        "country_key": country_key,
        "country_requested": requested_country,
        "query": query,
        "search_type": search_type,
        "run_id": run_id,
        "collected_at": collected_at,
        "raw": post,
    }


def reply_to_document(
    reply: dict[str, Any],
    *,
    post_id: str,
    requested_country: str,
    run_id: str,
    collected_at: datetime,
) -> dict[str, Any] | None:
    reply_id = reply.get("id")
    if not reply_id:
        return None
    root = reply.get("root_post") or {}
    parent = reply.get("replied_to") or {}
    texto_raw = reply.get("text") or ""
    text = clean_social_text(texto_raw)
    return {
        "id": str(reply_id),
        "post_id": post_id,
        "root_post_id": root.get("id"),
        "replied_to_id": parent.get("id"),
        "source": "threads",
        "source_type": "social_reply",
        "origin_platform": "threads",
        "permalink": reply.get("permalink"),
        "username": reply.get("username"),
        "texto_raw": texto_raw,
        "texto_raw_length": len(texto_raw),
        "text": text,
        "text_length": len(text),
        "timestamp": reply.get("timestamp"),
        "shortcode": reply.get("shortcode"),
        "media_type": reply.get("media_type"),
        "has_replies": bool(reply.get("has_replies")),
        "country_requested": requested_country,
        "run_id": run_id,
        "collected_at": collected_at,
        "raw": reply,
    }
