from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _format_metrics_rows(metrics: dict[str, Any]) -> str:
    rows = []
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        if key in metrics:
            rows.append(f"| {key} | {_format_value(metrics[key])} |")
    return "\n".join(rows) if rows else "| (no metrics) | |"


def _format_quality_checks(quality: dict[str, Any]) -> str:
    lines = []
    for check in quality.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- [{status}] {check.get('name')}: {check.get('details')}")
    return "\n".join(lines) if lines else "- No checks recorded."


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline (phase 1) markdown report: source, metrics, quality, freshness."""
    lines = [
        "# Phase 1 Baseline Report",
        "",
        f"_Generated at {now_utc().isoformat()}_",
        "",
        "## Source",
        "",
        *(f"- **{key}**: {value}" for key, value in source_summary.items()),
        "",
        "## Evaluation metrics",
        "",
        "| metric | value |",
        "| --- | --- |",
        _format_metrics_rows(metrics),
        "",
        "## Data quality",
        "",
        f"- **status**: {'PASS' if quality.get('success') else 'FAIL'}",
        f"- **total_rows**: {quality.get('total_rows')}",
        "",
        _format_quality_checks(quality),
        "",
        "## Freshness",
        "",
        f"- **is_fresh**: {freshness.get('is_fresh')}",
        f"- **latest_published**: {freshness.get('latest_published')}",
        f"- **oldest_published**: {freshness.get('oldest_published')}",
        f"- **stale_rows**: {freshness.get('stale_rows')} / {freshness.get('total_rows')}",
        "",
    ]
    write_text(report_path, "\n".join(lines))


def _format_comparison_rows(baseline: dict[str, Any], corrupted: dict[str, Any], repaired: dict[str, Any]) -> str:
    keys = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]
    rows = []
    for key in keys:
        rows.append(
            f"| {key} | {_format_value(baseline.get(key))} | {_format_value(corrupted.get(key))} | "
            f"{_format_value(repaired.get(key))} |"
        )
    return "\n".join(rows)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write the markdown report comparing baseline vs corrupted vs repaired states."""
    lines = [
        "# Corruption / Repair Comparison Report",
        "",
        f"_Generated at {now_utc().isoformat()}_",
        "",
        "## Metrics comparison",
        "",
        "| metric | baseline | corrupted | repaired |",
        "| --- | --- | --- | --- |",
        _format_comparison_rows(baseline_metrics, corrupted_metrics, repaired_metrics),
        "",
        "## Data quality",
        "",
        f"- **corrupted**: {'PASS' if corrupted_quality.get('success') else 'FAIL'}",
        _format_quality_checks(corrupted_quality),
        "",
        f"- **repaired**: {'PASS' if repaired_quality.get('success') else 'FAIL'}",
        _format_quality_checks(repaired_quality),
        "",
        "## Freshness",
        "",
        f"- **corrupted.is_fresh**: {corrupted_freshness.get('is_fresh')} "
        f"(stale_rows={corrupted_freshness.get('stale_rows')}/{corrupted_freshness.get('total_rows')})",
        f"- **repaired.is_fresh**: {repaired_freshness.get('is_fresh')} "
        f"(stale_rows={repaired_freshness.get('stale_rows')}/{repaired_freshness.get('total_rows')})",
        "",
        "## Interpretation",
        "",
        "- `corrupted` vs `baseline`: corruption is expected to lower retrieval/answer quality metrics "
        "and/or fail quality or freshness checks.",
        "- `repaired` vs `baseline`: repairing from the raw source records should restore metrics close "
        "to the baseline.",
        "",
    ]
    write_text(report_path, "\n".join(lines))
