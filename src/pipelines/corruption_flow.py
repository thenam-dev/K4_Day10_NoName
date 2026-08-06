from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    print("=== Step 0: Loading Settings & Baseline Artifacts ===")
    settings = load_settings()

    if not settings.paths.baseline_metrics.exists() or not settings.paths.clean_json.exists():
        raise RuntimeError("Baseline artifacts not found. Run `script/run_phase1.py` before the corruption flow.")

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_df = pd.DataFrame(read_json(settings.paths.clean_json))
    print(f"Loaded baseline dataset with {len(baseline_df)} rows.")

    print("=== Step 1: Corrupting Clean Data ===")
    corrupted_df = corrupt_clean_dataframe(baseline_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    print(
        f"Corrupted dataset has {len(corrupted_df)} rows (from {len(baseline_df)} baseline rows). "
        f"Log: {settings.paths.corruption_log.name}"
    )

    print("=== Step 2: Rebuilding Vector Store on Corrupted Data ===")
    corrupted_index = LocalEmbeddingIndex.build(corrupted_df, settings, settings.paths.corrupted_embeddings_json)

    print("=== Step 3: Evaluating Corrupted Data on the Frozen Test Set ===")
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    print(f"Corrupted Retrieval Hit Rate: {corrupted_bundle.summary['retrieval_hit_rate']:.4f}")
    print(f"Corrupted Mean Token F1:     {corrupted_bundle.summary['mean_token_f1']:.4f}")

    print("=== Step 4: Quality & Freshness Checks on Corrupted Data ===")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted_quality_checks")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, settings.paths.quality_dir / "corrupted_freshness_report.json"
    )
    print(f"Corrupted Quality Status: {'PASSED' if corrupted_quality.get('overall_passed') else 'FAILED'}")

    print("=== Step 5: Repairing Data From Raw Snapshot ===")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, now_utc())
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    print(f"Repaired dataset has {len(repaired_df)} rows.")

    print("=== Step 6: Rebuilding Vector Store on Repaired Data ===")
    repaired_index = LocalEmbeddingIndex.build(repaired_df, settings, settings.paths.repaired_embeddings_json)

    print("=== Step 7: Evaluating Repaired Data on the Frozen Test Set ===")
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    print(f"Repaired Retrieval Hit Rate: {repaired_bundle.summary['retrieval_hit_rate']:.4f}")
    print(f"Repaired Mean Token F1:     {repaired_bundle.summary['mean_token_f1']:.4f}")

    print("=== Step 8: Quality & Freshness Checks on Repaired Data ===")
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired_quality_checks")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, settings.paths.quality_dir / "repaired_freshness_report.json"
    )
    print(f"Repaired Quality Status: {'PASSED' if repaired_quality.get('overall_passed') else 'FAILED'}")

    print("=== Step 9: Generating Comparison Report ===")
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print(f"Successfully generated comparison report: {settings.paths.comparison_report}")
