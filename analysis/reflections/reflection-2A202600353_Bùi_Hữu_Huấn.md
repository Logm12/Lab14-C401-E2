# Báo cáo cá nhân - Lab 14: AI Evaluation Factory

**Họ và tên:** Bùi Hữu Huấn  
**Mã số SV:** 2A202600353  
**Vai trò:** Giai đoạn 3 - Benchmark + Failure Analysis

## 1. Phần việc phụ trách

Trong dự án này, em phụ trách phần việc của **Giai đoạn 3**, tập trung vào:

- tổ chức chạy benchmark cho hệ thống hiện tại
- tổng hợp metric ra file báo cáo
- đọc kết quả benchmark ở mức từng case
- phân cụm lỗi và viết failure analysis

Các file em phụ trách chính là:

- `main.py`
- `reports/summary.json`
- `reports/benchmark_results.json`
- `analysis/failure_analysis.md`

Phần việc của em **không đi sang Giai đoạn 4**. Nghĩa là em không nhận phần tối ưu lại model, không triển khai một agent mới để cải thiện kết quả, và cũng không xem vai trò của mình là phát triển phiên bản model nâng cấp.

## 2. Công việc kỹ thuật đã thực hiện

### 2.1. Xây dựng luồng benchmark cho agent hiện tại

Trong `main.py`, em tổ chức luồng chạy benchmark cho agent hiện tại đang có trong repo. Luồng này gồm các bước:

1. nạp `data/golden_dataset.json`
2. khởi tạo `MainAgent`, `RetrievalEvaluator`, `LLMJudge`
3. chạy toàn bộ test cases qua `BenchmarkRunner`
4. tổng hợp metric toàn cục bằng `compute_summary(...)`
5. ghi kết quả ra `reports/summary.json` và `reports/benchmark_results.json`

Mục tiêu của em ở giai đoạn này là tạo ra một pipeline benchmark hoàn chỉnh để nhóm có thể đo chất lượng hệ thống bằng số liệu thật, thay vì chỉ đánh giá cảm tính.

### 2.2. Tổng hợp metric ở mức hệ thống

Em chịu trách nhiệm tổng hợp các chỉ số quan trọng từ kết quả từng case thành báo cáo tổng:

- `avg_score`
- `hit_rate`
- `avg_map`
- `avg_mrr`
- `avg_faithfulness`
- `avg_answer_relevance`
- `agreement_rate`
- `avg_latency_s`
- `total_cost_usd`
- `cost_per_eval_usd`

Theo em, điểm quan trọng nhất của `summary.json` là nó cho thấy bức tranh ở cấp hệ thống. Nhìn vào các metric này, nhóm có thể biết hệ thống đang yếu chủ yếu ở retrieval, ở answer synthesis, hay ở chi phí và độ trễ.

### 2.3. Lưu kết quả chi tiết cho từng test case

Ngoài báo cáo tổng hợp, em cũng phụ trách việc ghi `reports/benchmark_results.json` để giữ lại kết quả chi tiết của từng câu hỏi benchmark. File này bao gồm:

- câu hỏi
- expected answer
- agent answer
- relevant passage IDs
- retrieved IDs
- metric retrieval
- faithfulness
- answer relevance
- final score
- trạng thái pass/fail

Nhờ có file chi tiết này, em có thể đọc lại các case fail và xác định xem lỗi đến từ retrieve sai, answer sai, hay answer thiếu bằng chứng.

### 2.4. Viết failure analysis từ dữ liệu benchmark

Sau khi có `benchmark_results.json`, em tiếp tục viết `analysis/failure_analysis.md`. Phần này không chỉ tóm tắt con số, mà còn làm ba việc chính:

- gom lỗi thành các cụm có ý nghĩa
- chọn các case đại diện
- phân tích nguyên nhân gốc bằng 5 Whys

Kết quả là báo cáo failure analysis có thể trả lời được:

- hệ thống fail nhiều nhất ở loại câu hỏi nào
- retrieval đang hỏng ở đâu
- khi retrieve đúng thì answer còn sai kiểu gì
- nguyên nhân gốc nằm ở retrieval hay answer synthesis

## 3. Technical depth

## 3.1. Hiểu mối liên hệ giữa retrieval quality và answer quality

Qua phần benchmark, em hiểu rõ hơn rằng retrieval tốt chưa đủ để đảm bảo câu trả lời tốt. Trong kết quả hiện tại:

- `hit_rate = 0.66`
- nhưng `avg_faithfulness = 0.3086`

Điều này có nghĩa là hệ thống không hẳn thất bại hoàn toàn ở retrieve. Ngược lại, có khá nhiều trường hợp retrieve đã lấy được passage liên quan, nhưng agent vẫn không chuyển hóa được context đó thành câu trả lời đúng.

Theo em, đây là insight quan trọng nhất của Giai đoạn 3, vì nếu chỉ nhìn mỗi Hit Rate thì rất dễ kết luận sai rằng hệ thống đang ổn.

## 3.2. Hiểu vai trò của từng metric benchmark

Trong quá trình tổng hợp và đọc report, em phải hiểu rõ ý nghĩa của từng metric:

- `Hit Rate`: có retrieve được passage đúng trong top-k hay không
- `MRR`: passage đúng xuất hiện sớm đến mức nào
- `MAP`: chất lượng xếp hạng toàn danh sách retrieved
- `Faithfulness`: câu trả lời có bám answer points kỳ vọng hay không
- `Answer Relevance`: câu trả lời có thật sự trả lời đúng câu hỏi hay không
- `Agreement Rate`: mức đồng thuận giữa hai judge

Việc hiểu đồng thời các metric này giúp em không đánh giá benchmark theo một chiều. Ví dụ, có case `answer_relevance` khá ổn nhưng `faithfulness` rất thấp, tức là câu trả lời nghe có vẻ đúng hướng nhưng thực ra không bám đủ evidence.

## 3.3. Hiểu giá trị của failure analysis

Trước khi làm phần này, em nghĩ benchmark chủ yếu là để lấy số. Nhưng sau khi trực tiếp đọc `benchmark_results.json`, em nhận ra giá trị lớn nhất của benchmark là ở bước phân tích fail.

Em thấy failure analysis quan trọng ở chỗ:

- nó biến dữ liệu benchmark thành insight kỹ thuật
- nó giúp phân biệt lỗi retrieval với lỗi answer synthesis
- nó giúp nhóm biết nên nhìn vào đâu trong hệ thống, thay vì sửa cảm tính

## 4. Khó khăn và cách em xử lý

Khó khăn lớn nhất của em là `benchmark_results.json` rất dài, và nếu chỉ đọc tuần tự từng case thì rất khó nhìn ra pattern lỗi chung.

Cách em xử lý là:

- đọc lại summary để nắm mặt bằng chung
- lọc riêng các case fail
- đối chiếu `retrieval`, `faithfulness`, `answer_relevance`, `status`
- dùng thêm metadata như `question_type`, `difficulty`, `requires_supplemental`
- từ đó gom thành các cụm lỗi có thể diễn giải được

Nhờ cách làm này, em xác định được mấy điểm rất rõ:

- có nhiều fail đến từ retrieval miss
- nhưng cũng có nhiều fail xảy ra dù `hit_rate > 0`
- lỗi tập trung khá nhiều ở `case_reading`
- nhiều câu trả lời đúng chủ đề nhưng sai kết luận chính

Một khó khăn khác là viết báo cáo sao cho đúng phạm vi phần việc của mình. Ban đầu một số chỗ dễ bị viết lấn sang phần tối ưu agent, nhưng sau khi rà lại code và reports, em chỉnh lại để báo cáo chỉ phản ánh đúng Giai đoạn 3: benchmark và failure analysis của hệ thống hiện tại.

## 5. Tự đánh giá

Em tự đánh giá phần việc của mình hoàn thành tốt ở các điểm sau:

- tổ chức được luồng benchmark từ chạy test đến sinh report
- tổng hợp được metric hệ thống rõ ràng
- lưu được kết quả chi tiết từng case để phục vụ phân tích
- viết được failure analysis có phân cụm lỗi và 5 Whys

Theo em, phần việc em làm đã đáp ứng đúng mục tiêu của Giai đoạn 3 vì nó giúp nhóm:

- biết hệ thống đang ở mức nào
- biết fail ở đâu
- biết nguyên nhân gốc là gì

## 6. Kết luận

Qua phần việc này, em học được rằng benchmark không chỉ là bước chạy thử để lấy con số, mà là bước giúp nhìn hệ thống một cách có cấu trúc và có bằng chứng.

Giai đoạn 3 mà em phụ trách đã tạo ra:

- `summary.json` để nhìn chất lượng hệ thống ở mức tổng thể
- `benchmark_results.json` để soi lỗi ở mức từng case
- `failure_analysis.md` để truy ra nguyên nhân gốc

Đây là phần việc giúp nhóm hiểu rõ tình trạng hiện tại của hệ thống trước khi nghĩ đến bất kỳ bước phát triển tiếp theo nào.
