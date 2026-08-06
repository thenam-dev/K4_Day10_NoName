from pathlib import Path
from typing import Any
import pandas as pd

from core.utils import first_sentence, read_json, write_json


def build_test_set(df: pd.DataFrame, output_path: Path, force_refresh: bool = False) -> list[dict[str, Any]]:
    """Tạo bộ câu hỏi đánh giá (evaluation test set) từ cleaned dataframe."""
    out_path = Path(output_path)
    if not force_refresh and out_path.exists():
        return read_json(out_path)

    test_set: list[dict[str, Any]] = []
    item_counter = 1

    for _, row in df.iterrows():
        paper_id = str(row["paper_id"])
        title = str(row["title"])
        summary = str(row["summary"])
        authors = str(row["authors_joined"])
        published = str(row["published"])
        categories = str(row["categories_joined"])

        # 1. Câu hỏi về summary / kết quả chính
        test_set.append(
            {
                "id": f"test-{item_counter:03d}",
                "question_type": "summary",
                "question": f"What is the main finding or summary of the paper '{title}'?",
                "ground_truth": first_sentence(summary),
                "ground_truth_doc_ids": [paper_id],
            }
        )
        item_counter += 1

        # 2. Câu hỏi về tác giả (authors)
        test_set.append(
            {
                "id": f"test-{item_counter:03d}",
                "question_type": "authors",
                "question": f"Who authored the paper '{title}'?",
                "ground_truth": authors,
                "ground_truth_doc_ids": [paper_id],
            }
        )
        item_counter += 1

        # 3. Câu hỏi về ngày xuất bản (published date)
        test_set.append(
            {
                "id": f"test-{item_counter:03d}",
                "question_type": "date",
                "question": f"When was the paper '{title}' published?",
                "ground_truth": published,
                "ground_truth_doc_ids": [paper_id],
            }
        )
        item_counter += 1

        # 4. Câu hỏi về chủ đề / danh mục (categories)
        test_set.append(
            {
                "id": f"test-{item_counter:03d}",
                "question_type": "categories",
                "question": f"What categories does the paper '{title}' belong to?",
                "ground_truth": categories,
                "ground_truth_doc_ids": [paper_id],
            }
        )
        item_counter += 1

    write_json(out_path, test_set)
    return test_set

