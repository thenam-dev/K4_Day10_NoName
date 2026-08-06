from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_SUMMARY_CHARS = 100


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run a small suite of data quality checks and persist the report.

    Checks: row count, `paper_id` not-null/unique, `title` not-null,
    minimum `summary` length, and freshness based on `age_days` vs.
    `settings.freshness_threshold_days`.
    """
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, details: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    total_rows = len(df)
    add_check("row_count_min", total_rows > 0, f"total_rows={total_rows}")

    if total_rows == 0:
        result = {
            "report_name": report_name,
            "generated_at": now_utc().isoformat(),
            "total_rows": 0,
            "checks": checks,
            "success": False,
        }
        write_json(settings.paths.quality_dir / f"{report_name}.json", result)
        return result

    paper_id_present = df["paper_id"].notna() & (df["paper_id"].astype(str).str.strip() != "")
    add_check(
        "paper_id_not_null",
        bool(paper_id_present.all()),
        f"missing_paper_id={int((~paper_id_present).sum())}",
    )

    paper_id_unique = not bool(df["paper_id"].duplicated().any())
    add_check(
        "paper_id_unique",
        paper_id_unique,
        f"duplicate_paper_id={int(df['paper_id'].duplicated().sum())}",
    )

    title_present = df["title"].notna() & (df["title"].astype(str).str.strip() != "")
    add_check(
        "title_not_null",
        bool(title_present.all()),
        f"missing_title={int((~title_present).sum())}",
    )

    summary_len_ok = df["summary"].astype(str).str.len() >= MIN_SUMMARY_CHARS
    add_check(
        "summary_min_length",
        bool(summary_len_ok.all()),
        f"short_summary_rows={int((~summary_len_ok).sum())} (min={MIN_SUMMARY_CHARS} chars)",
    )

    freshness_threshold = settings.freshness_threshold_days
    age_days = pd.to_numeric(df["age_days"], errors="coerce")
    fresh_ok = age_days.notna() & (age_days <= freshness_threshold)
    add_check(
        "freshness_within_threshold",
        bool(fresh_ok.all()),
        f"stale_or_missing_date_rows={int((~fresh_ok).sum())} (threshold={freshness_threshold} days)",
    )

    success = all(check["passed"] for check in checks)
    result = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "total_rows": total_rows,
        "checks": checks,
        "success": success,
    }
    write_json(settings.paths.quality_dir / f"{report_name}.json", result)
    return result


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize dataset freshness: latest/oldest published date and stale row count."""
    total_rows = len(df)
    if total_rows == 0:
        payload = {
            "generated_at": now_utc().isoformat(),
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "is_fresh": False,
        }
        write_json(report_path, payload)
        return payload

    published_dates = pd.to_datetime(df["published"], errors="coerce")
    valid_dates = published_dates.dropna()
    latest_published = valid_dates.max().date().isoformat() if not valid_dates.empty else None
    oldest_published = valid_dates.min().date().isoformat() if not valid_dates.empty else None

    age_days = pd.to_numeric(df["age_days"], errors="coerce")
    stale_mask = age_days.isna() | (age_days > settings.freshness_threshold_days)
    stale_rows = int(stale_mask.sum())

    payload = {
        "generated_at": now_utc().isoformat(),
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "is_fresh": stale_rows == 0,
    }
    write_json(report_path, payload)
    return payload
