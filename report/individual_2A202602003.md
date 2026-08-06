# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Văn Thắng |
| MSSV | 2A202602003 |
| Khóa/Lớp | K4 |
| Tên nhóm | NoName |
| Vai trò chính | Thành viên 3 — Observability Owner |
| Repository | https://github.com/thenam-dev/K4_Day10_NoName |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data quality | `src/observability/quality.py` — `run_data_quality_checks` | Dataframe ở từng trạng thái và `Settings` | Các file `*_quality_checks.json` trong `data/quality/` | Hoàn thành phần triển khai |
| Freshness monitoring | `src/observability/quality.py` — `build_freshness_report` | Dataframe có `published`, `age_days`; ngưỡng freshness | Các file `*_freshness_report.json` | Hoàn thành phần triển khai |
| Reporting | `src/observability/reporting.py` — `generate_phase1_report`, `generate_corruption_report` | Source summary, metrics, quality và freshness results | `phase1_report.md`, `corruption_report.md` | Hoàn thành phần triển khai |

Các module ingestion, cleaning và evaluation cung cấp dữ liệu đầu vào cho phần observability. Tôi không nhận ownership chính cho Crossref ingestion, data modeling, corruption hoặc orchestration.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất contract dữ liệu clean | Role 2 — cleaning và evaluation set | Xác định các cột `paper_id`, `title`, `summary_chars`, `published`, `age_days` mà quality checks sử dụng. |
| Kiểm tra tích hợp report | Role 4 — pipeline integration | Đối chiếu tham số được truyền từ `phase1.py` và `corruption_flow.py` với nội dung report. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây bộ kiểm tra chất lượng | `quality.py` — `run_data_quality_checks` | Sáu checks: row count, ID validity, title completeness, summary length, freshness ratio và title uniqueness | Đọc `checks` và `overall_passed` trong JSON output |
| Theo dõi freshness | `quality.py` — `build_freshness_report` | Latest/oldest publication date, số và tỷ lệ stale records, trạng thái fresh/stale | Đối chiếu `age_days` với ngưỡng 180 ngày |
| Sinh báo cáo baseline | `reporting.py` — `generate_phase1_report` | Tổng hợp source, bốn RAG metrics, quality checks và freshness | Mở `data/reports/phase1_report.md` sau khi Phase 1 hoàn tất |
| Sinh báo cáo so sánh | `reporting.py` — `generate_corruption_report` | Bảng baseline/corrupted/repaired và các nhận định phục hồi | Mở `data/reports/corruption_report.md` sau corruption flow |

Tại thời điểm hoàn thiện báo cáo cá nhân, raw/clean/index/test-set đã hiện diện, nhưng các artifact trong `data/results/`, `data/quality/` và `data/reports/` đang được tái sinh bằng pipeline. Vì vậy tôi không điền số liệu corruption/repaired khi chưa có file đối chiếu.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline chạy thành công chưa đủ để khẳng định corpus phù hợp cho RAG. Dữ liệu có thể mất record, trùng ID/title, thiếu title, summary quá ngắn hoặc trở nên cũ. Những lỗi này cần được chuyển thành tín hiệu định lượng, lưu thành artifact và xuất hiện trong report để nhóm có thể liên hệ thay đổi dữ liệu với retrieval và answer metrics.

### Cách triển khai

`run_data_quality_checks` nhận dataframe và tạo sáu kiểm tra:

1. `row_count`: yêu cầu tối thiểu 5 record.
2. `paper_id_validity`: `paper_id` phải khác null và unique.
3. `title_completeness`: không có title null hoặc rỗng.
4. `summary_min_length`: mọi summary phải có ít nhất 50 ký tự.
5. `freshness_ratio`: ít nhất 70% record có `age_days <= 180`.
6. `title_uniqueness`: title phải unique.

Kết quả mỗi check gồm trạng thái pass/fail và giá trị thực tế. `overall_passed` chỉ bằng `true` khi toàn bộ checks đều pass. Hàm ghi kết quả vào `data/quality/<report_name>.json`, nhờ đó baseline, corrupted và repaired có thể được đối chiếu bằng cùng một contract.

`build_freshness_report` tính ngày publish mới nhất/cũ nhất, số record vượt ngưỡng 180 ngày và `stale_ratio`. Corpus được xem là fresh khi tỷ lệ stale nhỏ hơn 30%. `generate_phase1_report` và `generate_corruption_report` chuyển metrics cùng các tín hiệu quality/freshness thành báo cáo Markdown dễ kiểm tra.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Pandas DataFrame có `paper_id`, `title`, `summary_chars`, `published`, `age_days`; `Settings` chứa paths và `freshness_threshold_days`. |
| Output quality | Dictionary/JSON gồm `report_name`, `total_rows`, `overall_passed` và chi tiết từng check. |
| Output freshness | Dictionary/JSON gồm latest/oldest date, stale rows, stale ratio, threshold và `is_fresh`. |
| Output report | Markdown tổng hợp source, metrics, quality và freshness cho baseline hoặc ba trạng thái. |
| Module gọi | `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py`. |
| Điều kiện cần | Schema clean nhất quán; `age_days` và `summary_chars` đã được cleaning tính đúng. |

### Cách xác minh

Baseline:

```powershell
python script\run_phase1.py
```

Corruption và repair, chỉ chạy sau khi baseline hoàn tất:

```powershell
python script\run_corruption_flow.py
```

Các artifact cần đối chiếu:

- `data/quality/baseline_quality_checks.json`
- `data/quality/freshness_report.json`
- `data/quality/corrupted_quality_checks.json`
- `data/quality/corrupted_freshness_report.json`
- `data/quality/repaired_quality_checks.json`
- `data/quality/repaired_freshness_report.json`
- `data/reports/phase1_report.md`
- `data/reports/corruption_report.md`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần một quy tắc freshness có thể sử dụng nhất quán giữa baseline, corrupted và repaired.
- **Các phương án đã cân nhắc:** (1) chỉ dùng ngày publish mới nhất; (2) dùng tuổi trung bình; (3) đo tỷ lệ record vượt ngưỡng.
- **Phương án đã chọn:** dùng `stale_ratio`, trong đó record quá 180 ngày được coi là stale và corpus pass khi ít nhất 70% record còn fresh.
- **Lý do:** Một record mới nhất không đại diện cho toàn corpus, còn tỷ lệ stale phản ánh trực tiếp mức độ bao phủ của dữ liệu cũ và dễ giải thích trong report.
- **Bằng chứng quyết định phù hợp:** cùng một `freshness_threshold_days` được sử dụng bởi quality check và freshness report, giúp kết quả giữa JSON artifact và Markdown report nhất quán.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** report có thể ghi kết luận mạnh về corruption/repair trong khi metrics hoặc quality artifact của các trạng thái này chưa tồn tại.
- **Nguyên nhân gốc:** hàm tạo report nhận dữ liệu tổng hợp từ pipeline; nếu flow chưa chạy xong thì chưa có bằng chứng để kiểm chứng các nhận định.
- **Cách xử lý:** phân biệt rõ phần code đã hoàn thành với artifact đã được tái hiện; không đưa số liệu giả vào báo cáo cá nhân và yêu cầu chạy Phase 1 trước corruption flow.
- **Cách xác minh:** kiểm tra sự tồn tại của các file trong `data/results/`, `data/quality/`, `data/reports/`, rồi đối chiếu trực tiếp các giá trị trong bảng report với JSON nguồn.
- **Điều học được:** observability không chỉ là sinh report; mọi kết luận phải truy ngược được về artifact và trạng thái pipeline cụ thể.

## 7. Hiểu biết về luồng end-to-end

1. Ingestion lấy dữ liệu Crossref và lưu raw snapshot để có thể truy vết và repair.
2. Cleaning chuẩn hóa metadata, tạo document ID ổn định, `summary_chars`, `age_days` và `text_for_embedding`.
3. Retrieval tạo embedding/index; evaluation dùng test set cố định để tính retrieval hit rate, token F1 và judge metrics.
4. Observability kiểm tra quality/freshness trên dataframe tương ứng và lưu JSON artifacts trước khi tạo Markdown report.
5. Corruption thay đổi dữ liệu clean, sau đó pipeline build lại index và đánh giá trên đúng test set baseline.
6. Repair phải tái tạo clean data từ raw snapshot đáng tin cậy, build lại index, chạy lại quality/freshness và so sánh metrics với baseline.

Việc giữ nguyên evaluation set giúp tách ảnh hưởng của thay đổi dữ liệu khỏi thay đổi câu hỏi. Nếu đồng thời thay test set, chênh lệch metrics không còn đủ cơ sở để quy cho corruption hoặc repair.

## 8. Phân tích kết quả

### Metrics và tín hiệu chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | Chờ artifact tái sinh | Chưa có artifact | Chưa có artifact | Đối chiếu từ các file metrics, không suy đoán từ quality status. |
| `mean_token_f1` | Chờ artifact tái sinh | Chưa có artifact | Chưa có artifact | Summary rỗng/nhiễu có thể làm giảm metric nhưng phải xác minh bằng số liệu. |
| `judge_accuracy` | Chờ artifact tái sinh | Chưa có artifact | Chưa có artifact | Cần ghi rõ dùng LLM judge hay fallback heuristic. |
| `mean_judge_score` | Chờ artifact tái sinh | Chưa có artifact | Chưa có artifact | Không kết luận phục hồi nếu repaired chưa được đánh giá. |
| Quality checks | Chờ JSON tái sinh | Chưa có artifact | Chưa có artifact | Corruption dự kiến làm fail ID uniqueness hoặc summary length; đây mới là kỳ vọng. |
| Freshness status | Chờ JSON tái sinh | Chưa có artifact | Chưa có artifact | Kết luận phải dựa trên `stale_ratio` và threshold 180 ngày. |

Các quality signal và RAG metrics trả lời hai câu hỏi khác nhau. Quality checks cho biết schema/corpus có vi phạm kỳ vọng hay không; retrieval và answer metrics cho biết vi phạm đó có ảnh hưởng đến agent trên test set hiện tại hay không. Vì vậy không thể suy ra agent giảm chất lượng chỉ từ một quality check bị fail.

Sau khi Role 4 hoàn thành corruption flow, hai quan hệ cần được xác minh là:

1. Corruption cụ thể → check/freshness signal thay đổi → retrieval hoặc answer metric thay đổi thực tế.
2. Repair từ raw snapshot → quality/freshness trở lại gần baseline → agent metrics phục hồi hoặc có giải thích nếu chưa phục hồi.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Quality checks phải có ngưỡng, giá trị thực tế và artifact; chỉ ghi pass/fail là chưa đủ để điều tra lỗi.
2. Freshness nên được đo trên phân bố của toàn corpus thay vì dựa vào một timestamp đại diện.
3. Report chỉ đáng tin khi mỗi kết luận có thể truy ngược tới JSON metrics hoặc quality artifact tương ứng.

### Nếu có thêm thời gian

Tôi sẽ bổ sung kiểm tra tỷ lệ summary nhiễu, phân bố độ dài title/summary, schema validation rõ kiểu dữ liệu và kiểm tra drift giữa các lần chạy. Hiệu quả sẽ được đo bằng khả năng phát hiện chính xác từng corruption scenario, tỷ lệ cảnh báo sai và mức tương quan giữa quality signals với retrieval/answer metrics.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng vai trò Observability Owner và phạm vi module được giao.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận định lượng phải có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này được viết riêng cho Role 3, không sao chép nguyên văn báo cáo thành viên khác.

**Họ và tên:** Trần Văn Thắng  
**Ngày xác nhận:** 2026-08-06
