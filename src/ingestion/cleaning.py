from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
import re
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


_CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "authors_joined",
    "categories",
    "categories_joined",
    "primary_category",
    "published",
    "updated",
    "age_days",
    "summary_chars",
    "text_for_embedding",
    "abs_url",
    "pdf_url",
    "comment",
]


def _clean_text(value: Any) -> str:
    """Remove lightweight HTML/JATS markup and normalize whitespace."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", str(value)))


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    cleaned = [_clean_text(item) for item in value]
    return list(dict.fromkeys(item for item in cleaned if item))


def _parse_iso_date(value: Any) -> date | None:
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _empty_clean_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=_CLEAN_COLUMNS)


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize valid Crossref records into the stable schema used downstream.

    A record is valid only when it has a stable ID, a title, a sufficiently useful
    abstract, and a parseable publication date.  Invalid dates are deliberately
    dropped instead of being replaced with the run date, which would hide a
    freshness issue from the observability checks.
    """
    run_day = run_date.date() if isinstance(run_date, datetime) else run_date
    if not isinstance(run_day, date):
        raise TypeError("run_date must be a datetime or date instance.")

    rows: list[dict[str, Any]] = []
    for record in records:
        raw = asdict(record)
        paper_id = _clean_text(raw["paper_id"])
        title = _clean_text(raw["title"])
        summary = _clean_text(raw["summary"])
        published_day = _parse_iso_date(raw["published"])
        updated_day = _parse_iso_date(raw["updated"])

        # Keep cleaning rules explicit so quality reports reflect real defects.
        if not paper_id or not title or len(summary) < 50 or published_day is None:
            continue

        authors = _clean_list(raw["authors"])
        categories = _clean_list(raw["categories"])
        authors_joined = compact_join(authors) or "Anonymous"
        categories_joined = compact_join(categories) or "Uncategorized"
        primary_category = _clean_text(raw["primary_category"])
        if not primary_category:
            primary_category = categories[0] if categories else "Uncategorized"

        text_for_embedding = " | ".join(
            (
                f"Title: {title}",
                f"Authors: {authors_joined}",
                f"Categories: {categories_joined}",
                f"Published: {published_day.isoformat()}",
                f"Summary: {summary}",
            )
        )
        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": primary_category,
                "published": published_day.isoformat(),
                "updated": updated_day.isoformat() if updated_day else published_day.isoformat(),
                "age_days": max(0, (run_day - published_day).days),
                "summary_chars": len(summary),
                "text_for_embedding": text_for_embedding,
                "abs_url": _clean_text(raw["abs_url"]),
                "pdf_url": _clean_text(raw["pdf_url"]),
                "comment": _clean_text(raw["comment"]),
            }
        )

    if not rows:
        return _empty_clean_dataframe()

    df = pd.DataFrame(rows)
    # Prefer the most complete/most recently updated version of a duplicate.
    df = df.sort_values(
        ["summary_chars", "updated", "paper_id"],
        ascending=[False, False, True],
        kind="mergesort",
    )
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df.drop_duplicates(subset=["title"], keep="first")
    return df.sort_values(["published", "paper_id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
