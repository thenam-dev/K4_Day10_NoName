# Baseline Data Pipeline & RAG Evaluation Report

## 1. Source Summary
- **Source API**: Crossref REST API
- **Total Raw Records**: 24
- **Cleaned Records**: 24

## 2. RAG Evaluation Metrics (Baseline)
| Metric | Value |
| --- | --- |
| Total Samples | 96 |
| **Retrieval Hit Rate** | 1.0000 |
| **Mean Token F1** | 1.0000 |
| **Judge Accuracy** | 1.0000 |
| **Mean Judge Score** | 5.0000 |

## 3. Data Quality & Observability
- **Overall Quality Status**: PASSED
- **Total Clean Rows**: 24

### Detailed Quality Checks
- **row_count**: `PASSED` ({'passed': True, 'actual': 24, 'expected': '>= 5'})
- **paper_id_validity**: `PASSED` ({'passed': True, 'not_null': True, 'is_unique': True})
- **title_completeness**: `PASSED` ({'passed': True, 'empty_titles': 0})
- **summary_min_length**: `PASSED` ({'passed': True, 'short_summaries': 0})
- **freshness_ratio**: `PASSED` ({'passed': True, 'actual_ratio': 1.0, 'threshold': 0.7})
- **title_uniqueness**: `PASSED` ({'passed': True, 'duplicate_titles': 0})

## 4. Freshness Monitoring Report
- **Latest Published Date**: 2026-08-05
- **Oldest Published Date**: 2026-02-12
- **Stale Record Count**: 0 / 24
- **Stale Ratio**: 0.0000
- **Freshness Threshold (days)**: 180
- **Corpus Freshness Status**: FRESH
