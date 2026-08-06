from core.config import load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    print("=== Step 1: Loading Settings & Ingesting Raw Data ===")
    settings = load_settings()
    records = fetch_source_records(settings)
    print(f"Ingested {len(records)} raw paper records from {settings.source_api}.")

    print("=== Step 2: Cleaning Data & Building DataFrame ===")
    run_date = now_utc()
    clean_df = build_clean_dataframe(records, run_date)
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))
    print(f"Cleaned {len(clean_df)} valid paper records. Saved to {settings.paths.clean_csv.name}.")

    print("=== Step 3: Building Vector Store (Embedding Index) ===")
    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)
    print(f"Created Vector Index '{index.collection_name}' with {len(clean_df)} embeddings (backend: {index.embedding_backend}).")

    print("=== Step 4: Generating/Loading Test Set ===")
    test_set = build_test_set(clean_df, settings.paths.eval_testset, force_refresh=settings.refresh_test_set)
    print(f"Prepared test set with {len(test_set)} evaluation samples.")

    print("=== Step 5: Running Baseline Evaluation Pipeline ===")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print(f"Baseline Retrieval Hit Rate: {bundle.summary['retrieval_hit_rate']:.4f}")
    print(f"Baseline Mean Token F1:     {bundle.summary['mean_token_f1']:.4f}")
    print(f"Baseline Judge Score:       {bundle.summary['mean_judge_score']:.4f}")

    print("=== Step 6: Data Quality & Freshness Observability ===")
    quality = run_data_quality_checks(clean_df, settings, "baseline_quality_checks")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)

    source_summary = {
        "source_api": settings.source_api,
        "total_raw_records": len(records),
        "total_clean_records": len(clean_df),
    }
    generate_phase1_report(settings.paths.baseline_report, source_summary, bundle.summary, quality, freshness)
    print(f"Successfully generated baseline report: {settings.paths.baseline_report}")

