from __future__ import annotations

import logging

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex

logger = logging.getLogger(__name__)

DEMO_QUESTION_COUNT = 3


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings()

    # 1-2. Load or fetch raw records.
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        logger.info("Fetching raw records from %s", settings.source_api)
        records = fetch_source_records(settings)
    else:
        logger.info("Loading cached raw records from %s", settings.paths.raw_records_json)
        records = load_raw_records(settings.paths.raw_records_json)

    # 3-4. Clean data and persist clean CSV/JSON.
    df = build_clean_dataframe(records, now_utc())
    if df.empty:
        raise RuntimeError("Cleaning produced an empty dataset; check the raw records and cleaning rules.")
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))
    logger.info("Cleaned dataset: %s rows (from %s raw records)", len(df), len(records))

    # 5. Build embedding index (ChromaDB + MiniLM).
    logger.info("Building embedding index...")
    index = LocalEmbeddingIndex.build(df, settings)

    # 6. Create or load the evaluation test set.
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        build_test_set(df, settings.paths.eval_testset)
    test_set = read_json(settings.paths.eval_testset)
    logger.info("Evaluation set has %s questions", len(test_set))

    # 7. Evaluate.
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    logger.info("Baseline metrics: %s", bundle.summary)

    # 8-9. Data quality checks and freshness report.
    quality = run_data_quality_checks(df, settings, "baseline_quality")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

    # 10. Markdown report.
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "max_results": settings.max_results,
        "raw_records": len(records),
        "clean_records": len(df),
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )

    # 11. Demo the agent on a few sample questions (best-effort; needs LLM credentials).
    demo_questions = [item["question"] for item in test_set[:DEMO_QUESTION_COUNT]]
    try:
        agent = build_agent(settings, index)
        demo_answers = [
            {"question": question, "answer": run_agent_question(agent, question)} for question in demo_questions
        ]
    except Exception as exc:  # pragma: no cover - depends on LLM credentials being configured
        logger.warning("Skipping agent demo because the LLM provider is not usable: %s", exc)
        demo_answers = [{"question": q, "answer": None, "error": str(exc)} for q in demo_questions]
    write_json(settings.paths.demo_answers, demo_answers)

    logger.info("Phase 1 baseline pipeline complete.")
