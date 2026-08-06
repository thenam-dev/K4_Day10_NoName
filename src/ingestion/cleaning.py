from dataclasses import asdict
from datetime import datetime
import re
import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def _strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    return normalize_whitespace(cleaned)


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    rows = []
    run_dt_date = run_date.date() if isinstance(run_date, datetime) else run_date

    for record in records:
        data = asdict(record)
        title = _strip_html(data.get("title", ""))
        summary = _strip_html(data.get("summary", ""))
        authors = data.get("authors", [])
        categories = data.get("categories", [])
        published_str = data.get("published", "2024-01-01")

        try:
            pub_date = datetime.strptime(published_str[:10], "%Y-%m-%d").date()
        except ValueError:
            pub_date = run_dt_date

        age_days = (run_dt_date - pub_date).days
        authors_joined = ", ".join(authors) if isinstance(authors, list) else str(authors)
        categories_joined = ", ".join(categories) if isinstance(categories, list) else str(categories)
        summary_chars = len(summary)

        # Tạo cột biểu diễn ngữ nghĩa cho vector embedding
        text_for_embedding = (
            f"Title: {title} | Authors: {authors_joined} | Summary: {summary}"
        )

        rows.append(
            {
                "paper_id": data.get("paper_id", "").strip(),
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": data.get("primary_category", "Computer Science"),
                "published": published_str,
                "updated": data.get("updated", published_str),
                "age_days": age_days,
                "summary_chars": summary_chars,
                "text_for_embedding": text_for_embedding,
                "abs_url": data.get("abs_url", ""),
                "pdf_url": data.get("pdf_url", ""),
                "comment": data.get("comment", ""),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Deduplicate theo paper_id và title
    df = df.drop_duplicates(subset=["paper_id"]).drop_duplicates(subset=["title"])

    # Loại bỏ bản ghi rác: title không rỗng và summary_chars >= 50
    df = df[(df["title"].str.strip() != "") & (df["summary_chars"] >= 50)]
    df = df.sort_values(by="published", ascending=False).reset_index(drop=True)
    return df

