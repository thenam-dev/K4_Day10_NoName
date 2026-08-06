# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                      |
| --------------- | --------------------------------------------- |
| Họ và tên       | Nguyễn Thế Nam                                |
| MSSV            | 2A202601958                                   |
| Khóa/Lớp        | K4                                            |
| Tên nhóm        | NoName                                        |
| Vai trò chính   | Thành viên 4 — Corruption & Integration Owner |
| Repository      | https://github.com/thenam-dev/K4_Day10_NoName |
| Ngày hoàn thành | 2026-08-06                                    |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable              | File/hàm phụ trách                                            | Input nhận vào                                                              | Output bàn giao                                                                         | Trạng thái |
| -------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- | ---------- |
| Corruption simulation           | `src/ingestion/corruption.py` — `corrupt_clean_dataframe`     | Cleaned baseline dataframe, đường dẫn ghi corruption log                    | Corrupted dataframe; `papers_clean_corrupted.csv/json`; `corruption_log.json`             | Hoàn thành |
| Baseline orchestration          | `src/pipelines/phase1.py` — `main`                             | `Settings` (đường dẫn, provider, query Crossref)                            | Raw/clean/embedding/eval/metrics/quality/freshness/report của Pha 1                        | Hoàn thành |
| Corruption & repair integration | `src/pipelines/corruption_flow.py` — `main`                    | Artifact Pha 1 (`papers_clean.json`, `baseline_metrics.json`, raw snapshot) | Corrupted + repaired dataset, metrics, quality/freshness, `data/reports/corruption_report.md` | Hoàn thành |

Tôi là người điều phối tích hợp: ghép output của `crossref.py`, `cleaning.py`, `testset.py`, `quality.py`, `reporting.py` (do các thành viên khác sở hữu) thành hai flow chạy được end-to-end. Tôi không nhận ownership cho ingestion, cleaning, evaluation-set hay observability logic — chỉ tiêu thụ đúng contract của các module đó.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                                | Thành viên/module được hỗ trợ | Kết quả                                                                                                                                                    |
| ------------------------------------------ | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Đối chiếu contract quality/reporting     | `quality.py`, `reporting.py`  | Phát hiện `run_data_quality_checks` trả về schema `{overall_passed, checks: {name: {...}}}` — cập nhật code tích hợp của tôi để đọc đúng field này thay vì giả định `{success, checks: [...]}`. |
| Đối chiếu contract test set              | `testset.py`                  | Xác nhận `build_test_set` hỗ trợ `force_refresh` và tự kiểm tra cache có khớp dataframe hiện tại không; `corruption_flow.py` chủ động **không** gọi lại `build_test_set` để giữ test set đóng băng. |
| Kiểm tra retry/backoff của nguồn raw      | `crossref.py`                 | Xác minh `fetch_source_records` tự cache theo `settings.refresh_source`, không fetch lại API khi repair.                                                     |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện          | File/hàm/artifact liên quan                                                                 | Kết quả bàn giao                                                                                   | Cách xác minh                                              |
| -------------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| Ghép baseline pipeline           | `phase1.py`; `data/reports/phase1_report.md`                                                  | Baseline chạy hết 6 bước: ingest → clean → index → test set → evaluate → quality/freshness → report | Chạy `script/run_phase1.py`, đọc `phase1_report.md`        |
| Corrupt dữ liệu có kiểm soát   | `corruption.py`; `data/clean/papers_clean_corrupted.csv/json`, `corruption_log.json`         | 6 kịch bản lỗi: drop bản ghi mới nhất, blank summary, noise summary, truncate title, stale date, duplicate row | Đếm event trong `corruption_log.json`, đối chiếu `paper_id` bị corrupt với `ground_truth_doc_ids` trong test set |
| Đánh giá corrupted trên test set đóng băng | `corruption_flow.py`; `data/results/corrupted_metrics.json`                                  | Xem mục 8                                                                                               | Chạy `script/run_corruption_flow.py`                        |
| Repair từ raw snapshot          | `corruption_flow.py` (bước repair); `data/clean/papers_clean_repaired.csv/json`               | Repair build lại từ `data/raw/crossref_records.json`, không fetch lại API                            | Kiểm tra `load_raw_records` được gọi thay vì `fetch_source_records` trong `corruption_flow.py` |
| So sánh 3 trạng thái            | `data/reports/corruption_report.md`                                                           | Xem mục 8                                                                                               | Đọc `corruption_report.md`                                  |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mục tiêu của vai trò này không phải là làm ETL chạy được, mà phải **chứng minh bằng số liệu** rằng dữ liệu lỗi làm giảm chất lượng agent, và pipeline có thể phục hồi sau lỗi. Điều đó đòi hỏi ba việc phải khớp nhau tuyệt đối: (1) corruption phải đụng trúng ít nhất một tài liệu nằm trong evaluation set, nếu không metric sẽ không đổi; (2) baseline, corrupted, repaired phải dùng **chung một** evaluation set đã đóng băng, nếu không phép so sánh mất ý nghĩa; (3) repair phải dựng lại từ raw snapshot đã lưu, không fetch lại API, để không đổi luôn cả tập tài liệu nền.

### Cách triển khai

**`corruption.py`** — `corrupt_clean_dataframe` nhận cleaned dataframe (đã sort theo `published` giảm dần) và áp 6 kịch bản lỗi trên các tập chỉ số **rời nhau** (không chồng lấp), dùng `random.Random(seed=42)` để có thể tái lập:

1. Xoá một tỉ lệ (~15%) bản ghi **mới nhất** — vì dataframe sort theo published desc, nhóm bị xoá luôn nằm ở đầu, và vì `testset.py` cũng sinh câu hỏi cho toàn bộ tài liệu, corruption này chắc chắn đụng trúng test set.
2. Blank summary trên một mẫu khác.
3. Chèn noise text vào summary trên một mẫu khác.
4. Truncate title (cắt còn 1/3 độ dài).
5. Đẩy `published` về 3 năm trước, tính lại `age_days` — để trigger freshness check.
6. Nhân bản một số dòng (giữ nguyên `paper_id`) để trigger check `paper_id`/`title` uniqueness.

Sau khi corrupt, `text_for_embedding` được build lại đúng theo layout 5 phần (`Title | Authors | Categories | Published | Summary`) mà `cleaning.py` dùng, để index phản ánh đúng nội dung đã hỏng. Mọi `paper_id` bị tác động cùng loại corruption được ghi vào `corruption_log.json` để audit.

**`phase1.py`** — ghép tuần tự: load settings → fetch/cache raw records → `build_clean_dataframe` → lưu clean CSV/JSON → build ChromaDB index → tạo/tái sử dụng test set (`force_refresh=settings.refresh_test_set`) → `evaluate_pipeline` → `run_data_quality_checks` + `build_freshness_report` → `generate_phase1_report`.

**`corruption_flow.py`** — 9 bước: (0) load baseline artifacts, chặn sớm nếu chưa có `baseline_metrics.json`/`papers_clean.json`; (1) corrupt; (2-3) rebuild index + evaluate trên corrupted, **dùng lại đúng** `settings.paths.eval_testset` của baseline; (4) quality + freshness trên corrupted; (5) repair — đọc lại `raw_records_json` bằng `load_raw_records` rồi chạy lại `build_clean_dataframe`, **không** gọi `fetch_source_records`; (6-7) rebuild index + evaluate trên repaired, cùng test set; (8) quality + freshness trên repaired; (9) `generate_corruption_report` so sánh cả 3 trạng thái.

### Input, output và contract

| Thành phần            | Mô tả                                                                                                                                     |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Input                  | Cleaned dataframe (từ `cleaning.py`), raw records snapshot (`data/raw/crossref_records.json`), evaluation set đóng băng (`data/eval/test_set.json`), `Settings` từ `core/config.py`. |
| Output                 | `papers_clean_corrupted.*`, `papers_clean_repaired.*`, `corruption_log.json`, `corrupted_metrics.json`/`repaired_metrics.json`, `corrupted_quality_checks.json`/`repaired_quality_checks.json`, freshness reports, `corruption_report.md`. |
| Module phụ thuộc       | `ingestion.cleaning.build_clean_dataframe`, `ingestion.crossref.load_raw_records`, `retrieval.index.LocalEmbeddingIndex`, `evaluation.metrics.evaluate_pipeline`, `observability.quality.*`, `observability.reporting.*`. |
| Module dùng output     | Không có module downstream nào khác — đây là bước cuối của pipeline; output là bằng chứng nộp bài.                                          |
| Điều kiện lỗi xử lý    | Thiếu baseline artifact → `RuntimeError` chặn sớm; dataframe rỗng → ghi corruption log rỗng và trả về nguyên bản; LLM judge lỗi/hết quota → `evaluate_pipeline` tự fallback về heuristic (không làm sập flow). |

### Cách xác minh

```powershell
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** baseline chạy xong tạo đủ artifact Pha 1; corruption flow chạy sau đó tạo corrupted/repaired dataset, metrics, quality/freshness và `corruption_report.md`.
- **Kết quả thực tế:** xem số liệu tại mục 8 (lấy trực tiếp từ artifact trong lần chạy gần nhất, không chỉnh tay).
- **Artifact/log:** `data/results/corrupted_metrics.json`, `data/results/repaired_metrics.json`, `data/results/corruption_log.json`, `data/quality/corrupted_quality_checks.json`, `data/quality/repaired_quality_checks.json`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Nếu corruption ngẫu nhiên hoàn toàn trên cả dataset, có rủi ro lỗi rơi vào các tài liệu không nằm trong evaluation set — khi đó metric sẽ không đổi và không chứng minh được gì (đây là cảnh báo rõ ràng trong đề bài).
- **Các phương án đã cân nhắc:** (1) chọn ngẫu nhiên hoàn toàn trên toàn bộ dataframe cho mọi kịch bản; (2) cố tình chọn corruption trên đúng các `paper_id` xuất hiện trong `ground_truth_doc_ids` của test set; (3) tận dụng cách `testset.py` sinh câu hỏi cho **toàn bộ** tài liệu clean, kết hợp việc kịch bản "drop latest" luôn nhắm vào nhóm tài liệu mới nhất.
- **Phương án đã chọn:** phương án (3) — vì `testset.py` hiện tại sinh 4 câu hỏi cho mỗi paper trong dataset, **mọi** `paper_id` đều nằm trong test set, nên bất kỳ corruption nào trên dataframe gốc cũng tự động đụng trúng test set mà không cần hard-code danh sách ID cần corrupt.
- **Lý do:** không cần biết trước nội dung test set (giữ corruption module độc lập với evaluation module), đồng thời vẫn đảm bảo overlap 100%.
- **Bằng chứng quyết định phù hợp:** đối chiếu `corruption_log.json` (danh sách `paper_id` bị corrupt) với `ground_truth_doc_ids` trong `test_set.json` — xem mục 8.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `chromadb.errors.NotFoundError: Error getting collection: Collection [...] does not exist.` xảy ra giữa vòng lặp `evaluate_pipeline`, sau khi `LocalEmbeddingIndex.build()` đã trả về thành công.
- **Lệnh hoặc bước tái hiện:** chạy `run_phase1.py` trong lúc LLM provider bị lỗi model/quota (khiến mỗi câu hỏi phải retry hàng chục giây trước khi rơi về fallback), kéo dài thời gian giữa các lần query ChromaDB.
- **Nguyên nhân gốc:** nghi vấn là race condition khi `LocalEmbeddingIndex.build()` mở một `PersistentClient` để ghi, sau đó `__init__` mở **client thứ hai** trên cùng `data/chroma/` để đọc lại collection vừa tạo — độ trễ lớn giữa các lần gọi (do LLM retry) làm lộ ra sự không nhất quán này.
- **Cách xử lý:** không sửa `index.py` (không thuộc phạm vi sở hữu, thuộc nhóm code tham khảo dùng chung); thay vào đó xử lý ở tầng vận hành — đổi `LLM_MODEL` sang một model còn quota để vòng lặp evaluate chạy đủ nhanh, tránh rơi vào khoảng chờ dài gây lộ race condition; đồng thời xoá sạch `data/chroma/` trước khi chạy lại từ đầu.
- **Cách xác minh sau khi sửa:** chạy lại `run_phase1.py` với model có quota, `evaluate_pipeline` chạy hết toàn bộ câu hỏi không crash.
- **Điều học được:** lỗi "ngẫu nhiên" xuất hiện dưới tải/độ trễ bất thường thường là dấu hiệu của race condition tiềm ẩn trong code dùng chung — cần ghi nhận lại dù không thuộc phạm vi sở hữu, để nhóm biết rủi ro khi vận hành lâu dài với provider chậm.

## 7. Hiểu biết về luồng end-to-end

1. `crossref.py` gọi API, lưu raw response + raw records. `cleaning.py` chuẩn hoá thành dataframe với `text_for_embedding`. `index.py` dùng MiniLM tạo vector, nạp ChromaDB kèm metadata (`paper_id`, `title`, `published`, ...).
2. `testset.py` sinh câu hỏi cho **mọi** tài liệu clean, mỗi câu có `ground_truth` và `ground_truth_doc_ids`. `evaluate_pipeline` (metrics.py) chạy agent trên từng câu, so `retrieved_doc_ids` với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, so câu trả lời với `ground_truth` bằng token F1 và LLM-judge (có fallback heuristic khi LLM lỗi).
3. `quality.py` kiểm tra row count, tính hợp lệ/duy nhất của `paper_id`, độ dài title/summary, tỉ lệ tài liệu còn trong ngưỡng freshness. `build_freshness_report` tổng hợp latest/oldest published, số dòng stale, trạng thái fresh/stale.
4. Vai trò của tôi là đảm bảo baseline, corrupted, repaired **chỉ khác nhau ở trạng thái dữ liệu/index**, còn lại (test set, provider, threshold) giữ nguyên — nên mọi chênh lệch metric chỉ có thể quy về corruption hoặc repair, không phải do đổi cách đo.
5. Repair coi là thành công khi: (a) `repaired_quality_checks.json.overall_passed = true`, (b) `repaired_freshness_report.is_fresh = true`, (c) `repaired_metrics.json` phục hồi về gần bằng `baseline_metrics.json` trên cùng test set. Nếu một trong ba điều kiện không đạt, không được kết luận là đã repair thành công.

## 8. Phân tích kết quả

### Trạng thái tại thời điểm viết báo cáo

Tại thời điểm nộp báo cáo này, `run_phase1.py` trên bộ code hiện tại của repo (evaluation set 96 câu hỏi — 24 paper × 4 loại) **chưa chạy xong** trong môi trường soạn báo cáo: `LLM_MODEL` đang trỏ tới một model bị nhà cung cấp chặn với tài khoản mới (`404 NOT_FOUND`) và đã hết quota ngày (`429 RESOURCE_EXHAUSTED`), khiến mỗi lệnh gọi LLM-judge phải retry/backoff dài trước khi rơi về fallback heuristic — với 96 câu, tổng thời gian vượt quá phạm vi một lần chạy hợp lý nên đã dừng lại thay vì tiếp tục chờ.

Vì vậy tôi **không điền số liệu baseline/corrupted/repaired thật** trong bảng dưới đây — đúng cam kết ở mục 10. `corruption.py`, `phase1.py`, `corruption_flow.py` đã hoàn thành về mặt code và logic (mô tả ở mục 4), nhưng phần "bằng chứng bằng số liệu" cho mục tiêu cốt lõi của bài lab (corruption làm giảm chất lượng, repair phục hồi được) **cần một lần chạy end-to-end thành công** để xác nhận, chưa thể coi là đã hoàn tất.

### Cách lấy số liệu để hoàn thiện mục này

```powershell
python script/run_phase1.py
python script/run_corruption_flow.py
```

Sau khi hai lệnh trên chạy xong (khuyến nghị đổi `LLM_MODEL` sang một model còn quota, hoặc chấp nhận toàn bộ judge score chạy theo fallback heuristic — cả hai đều hợp lệ vì `evaluate_pipeline` không phụ thuộc LLM để tính `retrieval_hit_rate`/`mean_token_f1`), điền lại bảng dưới từ đúng các file:

- `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`
- `data/quality/baseline_quality_checks.json`, `corrupted_quality_checks.json`, `repaired_quality_checks.json`
- `data/quality/freshness_report.json`, `corrupted_freshness_report.json`, `repaired_freshness_report.json`
- `data/results/corruption_log.json` đối chiếu `paper_id` với `ground_truth_doc_ids` trong `data/eval/test_set.json` để xác nhận corruption có overlap với test set (điều kiện bắt buộc để metric có thay đổi)

### Metrics chính (mẫu bảng — điền từ artifact thật)

| Metric/signal         | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ----------------------- | -------: | --------: | -------: | ---------------------- |
| `retrieval_hit_rate`  |    _TBD_ |     _TBD_ |    _TBD_ |                        |
| `mean_token_f1`       |    _TBD_ |     _TBD_ |    _TBD_ |                        |
| `judge_accuracy`      |    _TBD_ |     _TBD_ |    _TBD_ |                        |
| `mean_judge_score`    |    _TBD_ |     _TBD_ |    _TBD_ |                        |
| Quality checks         |    _TBD_ |     _TBD_ |    _TBD_ |                        |
| Freshness status       |    _TBD_ |     _TBD_ |    _TBD_ |                        |

_TBD = chưa có artifact tại thời điểm viết báo cáo. Không suy diễn hay ước lượng thay cho số liệu thật._

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Vai trò tích hợp phải hiểu contract (schema, tên field trả về) của **từng** module khác trước khi ghép — không thể chỉ giả định theo pseudo-code, vì các thành viên có thể hiện thực khác chi tiết (ví dụ schema `checks` là dict thay vì list).
2. "Đóng băng" evaluation set không chỉ là quy ước — phải thể hiện bằng code: không gọi lại hàm sinh test set trong corruption flow, mà tái sử dụng đúng đường dẫn file đã tạo ở baseline.
3. Corruption ngẫu nhiên vô hướng dễ tạo ra kết quả "không chứng minh được gì" nếu không cố tình đảm bảo nó chạm vào evaluation set — đây là lỗi thiết kế dễ mắc phải nhất của vai trò này.

### Nếu có thêm thời gian

Tôi sẽ thêm bước xác thực tự động (assert) ngay trong `corruption_flow.py` để kiểm tra `corruption_log.json` có overlap với `ground_truth_doc_ids` của test set trước khi tiếp tục evaluate — hiện việc này đang được kiểm tra thủ công. Cũng sẽ thử nhiều seed corruption khác nhau để đo độ nhạy của metric với các tỉ lệ lỗi khác nhau (5%, 15%, 30%).

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu. _(chưa đạt — xem mục 8: pipeline chưa chạy xong end-to-end trong môi trường soạn báo cáo, cần chạy lại và điền số liệu thật trước khi nộp)_
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Thế Nam
**Ngày xác nhận:** 2026-08-06
