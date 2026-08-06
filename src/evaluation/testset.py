from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "published",
    "categories_joined",
}
_QUESTION_TYPES = ("summary", "authors", "date", "categories")
_MIN_DOCUMENTS = 4


def _validate_clean_dataframe(df: pd.DataFrame) -> None:
    missing = sorted(_REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Clean dataframe is missing required columns: {', '.join(missing)}")
    if len(df) < _MIN_DOCUMENTS:
        raise ValueError(f"At least {_MIN_DOCUMENTS} cleaned documents are required to build the evaluation set.")
    if df["paper_id"].isna().any() or df["paper_id"].astype(str).str.strip().eq("").any():
        raise ValueError("Clean dataframe contains an empty paper_id.")
    if not df["paper_id"].is_unique:
        raise ValueError("Clean dataframe must have unique paper_id values.")


def build_test_set(
    df: pd.DataFrame,
    output_path: Path,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Build a deterministic four-question evaluation set for each clean paper.

    The existing file is reused by default. This keeps exactly the same evaluation
    set for baseline, corrupted, and repaired runs, making their metrics comparable.
    """
    output_path = Path(output_path)
    if output_path.exists() and not force_refresh:
        return read_json(output_path)

    _validate_clean_dataframe(df)
    ordered = df.sort_values(["published", "paper_id"], ascending=[False, True], kind="mergesort")
    test_set: list[dict[str, Any]] = []

    for index, (_, row) in enumerate(ordered.iterrows(), start=1):
        paper_id = str(row["paper_id"]).strip()
        title = str(row["title"]).strip()
        if not title:
            raise ValueError("Clean dataframe contains an empty title.")

        values = {
            "summary": first_sentence(str(row["summary"])),
            "authors": str(row["authors_joined"]),
            "date": str(row["published"]),
            "categories": str(row["categories_joined"]),
        }
        questions = {
            "summary": f"What is the main finding or summary of the paper '{title}'?",
            "authors": f"Who authored the paper '{title}'?",
            "date": f"When was the paper '{title}' published?",
            "categories": f"What categories does the paper '{title}' belong to?",
        }
        for offset, question_type in enumerate(_QUESTION_TYPES):
            test_set.append(
                {
                    "id": f"test-{((index - 1) * len(_QUESTION_TYPES)) + offset + 1:03d}",
                    "question_type": question_type,
                    "question": questions[question_type],
                    "ground_truth": values[question_type],
                    "ground_truth_doc_ids": [paper_id],
                }
            )

    write_json(output_path, test_set)
    return test_set
