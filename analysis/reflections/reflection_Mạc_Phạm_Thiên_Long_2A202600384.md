# Individual Report
**Họ và tên:** Mạc Phạm Thiên Long - 2A202600384
**Vai trò:** Phát triển RAG Agent và hệ thống runner async

## 1. Đóng góp kỹ thuật:

Trong Lab này, em chịu trách nhiệm chính về hạ tầng core của hệ thống bao gồm agent thực thi và bộ chạy benchmark tự động. Các đóng góp cụ thể của tôi tập trung vào tính hiệu quả và khả năng mở rộng của hệ thống:

### Phát triển Hybrid RAG Agent (v1 & v2)
Thiết kế lớp `MainAgent` với cấu trúc linh hoạt để hỗ trợ hai phiên bản thử nghiệm:
*   **Version 1 (Baseline):** Sử dụng thuật toán BM25 truyền thống để truy xuất từ khóa, phù hợp với các truy vấn luật pháp có tính định danh cao.
*   **Version 2 (Hybrid):** Đây là module phức tạp nhất, kết hợp giữa Dense retrieval (Sentence transformers - mô hình `all-MiniLM-L6-v2`) và Sparse tetrieval (BM25) thông qua cơ chế Reciprocal Rank Fusion (RRF). Việc triển khai RRF giúp hệ thống tận dụng được thế mạnh của cả hai phương pháp: tính chính xác của từ khóa và tính ngữ nghĩa của không gian vector.

### Xây dựng Async Benchmark Runner
Để xử lý hàng trăm bản ghi kiểm định một cách nhanh chóng mà không vượt quá limit của OpenAI API, em đã xây dựng `BenchmarkRunner` dựa trên thư viện `asyncio`:
*   Sử dụng **Asyncio semaphore** để kiểm soát số lượng request song song (concurrency control). Điều này cực kỳ quan trọng để duy trì tính ổn định của hệ thống và tránh lỗi rate limit.
*   Tích hợp trực tiếp các chỉ số đo lường từ Retrieval evaluator và LLM judge vào quy trình chạy, tạo ra data pipeline khép kín từ khâu truy vấn đến khâu chấm điểm.

## 2. Technical depth

Trong quá trình phát triển, em đã tập trung nghiên cứu và áp dụng các khái niệm nền tảng để tối ưu hóa hệ thống:

### Chỉ số MRR (Mean Reciprocal Rank)
Thay vì chỉ quan tâm đến việc có tìm thấy tài liệu hay không, em sử dụng MRR để đánh giá thứ hạng của tài liệu đúng đầu tiên. Nếu hệ thống trả về tài liệu đúng ở vị trí số 1, giá trị là 1; nếu ở vị trí số 2, giá trị giảm xuống 0.5. Việc tối ưu MRR là chìa khóa để cải thiện chất lượng câu trả lời của LLM, vì tài liệu ở vị trí cao nhất thường có ảnh hưởng lớn nhất đến output.

### Cohen's Kappa và Agreement Rate
Để đảm bảo tính khách quan của bộ chấm điểm Multi-judge (kết hợp GPT và Claude), tôi đã nghiên cứu về chỉ số Cohen's Kappa. Đây là phương pháp đo lường sự đồng thuận giữa các AI judges sau khi đã loại trừ yếu tố trùng hợp ngẫu nhiên. Trong hệ thống của chúng tôi, việc theo dõi Agreement rate giúp nhận diện được các ca khó (Hard cases) mà ngay cả các mô hình ngôn ngữ lớn cũng không thống nhất được câu trả lời.
### Position Bias và Trade-off
Em nhận thức rõ về hiện tượng Position bias (mô hình thường chú ý nhiều hơn đến đoạn văn đầu và cuối của ngữ cảnh). Do đó, trong phần Prompting của v2, em đã thiết kế cấu trúc chặt chẽ để buộc mô hình phải quét toàn bộ văn bản nguồn. 
Về mặt kinh tế, em đã thiết lập báo cáo chi tiết hóa theo từng request để cân đối giữa:
*   **Chi phí:** Proxy model rẻ hơn nhưng có thể giảm khả năng suy luận pháp lý.
*   **Chất lượng:** Sử dụng Hybrid search tăng latency nhưng cải thiện đáng kể độ trung thực (Faithfulness).

## 3. Giải quyết vấn đề

Thách thức lớn nhất em gặp phải là việc quản lý tài nguyên embeddings khi quy mô corpus tăng lên. Ban đầu, việc tính toán lại vector mỗi lần khởi tạo Agent gây tốn thời gian đáng kể (latency startup).

**Giải pháp:** Em đã xây dựng một script tách biệt (`build_embeddings.py`) để pre-build không gian vector và lưu trữ dưới dạng định dạng `.npy`. Hệ thống sẽ ưu tiên tải dữ liệu đã được tính toán từ trước. Nếu không tìm thấy, agent mới kích hoạt fallback tự tính toán. Cách tiếp cận này giúp giảm thời gian khởi động hệ thống từ hàng chục giây xuống còn dưới 1 giây.

Đồng thời, khi xử lý các dữ liệu pháp lý phức tạp, em nhận thấy LLM đôi khi đưa ra các câu trả lời dựa trên kiến thức bên ngoài (hallucination). Em đã khắc phục bằng cách thiết kế hệ thống Strict evidentiary boundary trong prompt v2, yêu cầu mô hình chỉ phản hồi dựa trên tài liệu được cung cấp và sử dụng prompt chuẩn.
