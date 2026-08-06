from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import read_json, write_json

CROSSREF_API_URL = "https://api.crossref.org/works"

_TAG_RE = re.compile(r"<[^>]+>")
_RETRYABLE_STATUS_CODES = {429, 503}
_MAX_ATTEMPTS = 5
_INITIAL_BACKOFF_SECONDS = 1.0


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


def _strip_tags(value: str | None) -> str:
    """Remove XML/HTML tags (e.g. <jats:p>, <b>) and collapse whitespace."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", value)).strip()


def _format_date_parts(date_field: dict | None) -> str:
    if not date_field:
        return ""
    parts = date_field.get("date-parts")
    if not parts or not parts[0]:
        return ""
    piece = parts[0]
    if not piece or not piece[0]:
        return ""
    year = piece[0]
    month = piece[1] if len(piece) > 1 else 1
    day = piece[2] if len(piece) > 2 else 1
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except (TypeError, ValueError):
        return ""


def _extract_published(item: dict) -> str:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        formatted = _format_date_parts(item.get(key))
        if formatted:
            return formatted
    return ""


def _extract_updated(item: dict) -> str:
    for key in ("deposited", "indexed"):
        formatted = _format_date_parts(item.get(key))
        if formatted:
            return formatted
    return ""


def _extract_authors(item: dict) -> list[str]:
    authors: list[str] = []
    for author in item.get("author", []) or []:
        given = (author.get("given") or "").strip()
        family = (author.get("family") or "").strip()
        name = " ".join(part for part in (given, family) if part)
        if not name:
            name = (author.get("name") or "").strip()
        if name:
            authors.append(name)
    return authors


def _extract_pdf_url(item: dict) -> str:
    for link in item.get("link", []) or []:
        if link.get("content-type") == "application/pdf" and link.get("URL"):
            return link["URL"]
    resource_url = (item.get("resource", {}) or {}).get("primary", {}).get("URL")
    return resource_url or ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse the raw Crossref `/works` payload into a list of `PaperRecord`.

    Only items with a non-empty DOI, title and abstract are kept; XML/HTML
    tags found in Crossref's JATS-flavoured title/abstract fields are
    stripped out here.
    """
    items = ((payload or {}).get("message") or {}).get("items", []) or []
    records: list[PaperRecord] = []
    seen_ids: set[str] = set()

    for item in items:
        doi = (item.get("DOI") or "").strip()
        titles = item.get("title") or []
        title = _strip_tags(titles[0]) if titles else ""
        summary = _strip_tags(item.get("abstract"))

        if not doi or not title or not summary:
            continue
        if doi in seen_ids:
            continue
        seen_ids.add(doi)

        categories = [str(subject).strip() for subject in item.get("subject", []) or [] if str(subject).strip()]
        container_titles = item.get("container-title") or []
        comment = _strip_tags(container_titles[0]) if container_titles else ""

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=_extract_authors(item),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=_extract_published(item),
                updated=_extract_updated(item),
                abs_url=item.get("URL") or f"https://doi.org/{doi}",
                pdf_url=_extract_pdf_url(item),
                comment=comment,
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Call the Crossref API, persist raw artifacts and return parsed records.

    - Retries on HTTP 429/503 (and transient network errors) with
      exponential backoff, honouring `Retry-After` when present.
    - Saves the raw HTTP response to `settings.paths.raw_api_response`.
    - Saves the parsed flat records to `settings.paths.raw_records_json`.
    """
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }

    backoff_seconds = _INITIAL_BACKOFF_SECONDS
    last_error: Exception | None = None
    payload: dict | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = requests.get(CROSSREF_API_URL, params=params, timeout=30)
        except requests.RequestException as exc:
            last_error = exc
            if attempt == _MAX_ATTEMPTS:
                break
            time.sleep(backoff_seconds)
            backoff_seconds *= 2
            continue

        if response.status_code in _RETRYABLE_STATUS_CODES:
            last_error = RuntimeError(f"Crossref returned HTTP {response.status_code}")
            if attempt == _MAX_ATTEMPTS:
                break
            retry_after = response.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else backoff_seconds
            time.sleep(wait_seconds)
            backoff_seconds *= 2
            continue

        response.raise_for_status()
        payload = response.json()
        break

    if payload is None:
        raise RuntimeError(f"Failed to fetch data from Crossref after {_MAX_ATTEMPTS} attempts: {last_error}")

    write_json(settings.paths.raw_api_response, payload)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a previously saved `raw_records_json` snapshot back into `PaperRecord`."""
    payload = read_json(path)
    return [PaperRecord(**item) for item in payload]
