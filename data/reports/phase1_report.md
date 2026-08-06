# Phase 1 Baseline Report

_Generated at 2026-08-06T09:17:31.334128+00:00_

## Source

- **source_api**: Crossref REST API
- **source_query**: agentic retrieval augmented generation large language model
- **source_filter**: from-pub-date:2026-02-07,has-abstract:true
- **max_results**: 24
- **raw_records**: 24
- **clean_records**: 24

## Evaluation metrics

| metric | value |
| --- | --- |
| samples | 18 |
| retrieval_hit_rate | 1.0000 |
| mean_token_f1 | 1.0000 |
| judge_accuracy | 1.0000 |
| mean_judge_score | 5 |

## Data quality

- **status**: PASS
- **total_rows**: 24

- [PASS] row_count_min: total_rows=24
- [PASS] paper_id_not_null: missing_paper_id=0
- [PASS] paper_id_unique: duplicate_paper_id=0
- [PASS] title_not_null: missing_title=0
- [PASS] summary_min_length: short_summary_rows=0 (min=100 chars)
- [PASS] freshness_within_threshold: stale_or_missing_date_rows=0 (threshold=180 days)

## Freshness

- **is_fresh**: True
- **latest_published**: 2026-08-01
- **oldest_published**: 2026-02-12
- **stale_rows**: 0 / 24
