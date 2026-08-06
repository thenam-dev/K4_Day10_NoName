from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import html
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import read_json, write_json


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_jats(text: Any) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", str(text))
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_date(item: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        date_payload = item.get(key)
        if not isinstance(date_payload, dict):
            continue

        date_parts = date_payload.get("date-parts") or []
        if date_parts and date_parts[0]:
            try:
                parts = [int(part) for part in date_parts[0]]
                year = parts[0]
                month = parts[1] if len(parts) >= 2 else 1
                day = parts[2] if len(parts) >= 3 else 1
                return datetime(year, month, day).date().isoformat()
            except (TypeError, ValueError):
                continue

        date_time = str(date_payload.get("date-time", ""))[:10]
        try:
            return datetime.strptime(date_time, "%Y-%m-%d").date().isoformat()
        except ValueError:
            continue
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref API payload response thành danh sách PaperRecord."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        doi = _clean_jats(item.get("DOI"))
        titles = item.get("title") or []
        title = _clean_jats(titles[0]) if titles else ""

        raw_abstract = item.get("abstract", "")
        summary = _clean_jats(raw_abstract)

        # Lọc bản ghi: bắt buộc có DOI, title và summary
        if not doi or not title or not summary:
            continue

        raw_authors = item.get("author") or []
        authors: list[str] = []
        for author in raw_authors:
            given = author.get("given", "").strip()
            family = author.get("family", "").strip()
            name = author.get("name", "").strip()
            full = f"{given} {family}".strip() if (given or family) else name
            if full:
                authors.append(full)
        if not authors:
            authors = ["Anonymous"]

        subjects = item.get("subject") or []
        categories = list(dict.fromkeys(filter(None, (_clean_jats(subject) for subject in subjects))))
        primary_category = categories[0] if categories else ""

        published = _extract_date(item, ["published-online", "published-print", "issued", "created"])
        updated = _extract_date(item, ["indexed", "deposited", "published-online", "published-print"])

        abs_url = _clean_jats(item.get("URL")) or f"https://doi.org/{doi}"

        pdf_url = abs_url
        for link in item.get("link", []):
            if link.get("content-type") == "application/pdf" and link.get("URL"):
                pdf_url = link["URL"]
                break

        container = item.get("container-title") or []
        comment = _clean_jats(container[0]) if container else ""

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Gọi Crossref API, lưu raw response, parse thành PaperRecord và lưu snapshot."""
    if not settings.refresh_source and settings.paths.raw_records_json.exists():
        return load_raw_records(settings.paths.raw_records_json)

    url = "https://api.crossref.org/works"
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {"User-Agent": "Day10DataObservabilityLab/1.0"}

    payload: dict[str, Any] | None = None
    last_error = "Crossref returned no usable response."
    max_retries = 4

    # Retry mechanism với exponential backoff cho 429/503/500/timeout
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                candidate = response.json()
                if not isinstance(candidate, dict):
                    last_error = "Crossref returned an invalid JSON payload."
                    break
                payload = candidate
                break
            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = f"Crossref returned retryable HTTP {response.status_code}."
                if attempt < max_retries - 1:
                    time.sleep((2**attempt) + 1)
                continue
            last_error = f"Crossref returned HTTP {response.status_code}."
            break
        except (requests.RequestException, ValueError) as exc:
            last_error = f"Crossref request failed: {exc}"
            if attempt < max_retries - 1:
                time.sleep((2**attempt) + 1)

    if payload is None:
        if settings.paths.raw_records_json.exists():
            return load_raw_records(settings.paths.raw_records_json)
        raise RuntimeError(last_error)

    records = parse_crossref_payload(payload)
    if not records:
        if settings.paths.raw_records_json.exists():
            return load_raw_records(settings.paths.raw_records_json)
        raise RuntimeError("Crossref response contained no valid paper records.")

    write_json(settings.paths.raw_api_response, payload)
    write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Đọc JSON snapshot và map thành danh sách PaperRecord."""
    raw_data = read_json(path)
    return [PaperRecord(**item) for item in raw_data]

