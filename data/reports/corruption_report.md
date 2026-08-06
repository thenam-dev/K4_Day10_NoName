# Corruption / Repair Comparison Report

_Generated at 2026-08-06T09:16:16.791148+00:00_

## Metrics comparison

| metric | baseline | corrupted | repaired |
| --- | --- | --- | --- |
| retrieval_hit_rate | 1.0000 | 0.8333 | 1.0000 |
| mean_token_f1 | 1.0000 | 0.6111 | 1.0000 |
| judge_accuracy | 1.0000 | 0.6111 | 1.0000 |
| mean_judge_score | 5 | 3.4444 | 5 |

## Data quality

- **corrupted**: FAIL
- [PASS] row_count_min: total_rows=23
- [PASS] paper_id_not_null: missing_paper_id=0
- [FAIL] paper_id_unique: duplicate_paper_id=3
- [PASS] title_not_null: missing_title=0
- [FAIL] summary_min_length: short_summary_rows=3 (min=100 chars)
- [FAIL] freshness_within_threshold: stale_or_missing_date_rows=3 (threshold=180 days)

- **repaired**: PASS
- [PASS] row_count_min: total_rows=24
- [PASS] paper_id_not_null: missing_paper_id=0
- [PASS] paper_id_unique: duplicate_paper_id=0
- [PASS] title_not_null: missing_title=0
- [PASS] summary_min_length: short_summary_rows=0 (min=100 chars)
- [PASS] freshness_within_threshold: stale_or_missing_date_rows=0 (threshold=180 days)

## Freshness

- **corrupted.is_fresh**: False (stale_rows=3/23)
- **repaired.is_fresh**: True (stale_rows=0/24)

## Interpretation

- `corrupted` vs `baseline`: corruption is expected to lower retrieval/answer quality metrics and/or fail quality or freshness checks.
- `repaired` vs `baseline`: repairing from the raw source records should restore metrics close to the baseline.
