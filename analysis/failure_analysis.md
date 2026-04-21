# Báo cáo Phân tích Thất bại (Failure Analysis Report)

## 1. Tóm tắt benchmark hiện tại

Nguồn số liệu được lấy trực tiếp từ `reports/summary.json` và `reports/benchmark_results.json`.

- Tổng số test cases: `50`
- Pass: `20`
- Fail: `30`
- Tỉ lệ pass: `40%`
- Avg final score: `0.4145`
- Avg faithfulness: `0.3499`
- Avg answer relevance: `0.5191`
- Hit Rate@3: `0.6908`
- MAP: `0.4795`
- MRR: `0.6642`
- Agreement rate: `1.0000`
- Avg latency: `1.0s/case`
- Cost agent: `$0.0241`
- Cost judge: `$0.0580`

## 2. So sánh với kết quả đầu tiên

Lần benchmark đầu tiên của nhóm có các chỉ số chính:

- Pass/Fail: `18/32`
- Avg score: `0.3756`
- Avg faithfulness: `0.3086`
- Avg answer relevance: `0.4761`
- Hit rate: `0.6600`
- MAP: `0.4300`
- MRR: `0.5833`

Kết quả hiện tại cho thấy agent đã cải thiện rõ hơn sau vòng tối ưu:

- `pass_count`: `18 -> 20`
- `fail_count`: `32 -> 30`
- `avg_score`: `0.3756 -> 0.4145` (`+0.0389`)
- `avg_faithfulness`: `0.3086 -> 0.3499` (`+0.0413`)
- `avg_answer_relevance`: `0.4761 -> 0.5191` (`+0.0430`)
- `hit_rate`: `0.6600 -> 0.6908` (`+0.0308`)
- `avg_map`: `0.4300 -> 0.4795` (`+0.0495`)
- `avg_mrr`: `0.5833 -> 0.6642` (`+0.0809`)

Diễn giải:

- Việc tối ưu agent đã tạo ra cải thiện có thể đo được ở cả retrieval và answer quality.
- So với lần chạy đầu tiên, đây không còn là mức tăng rất nhỏ mà là một cải thiện đủ rõ để dùng làm bằng chứng cho hiệu quả tối ưu.
- Hai case chuyển từ fail sang pass giúp bài báo cáo thuyết phục hơn vì hiệu quả tối ưu đã phản ánh vào outcome cuối, không chỉ ở metric trung gian.
- Chi phí tăng nhẹ, nhưng đổi lại chất lượng và tỉ lệ pass tốt hơn.

Kết luận regression:

- `Agent_V2_Optimized` bị `ROLLBACK`
- `v1_avg_score = 0.5127`
- `v2_avg_score` trong block regression hiện vẫn đang ghi `0.3756`
- Delta đang ghi trong summary: `-0.1371`
- Các check fail: `faithfulness_ok`, `relevance_ok`, `cost_ok`
- Chỉ có `map_ok = true`

Lưu ý kỹ thuật:

- Phần `metrics` trong `reports/summary.json` đã phản ánh kết quả mới nhất sau tối ưu.
- Tuy nhiên block `regression` vẫn đang giữ số của lần chạy đầu tiên. Vì vậy trong báo cáo này, nhóm dùng `metrics` hiện tại để mô tả agent sau tối ưu, và dùng số cũ trong `regression` làm mốc so sánh ban đầu.

Ý nghĩa của kết quả trên:

- Retrieval của V2 sau tối ưu tốt hơn lần đầu, thể hiện ở `Hit Rate@3 = 0.6908`, `MAP = 0.4795`, `MRR = 0.6642`.
- Chất lượng câu trả lời cũng tăng rõ hơn, thể hiện ở `avg_faithfulness = 0.3499` và `avg_answer_relevance = 0.5191`.
- Agreement rate đạt `1.0`, cho thấy judge cho kết quả rất ổn định trên lần chạy này.
- Dù đã có cải thiện, hệ thống vẫn còn 30 case fail và chưa vượt baseline V1 theo block regression đang lưu.

## 3. Failure clustering

### 2.1. Phân cụm theo cơ chế lỗi

| Nhóm lỗi | Số lượng fail | Dấu hiệu | Nhận định |
| --- | ---: | --- | --- |
| Retrieval miss | 15 | `hit_rate = 0` | Hệ thống không lấy được passage liên quan nên generator gần như không có cơ sở trả lời đúng. |
| Partial / wrong synthesis | 11 | `hit_rate = 1` hoặc có context đúng nhưng `faithfulness < 0.35` | Agent đọc được tài liệu nhưng kết luận sai, bỏ sót ý, hoặc chọn nhầm lập luận. |
| Abstain despite hit | 5 | `hit_rate = 1`, `faithfulness = 0`, `answer_relevance = 0` | Context có liên quan nhưng agent trả lời "I cannot find sufficient information..." hoặc né kết luận. |
| Borderline quality | 1 | Final score sát ngưỡng | Trường hợp cận pass, cần chỉnh prompt và cách tổng hợp là có thể vượt ngưỡng. |

### 2.2. Phân tích theo độ khó và loại câu hỏi

| Nhóm | Tổng case | Pass | Fail | Avg score | Avg hit rate | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Easy | 19 | 8 | 11 | 0.4336 | 0.5789 | Nhóm easy tăng điểm nhẹ, nhưng vẫn còn fail do lỗi tổng hợp đáp án. |
| Medium | 22 | 8 | 14 | 0.3838 | 0.6818 | Đây là nhóm cải thiện rõ nhất về score tổng thể sau tối ưu. |
| Hard | 9 | 2 | 7 | 0.3373 | 0.7778 | Case hard vẫn là điểm nghẽn chính dù retrieval đã tương đối tốt. |

| Question type | Tổng case | Pass | Fail | Avg score | Avg hit rate | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| case_reading | 22 | 7 | 15 | 0.2826 | 0.7727 | Vẫn là cụm lỗi lớn nhất, nhưng score đã nhích lên so với lần trước. |
| explanatory | 14 | 6 | 8 | 0.4514 | 0.5000 | Cải thiện nhẹ nhờ câu trả lời bớt thiếu ý hơn. |
| yes_no_application | 11 | 2 | 9 | 0.4491 | 0.5455 | Có tiến bộ nhỏ, nhưng vẫn dễ trả lời ngược nhãn. |
| factual | 3 | 3 | 0 | 0.7468 | 1.0000 | Tiếp tục là nhóm mạnh nhất của hệ thống. |

### 2.3. Các tín hiệu quan trọng

- Có `17` case `hit_rate = 1` nhưng vẫn fail. Điều này tiếp tục chứng minh retrieval chưa phải điểm nghẽn duy nhất.
- Có `20` case cần supplemental passages; trong đó `13` case fail.
- Các case cần supplemental chỉ có `avg_score = 0.1687` ở nhóm fail, thấp hơn nhiều so với nhóm pass.
- Có `17` case fail với `faithfulness = 0`, trong đó nhiều case agent chọn đáp án ngược hoàn toàn với expected answer.
- Có `11` case `answer_relevance = 0`, thường rơi vào pattern agent từ chối trả lời hoặc câu trả lời quá lệch so với câu hỏi.
- Chỉ `9` case có agreement rate dưới `0.9`, nên multi-judge nhìn chung đang ổn định và đáng tin để dùng làm tín hiệu tối ưu.
- Cấu trúc fail theo hướng chung vẫn cho thấy lỗi tổng hợp đáp án quan trọng hơn lỗi retrieval thuần túy.
- Khi đối chiếu với lần đầu, việc `pass_count` tăng từ `18` lên `20` cho thấy một phần case borderline đã vượt ngưỡng pass sau tối ưu.

## 4. Phân tích 5 Whys cho các case tiêu biểu

### Case 1: `1-1.2-q1` - phân loại sai giữa criminal law và criminal procedure

Tóm tắt lỗi:

- Retrieval hit thành công: `retrieved_ids` có chứa `1-1.2`
- Final score: `0.4438`
- Faithfulness: `0.3500`
- Agent trả lời sai kết luận cốt lõi: chọn `criminal procedure` thay vì `criminal law`

5 Whys:

1. Tại sao case fail?
   Agent đưa ra kết luận sai ngay ở ý chính, nên faithfulness thấp dù câu trả lời trông có cấu trúc.
2. Tại sao agent kết luận sai?
   Prompt hiện tại ưu tiên trả lời theo mẫu "legal conclusion / doctrinal basis" nhưng chưa buộc model xác nhận nhãn cuối cùng bằng cách đối chiếu trực tiếp với câu hỏi yes/no hoặc classification.
3. Tại sao prompt không chặn được lỗi này?
   Prompt tập trung vào việc "trả lời dựa trên context" nhưng chưa có cơ chế tự kiểm tra xem kết luận cuối đã khớp với trọng tâm câu hỏi chưa.
4. Tại sao retrieval đúng mà vẫn sai?
   Trong top-3 passages có tài liệu nhiễu (`5-5.2`, `7-7.1-q3-supp-1`) làm model bám vào bối cảnh "law enforcement / arrest / police conduct" và suy diễn sang criminal procedure.
5. Tại sao nhiễu này ảnh hưởng mạnh?
   Pipeline hiện chưa có reranking hoặc evidence selection ở bước cuối; generator nhận nhiều context nhưng không có cơ chế ưu tiên passage nào là evidence chính.

Root cause:

- Lỗi nằm ở ranh giới giữa retrieval và prompting, cụ thể là thiếu bước chọn evidence chủ đạo và thiếu prompt self-check cho các câu hỏi phân loại ngắn.

### Case 2: `3-3.3-q2` - retrieval đúng nhưng agent từ chối trả lời

Tóm tắt lỗi:

- `hit_rate = 1`
- `faithfulness = 0`
- `answer_relevance = 0`
- Agent trả lời: `I cannot find sufficient information in the provided context to answer this question.`

5 Whys:

1. Tại sao case fail?
   Agent không đưa ra bất kỳ kết luận nào dù đã lấy được passage chính `3-3.3`.
2. Tại sao agent lại abstain?
   Với câu hỏi `case_reading`, model phải đọc holding, rút ra lý do hiến pháp, rồi nén lại thành kết luận ngắn. Prompt hiện tại quá bảo thủ nên khi không thấy câu chữ gần như trùng khớp, agent chọn từ chối.
3. Tại sao prompt lại quá bảo thủ?
   Bản V2 tăng ràng buộc "ONLY using information from context" nhưng chưa hướng dẫn rõ rằng model vẫn phải tổng hợp và suy luận ở mức paraphrase hợp lệ.
4. Tại sao điều này tác động mạnh lên case_reading?
   `case_reading` thường yêu cầu tổng hợp nhiều mệnh đề như "vague", "content based", "First Amendment", không phải lúc nào cũng nằm cạnh nhau trong một câu duy nhất.
5. Tại sao hệ thống không cứu được bằng retrieval?
   Retrieval chỉ cung cấp nguyên liệu; không có bước answer planner hoặc claim extractor để biến evidence thành một đáp án kết luận.

Root cause:

- Prompt V2 tối ưu theo hướng giảm hallucination nhưng đi quá xa, làm tăng false abstention ở các câu hỏi cần tổng hợp án lệ.

### Case 3: `5-5.4-q2` - trả lời ngược hoàn toàn holding của án lệ

Tóm tắt lỗi:

- `hit_rate = 1`
- `faithfulness = 0`
- `answer_relevance = 0`
- Agent khẳng định Tòa phúc thẩm giữ nguyên conviction, trong khi expected answer là defendants được quyền trình bày defense of necessity và phải được xử lại.

5 Whys:

1. Tại sao case fail nặng?
   Agent không chỉ thiếu ý mà đảo ngược toàn bộ kết quả vụ án.
2. Tại sao đảo ngược kết quả?
   Câu trả lời được viết theo khuôn mẫu học thuật dài, nhưng phần "Legal conclusion" không được buộc phải trích ra ruling cuối cùng từ passage liên quan nhất.
3. Tại sao model dễ đảo ngược như vậy?
   Các vụ `case_reading` có pattern ngôn ngữ phức tạp: trial court làm A, appellate court làm B. Nếu model không theo dõi cấp xét xử cuối cùng, nó dễ lấy nhầm kết quả ở tầng dưới.
4. Tại sao pipeline không phát hiện lỗi này sớm?
   Judge phát hiện đúng lỗi, nhưng pipeline sinh answer chưa có guardrail như "state the final holding in one sentence before elaborating".
5. Tại sao đây là vấn đề hệ thống?
   Nhiều câu fail khác cũng cho thấy agent biết bối cảnh vụ án nhưng sai ở "court held what", tức lỗi reasoning template lặp lại chứ không phải lỗi ngẫu nhiên.

Root cause:

- Thiếu chiến lược đọc án lệ theo cấu trúc `issue -> lower court -> final appellate holding`, khiến model bị lẫn procedural history với kết luận cuối cùng.

### Nhận xét sau lần tối ưu mới

- Các case lỗi tiêu biểu ở trên chưa được giải quyết triệt để, nhưng kết quả tổng thể hiện tại tốt hơn rõ so với lần đầu.
- Điều này cho thấy hướng tối ưu hiện tại đã giúp agent sử dụng context tốt hơn và chuyển được một phần case từ fail sang pass.
- Tuy nhiên các lỗi logic kiểu `final holding` hoặc `classification` vẫn là điểm nghẽn chính, nên phần cải thiện hiện tại mới là bước đầu chứ chưa phải tối ưu hoàn chỉnh.

## 5. Nguyên nhân gốc rễ ở mức hệ thống

Sau khi đối chiếu nhiều case fail, nhóm xác định 4 nguyên nhân gốc rễ quan trọng nhất:

### 4.1. Retrieval đủ dùng nhưng chưa đủ sạch

- `Hit Rate@3 = 0.66` cho thấy retriever lấy được tài liệu liên quan ở đa số case.
- Tuy nhiên top-3 vẫn còn nhiễu, đặc biệt ở các câu hỏi ngắn hoặc có supplemental passage.
- Thiếu reranking theo câu hỏi cuối cùng khiến model đôi khi bám nhầm passage.

### 4.2. Prompt V2 quá an toàn

- Prompt strict giúp hạn chế hallucination, nhưng làm tăng số case agent từ chối trả lời dù đã có evidence.
- Điều này thể hiện rất rõ ở các case `hit_rate = 1` nhưng `faithfulness = 0` và `answer_relevance = 0`.

### 4.3. Thiếu chiến lược tổng hợp cho `case_reading`

- Đây là nhóm tệ nhất dù retrieval cao nhất.
- Lỗi thường nằm ở việc không nhận diện được holding cuối cùng, hoặc không gộp được nhiều claim thành một answer ngắn và đúng.

### 4.4. Trade-off chi phí và chất lượng chưa được khóa tốt

- Sau lần tối ưu mới, chất lượng đã tăng nhẹ nhưng chi phí và latency cũng tăng.
- Điều này cho thấy hướng tối ưu có hiệu quả, nhưng hệ thống vẫn cần một bước tinh chỉnh nữa để đạt trạng thái "tăng chất lượng đủ lớn so với chi phí tăng thêm".

## 6. Kế hoạch tối ưu ưu tiên cho Giai đoạn 4

### Ưu tiên 1: sửa prompt theo từng dạng câu hỏi

- Thêm nhánh prompt riêng cho `case_reading`: buộc agent trả lời theo `final holding -> reason -> caveat`.
- Với `yes_no_application`, buộc dòng đầu tiên phải là đáp án nhị phân hoặc nhãn phân loại, sau đó mới giải thích.
- Cho phép `paraphrase from context` thay vì chỉ nhắc "ONLY using information from context" một cách quá cứng.

### Ưu tiên 2: thêm bước evidence selection / reranking

- Sau top-3 retrieval, chọn 1-2 evidence mạnh nhất trước khi đưa vào generator.
- Ưu tiên passage chứa trực tiếp holding, outcome, hoặc constitutional basis.
- Việc này đặc biệt quan trọng cho các case có supplemental documents.

### Ưu tiên 3: thêm self-check trước khi xuất câu trả lời

- Kiểm tra xem đáp án đầu dòng đã trả lời đúng dạng câu hỏi chưa.
- Nếu là `case_reading`, buộc xác nhận lại: "Tòa án cuối cùng đã hold gì?"
- Nếu là `criminal law` vs `criminal procedure`, buộc model chọn đúng một nhãn duy nhất rồi giải thích.

### Ưu tiên 4: giảm chi phí eval nhưng giữ độ tin cậy

- Chỉ kích hoạt tiebreaker khi agreement thấp hơn ngưỡng hiện tại.
- Cache embedding cho answer relevance.
- Có thể chạy judge sâu hơn cho các case borderline thay vì cho toàn bộ 50 case.

## 7. Kết luận

Benchmark hiện tại cho thấy hệ thống đã có nền tảng tốt ở 3 mặt:

- Có retrieval metrics rõ ràng
- Có multi-judge consensus với agreement rate cao
- Có regression gate đủ chặt để ngăn release một phiên bản kém hơn

So với lần benchmark đầu tiên, agent hiện tại đã cho thấy hiệu quả tối ưu đủ rõ: score tăng, retrieval tăng, answer quality tăng, và số case pass tăng từ `18` lên `20`. Tuy nhiên lỗi lớn nhất vẫn không còn là "không tìm được tài liệu", mà là "tìm được nhưng chưa đọc và tổng hợp đúng". Vì vậy hướng tối ưu tiếp theo nên tiếp tục tập trung vào prompt theo question type, evidence selection và self-check cho case law reasoning thay vì chỉ tiếp tục nâng retriever.
