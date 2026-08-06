from __future__ import annotations

from datetime import datetime
import re

import pandas as pd

from ingestion.crossref import PaperRecord

_TAG_RE = re.compile(r"<[^>]+>")
MIN_SUMMARY_CHARS = 100


def _strip_tags(value: str | None) -> str:
    """Remove any leftover XML/HTML tags (e.g. <jats:p>, <b>) and collapse whitespace."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", value)).strip()


def _parse_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a dataframe ready for embedding.

    - Strips XML/HTML tags from title/summary.
    - Drops records without a title or with a summary shorter than
      `MIN_SUMMARY_CHARS` characters.
    - Normalizes published date to YYYY-MM-DD and computes `age_days`.
    - Joins authors/categories into `authors_joined`/`categories_joined`.
    - Builds `text_for_embedding`.
    - Drops duplicate `paper_id` and sorts by freshness (newest first).
    """
    run_day = run_date.date() if isinstance(run_date, datetime) else run_date

    rows: list[dict] = []
    for record in records:
        title = _strip_tags(record.title)
        summary = _strip_tags(record.summary)

        if not record.paper_id or not title or len(summary) < MIN_SUMMARY_CHARS:
            continue

        authors = [author.strip() for author in record.authors if author and author.strip()]
        categories = [category.strip() for category in record.categories if category and category.strip()]
        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)

        published_date = _parse_date(record.published)
        published = published_date.isoformat() if published_date else ""
        age_days = (run_day - published_date).days if published_date else None

        text_for_embedding = f"Title: {title} | Authors: {authors_joined} | Summary: {summary}"

        rows.append(
            {
                "paper_id": record.paper_id,
                "title": title,
                "summary": summary,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "primary_category": _strip_tags(record.primary_category),
                "published": published,
                "updated": record.updated,
                "age_days": age_days,
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
                "comment": _strip_tags(record.comment),
                "summary_chars": len(summary),
                "text_for_embedding": text_for_embedding,
            }
        )

    columns = [
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "categories_joined",
        "primary_category",
        "published",
        "updated",
        "age_days",
        "abs_url",
        "pdf_url",
        "comment",
        "summary_chars",
        "text_for_embedding",
    ]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df

    df = df.drop_duplicates(subset="paper_id", keep="first")
    df = df[df["title"].str.len() > 0]
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df
