# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                         |
| --------------- | ------------------------------------------------ |
| Họ và tên       | Đào Duy Hưng                                     |
| MSSV            | 2A202601166                                      |
| Khóa/Lớp        | K4                                               |
| Tên nhóm        | NoName                                           |
| Vai trò chính   | Thành viên 2 — Data Model & Evaluation-set Owner |
| Repository      | https://github.com/thenam-dev/K4_Day10_NoName    |
| Ngày hoàn thành | 2026-08-06                                       |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable     | File/hàm phụ trách                                    | Input nhận vào                                | Output bàn giao                                            | Trạng thái |
| ---------------------- | ----------------------------------------------------- | --------------------------------------------- | ---------------------------------------------------------- | ---------- |
| Cleaning và data model | `src/ingestion/cleaning.py` — `build_clean_dataframe` | `list[PaperRecord]` từ Crossref và `run_date` | Dataframe clean; `papers_clean.csv` và `papers_clean.json` | Hoàn thành |
| Evaluation set         | `src/evaluation/testset.py` — `build_test_set`        | Clean dataframe và đường dẫn output           | `data/eval/test_set.json`                                  | Hoàn thành |

Các module retrieval, quality và pipeline sử dụng schema clean do tôi bàn giao. Tôi không nhận ownership cho Crossref ingestion, observability, corruption hoặc orchestration.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                      | Thành viên/module được hỗ trợ | Kết quả                                                                                                     |
| ------------------------------ | ----------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Kiểm tra contract raw-to-clean | `crossref.py` và `phase1.py`  | Xác minh raw snapshot có 24 records và schema phù hợp để clean.                                             |
| Tái sinh baseline artifact     | Baseline pipeline             | Tạo lại clean data, embedding manifest, evaluation set và baseline answers sau khi cập nhật cleaning rules. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện      | File/hàm/artifact liên quan                                       | Kết quả bàn giao                                                                            | Cách xác minh                                                |
| -------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Chuẩn hóa raw records      | `cleaning.py`; `data/clean/papers_clean.csv`, `papers_clean.json` | 24 records clean, `paper_id` unique, không có title/summary rỗng                            | Kiểm tra dataframe và `baseline_quality_checks.json`         |
| Tạo nội dung embedding     | `cleaning.py` — `text_for_embedding`                              | Mỗi document có title, authors, categories, published date và summary                       | Kiểm tra 24/24 rows có trường này                            |
| Xây test set ổn định       | `testset.py`; `data/eval/test_set.json`                           | 96 samples: 24 cho mỗi loại `summary`, `authors`, `date`, `categories`                      | Đếm sample và đối chiếu `ground_truth_doc_ids` với clean IDs |
| Kiểm tra baseline tích hợp | `data/results/baseline_metrics.json`                              | `retrieval_hit_rate=1.0`, `mean_token_f1=1.0`, `judge_accuracy=1.0`, `mean_judge_score=5.0` | Chạy `script/run_phase1.py`                                  |

Output cụ thể do phần việc của tôi tạo ra là `data/eval/test_set.json`: 96 câu hỏi có `ground_truth_doc_ids` trỏ đúng 24 `paper_id` trong cleaned dataset. Artifact này là input dùng chung để so sánh các trạng thái pipeline.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Raw metadata từ Crossref có thể chứa HTML/JATS, khoảng trắng thừa, list tác giả/chủ đề chưa chuẩn hóa, bản ghi trùng hoặc ngày không parse được. Nếu đưa trực tiếp vào embedding, retrieval khó dùng metadata để trả lời và freshness có thể sai. Đồng thời evaluation phải có ground truth gắn với document ID ổn định để đo đúng retrieval hit rate.

### Cách triển khai

`build_clean_dataframe` loại record thiếu `paper_id`, title, summary đủ dài hoặc ngày publish hợp lệ; loại HTML/JATS và HTML entities; chuẩn hóa khoảng trắng; chuẩn hóa `authors` và `categories`; chuyển DOI về lowercase; tính `age_days`; và deduplicate theo `paper_id` rồi title không phân biệt hoa/thường. Khi không có category, dữ liệu được gắn rõ là `Uncategorized` thay vì gán một chủ đề học thuật không có trong source.

`text_for_embedding` ghép theo cấu trúc: title, authors, categories, published date và summary. Vì vậy vector index có cả nội dung nghiên cứu và metadata cần cho bốn dạng câu hỏi.

`build_test_set` kiểm tra schema clean, tối thiểu 4 documents và `paper_id` unique. Mỗi paper tạo bốn câu hỏi theo template; mỗi câu chứa `id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids`. Test set được sắp xếp deterministic theo `published` và `paper_id`. Khi có file test set cũ, hàm kiểm tra nội dung có còn khớp dataframe hiện tại không; nếu không khớp thì tự tạo lại.

### Input, output và contract

| Thành phần            | Mô tả                                                                                                                                                                                            |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Input                 | `PaperRecord` có DOI, title, summary, authors, categories, dates và URLs; `run_date` là `date` hoặc `datetime`.                                                                                  |
| Output                | Clean dataframe gồm các cột bắt buộc: `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days`, `summary_chars`, `text_for_embedding` cùng metadata nguồn. |
| Module phụ thuộc      | `src/ingestion/crossref.py` cung cấp `PaperRecord`; `src/core/utils.py` cung cấp hàm đọc/ghi và normalize.                                                                                       |
| Module sử dụng output | `retrieval/index.py`, `evaluation/metrics.py`, `observability/quality.py`, `pipelines/phase1.py` và corruption flow.                                                                             |
| Điều kiện lỗi xử lý   | Dataframe thiếu cột, ít hơn 4 documents, DOI rỗng/trùng; record có title/summary/date không hợp lệ; test set cache không còn khớp dữ liệu clean.                                                 |

### Cách xác minh

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:LLM_PROVIDER='invalid'
$env:REFRESH_TEST_SET='true'
\.venv\Scripts\python.exe -B script\run_phase1.py
```

- **Kết quả mong đợi:** tạo clean dataset, embedding manifest, test set và baseline metrics mà không có record invalid.
- **Kết quả thực tế:** 24 raw records → 24 cleaned records → 96 evaluation samples; quality checks pass và freshness report là `FRESH`.
- **Artifact/log:** `data/clean/papers_clean.json`, `data/eval/test_set.json`, `data/results/baseline_metrics.json`, `data/quality/baseline_quality_checks.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Crossref records thiếu subject hoặc ngày có thể làm cho category/freshness trở nên sai lệch.
- **Các phương án đã cân nhắc:** (1) gán category/date mặc định giống dữ liệu thật; (2) giữ giá trị thiếu rõ ràng và lọc record không có ngày publish hợp lệ.
- **Phương án đã chọn:** category thiếu được biểu diễn là `Uncategorized`; record thiếu hoặc không parse được ngày publish bị loại trong cleaning.
- **Lý do:** Không che giấu vấn đề chất lượng dữ liệu. Freshness report và evaluation set phải dựa trên metadata có thể giải thích được.
- **Bằng chứng quyết định phù hợp:** `baseline_quality_checks.json` xác nhận 24 IDs unique, 0 title rỗng, 0 summary ngắn; `freshness_report.json` ghi 0 stale rows trên 24 records.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `WinError 10013 ... forbidden by its access permissions` khi SentenceTransformer cố tải model từ Hugging Face trong môi trường sandbox.
- **Lệnh hoặc bước tái hiện:** chạy `script/run_phase1.py` khi model chưa dùng cache offline.
- **Nguyên nhân gốc:** môi trường chạy bị hạn chế network, không phải lỗi của cleaning hoặc test-set.
- **Cách xử lý:** sau khi model đã được cache, chạy baseline với `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1`; đặt `LLM_PROVIDER=invalid` để evaluator dùng fallback heuristic thay vì chờ gọi LLM bên ngoài.
- **Cách xác minh sau khi sửa:** baseline chạy hết 6 bước và tạo đầy đủ artifact clean/eval/results/quality/report.
- **Điều học được:** tách lỗi dependency/network khỏi lỗi data contract giúp xác minh module chính xác hơn và làm pipeline tái lập được.

## 7. Hiểu biết về luồng end-to-end

1. Crossref API trả response JSON; ingestion lưu response/raw records; cleaning biến `PaperRecord` thành schema clean; embedding index dùng `text_for_embedding` để tạo vector và lưu metadata.
2. Mỗi item evaluation có ground truth và `ground_truth_doc_ids`. Sau retrieval, metric kiểm tra document được trả về có chứa ID đúng không để tính `retrieval_hit_rate`; câu trả lời được so với ground truth bằng token F1 và judge.
3. Quality checks kiểm tra completeness, uniqueness, summary length và row count. Freshness monitoring tập trung vào tuổi của publication date, số stale rows, oldest/latest record và trạng thái fresh/stale.
4. Cùng test set giúp baseline, corrupted và repaired chỉ khác trạng thái dữ liệu/index; do đó chênh lệch metric mới có thể quy cho corruption hoặc repair.
5. Repair thành công khi artifact repaired khôi phục được schema/quality/freshness và metrics trên cùng test set phục hồi gần baseline. Cần đối chiếu các file metrics, quality/freshness report và comparison report.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal        | Baseline |        Corrupted |         Repaired | Nhận xét của cá nhân                                            |
| -------------------- | -------: | ---------------: | ---------------: | --------------------------------------------------------------- |
| `retrieval_hit_rate` |   1.0000 | Chưa có artifact | Chưa có artifact | Baseline retrieve đúng document ID cho 96 samples.              |
| `mean_token_f1`      |   1.0000 | Chưa có artifact | Chưa có artifact | Answer khớp ground truth theo token F1.                         |
| `judge_accuracy`     |   1.0000 | Chưa có artifact | Chưa có artifact | Judge dùng fallback heuristic vì không chạy external LLM judge. |
| `mean_judge_score`   |   5.0000 | Chưa có artifact | Chưa có artifact | Cần diễn giải cùng giới hạn của fallback judge.                 |
| Quality checks       |     PASS | Chưa có artifact | Chưa có artifact | 24 rows, IDs unique, 0 title rỗng, 0 summary ngắn.              |
| Freshness status     |    FRESH | Chưa có artifact | Chưa có artifact | Latest: 2026-08-05; oldest: 2026-02-12; stale: 0/24.            |

Kết quả baseline xác minh contract Role 2 hoạt động với pipeline. Tuy nhiên, score 1.0 không nên được hiểu là hệ thống đã được đánh giá toàn diện: câu hỏi hiện chứa title paper, vì vậy exact lookup làm bài baseline thuận lợi; Ragas cũng đang được tắt.

Hai chuỗi nguyên nhân–bằng chứng cho corruption/repair **chưa thể kết luận** vì chưa có `corrupted_metrics.json`, `repaired_metrics.json`, quality/freshness artifacts tương ứng hoặc `corruption_report.md`. Tôi không điền số liệu giả cho hai trạng thái này. Khi Role 4 hoàn thành, cần dùng nguyên `data/eval/test_set.json` hiện tại để phân tích hai chuỗi đó.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Schema và document ID ổn định là điều kiện để retrieval, quality và evaluation nói cùng một ngôn ngữ dữ liệu.
2. Không nên thay giá trị thiếu bằng metadata có vẻ hợp lý, vì điều đó có thể làm report chất lượng/freshness đẹp giả.
3. Test set cần tái lập được và giữ nguyên giữa các trạng thái dữ liệu để metric có ý nghĩa so sánh.

### Nếu có thêm thời gian

Tôi sẽ thêm các câu hỏi summary không chứa exact title và đánh giá bằng LLM judge/Ragas có cấu hình đầy đủ. Có thể đo cải thiện bằng sự thay đổi retrieval hit rate, token F1, judge score và độ nhạy của các metric sau corruption.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đào Duy Hưng  
**Ngày xác nhận:** 2026-08-06
