# Báo cáo Cá nhân – Lab Day 14: AI Evaluation & Benchmarking

**Họ và tên:** Nguyễn Văn Đạt
**MSSV:** 2A202600411
**Ngày:** 2026-04-21

---

## 1. Tổng quan đóng góp

Trong lab này, tôi chịu trách nhiệm toàn bộ phần **xây dựng Data Pipeline** – từ corpus thô đến bộ golden dataset hoàn chỉnh phục vụ đánh giá hệ thống RAG. Cụ thể gồm hai nhánh công việc chính:

| Nhánh | Mô tả |
|---|---|
| **Vector Store Infrastructure** | Pre-compute embeddings + build ChromaDB để retrieval pipeline hoạt động |
| **Golden Dataset Construction** | Thiết kế thuật toán chọn mẫu + tự động phân rã câu trả lời thành điểm nguyên tử |

---

## 2. Các file đã thực hiện

### 2.1 `Data/build_embeddings.py` — Pre-compute dense embeddings

Script chạy **một lần** để encode toàn bộ corpus bằng model `all-MiniLM-L6-v2` (SentenceTransformers), lưu kết quả ra:

- `data/corpus_embeddings.npy` — ma trận embedding shape `(N, 384)`
- `data/corpus_ids.json` — danh sách ID tương ứng theo thứ tự hàng

Mục đích: tách biệt bước encode tốn kém (chạy một lần) khỏi bước truy vấn (chạy nhiều lần), tránh re-compute mỗi lần chạy evaluation.

### 2.2 `Data/build_chroma.py` — Build ChromaDB vector store

Từ cùng corpus.csv và cùng model embedding, script này nạp toàn bộ document vào **ChromaDB persistent collection** với:

- Metric: cosine similarity (`hnsw:space: cosine`)
- Batch upsert theo `BATCH_SIZE = 32`
- Tự động xóa collection cũ và build lại từ đầu để đảm bảo tính nhất quán

ChromaDB collection này được sử dụng bởi `MainAgent V2` để semantic search.

### 2.3 `data/select_golden.py` — Stratified sampling 50 golden questions

Đây là script phức tạp nhất tôi thực hiện. Thuật toán gồm các bước:

**a) Phân loại dữ liệu:**

- **Difficulty**: `easy` / `medium` / `hard` dựa trên cờ `requires_supplemental` và độ dài câu trả lời (> 400/500 ký tự)
- **Question type**: 4 loại — `case_reading`, `explanatory`, `yes_no_application`, `factual` — phân loại bằng keyword matching

**b) Tính quota theo chương:**

- Phân bổ tỉ lệ thuận với số câu hỏi trong mỗi chương (13 chương), tối thiểu 3 câu/chương
- Điều chỉnh tổng về đúng 50 bằng cách thêm/bớt từ chương lớn nhất

**c) Greedy selection với diversity score:**

- Mỗi candidate được chấm điểm: `+2` nếu section chưa được chọn, `+1` nếu question type chưa xuất hiện
- Trong mỗi chương, ưu tiên: hard (≤ 30%) → easy (≤ 30%) → medium (phần còn lại)
- Đảm bảo coverage đa dạng cả 13 chương

**d) Enrichment:**

- Gắn thêm `context_texts` từ corpus cho mỗi câu hỏi dựa trên `relevant_passage_ids`
- Output: `data/golden_set.jsonl` — 50 records đầy đủ metadata

### 2.4 `data/split_answer_points.py` — Phân rã câu trả lời thành atomic points

Script gọi **GPT-4.1-mini** để decompose mỗi `expected_answer` thành danh sách các điểm trả lời nguyên tử (atomic answer points), phục vụ đánh giá fine-grained.

Các tính năng kỹ thuật đáng chú ý:

- **Auto-detect format**: hỗ trợ cả JSONL lẫn JSON array làm input
- **Resume mode** (`RESUME=True`): bỏ qua các record đã xử lý, an toàn khi bị ngắt giữa chừng
- **Checkpoint sau mỗi record**: lưu file output ngay sau mỗi lần gọi API thành công, tránh mất dữ liệu khi crash
- **Exponential backoff**: retry tối đa 3 lần với thời gian chờ `2^attempt` giây

System prompt tôi thiết kế cho GPT-4.1-mini tuân theo 6 nguyên tắc: **ATOMIC**, **NON-REDUNDANT**, **FAITHFUL**, **QUESTION-RELEVANT**, **GRANULAR**, **NEUTRAL PHRASING** — đảm bảo chất lượng điểm đánh giá.

Kết quả: `data/golden_dataset.json` — 50/50 records có `answer_points` đầy đủ.

### 2.5 `data/synthetic_gen.py` — Xác minh dataset

Script kiểm tra sự tồn tại của `golden_dataset.json` và báo cáo thống kê (số records, số records có `answer_points`). Dùng để verify pipeline đã chạy đúng trước khi chạy evaluation.

---

## 3. Kiến thức kỹ thuật đúc rút

### Tại sao tách `build_embeddings.py` và `build_chroma.py`?

Hai script phục vụ hai use case khác nhau. `corpus_embeddings.npy` dùng cho numpy-based cosine similarity (retrieval nhanh, không cần external dependency), còn ChromaDB dùng cho MainAgent V2 với persistent storage và HNSW index. Việc tách ra cho phép chạy độc lập và chọn backend phù hợp.

### Trade-off trong stratified sampling

Nếu chỉ random sample, dễ bị skew về chương có nhiều câu (e.g., chương 1) và thiếu coverage. Greedy diversity scoring giải quyết vấn đề này nhưng có chi phí: thuật toán `O(N × quota)`, chấp nhận được với dataset ~500 câu.

### Tại sao dùng GPT-4.1-mini thay vì rule-based để split answer points?

Answer points cần hiểu ngữ nghĩa — ví dụ tách "The court held X because Y" thành hai điểm riêng. Rule-based (split by `.` hoặc `;`) không đủ chính xác. GPT-4.1-mini (`temperature=0`, `response_format: json_object`) cho kết quả nhất quán và có thể kiểm soát được.

---

## 4. Vấn đề gặp phải và cách giải quyết

| Vấn đề | Giải pháp |
|---|---|
| `csv.field_size_limit` lỗi với corpus text dài | Tăng limit lên `10_000_000` bytes |
| Gọi API bị ngắt giữa chừng (50 records × delay) | Implement resume mode + checkpoint sau từng record |
| Chapter quota tổng không bằng đúng 50 sau `round()` | Vòng lặp điều chỉnh tăng/giảm từ chương có surplus lớn nhất |
| `relevant_passages` trong CSV có format `['id1', 'id2']` dạng string | Parse bằng regex `re.findall(r"'([^']+)'", inner)` thay vì `json.loads` |

---

## 5. Kết quả cụ thể

- **50/50 golden questions** được chọn từ qa.csv, phủ đủ 13 chương
- **50/50 records** có `answer_points` trong `golden_dataset.json`
- Vector store ChromaDB sẵn sàng tại `data/chroma_db/`
- Embedding matrix `(N, 384)` được pre-compute và lưu tại `data/corpus_embeddings.npy`
