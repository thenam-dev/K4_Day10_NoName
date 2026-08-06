from pathlib import Path
from typing import Any
import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    total_rows = len(df)
    checks: dict[str, dict[str, Any]] = {}

    # Check 1: Row count
    row_count_passed = total_rows >= 5
    checks["row_count"] = {
        "passed": bool(row_count_passed),
        "actual": total_rows,
        "expected": ">= 5",
    }

    # Check 2: Paper ID uniqueness & non-null
    id_not_null = bool(df["paper_id"].notnull().all()) if total_rows > 0 else False
    id_unique = bool(df["paper_id"].is_unique) if total_rows > 0 else False
    checks["paper_id_validity"] = {
        "passed": id_not_null and id_unique,
        "not_null": id_not_null,
        "is_unique": id_unique,
    }

    # Check 3: Title completeness
    title_valid = bool(((df["title"].notnull()) & (df["title"].str.strip() != "")).all()) if total_rows > 0 else False
    checks["title_completeness"] = {
        "passed": title_valid,
        "empty_titles": int((df["title"].str.strip() == "").sum()) if total_rows > 0 else 0,
    }

    # Check 4: Summary length
    min_len_passed = bool((df["summary_chars"] >= 50).all()) if total_rows > 0 else False
    checks["summary_min_length"] = {
        "passed": min_len_passed,
        "short_summaries": int((df["summary_chars"] < 50).sum()) if total_rows > 0 else 0,
    }


    # Check 5: Freshness threshold ratio
    if total_rows > 0:
        fresh_count = int((df["age_days"] <= settings.freshness_threshold_days).sum())
        fresh_ratio = fresh_count / total_rows
    else:
        fresh_ratio = 0.0
    freshness_passed = fresh_ratio >= 0.7
    checks["freshness_ratio"] = {
        "passed": bool(freshness_passed),
        "actual_ratio": round(fresh_ratio, 4),
        "threshold": 0.7,
    }

    # Check 6: Title uniqueness
    title_unique = bool(df["title"].is_unique) if total_rows > 0 else False
    checks["title_uniqueness"] = {
        "passed": title_unique,
        "duplicate_titles": int(total_rows - df["title"].nunique()) if total_rows > 0 else 0,
    }

    all_passed = all(c["passed"] for c in checks.values())

    result = {
        "report_name": report_name,
        "total_rows": total_rows,
        "overall_passed": all_passed,
        "checks": checks,
    }

    output_path = settings.paths.quality_dir / f"{report_name}.json"
    write_json(output_path, result)
    return result


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path) -> dict[str, Any]:
    total_rows = len(df)
    if total_rows > 0:
        latest = str(df["published"].max())
        oldest = str(df["published"].min())
        stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum())
        stale_ratio = stale_rows / total_rows
        is_fresh = stale_ratio < 0.3
    else:
        latest = "N/A"
        oldest = "N/A"
        stale_rows = 0
        stale_ratio = 0.0
        is_fresh = False

    result = {
        "latest_published": latest,
        "oldest_published": oldest,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "freshness_threshold_days": settings.freshness_threshold_days,
        "is_fresh": is_fresh,
    }

    write_json(report_path, result)
    return result

