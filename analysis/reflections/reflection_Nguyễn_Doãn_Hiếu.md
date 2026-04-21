# Reflection cá nhân - Giai đoạn 4: Tối ưu Agent dựa trên kết quả và hoàn thiện báo cáo


## 1. Vai trò của tôi trong Giai đoạn 4

Trong Giai đoạn 4, tôi tập trung vào phần "đọc kết quả benchmark để ra quyết định tối ưu" thay vì chỉ nhìn vào một chỉ số tổng quát. Cụ thể, tôi phụ trách:

- Đối chiếu `reports/summary.json` với `reports/benchmark_results.json` để kiểm tra V2 đang tốt hơn hay tệ hơn V1.
- Phân tích các nhóm lỗi chính theo `hit_rate`, `faithfulness`, `answer_relevance`, `question_type`, `difficulty` và `requires_supplemental`.
- Viết lại báo cáo `analysis/failure_analysis.md` theo hướng có số liệu, có 5 Whys và có action plan ưu tiên rõ ràng.
- Hoàn thiện phần giải trình cho submission: nêu được vì sao regression gate đưa ra quyết định `ROLLBACK` thay vì cố gắng mô tả V2 như một bản nâng cấp thành công.

Sau khi nhóm chạy lại benchmark sau tối ưu, tôi tiếp tục cập nhật báo cáo dựa trên bộ số liệu mới và đặt trọng tâm vào việc so sánh với kết quả đầu tiên. Đây là phần quan trọng vì nó cho thấy agent không chỉ "có vẻ tốt hơn", mà thật sự tốt hơn khi đo bằng số liệu.

Tôi xem phần việc của mình là cầu nối giữa kỹ thuật và báo cáo: biến dữ liệu benchmark thành kết luận có thể bảo vệ được trước rubric chấm điểm.

## 2. Tôi đã hoàn thiện những gì

### 2.1. Hoàn thiện phần đọc và diễn giải metrics

Tôi tổng hợp lại các chỉ số chính của hệ thống ở lần chạy hiện tại:

- `total = 50`
- `pass_count = 20`, `fail_count = 30`
- `avg_score = 0.4145`
- `hit_rate = 0.6908`
- `agreement_rate = 1.0072` theo summary hiện tại
- `avg_faithfulness = 0.3499`
- `avg_answer_relevance = 0.5191`

So với kết quả đầu tiên của nhóm:

- `pass_count` tăng từ `18` lên `20`
- `avg_score` tăng từ `0.3756` lên `0.4145`
- `avg_faithfulness` tăng từ `0.3086` lên `0.3499`
- `avg_answer_relevance` tăng từ `0.4761` lên `0.5191`
- `hit_rate` tăng từ `0.6600` lên `0.6908`
- `avg_map` tăng từ `0.4300` lên `0.4795`
- `avg_mrr` tăng từ `0.5833` lên `0.6642`

Điểm quan trọng tôi rút ra là:

- Retrieval không phải lỗi duy nhất, vì có tới `17` case retrieval trúng nhưng vẫn fail.
- Vấn đề nặng nhất nằm ở phần generation/synthesis, đặc biệt ở nhóm `case_reading`.
- Hai judge đồng thuận cao, nên số liệu judge đủ tin cậy để làm căn cứ tối ưu.
- Sau lần tối ưu mới, hướng cải thiện là đúng vì cả retrieval lẫn answer quality đều tăng, và số case pass cũng tăng thực tế.

### 2.2. Hoàn thiện phần regression analysis

Tôi dùng dữ liệu trong `summary.json` để kết luận:

- `v1_avg_score = 0.5127`
- `metrics.avg_score` hiện tại của V2 là `0.4145`
- block `regression.v2_avg_score` vẫn đang ghi `0.3756`
- Quyết định gần nhất được lưu trong summary vẫn là `ROLLBACK`

Ngoài ra, tôi chỉ ra chính xác các check bị fail:

- `faithfulness_ok = false`
- `relevance_ok = false`
- `cost_ok = false`
- `map_ok = true`

Từ đó, tôi kết luận rằng V2 không phải thất bại ở retrieval thuần túy, mà thất bại ở trade-off tổng thể giữa chất lượng câu trả lời, độ liên quan và chi phí. Đồng thời, lần chạy hiện tại cho thấy hướng tối ưu đang tạo ra cải thiện thật so với kết quả đầu tiên, chứ không chỉ là cảm giác chủ quan. Đây là một kết luận quan trọng vì nếu chỉ nhìn `hit_rate` hoặc `MAP`, nhóm có thể rút ra nhận định sai.

### 2.3. Hoàn thiện failure analysis theo cụm lỗi

Tôi chia lỗi thành 4 nhóm có thể hành động được:

- `Retrieval miss`
- `Partial / wrong synthesis`
- `Abstain despite hit`
- `Borderline quality`

Khi so với lần benchmark đầu tiên, tôi nhận thấy cấu trúc kết quả đã có dịch chuyển tích cực:

- Một phần các case fail đã được kéo lên gần ngưỡng pass hơn
- Số case pass cuối cùng tăng từ `18` lên `20`

Điều này có nghĩa là tối ưu agent đã tác động được vào outcome cuối, nên bước tối ưu tiếp theo có cơ sở rất rõ ràng.

Cách chia này giúp báo cáo không dừng ở mô tả "agent trả lời sai", mà chỉ rõ agent sai ở đâu trong pipeline:

- Sai do không lấy được context
- Sai do lấy được nhưng tổng hợp sai
- Sai do quá bảo thủ nên từ chối trả lời
- Sai do chỉ thiếu một bước tối ưu nhỏ

### 2.4. Hoàn thiện action plan cho vòng tối ưu tiếp theo

Từ các failure patterns, tôi đề xuất các hướng sửa có thứ tự ưu tiên:

1. Viết prompt riêng cho `case_reading` và `yes_no_application`.
2. Thêm bước evidence selection hoặc reranking sau retrieval.
3. Thêm self-check để ép model xác nhận `final holding` hoặc nhãn phân loại trước khi giải thích.
4. Giảm chi phí eval bằng cách chỉ dùng tiebreaker ở các case thực sự cần thiết.

Điểm tôi chú ý là mọi đề xuất đều bám trực tiếp vào lỗi xuất hiện trong benchmark, không phải đề xuất chung chung.

## 3. Kết quả phần việc của tôi

Kết quả rõ nhất là bộ báo cáo cuối cùng thuyết phục hơn và bám rubric hơn:

- Báo cáo nhóm không còn ở dạng khung mẫu, mà đã có số liệu thật, cụm lỗi thật và phân tích nguyên nhân gốc rễ.
- Phần giải trình cá nhân thể hiện được tư duy kỹ thuật ở Giai đoạn 4: không "làm đẹp" kết quả mà dùng regression gate để đưa ra quyết định đúng.
- Submission có cơ sở giải thích vì sao V2 phải rollback và nhóm nên tối ưu tiếp ở đâu.
- Sau khi nhóm chạy lại benchmark, tôi đã cập nhật báo cáo để phản ánh đúng việc agent đã cải thiện so với kết quả đầu tiên, thay vì chỉ mô tả một lần chạy độc lập.

Về mặt kỹ thuật, dù V2 chưa đạt yêu cầu release hoàn toàn theo summary hiện có, tôi cho rằng phần việc của mình giúp nhóm có hai thứ quan trọng: một mốc ban đầu để đối chiếu và một bản cập nhật trung thực cho thấy hệ thống đã tiến bộ sau tối ưu. Trong các bài lab đánh giá hệ thống AI, điều này quan trọng vì nếu không so với baseline ban đầu thì rất khó chứng minh hiệu quả cải tiến.

## 4. Khó khăn tôi gặp và cách tôi xử lý

Khó khăn lớn nhất là kết quả benchmark không hoàn toàn "đẹp": agent có cải thiện sau tối ưu, nhưng dữ liệu trong `summary.json` lại đang ở trạng thái chuyển tiếp, tức phần `metrics` đã tăng còn block `regression` vẫn giữ số cũ của lần đầu. Nếu không đọc kỹ, báo cáo rất dễ thiếu nhất quán.

Cách tôi xử lý là:

- Bám vào dữ liệu thật trong `summary.json`
- Dùng `benchmark_results.json` để kiểm tra từng pattern fail thay vì kết luận cảm tính
- Tách riêng lỗi retrieval và lỗi generation để tránh đổ hết trách nhiệm cho retriever
- Dùng regression gate như một công cụ ra quyết định kỹ thuật, không chỉ như phần trang trí trong báo cáo
- Ghi rõ đâu là kết quả mới trong `metrics`, đâu là thông tin cũ còn nằm trong block `regression`
- Luôn trình bày kết quả hiện tại bên cạnh baseline đầu tiên để người chấm nhìn thấy hiệu quả tối ưu

Nhờ vậy, báo cáo cuối cùng trung thực hơn và cũng chuyên nghiệp hơn.

## 5. Điều tôi học được

Qua phần việc này, tôi hiểu rõ hơn một số điểm kỹ thuật quan trọng:

- `Hit Rate` và `MAP` chỉ cho biết retriever tìm tài liệu tốt đến đâu, không đảm bảo câu trả lời cuối cùng đúng.
- `Faithfulness` là chỉ số rất quan trọng để phát hiện tình huống "retrieval đúng nhưng generator kết luận sai".
- `Agreement rate` cao giúp tăng độ tin cậy khi dùng multi-judge làm tín hiệu tối ưu.
- Regression gate có giá trị thực tế vì nó buộc nhóm nhìn bài toán theo trade-off chất lượng, chi phí và độ ổn định, thay vì chỉ cố tăng một chỉ số đơn lẻ.
- Khi agent được tối ưu và benchmark chạy lại, việc cập nhật lại báo cáo theo số liệu mới và so với baseline đầu tiên cũng là một phần của engineering rigor, không phải việc phụ.

Đây là phần tôi thấy mình tiến bộ nhất trong lab này: biết cách đọc benchmark như một AI engineer, không chỉ như người chạy script.

## 6. Nếu có thêm thời gian

Nếu có thêm thời gian, tôi sẽ tiếp tục hỗ trợ nhóm ở 3 hướng:

- Thử prompt template riêng cho `case_reading`
- Bổ sung reranking hoặc evidence selector cho các case có supplemental passage
- Chạy lại benchmark sau tối ưu để xem có thể chuyển quyết định từ `ROLLBACK` sang `RELEASE` hay không

## 7. Tự đánh giá đóng góp

Tôi đánh giá phần đóng góp của mình ở Giai đoạn 4 nằm ở 3 điểm:

- Đọc và diễn giải đúng benchmark
- Chuyển metrics thành quyết định tối ưu có cơ sở
- Hoàn thiện báo cáo nhóm và báo cáo cá nhân theo hướng có chiều sâu kỹ thuật
- Cập nhật lại báo cáo khi benchmark mới chứng minh agent đã cải thiện rõ hơn so với baseline đầu tiên

Tôi chưa trực tiếp làm phần core module như retrieval hay multi-judge, nhưng tôi đã hoàn thiện phần tối ưu sau benchmark và phần giải trình kỹ thuật, là đúng với phạm vi của Giai đoạn 4 trong đề bài.
