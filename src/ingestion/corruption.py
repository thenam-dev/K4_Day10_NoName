from __future__ import annotations

from pathlib import Path
import random
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json

_SEED = 42
_CORRUPTION_FRACTION = 0.15
_NOISE_SNIPPET = " asldkfj ##corrupted-noise## qqqq111 "
_STALE_YEARS = 3


def _corruption_count(pool_size: int, fraction: float = _CORRUPTION_FRACTION, minimum: int = 1) -> int:
    if pool_size <= 0:
        return 0
    return max(minimum, round(pool_size * fraction))


def _rebuild_text_for_embedding(row: pd.Series) -> str:
    """Match the 5-field layout produced by `ingestion.cleaning.build_clean_dataframe`."""
    return " | ".join(
        (
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Categories: {row['categories_joined']}",
            f"Published: {row['published']}",
            f"Summary: {row['summary']}",
        )
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path) -> pd.DataFrame:
    """Simulate several kinds of data corruption on a cleaned dataframe.

    Scenarios applied (each on a disjoint random sample, seeded for reproducibility):
    - Drop some of the most recently published records (missing data).
    - Blank out summaries.
    - Inject noise text into summaries.
    - Truncate titles.
    - Make publication dates stale.
    - Duplicate rows (same `paper_id`, breaks uniqueness).

    Every affected `paper_id` and the corruption type applied to it is written to
    `output_log_path` so the impact can be audited and cross-checked against the
    frozen evaluation set.
    """
    events: list[dict[str, Any]] = []

    if df.empty:
        write_json(
            output_log_path,
            {"generated_at": now_utc().isoformat(), "original_rows": 0, "corrupted_rows": 0, "events": events},
        )
        return df.copy()

    working = df.sort_values(["published", "paper_id"], ascending=[False, True], kind="mergesort").reset_index(
        drop=True
    )
    original_rows = len(working)

    # 1. Drop some of the most recently published records.
    drop_count = min(_corruption_count(original_rows), original_rows - 1) if original_rows > 1 else 0
    dropped_ids = working.iloc[:drop_count]["paper_id"].tolist() if drop_count else []
    remaining = working.iloc[drop_count:].reset_index(drop=True)
    for paper_id in dropped_ids:
        events.append({"paper_id": paper_id, "type": "dropped_latest_record"})

    remaining_n = len(remaining)
    rng = random.Random(_SEED)
    available = list(range(remaining_n))
    rng.shuffle(available)

    def _take(count: int) -> list[int]:
        taken, rest = available[:count], available[count:]
        available[:] = rest
        return taken

    blank_idx = _take(_corruption_count(remaining_n))
    noise_idx = _take(_corruption_count(remaining_n))
    truncate_idx = _take(_corruption_count(remaining_n))
    stale_idx = _take(_corruption_count(remaining_n))
    duplicate_idx = _take(_corruption_count(remaining_n))

    # 2. Blank summaries.
    for idx in blank_idx:
        remaining.at[idx, "summary"] = ""
        remaining.at[idx, "summary_chars"] = 0
        events.append({"paper_id": remaining.at[idx, "paper_id"], "type": "blank_summary"})

    # 3. Inject noise into summaries.
    for idx in noise_idx:
        remaining.at[idx, "summary"] = str(remaining.at[idx, "summary"]) + _NOISE_SNIPPET
        remaining.at[idx, "summary_chars"] = len(remaining.at[idx, "summary"])
        events.append({"paper_id": remaining.at[idx, "paper_id"], "type": "noisy_summary"})

    # 4. Truncate titles.
    for idx in truncate_idx:
        title = str(remaining.at[idx, "title"])
        remaining.at[idx, "title"] = title[: max(1, len(title) // 3)]
        events.append({"paper_id": remaining.at[idx, "paper_id"], "type": "truncated_title"})

    # 5. Stale publication dates.
    stale_date = (now_utc() - pd.Timedelta(days=365 * _STALE_YEARS)).date()
    for idx in stale_idx:
        remaining.at[idx, "published"] = stale_date.isoformat()
        remaining.at[idx, "age_days"] = (now_utc().date() - stale_date).days
        events.append({"paper_id": remaining.at[idx, "paper_id"], "type": "stale_publication_date"})

    # 6. Duplicate rows (exact clones taken from untouched rows).
    duplicate_rows = remaining.loc[duplicate_idx]
    for paper_id in duplicate_rows["paper_id"]:
        events.append({"paper_id": paper_id, "type": "duplicate_row"})

    corrupted = pd.concat([remaining, duplicate_rows], ignore_index=True)

    # 7. Rebuild text_for_embedding so the corruption is reflected in the index.
    corrupted["text_for_embedding"] = corrupted.apply(_rebuild_text_for_embedding, axis=1)

    write_json(
        output_log_path,
        {
            "generated_at": now_utc().isoformat(),
            "original_rows": original_rows,
            "corrupted_rows": len(corrupted),
            "events": events,
        },
    )
    return corrupted
