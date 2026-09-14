from __future__ import annotations

import random
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

API_BASE = "https://public.api.bsky.app"
AUTH_API_BASE = "https://bsky.social"
SEARCH_POSTS_ENDPOINT = f"{API_BASE}/xrpc/app.bsky.feed.searchPosts"
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class CountryConfig:
    key: str
    name: str
    queries: tuple[str, ...]
    country_terms: tuple[str, ...]
    location_terms: tuple[str, ...] = field(default_factory=tuple)
    organization_terms: tuple[str, ...] = field(default_factory=tuple)


COUNTRIES: dict[str, CountryConfig] = {
    "colombia": CountryConfig(
        key="colombia",
        name="Colombia",
        queries=(
            "biodiversidad Colombia",
            "biodiversity Colombia",
            "conservacion Colombia",
            "deforestacion Colombia",
            "Amazon Colombia biodiversity",
            "COP16 biodiversity Cali",
        ),
        country_terms=("colombia", "colombian", "colombiana", "colombiano"),
        location_terms=("bogota", "bogota", "cali", "medellin", "choco", "amazonas"),
        organization_terms=("instituto humboldt", "parques nacionales naturales", "minambiente"),
    ),
    "united_kingdom": CountryConfig(
        key="united_kingdom",
        name="United Kingdom",
        queries=(
            "biodiversity UK",
            "UK biodiversity loss",
            "nature recovery UK",
            "wildlife UK",
            "rewilding UK",
        ),
        country_terms=("united kingdom", "uk biodiversity", "britain", "british", "england", "scotland", "wales"),
        location_terms=("london", "edinburgh", "cardiff", "belfast", "yorkshire"),
        organization_terms=("natural england", "naturescot", "wildlife trusts", "rspb", "defra"),
    ),
    "hungary": CountryConfig(
        key="hungary",
        name="Hungary",
        queries=(
            "biodiversity Hungary",
            "Hungarian biodiversity",
            "conservation Hungary",
            "wildlife Hungary",
            "termeszetvedelem Magyarorszag",
        ),
        country_terms=("hungary", "hungarian", "magyarorszag", "magyar"),
        location_terms=("budapest", "balaton", "hortobagy", "danube hungary"),
        organization_terms=("mme birdlife hungary", "hortobagyi nemzeti park"),
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


def to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_for_matching(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.lower()).strip()


def clean_social_text(text: str) -> str:
    text = text or ""
    text = _URL_RE.sub(" ", text)
    text = _MENTION_RE.sub(" ", text)
    text = _HASHTAG_RE.sub(r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_country(text: str, configs: dict[str, CountryConfig] = COUNTRIES) -> tuple[str | None, float, list[str]]:
    normalized = normalize_for_matching(text)
    best_country: str | None = None
    best_score = 0.0
    best_evidence: list[str] = []

    for cfg in configs.values():
        score = 0.0
        evidence: list[str] = []
        for term in cfg.country_terms:
            if normalize_for_matching(term) in normalized:
                score += 0.55
                evidence.append(term)
        for term in cfg.location_terms:
            if normalize_for_matching(term) in normalized:
                score += 0.30
                evidence.append(term)
        for term in cfg.organization_terms:
            if normalize_for_matching(term) in normalized:
                score += 0.25
                evidence.append(term)
        if score > best_score:
            best_score = min(score, 1.0)
            best_country = cfg.name
            best_evidence = evidence

    return best_country, round(best_score, 3), best_evidence


class BlueskyPublicClient:
    def __init__(
        self,
        *,
        timeout: float = 30,
        min_delay: float = 0.6,
        max_retries: int = 4,
        user_agent: str = "DragonsDataETL/0.1 (research; biodiversity corpus)",
        identifier: str | None = None,
        app_password: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.min_delay = min_delay
        self.max_retries = max_retries
        self.base_url = AUTH_API_BASE if identifier and app_password else API_BASE
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
        if identifier and app_password:
            self.authenticate(identifier=identifier, app_password=app_password)

    def authenticate(self, *, identifier: str, app_password: str) -> None:
        response = self.session.post(
            f"{AUTH_API_BASE}/xrpc/com.atproto.server.createSession",
            json={"identifier": identifier, "password": app_password},
            timeout=self.timeout,
        )
        response.raise_for_status()
        access_jwt = response.json()["accessJwt"]
        self.session.headers.update({"Authorization": f"Bearer {access_jwt}"})

    def search_page(
        self,
        *,
        query: str,
        since: str,
        until: str,
        cursor: str | None = None,
        limit: int = MAX_PAGE_SIZE,
        sort: str = "latest",
    ) -> tuple[dict[str, Any], int]:
        params: dict[str, Any] = {
            "q": query,
            "limit": min(int(limit), MAX_PAGE_SIZE),
            "sort": sort,
            "since": since,
            "until": until,
        }
        if cursor:
            params["cursor"] = cursor

        for attempt in range(self.max_retries + 1):
            if self.min_delay > 0:
                time.sleep(self.min_delay + random.uniform(0, 0.25))
            response = self.session.get(
                f"{self.base_url}/xrpc/app.bsky.feed.searchPosts",
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json(), response.status_code
            if response.status_code == 429 or 500 <= response.status_code <= 599:
                if attempt >= self.max_retries:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else min(60.0, (2 ** attempt) + random.uniform(0, 2))
                time.sleep(wait)
                continue
            response.raise_for_status()

        raise RuntimeError("Bluesky search did not return a response")


def post_to_document(
    post: dict[str, Any],
    *,
    requested_country: str,
    country_key: str,
    query: str,
    run_id: str,
    collected_at: datetime,
) -> dict[str, Any] | None:
    uri = post.get("uri")
    if not uri:
        return None

    record = post.get("record") or {}
    author = post.get("author") or {}
    handle = author.get("handle")
    rkey = str(uri).rsplit("/", 1)[-1]
    web_url = f"https://bsky.app/profile/{handle}/post/{rkey}" if handle else None
    texto_raw = record.get("text") or ""
    text = clean_social_text(texto_raw)
    detected, confidence, evidence = classify_country(texto_raw)

    return {
        "id": f"bluesky_{uri.rsplit('/', 1)[-1]}",
        "source": "bluesky",
        "source_type": "social_post",
        "origin_platform": "bluesky",
        "uri": uri,
        "cid": post.get("cid"),
        "web_url": web_url,
        "texto_raw": texto_raw,
        "texto_raw_length": len(texto_raw),
        "text": text,
        "text_length": len(text),
        "created_at": record.get("createdAt"),
        "indexed_at": post.get("indexedAt"),
        "langs": record.get("langs") or [],
        "author": {
            "did": author.get("did"),
            "handle": handle,
            "display_name": author.get("displayName"),
            "description": author.get("description"),
        },
        "engagement": {
            "reply_count": post.get("replyCount", 0),
            "repost_count": post.get("repostCount", 0),
            "like_count": post.get("likeCount", 0),
            "quote_count": post.get("quoteCount", 0),
        },
        "country_key": country_key,
        "country_requested": requested_country,
        "country_detected": detected,
        "country_confidence": confidence,
        "country_evidence": evidence,
        "query": query,
        "run_id": run_id,
        "collected_at": collected_at,
        "raw": post,
    }
