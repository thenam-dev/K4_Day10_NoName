from __future__ import annotations

import random

import pandas as pd

from core.utils import now_utc, write_json

CORRUPTION_SEED = 42
CORRUPTION_FRACTION = 0.15
NOISE_SNIPPET = " asldkfj ##corrupted-noise## qqqq111 "
STALE_YEARS = 3


def _corruption_count(pool_size: int, fraction: float = CORRUPTION_FRACTION, minimum: int = 1) -> int:
    if pool_size <= 0:
        return 0
    return max(minimum, round(pool_size * fraction))


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate several kinds of data corruption on a cleaned dataframe.

    - Drops some of the most recent records (missing data).
    - Blanks out summaries on a sample of rows.
    - Injects noise text into summaries on a (disjoint) sample of rows.
    - Truncates titles on another sample of rows.
    - Makes publication dates stale on another sample of rows.
    - Duplicates a sample of untouched rows.

    Every affected `paper_id` and corruption type is written to
    `output_log_path` so the impact can be audited later.
    """
    events: list[dict] = []

    if df.empty:
        write_json(
            output_log_path,
            {"generated_at": now_utc().isoformat(), "original_rows": 0, "corrupted_rows": 0, "events": events},
        )
        return df.copy()

    working = df.reset_index(drop=True).copy()
    original_rows = len(working)

    # 1. Drop some of the latest records (the dataframe is sorted newest-first).
    drop_count = min(_corruption_count(original_rows), original_rows - 1) if original_rows > 1 else 0
    dropped_ids = working.iloc[:drop_count]["paper_id"].tolist() if drop_count else []
    remaining = working.iloc[drop_count:].reset_index(drop=True)
    for paper_id in dropped_ids:
        events.append({"paper_id": paper_id, "type": "dropped_latest_record"})

    remaining_n = len(remaining)
    rng = random.Random(CORRUPTION_SEED)
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

    # 2. Blank summary.
    for idx in blank_idx:
        remaining.at[idx, "summary"] = ""
        remaining.at[idx, "summary_chars"] = 0
        events.append({"paper_id": remaining.at[idx, "paper_id"], "type": "blank_summary"})

    # 3. Inject noise into summary.
    for idx in noise_idx:
        remaining.at[idx, "summary"] = str(remaining.at[idx, "summary"]) + NOISE_SNIPPET
        remaining.at[idx, "summary_chars"] = len(remaining.at[idx, "summary"])
        events.append({"paper_id": remaining.at[idx, "paper_id"], "type": "noisy_summary"})

    # 4. Truncate title.
    for idx in truncate_idx:
        title = str(remaining.at[idx, "title"])
        remaining.at[idx, "title"] = title[: max(1, len(title) // 3)]
        events.append({"paper_id": remaining.at[idx, "paper_id"], "type": "truncated_title"})

    # 5. Make publication date stale.
    stale_date = (now_utc() - pd.Timedelta(days=365 * STALE_YEARS)).date()
    for idx in stale_idx:
        remaining.at[idx, "published"] = stale_date.isoformat()
        remaining.at[idx, "age_days"] = (now_utc().date() - stale_date).days
        events.append({"paper_id": remaining.at[idx, "paper_id"], "type": "stale_publication_date"})

    # 6. Duplicate rows (taken from untouched rows so duplicates are exact clones).
    duplicate_rows = remaining.loc[duplicate_idx]
    for paper_id in duplicate_rows["paper_id"]:
        events.append({"paper_id": paper_id, "type": "duplicate_row"})

    corrupted = pd.concat([remaining, duplicate_rows], ignore_index=True)

    # 7. Rebuild text_for_embedding so downstream embedding reflects the corruption.
    corrupted["text_for_embedding"] = (
        "Title: " + corrupted["title"].astype(str)
        + " | Authors: " + corrupted["authors_joined"].astype(str)
        + " | Summary: " + corrupted["summary"].astype(str)
    )

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
