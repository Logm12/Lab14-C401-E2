# Báo cáo Cá nhân - Lab 14: AI Evaluation Factory

**Họ và tên:** Cao Chí Hải  
**Mã số SV:** 2A202600011  
**Vai trò:** Person 2a — Giai đoạn 2: Retrieval Eval + LLM Judge  

## 1. Các file đảm nhiệm và chỉnh sửa
Trong khuôn khổ Giai đoạn 2 của dự án, tôi chịu trách nhiệm chính thiết kế và lập trình các module đánh giá tự động (Evaluation Engine) của hệ thống. Cụ thể, các file tôi đã trực tiếp phát triển và commit bao gồm:
- `engine/retrieval_eval.py`
- `engine/llm_judge.py`

*Lịch sử Git commit:*
```bash
git add engine/retrieval_eval.py engine/llm_judge.py
git commit -m "feat(engine): MAP/MRR/HitRate evaluator + multi-judge (GPT + Claude) 2A20260011"
git push
```

## 2. Chi tiết công việc đã thực hiện

### 2.1. Phát triển module Đánh giá Retrieval (`engine/retrieval_eval.py`)
Để đáp ứng yêu cầu tính toán Hit Rate và MRR cho Vector DB (chiếm 15% tiêu chí chấm điểm), tôi đã xây dựng lớp `RetrievalEvaluator` bao gồm:
- **Hàm `calculate_hit_rate`**: Tính tỉ lệ Hit Rate (Top-K) để xác định xem trong tập các tài liệu được retrieve về có chứa tài liệu Ground Truth hay không. Đây là bước sống còn để phân tích lỗi Hallucination có phải do Retrieval hay không.
- **Hàm `calculate_mrr` (Mean Reciprocal Rank)**: Đánh giá thứ hạng của tài liệu Ground Truth đầu tiên xuất hiện trong danh sách retrieved.
- **Hàm `calculate_ap` (Average Precision)**: Mở rộng thêm chỉ số AP để tính toán chính xác hơn chất lượng của toàn bộ tập tài liệu được trả về.
- **Hàm `evaluate_batch`**: Chạy đánh giá cho toàn bộ batch dữ liệu đầu vào và trả về điểm trung bình (`avg_map`, `avg_mrr`, `avg_hit_rate`) giúp dễ dàng phân tích trên toàn bộ test set.

### 2.2. Xây dựng Multi-Judge Consensus Engine (`engine/llm_judge.py`)
Đây là phần cốt lõi của Evaluation Engine, nhằm đảm bảo tính khách quan cho điểm số theo tiêu chí *Multi-Judge Reliability (20%)* và *Tối ưu hiệu năng (15%)*:
- **Sử dụng đa mô hình (Multi-Judge)**: Tôi đã tích hợp cả mô hình của OpenAI (GPT-4o-mini) và Anthropic (Claude-Haiku) cùng đóng vai trò làm "Giám khảo".
- **Chỉ số Faithfulness (Tính trung thực)**: Các mô hình được thiết lập hệ thống Prompt chuyên sâu (đóng vai trò chuyên gia NLI - Natural Language Inference) để xác minh xem câu trả lời của AI Agent có bám sát (entail) các facts gốc hay không.
- **Cơ chế Consensus (Đồng thuận) & Giải quyết xung đột**: 
  - Tính toán `agreement_rate` giữa 2 giám khảo.
  - Nếu độ đồng thuận quá thấp (dưới 60%), hệ thống tự động gọi một **Tiebreak Arbitrator** (Trọng tài giải quyết xung đột) để review lại mâu thuẫn giữa 2 điểm số và đưa ra kết luận quyết định.
- **Chỉ số Answer Relevance (Độ liên quan)**: Triển khai chiến lược "Reverse Question Generation". LLM sẽ tự động đặt ra các câu hỏi dựa trên câu trả lời của Agent, sau đó hệ thống dùng `SentenceTransformer (all-MiniLM-L6-v2)` kết hợp `cosine_similarity` so sánh với câu hỏi của người dùng ban đầu.
- **Tối ưu hiệu năng & Quản lý chi phí**:
  - Viết code bằng `asyncio` để chạy song song (Parallel/Async execution) các lượt LLM call, giảm tối đa thời gian tính toán của pipeline.
  - Xây dựng cơ chế tracking Token Tracking & Cost Calculation (`total_cost()`) để thống kê chính xác lượng tiền (USD) đã tiêu thụ, giúp dễ dàng lên phương án tối ưu (giảm chi phí eval mà không giảm độ chính xác).

## 3. Tự đánh giá và Kết luận
- **Mức độ hoàn thành:** Hoàn thành xuất sắc và đầy đủ các tiêu chí khắt khe của hệ thống đánh giá theo chuẩn sản xuất. Code chạy ổn định, chính xác và hiệu suất cao.
- **Kinh nghiệm rút ra:** Hiểu sâu sắc rằng việc đánh giá AI Agent không thể chỉ phụ thuộc vào 1 LLM đơn lẻ vì dễ bị Bias. Việc áp dụng kĩ thuật NLI Prompting, Multi-Agent Consensus và Async Tracking là phương pháp tối ưu nhất để xây dựng một Evaluation Factory tự động, khách quan với chi phí hợp lý.
