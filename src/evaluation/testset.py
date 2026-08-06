from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

MIN_DOCUMENTS = 3
MAX_REPRESENTATIVE_PAPERS = 6


def _select_representative_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Pick an evenly spaced subset of papers across the (freshness-sorted) dataframe."""
    count = min(MAX_REPRESENTATIVE_PAPERS, len(df))
    if count >= len(df):
        return df
    if count == 1:
        positions = [0]
    else:
        positions = sorted({round(i * (len(df) - 1) / (count - 1)) for i in range(count)})
    return df.iloc[positions]


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build an evaluation set from the cleaned dataframe.

    For each representative paper, generates up to 4 question types
    (summary/authors/date/categories) whose phrasing matches the heuristics
    in `retrieval/qa.py` so the agent's extracted answer can be compared
    fairly against `ground_truth`.
    """
    if len(df) < MIN_DOCUMENTS:
        raise ValueError(
            f"Not enough documents to build an evaluation set: got {len(df)}, need at least {MIN_DOCUMENTS}."
        )

    samples: list[dict[str, Any]] = []
    sample_id = 0

    for _, row in _select_representative_rows(df).iterrows():
        title = row["title"]
        ground_truth_doc_ids = [row["paper_id"]]

        question_specs = [
            ("summary", f"What is the paper '{title}' about?", first_sentence(row["summary"])),
            ("authors", f"Who authored the paper '{title}'?", row["authors_joined"]),
            ("date", f"When was the paper '{title}' published?", row["published"]),
            ("categories", f"What categories does the paper '{title}' belong to?", row["categories_joined"]),
        ]

        for question_type, question, ground_truth in question_specs:
            if not ground_truth:
                continue
            sample_id += 1
            samples.append(
                {
                    "id": f"q-{sample_id:03d}",
                    "question_type": question_type,
                    "question": question,
                    "ground_truth": ground_truth,
                    "ground_truth_doc_ids": ground_truth_doc_ids,
                }
            )

    write_json(output_path, samples)
    return samples
