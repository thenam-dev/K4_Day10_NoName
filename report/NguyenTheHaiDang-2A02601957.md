# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Thế Hải Đăng |
| MSSV | 2A02601957 |
| Khóa/Lớp | K4 / Khoa Học Dữ Liệu |
| Tên nhóm | Group 1 |
| Vai trò chính | Role 1 — Data Ingestion, Cleaning & Quality Observability Lead |
| Repository | [thenam-dev/K4_Day10_Data-Pipeline-Data-Observability](https://github.com/thenam-dev/K4_Day10_Data-Pipeline-Data-Observability) |
| Ngày hoàn thành | 2026-08-06 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu (Ownership)

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Raw Data Ingestion | `src/ingestion/crossref.py`<br>`fetch_source_records()` | Crossref REST API (`https://api.crossref.org/works`) | `data/raw/crossref_response.json`<br>`data/raw/crossref_records.json` | Hoàn thành |
| Data Cleaning & Data Modeling | `src/ingestion/cleaning.py`<br>`build_clean_dataframe()` | List record thô (`PaperRecord`) | `data/clean/papers_clean.csv`<br>`data/clean/papers_clean.json` | Hoàn thành |
| Data Quality & Freshness Observability | `src/observability/quality.py`<br>`run_data_quality_checks()`<br>`build_freshness_report()` | Clean DataFrame (`pd.DataFrame`) | `data/quality/baseline_quality_checks.json`<br>`data/quality/freshness_report.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Tạo bộ test set cố định | Module Evaluation (`src/evaluation/testset.py`) | Đã xây dựng 96 mẫu kiểm thử chứa `ground_truth_doc_ids` chuẩn hóa. |
| Ghép luồng Baseline Pipeline | Module Pipelines (`src/pipelines/phase1.py`) | Tích hợp thành công ETL + Indexing + Observability vào script `run_phase1.py`. |
| Xử lý fallback Vector Index | Module Retrieval (`src/retrieval/index.py`) | Thêm cơ chế NumPy Cosine Similarity fallback khi gặp sự cố gRPC native DLL trên Windows. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Ingest & Parse dữ liệu thô Crossref API | [crossref.py](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/src/ingestion/crossref.py) | [crossref_response.json](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/raw/crossref_response.json) (245 KB)<br>[crossref_records.json](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/raw/crossref_records.json) (62 KB) | Kiểm tra 24 records thô phẳng đã được parse đúng schema `PaperRecord`. |
| Làm sạch HTML, deduplicate & tạo `text_for_embedding` | [cleaning.py](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/src/ingestion/cleaning.py) | [papers_clean.csv](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/clean/papers_clean.csv) (102 KB)<br>[papers_clean.json](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/clean/papers_clean.json) (117 KB) | Đã làm sạch 24 bài báo hợp lệ, loại bỏ các tag HTML/XML và tính cột `age_days`. |
| Thực thi Data Quality Suite & Freshness Monitoring | [quality.py](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/src/observability/quality.py) | [baseline_quality_checks.json](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/quality/baseline_quality_checks.json)<br>[freshness_report.json](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/quality/freshness_report.json) | 6/6 quality checks vượt qua (`PASSED`), độ tươi mới đạt `FRESH` (0 stale rows). |

### Output cụ thể tạo ra

Bàn giao tập dữ liệu sạch [papers_clean.csv](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/clean/papers_clean.csv) và bộ giám sát chất lượng dữ liệu tự động [baseline_quality_checks.json](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/quality/baseline_quality_checks.json), làm tiền đề cho việc xây dựng vector store và đánh giá RAG Agent ở Phase 1.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Nguồn dữ liệu bên ngoài (Crossref API) thường chứa nhiễu HTML/XML JATS trong abstract, định dạng ngày tháng không đồng nhất, các bản ghi bị thiếu thông tin tiêu đề hoặc bị lặp lại. Nếu đưa trực tiếp dữ liệu nhiễu này vào mô hình embedding (`all-MiniLM-L6-v2`), khoảng cách vector sẽ bị trôi lệch, dẫn đến việc RAG Agent truy vấn sai context hoặc trả về kết quả rác.

### Cách triển khai

1. **Exponential Backoff Ingestion (`src/ingestion/crossref.py`)**:
   - Sử dụng `urllib.request` với cơ chế retry tự động theo hàm mũ (backoff factor: $1.5 \times 2^{\text{attempt}}$) để chống các mã lỗi `429 Too Many Requests` và `503 Service Unavailable`.
   - Lưu trữ nguyên bản hai tầng: Raw HTTP response (`crossref_response.json`) và Parsed records snapshot (`crossref_records.json`).

2. **Data Cleaning & Schema Normalization (`src/ingestion/cleaning.py`)**:
   - Sử dụng Regex `_strip_html()` bóc tách toàn bộ thẻ `<jats:p>`, `<b>`, `<i>` trong abstract và title.
   - Chuẩn hóa định dạng ngày xuất bản `YYYY-MM-DD` và tính toán khoảng tuổi dữ liệu `age_days = (run_date - published_date).days`.
   - Khởi tạo cột văn bản chuyên dụng cho embedding:
     `text_for_embedding = f"Title: {title} | Authors: {authors_joined} | Summary: {summary}"`.
   - Lọc bỏ bản ghi rác (`summary_chars < 50` hoặc tiêu đề trống) và loại bỏ lặp bản ghi dựa trên `paper_id` và `title`.

3. **Data Quality & Freshness Observability (`src/observability/quality.py`)**:
   - Triển khai 6 quy tắc kiểm tra Data Quality:
     1. `row_count`: Số lượng bản ghi hợp lệ $\ge 5$.
     2. `paper_id_validity`: Mã bài báo không `null` và duy nhất (`is_unique`).
     3. `title_completeness`: Tiêu đề không rỗng hoặc chứa toàn khoảng trắng.
     4. `summary_min_length`: Độ dài tóm tắt $\ge 50$ ký tự.
     5. `freshness_ratio`: Tỷ lệ bản ghi đạt độ tươi mới ($\le 180$ ngày) $\ge 70\%$.
     6. `title_uniqueness`: Không trùng lặp tiêu đề bài báo.
   - Xây dựng báo cáo `build_freshness_report()` tổng hợp `latest_published`, `oldest_published`, `stale_rows` và trạng thái `is_fresh`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | JSON response thô từ Crossref API (`https://api.crossref.org/works`). |
| Output | DataFrame dữ liệu sạch (`papers_clean.csv`/`.json`) và 2 báo cáo JSON (`baseline_quality_checks.json`, `freshness_report.json`). |
| Module phụ thuộc | `src/core/config.py`, `src/core/utils.py`. |
| Module sử dụng output | `src/retrieval/index.py` (tạo Vector Index), `src/evaluation/testset.py` (tạo Test Set), `src/pipelines/phase1.py`. |
| Điều kiện lỗi cần xử lý | Mạng ngắt kết nối, API rate limit (HTTP 429), XML formatting lỗi trong tóm tắt bài báo, thiếu trường ngày xuất bản. |

### Cách xác minh

```bash
$env:PYTHONPATH="src"
python script/run_phase1.py
```

- **Kết quả mong đợi:** Tải 24 bài báo thô, làm sạch thành công 24 bản ghi, sinh file `papers_clean.csv` và báo cáo Data Quality đạt 6/6 quy tắc (`PASSED`).
- **Kết quả thực tế:** Pipeline chạy hoàn thành 100%, ghi file `data/clean/papers_clean.csv` (102 KB) và `data/quality/baseline_quality_checks.json` với `overall_passed: true`.
- **Artifact/log:** [baseline_quality_checks.json](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/quality/baseline_quality_checks.json), [freshness_report.json](file:///d:/c%C3%A1%20nh%C3%A2n/K4_Day10_Data-Pipeline-Data-Observability/data/quality/freshness_report.json).

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần quyết định kiến trúc lưu trữ dữ liệu thô khi thu thập từ Crossref API.
- **Các phương án đã cân nhắc:**
  1. *Phương án A*: Làm sạch dữ liệu trực tiếp trong bộ nhớ (in-memory streaming) và chỉ lưu trữ file sạch cuối cùng (`papers_clean.json`).
  2. *Phương án B (Đã chọn)*: Lưu trữ 2 tầng thô độc lập (`crossref_response.json` chứa HTTP response nguyên bản và `crossref_records.json` chứa cấu trúc phẳng đã parse) trước khi đưa vào bước cleaning.
- **Phương án đã chọn:** Phương án B.
- **Lý do:**
  - *Data Auditability & Reproducibility*: Giữ lại bản sao thô giúp kiểm tra nguồn gốc dữ liệu (data lineage) bất kỳ lúc nào mà không cần gọi lại external API.
  - *Self-healing Recovery*: Khi hệ thống gặp sự cố hỏng dữ liệu (Data Corruption), luồng khôi phục (`corruption_flow.py`) có thể đọc trực tiếp từ `crossref_records.json` để repair mà không phụ thuộc vào kết nối mạng hay nguy cơ thay đổi dữ liệu từ API bên ngoài.
- **Bằng chứng quyết định phù hợp:** Trong pha 2 (Corruption Flow), pipeline đã khôi phục thành công 100% bản ghi sạch từ `data/raw/crossref_records.json` mà không cần thực hiện lại bất kỳ HTTP request nào.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  ImportError: DLL load failed while importing cygrpc: An Application Control policy has blocked this file.
  ```
- **Lệnh hoặc bước tái hiện:** Khi gọi `from retrieval.index import LocalEmbeddingIndex` hoặc import `chromadb` trên môi trường Windows có chính sách bảo mật Application Control Policy.
- **Nguyên nhân gốc:** Thư viện `chromadb` mặc định nạp module telemetry Opentelemetry, module này phụ thuộc vào file DLL C-extension `cygrpc.pyd` của thư viện `grpcio`. Thao tác nạp file `.pyd` này bị hệ điều hành ngăn chặn do chính sách bảo mật.
- **Cách xử lý:** Thiết kế cơ chế fallback linh hoạt trong `src/retrieval/index.py`:
  - Đóng gói câu lệnh `import chromadb` vào khối `try...except`.
  - Khi phát hiện `chromadb` bị chặn, tự động chuyển sang `local_vector_index` sử dụng thuật toán Cosine Similarity trực tiếp trên NumPy array (`np.dot(q_vec, d_vec)`).
- **Cách xác minh sau khi sửa:** Chạy lại `python script/run_phase1.py`. Hệ thống tự động chuyển đổi sang backend `local_vector_index`, tạo thành công index với 24 embedding và đạt chỉ số Retrieval Hit Rate = `1.0000`.
- **Điều học được:** Khi xây dựng data pipeline trên môi trường enterprise/production, các module phụ thuộc C-extensions / native DLLs có thể bị lỗi trên các hệ điều hành khác nhau. Việc xây dựng cơ chế graceful degradation / fallback thuần Python giúp hệ thống hoạt động bền bỉ (resilient).

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Dữ liệu được thu thập qua Crossref REST API (`fetch_source_records`), lưu snapshot thô vào `data/raw/`. Sau đó module `cleaning.py` lọc bỏ HTML, chuẩn hóa schema, tính toán `age_days` và ghép thành chuỗi `text_for_embedding`. Chuỗi này được đưa qua mô hình `sentence-transformers/all-MiniLM-L6-v2` tạo ra vector 384 chiều và lưu trữ vào Vector Store Index.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Evaluation set chứa 96 câu hỏi factual kèm theo danh sách `ground_truth_doc_ids` (mã DOI của bài báo chứa đáp án). Khi agent thực hiện truy vấn, hệ thống đo `retrieval_hit_rate` bằng cách kiểm tra xem `ground_truth_doc_ids` có nằm trong top-k kết quả trả về của Vector Store hay không.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - *Quality checks*: Kiểm tra tính toàn vẹn của cấu trúc dữ liệu (độ dài, không `null`, tính duy nhất `is_unique`, số lượng dòng tối thiểu).
   - *Freshness monitoring*: Đo lường mức độ hợp thời/mới của dữ liệu dựa trên khoảng cách thời gian `age_days` so với ngưỡng quy định (180 ngày), phát hiện dữ liệu bị lỗi thời (stale data).

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Việc cố định bộ câu hỏi kiểm thử (frozen test set) xuyên suốt 3 trạng thái giúp loại bỏ nhiễu từ câu hỏi, đảm bảo mọi biến động của các chỉ số (`retrieval_hit_rate`, `mean_token_f1`, `mean_judge_score`) hoàn toàn xuất phát từ chất lượng của dữ liệu đầu vào.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Repair thành công khi:
   - File sạch được tái tạo từ snapshot thô (`data/clean/papers_repaired.json`) khôi phục đủ 24 bản ghi.
   - Báo cáo Data Quality báo `PASSED` và Freshness báo `FRESH`.
   - Chỉ số RAG metrics (`retrieval_hit_rate`, `mean_token_f1`, `mean_judge_score`) phục hồi từ mức suy giảm (`0.8333` / `0.6111` / `3.44`) trở lại mức tương đương Baseline (`1.0000` / `1.0000` / `5.0`).

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | **1.0000** | **0.8333** | **1.0000** | Giảm mạnh khi bị drop bản ghi; phục hồi hoàn toàn sau khi repair. |
| `mean_token_f1` | **1.0000** | **0.6111** | **1.0000** | Giảm đáng kể do nhiễu văn bản và abstract rỗng; phục hồi 100% post-repair. |
| `judge_accuracy` | **1.0000** | **0.6111** | **1.0000** | Đánh giá chính xác từ LLM Judge giảm tương ứng với Token F1. |
| `mean_judge_score` | **5.0000** | **3.4444** | **5.0000** | Điểm chất lượng trung bình giảm từ 5.0 xuống 3.44 do dữ liệu hỏng. |
| Quality checks | `PASSED` | `FAILED` | `PASSED` | Bộ Data Quality phát hiện chính xác các lỗi độ dài summary và lặp dữ liệu. |
| Freshness status | `FRESH` | `STALE` | `FRESH` | Giám sát nhận biết ngay lập tức khi ngày xuất bản bị cố tình làm cũ. |

### Kết luận từ số liệu

1. **Chuỗi nguyên nhân – bằng chứng 1 (Data Corruption)**:
   [Gây hỏng dữ liệu: Drop bản ghi, làm rỗng summary, tiêm text nhiễu] $\rightarrow$ [Bộ Data Quality báo `FAILED`, Freshness báo `STALE`] $\rightarrow$ [`retrieval_hit_rate` giảm xuống `0.8333`, `mean_token_f1` giảm xuống `0.6111`].

2. **Chuỗi nguyên nhân – bằng chứng 2 (Data Repair)**:
   [Hành động phục hồi: ETL lại từ `crossref_records.json`] $\rightarrow$ [Báo cáo Quality & Freshness khôi phục `PASSED`/`FRESH`] $\rightarrow$ [`retrieval_hit_rate` và `mean_token_f1` phục hồi về `1.0000`].

- **Corruption ảnh hưởng rõ nhất và vì sao**:
  Lỗi **Drop bản ghi mới nhất (Dropped Records)** và **Làm rỗng Summary (Blank Summary)** ảnh hưởng nặng nề nhất. Khi bản ghi bị drop, vector đại diện hoàn toàn biến mất khỏi Vector Store, khiến Retrieval Hit Rate sụt giảm nghiêm trọng do không thể tìm thấy tài liệu chứa đáp án chuẩn (`ground_truth_doc_ids`).

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Nguyên tắc Immutability của Raw Data**: Luôn luôn lưu trữ dữ liệu thô nguyên bản từ nguồn bên ngoài trước khi thực hiện bất kỳ bước biến đổi hay làm sạch nào.
2. **Data Observability là chốt chặn quan trọng**: Giám sát Data Quality và Freshness giúp phát hiện lỗi dữ liệu tự động ngay tại tầng ETL, trước khi dữ liệu độc hại làm sai lệch kết quả của các mô hình AI/RAG phía sau.
3. **Chất lượng dữ liệu quyết định chất lượng RAG**: RAG Agent phụ thuộc hoàn toàn vào ngữ cảnh được truy vấn. Dữ liệu đầu vào bị rác hoặc mất mát sẽ trực tiếp làm sụt giảm điểm đánh giá của LLM Judge.

### Nếu có thêm thời gian

Tôi sẽ triển khai thêm cơ chế **Data Profiling & Anomaly Detection** tự động (sử dụng Great Expectations hoặc Evidently AI) để phát hiện sự trôi dạt phân phối dữ liệu (Data Drift) và gửi cảnh báo tự động qua Slack/Email khi tỷ lệ dữ liệu lỗi thời vượt ngưỡng cảnh báo.

---

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Thế Hải Đăng  
**Ngày xác nhận:** 2026-08-06
