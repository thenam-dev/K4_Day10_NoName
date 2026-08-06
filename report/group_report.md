# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin       | Nội dung                                      |
| --------------- | ---------------------------------------------- |
| Khóa/Lớp        | K4                                              |
| Tên nhóm        | NoName                                          |
| Repository      | https://github.com/thenam-dev/K4_Day10_NoName   |
| Ngày hoàn thành | 2026-08-06                                      |

### Thành viên và phân công

| STT | Họ và tên            | MSSV         | Vai trò chính                     | Module/deliverable sở hữu                                    |
| --: | --------------------- | ------------ | ----------------------------------- | ---------------------------------------------------------------- |
|   1 | Nguyễn Thế Hải Đăng   | 2A202601957  | Source Ingestion Owner              | `src/ingestion/crossref.py`                                    |
|   2 | Đào Duy Hưng          | 2A202601166  | Data Model & Evaluation-set Owner   | `src/ingestion/cleaning.py`, `src/evaluation/testset.py`      |
|   3 | Trần Văn Thắng        | 2A202602003  | Data Observability Owner            | `src/observability/quality.py`, `src/observability/reporting.py` |
|   4 | Nguyễn Thế Nam        | 2A202601958  | Corruption & Integration Owner      | `src/ingestion/corruption.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` |

Đây là mô hình nhóm 4 người theo khuyến nghị trong [report/README.md](README.md#4-phần-việc-và-báo-cáo-vai-trò-của-thành-viên). Module `src/retrieval/` (embedding, ChromaDB, LLM provider, agent) và `src/core/` là code tham khảo dùng chung, không thuộc ownership của thành viên nào.

> **Ghi chú cần nhóm thống nhất trước khi nộp:** báo cáo cá nhân của Thành viên 1 (`NguyenTheHaiDang-2A02601957.md`) mô tả phạm vi rộng hơn phân công ở trên (bao gồm cả `cleaning.py` và `quality.py`), và dùng MSSV `2A02601957` (thiếu một chữ số so với `2A202601957`). Nhóm cần đối chiếu lại để báo cáo cá nhân khớp đúng phân công trong bảng này trước khi nộp.

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành toàn bộ phần code cho cả hai pha: `crossref.py` (fetch + retry/backoff + lưu raw artifacts), `cleaning.py` (chuẩn hóa schema, `text_for_embedding`), `testset.py` (sinh 96 câu hỏi — 4 loại × 24 paper, đóng băng qua cơ chế `force_refresh`), `quality.py`/`reporting.py` (6 quality checks, freshness ratio, báo cáo Markdown), và `corruption.py`/`phase1.py`/`corruption_flow.py` (6 kịch bản lỗi, orchestration 2 pha, so sánh 3 trạng thái). Baseline pipeline đã xác nhận tạo được raw response, raw records, cleaned dataset (24 bài) và evaluation set (96 câu) trong `data/raw/`, `data/clean/`, `data/eval/`.

Tuy nhiên, tại thời điểm nộp báo cáo này, nhóm **chưa có một lần chạy end-to-end hoàn chỉnh** trên đúng phiên bản code mới nhất tạo ra `data/results/`, `data/quality/` và `data/reports/` đầy đủ cho cả ba trạng thái baseline/corrupted/repaired. Blocker chính là `LLM_MODEL` cấu hình mặc định bị nhà cung cấp Gemini chặn với tài khoản mới và hết quota miễn phí trong ngày, khiến 96 lệnh gọi LLM-judge (nhân ba cho mỗi trạng thái) phải retry/backoff rất lâu trước khi rơi về fallback heuristic — vượt quá thời gian hợp lý cho một lần chạy thử nghiệm. `retrieval_hit_rate` và `mean_token_f1` không phụ thuộc LLM nên vẫn tính được ngay cả khi judge fallback, nhưng nhóm chưa xác nhận số liệu cuối cùng. Một số báo cáo cá nhân trích dẫn số liệu từ lần chạy trên phiên bản code cũ hơn (18 câu hỏi) — nhóm cần chạy lại thống nhất trước khi dùng số liệu chính thức.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records
    -> cleaning và data modeling
    -> embedding + ChromaDB index
    -> evaluation baseline
    -> quality/freshness reports
    -> corruption
    -> re-index và re-evaluate
    -> repair từ dữ liệu nguồn
    -> comparison report
```

### Trách nhiệm của từng khối

| Khối               | Input                                                   | Xử lý chính                                                                                     | Output/artifact                                                        | Owner                  |
| ------------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ----------------------- |
| Ingestion           | Crossref REST API (`query`+`filter` từ `Settings`)      | Gọi API, retry/backoff cho HTTP 429/500/502/503/504 (tối đa 4 lần), parse thành `PaperRecord`     | `data/raw/crossref_response.json`, `crossref_records.json`             | Nguyễn Thế Hải Đăng    |
| Cleaning            | `list[PaperRecord]` + `run_date`                       | Strip HTML/JATS, chuẩn hóa authors/categories, tính `age_days`, build `text_for_embedding`, dedupe | `data/clean/papers_clean.csv`, `papers_clean.json`                     | Đào Duy Hưng           |
| Embedding/index     | Cleaned dataframe                                        | `sentence-transformers/all-MiniLM-L6-v2` (384 chiều) qua ChromaDB `PersistentClient`, cosine similarity | `data/embeddings/papers_embeddings*.json`, `data/chroma/`               | Code tham khảo dùng chung |
| Evaluation          | Cleaned dataframe                                        | Sinh 4 câu hỏi/paper (`summary`/`authors`/`date`/`categories`); tính `retrieval_hit_rate`, token F1, LLM-judge (có fallback) | `data/eval/test_set.json`, `data/results/*_metrics.json`, `*_answers.json` | Đào Duy Hưng (test set); code tham khảo (metrics) |
| Observability       | Dataframe ở từng trạng thái                              | 6 quality checks (row count, `paper_id` validity, title completeness, summary length, freshness ratio, title uniqueness); freshness report | `data/quality/*_quality_checks.json`, `*_freshness_report.json`         | Trần Văn Thắng          |
| Corruption/repair   | Cleaned baseline dataframe + raw snapshot                | 6 kịch bản lỗi có kiểm soát, seed cố định; repair build lại từ raw records                        | `papers_clean_corrupted.*`, `papers_clean_repaired.*`, `corruption_log.json` | Nguyễn Thế Nam          |
| Orchestration       | `Settings`                                              | `phase1.py` (6 bước baseline), `corruption_flow.py` (9 bước corrupt → evaluate → repair → evaluate → compare) | `data/reports/phase1_report.md`, `corruption_report.md`                | Nguyễn Thế Nam          |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình               | Giá trị sử dụng                                                                 |
| ----------------------------- | ---------------------------------------------------------------------------------- |
| `LLM_PROVIDER`               | `gemini`                                                                          |
| `LLM_MODEL`                  | `gemini-2.5-flash` (⚠️ hiện bị chặn với tài khoản mới — `404 NOT_FOUND` — và hết quota ngày; khuyến nghị đổi sang model còn quota, ví dụ `gemini-flash-lite-latest`, trước khi chạy lấy số liệu chính thức) |
| Embedding model                | `sentence-transformers/all-MiniLM-L6-v2` (384 chiều)                             |
| Số lượng Crossref records    | 24 (`max_results=24`)                                                            |
| Retrieval `top_k`             | 4                                                                                  |
| Freshness threshold            | 180 ngày                                                                          |
| Random seed corruption         | 42 (`random.Random(42)` trong `corruption.py`, để có thể tái lập kết quả)         |

Không dán nội dung API key hoặc file `.env` vào báo cáo.

### Lệnh cài đặt

```bash
uv sync
```

`uv sync` tự tải Python 3.13 (máy phát triển không sẵn Python 3.11–3.13) và cài 157 package theo `uv.lock`.

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Hoặc với môi trường `pip` đã kích hoạt:

```bash
python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

Hoặc với môi trường `pip` đã kích hoạt:

```bash
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh               | Trạng thái                                                                     | Thời điểm chạy gần nhất | Bằng chứng                                                                 |
| ------------------- | --------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------------ |
| Baseline pipeline   | Thất bại một phần — chạy tới bước build embedding index/evaluate nhưng chưa tạo được `baseline_metrics.json` trong lần chạy gần nhất do vòng lặp LLM-judge (96 câu) không hoàn tất trong thời gian hợp lý | 2026-08-06                 | `data/raw/`, `data/clean/`, `data/eval/` đã có đủ; `data/results/` còn trống |
| Corruption flow     | Chưa chạy được — phụ thuộc baseline hoàn tất (`corruption_flow.py` chặn sớm bằng `RuntimeError` nếu thiếu `baseline_metrics.json`) | —                           | —                                                                                |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính             | Giá trị                                                                       |
| ------------------------ | ---------------------------------------------------------------------------------- |
| Source                   | Crossref REST API — `https://api.crossref.org/works`                            |
| Query/filter              | `query="agentic retrieval augmented generation large language model"`, `filter="from-pub-date:<180 ngày trước>,has-abstract:true"` |
| Thời điểm lấy dữ liệu    | 2026-08-06                                                                        |
| Số record nhận được     | 24                                                                                 |
| Cơ chế retry/backoff     | Exponential backoff cho HTTP 429/500/502/503/504, tối đa 4 lần thử; nếu vẫn thất bại và đã có snapshot cũ thì dùng lại snapshot đó thay vì crash |

### Raw và clean schema

| Trường                              | Kiểu dữ liệu       | Bắt buộc?  | Ý nghĩa                                          | Xử lý khi thiếu/sai                                  |
| -------------------------------------- | --------------------- | ---------- | --------------------------------------------------- | -------------------------------------------------------- |
| `paper_id`                            | string (DOI, lowercase) | Có         | Định danh duy nhất của bài báo                      | Loại record nếu rỗng                                     |
| `title`                                | string               | Có         | Tiêu đề đã strip HTML/JATS                          | Loại record nếu rỗng                                     |
| `summary`                              | string               | Có         | Abstract đã làm sạch, tối thiểu 50 ký tự             | Loại record nếu quá ngắn                                  |
| `authors_joined` / `categories_joined` | string               | Không      | Chuỗi tác giả/chủ đề nối bằng dấu phẩy               | Gán `"Anonymous"` / `"Uncategorized"` khi thiếu           |
| `published`                            | ISO date (`YYYY-MM-DD`) | Có         | Ngày xuất bản chuẩn hóa                             | Loại record nếu không parse được ngày                    |
| `age_days`                             | int                  | Có         | Số ngày từ `published` đến `run_date`               | Tính lại mỗi lần build dataframe                          |
| `text_for_embedding`                   | string               | Có         | `Title: ... | Authors: ... | Categories: ... | Published: ... | Summary: ...` | Rebuild lại sau khi corrupt để phản ánh đúng nội dung lỗi |

### Quy tắc cleaning

| Quy tắc                                              | Quality dimension liên quan | Số record bị tác động (lần fetch gần nhất) | Cách xác minh                                        |
| ------------------------------------------------------- | ----------------------------- | -------------------------------------------: | --------------------------------------------------------- |
| Loại bỏ HTML/JATS (`<jats:p>`, `<b>`...) khỏi title/summary | Validity                      | Áp dụng cho cả 24 record                     | So sánh raw text với clean text                           |
| Loại record thiếu `paper_id`/title/summary đủ dài/ngày hợp lệ | Completeness                  | 0 trong lần fetch gần nhất (24/24 raw hợp lệ) | So `raw_records_json` với số dòng `papers_clean.json`   |
| Dedupe theo `paper_id`, sau đó theo title (không phân biệt hoa/thường) | Uniqueness                    | 0 trùng lặp phát hiện được                    | Check `paper_id_validity`/`title_uniqueness` trong quality checks |

Document ID dùng trực tiếp DOI (`paper_id`, đã lowercase) — ổn định và duy nhất theo nguồn, không tự sinh ID mới. `text_for_embedding` ghép 5 phần (title, authors, categories, published, summary) để vector vừa mang nội dung nghiên cứu vừa mang metadata cần cho 4 loại câu hỏi. `age_days` tính lại từ `run_date` mỗi lần build dataframe (baseline, corrupted, repaired đều tính tại đúng thời điểm build của trạng thái đó).

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế                                                                 |
| ----------------------------------------- | -------------------------------------------------------------------------------------- |
| Số câu hỏi                                | 96 (24 paper × 4 loại)                                                                |
| Các `question_type`                      | `summary`, `authors`, `date`, `categories`                                            |
| Ground-truth document ID                  | `[paper_id]` của chính paper mà câu hỏi được sinh ra                                  |
| Embedding model                           | `sentence-transformers/all-MiniLM-L6-v2`                                              |
| Vector store/collection                   | ChromaDB `PersistentClient` tại `data/chroma/`; collection `papers-baseline` / `papers-corrupted` / `papers-repaired` |
| Retrieval `top_k`                        | 4                                                                                        |
| LLM provider/model                        | `gemini` / `gemini-2.5-flash` (đang lỗi — xem mục 11 và 12)                            |
| Test set dùng chung cho ba trạng thái     | `data/eval/test_set.json` — `corruption_flow.py` không gọi lại `build_test_set`, dùng nguyên đường dẫn này cho cả 2 lần evaluate (corrupted, repaired) |

Test set được giữ nguyên (đóng băng) vì mục tiêu của bài lab là cô lập **một biến duy nhất**: trạng thái dữ liệu (sạch/lỗi/đã sửa). Nếu sinh lại câu hỏi ở mỗi trạng thái, bộ câu hỏi và ground truth có thể khác nhau giữa ba lần đánh giá, khiến chênh lệch metric không còn quy được rõ ràng cho corruption hay repair — mất hoàn toàn ý nghĩa so sánh. `testset.py` tự kiểm tra file cache có còn khớp dataframe hiện tại không (`_existing_test_set_matches`) và chỉ sinh lại khi không khớp hoặc khi `force_refresh=True`.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                    | Trạng thái | Ghi chú                                                              |
| ------------------------- | -------------------------------------- | ---------- | ------------------------------------------------------------------------ |
| Raw response/records      | `data/raw/`                          | Có         | `crossref_response.json` (245 KB), `crossref_records.json`, 24 record   |
| Cleaned dataset           | `data/clean/`                        | Có         | `papers_clean.csv`/`.json`, 24 record sạch                              |
| Embedding manifest/index  | `data/embeddings/`, `data/chroma/`   | Có         | Manifest MiniLM 384 chiều, collection `papers-baseline` đã build         |
| Evaluation set            | `data/eval/`                         | Có         | `test_set.json`, 96 câu hỏi                                            |
| Baseline metrics          | `data/results/baseline_metrics.json` | Thiếu      | Vòng lặp evaluate chưa hoàn tất trong lần chạy gần nhất (xem mục 4)      |
| Quality/freshness         | `data/quality/`                      | Thiếu      | Phụ thuộc bước evaluate hoàn tất trước                                   |
| Baseline report           | `data/reports/phase1_report.md`      | Thiếu      | Phụ thuộc metrics + quality + freshness                                  |

### Baseline metrics

| Metric                 | Giá trị | Diễn giải                                                                 |
| ----------------------- | -------: | ---------------------------------------------------------------------------- |
| `retrieval_hit_rate`   |    _TBD_ | Chưa có `baseline_metrics.json` mới nhất — cần chạy lại `run_phase1.py`     |
| `mean_token_f1`        |    _TBD_ | Không phụ thuộc LLM nên có thể tính nhanh nếu chạy lại thành công            |
| `judge_accuracy`       |    _TBD_ | Phụ thuộc LLM judge; có fallback heuristic nếu provider lỗi/hết quota        |
| `mean_judge_score`     |    _TBD_ | Như trên                                                                     |
| Ragas                  |     N/A  | `RUN_RAGAS` chưa được bật (mặc định skip vì tốn thời gian)                  |

## 8. Data quality và freshness

### Quality checks

| Check                    | Quality dimension | Ngưỡng/kỳ vọng                              | Kết quả baseline | Bằng chứng                              |
| -------------------------- | -------------------- | ------------------------------------------------ | ------------------- | ---------------------------------------------- |
| `row_count`                | Completeness          | Tối thiểu 5 record                                | _TBD_                | `data/quality/baseline_quality_checks.json`   |
| `paper_id_validity`        | Validity/Uniqueness   | `paper_id` không null và unique                   | _TBD_                | ″                                                |
| `title_completeness`       | Completeness          | Title không null/rỗng                             | _TBD_                | ″                                                |
| `summary_min_length`       | Validity               | Mọi `summary_chars` ≥ 50                          | _TBD_                | ″                                                |
| `freshness_ratio`          | Timeliness             | Tỉ lệ record có `age_days ≤ 180` phải ≥ 70%       | _TBD_                | ″                                                |
| `title_uniqueness`         | Uniqueness             | Title không trùng lặp                             | _TBD_                | ″                                                |

`overall_passed` chỉ `true` khi toàn bộ 6 check đều pass.

### Freshness

| Thuộc tính             | Giá trị                                                                 |
| ------------------------ | ---------------------------------------------------------------------------- |
| Freshness được đo tại   | Dataframe ở từng trạng thái (baseline/corrupted/repaired)                    |
| Timestamp mới nhất       | _TBD_ — cần `freshness_report.json` mới nhất                                |
| Ngưỡng freshness         | 180 ngày; corpus fresh khi `stale_ratio < 30%`                              |
| Trạng thái baseline      | _TBD_                                                                        |
| Lý do                    | Chưa có artifact mới nhất để đối chiếu (xem mục 4)                          |

## 9. Corruption scenarios và repair

| Corruption                | Cách tạo                                                                 | Record bị tác động (ước tính ~15%/loại) | Quality signal kỳ vọng                     | Tác động thực tế | Cách repair                                             |
| --------------------------- | ------------------------------------------------------------------------- | ------------------------------------------: | ------------------------------------------- | ------------------- | ------------------------------------------------------------ |
| Xóa bản ghi mới nhất        | Cắt N record đầu (df đã sort `published` giảm dần)                       | ~15% tổng record                             | `retrieval_hit_rate` giảm cho câu hỏi liên quan | _TBD_                | Repair đọc lại toàn bộ raw snapshot, bản ghi xuất hiện lại   |
| Blank summary               | Gán `summary = ""`, `summary_chars = 0`                                  | ~15% record còn lại                          | `summary_min_length` FAIL                    | _TBD_                | ″                                                              |
| Inject noise vào summary    | Nối chuỗi noise cố định vào cuối summary                                 | ~15%                                          | `mean_token_f1`/`judge_score` giảm            | _TBD_                | ″                                                              |
| Truncate title               | Cắt còn 1/3 độ dài title                                                 | ~15%                                          | Exact-title lookup thất bại                   | _TBD_                | ″                                                              |
| Stale publication date       | Gán `published` lùi 3 năm, tính lại `age_days`                           | ~15%                                          | `freshness_ratio` giảm, `is_fresh=false`      | _TBD_                | ″                                                              |
| Duplicate row                 | Nhân bản nguyên vẹn một số dòng chưa bị corrupt khác, giữ nguyên `paper_id` | ~15%                                          | `paper_id_validity`/`title_uniqueness` FAIL   | _TBD_                | Repair build lại từ raw nên không mang theo duplicate         |

Sáu kịch bản dùng `random.Random(seed=42)` với các tập chỉ số **rời nhau** (không chồng lấp giữa các loại lỗi), và luôn tác động lên nhóm record mới nhất trước — do `testset.py` sinh câu hỏi cho **toàn bộ** 24 paper, mọi corruption trên dataframe gốc chắc chắn overlap với `ground_truth_doc_ids` của test set.

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Thiếu (corruption flow chưa chạy được vì thiếu `baseline_metrics.json` — xem mục 4)
- Nhận xét: theo thiết kế code, log sẽ ghi `generated_at`, `original_rows`, `corrupted_rows` và danh sách `{paper_id, type}` cho từng sự kiện lỗi, đủ để đối chiếu với `ground_truth_doc_ids` của test set.

Repair đọc lại `data/raw/crossref_records.json` (raw snapshot đã lưu từ bước ingestion, không gọi lại Crossref API) rồi chạy lại đúng `build_clean_dataframe` — tức là dùng lại chính logic cleaning đã qua kiểm chứng ở baseline, không phải một đường xử lý riêng để "che" lỗi. Điều này đảm bảo repair phục hồi từ nguồn đáng tin cậy (raw snapshot đã audit) thay vì sửa tay dữ liệu đã hỏng.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal              | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét                                             |
| ---------------------------- | -------: | --------: | -------: | ------------------------: | --------------: | --------------------------------------------------------- |
| `retrieval_hit_rate`        |    _TBD_ |     _TBD_ |    _TBD_ |                      _TBD_ |            _TBD_ | Cần `corrupted_metrics.json`/`repaired_metrics.json`     |
| `mean_token_f1`             |    _TBD_ |     _TBD_ |    _TBD_ |                      _TBD_ |            _TBD_ | ″                                                          |
| `judge_accuracy`            |    _TBD_ |     _TBD_ |    _TBD_ |                      _TBD_ |            _TBD_ | ″                                                          |
| `mean_judge_score`          |    _TBD_ |     _TBD_ |    _TBD_ |                      _TBD_ |            _TBD_ | ″                                                          |
| Quality checks pass/fail    |    _TBD_ |     _TBD_ |    _TBD_ |                      _TBD_ |            _TBD_ | Cần `corrupted_quality_checks.json`/`repaired_quality_checks.json` |
| Freshness status            |    _TBD_ |     _TBD_ |    _TBD_ |                      _TBD_ |            _TBD_ | Cần `corrupted_freshness_report.json`/`repaired_freshness_report.json` |

_TBD = chưa có artifact mới nhất tại thời điểm viết báo cáo. Không điền số liệu ước lượng hoặc lấy từ lần chạy trên phiên bản code cũ.

Hai chuỗi nhân quả **kỳ vọng** (dựa trên thiết kế corruption và cơ chế tính metric, chưa được xác nhận bằng artifact thật — cần chạy lại để kiểm chứng):

1. Xóa bản ghi mới nhất + blank/noise summary → `paper_id_validity`/`summary_min_length` FAIL trong quality checks → tài liệu không còn được retrieve đúng hoặc context rỗng/nhiễu → `retrieval_hit_rate` và `mean_token_f1` giảm so với baseline.
2. Repair đọc lại raw snapshot và build lại clean data → quality checks trở lại `overall_passed=true`, freshness trở lại `is_fresh=true` → metrics phục hồi về gần bằng baseline trên cùng test set.

Nhóm **không** khẳng định corruption "có tác động" cho đến khi có `corrupted_metrics.json` thật để đối chiếu — đây là hành động tiếp theo ưu tiên cao nhất trước khi nộp bài.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi ghép `corruption_flow.py` (Thành viên 4) với `quality.py`/`reporting.py` (Thành viên 3), code tích hợp ban đầu giả định `run_data_quality_checks` trả về `{"success": bool, "checks": [...]}"` (list các dict có `name`/`passed`/`details`), nhưng bản triển khai thực tế trả về `{"overall_passed": bool, "checks": {name: {...}}}` (dict, các field khác nhau tùy check).
- **Nguyên nhân gốc:** Hai thành viên hiện thực chi tiết khác nhau so với pseudo-code trong starter, và không có bước đối chiếu schema trước khi tích hợp.
- **Cách xử lý:** Thành viên 4 đọc trực tiếp code hiện tại của `quality.py`/`reporting.py`, cập nhật `corruption_flow.py` để đọc đúng field `overall_passed` và cấu trúc `checks` dạng dict thay vì giả định theo pseudo-code.
- **Cách xác minh:** Chạy `run_phase1.py` xác nhận `phase1_report.md` in đúng trạng thái PASS/FAIL từ `quality.get("overall_passed")` mà không raise lỗi khi format báo cáo.

**Vấn đề thứ hai (chưa xử lý xong, cần nhóm thống nhất trước khi nộp):** các báo cáo cá nhân hiện không đồng nhất về số liệu corrupted/repaired — báo cáo của Thành viên 1 trích dẫn số liệu cụ thể (`retrieval_hit_rate` 0.8333/1.0, `mean_token_f1` 0.6111/1.0...) trong khi báo cáo của Thành viên 2, 3, 4 đều ghi nhận "chưa có artifact" trên phiên bản code hiện tại (test set 96 câu, sau khi `quality.py` đổi schema). Số liệu của Thành viên 1 nhiều khả năng đến từ một lần chạy trên phiên bản code cũ hơn (test set 18 câu). Nhóm cần chạy lại `run_phase1.py` rồi `run_corruption_flow.py` một lần thống nhất trên đúng commit cuối cùng, và cập nhật toàn bộ báo cáo (nhóm + cá nhân) từ cùng một bộ artifact trước khi nộp.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại                                                             | Ảnh hưởng                                                                            | Hướng cải thiện có thể kiểm chứng                                                                 |
| --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `LLM_MODEL` mặc định (`gemini-2.5-flash`) bị chặn/hết quota với tài khoản hiện tại | Vòng lặp evaluate 96 câu × tối đa 3 trạng thái không hoàn tất trong thời gian hợp lý, judge rơi hoàn toàn về fallback heuristic | Đổi `LLM_MODEL` sang model còn quota trước khi chạy lấy số liệu chính thức; kiểm tra quota bằng một request thử trước khi chạy full pipeline |
| Chưa có một lần chạy end-to-end thống nhất trên bản code mới nhất                  | Các báo cáo cá nhân/nhóm có số liệu không đồng nhất (mục 11)                             | Chạy lại toàn bộ 2 script trên đúng commit cuối cùng, cập nhật tất cả report từ cùng một lần chạy          |
| `LocalEmbeddingIndex` mở hai `PersistentClient` ChromaDB riêng biệt (một để build, một để đọc lại) trên cùng thư mục | Từng gây `chromadb.errors.NotFoundError` khi độ trễ giữa các lần query quá lớn (do LLM retry kéo dài) | Refactor để `build()` trả về instance dùng lại đúng client/collection vừa tạo thay vì mở kết nối thứ hai |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [ ] Phân công khớp với module, artifact và kết quả thực tế. _(cần đối chiếu lại báo cáo Thành viên 1 — xem mục 1 và 11)_
- [ ] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp. _(chưa — xem mục 4)_
- [x] Baseline, corrupted và repaired dùng cùng evaluation set (theo thiết kế code — xem mục 6).
- [ ] Bảng metrics khớp với các file trong `data/results/`. _(chưa — các file chưa tồn tại, xem mục 7 và 10)_
- [ ] Quality/freshness conclusions khớp với `data/quality/`. _(chưa — xem mục 8)_
- [ ] Các đường dẫn báo cáo và artifact truy cập được. _(mới đúng cho raw/clean/eval; results/quality/reports còn thiếu)_
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng (4/4 file `individual_*`/tên riêng đã có trong `report/`).
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
