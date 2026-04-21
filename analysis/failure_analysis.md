# Báo cáo Failure Analysis

## 1. Phạm vi báo cáo

Báo cáo này chỉ phản ánh **Giai đoạn 3: Benchmark + Failure Analysis** của dự án. Nhóm chạy benchmark trên **agent hiện tại đang có trong repo**, sau đó tổng hợp metric và phân tích lỗi từ `reports/benchmark_results.json` và `reports/summary.json`.

Báo cáo **không** bao gồm nội dung của Giai đoạn 4 như tối ưu agent, release gate sau tối ưu, hay so sánh một bản cải tiến mới với bản cũ.

## 2. Tổng quan benchmark hiện tại

### Thông tin chung

| Hạng mục | Giá trị |
|---|---:|
| Benchmark name | `Stage3_Current_Agent_Benchmark` |
| Agent version benchmark | `v2` |
| Tổng số test cases | 50 |
| Pass | 18 |
| Fail | 32 |

### Metric tổng hợp

| Chỉ số | Giá trị |
|---|---:|
| Avg final score | 0.3756 |
| Hit Rate@3 | 0.6600 |
| MAP | 0.4300 |
| MRR | 0.5833 |
| Avg faithfulness | 0.3086 |
| Avg answer relevance | 0.4761 |
| Agreement rate giữa 2 judge | 0.9592 |
| Avg latency | 9.519 s |
| Agent cost / eval | 0.000396 USD |
| Tổng cost judge | 0.0487 USD |

### Nhận xét nhanh

- Hệ thống retrieve được ít nhất một passage đúng trong khá nhiều trường hợp (`hit_rate = 0.66`).
- Tuy nhiên chất lượng câu trả lời cuối cùng vẫn thấp (`avg_score = 0.3756`, chỉ pass 18/50).
- Điểm yếu lớn nhất nằm ở `faithfulness = 0.3086`, tức là câu trả lời thường không bám chặt vào các answer points được kỳ vọng.
- Agreement rate giữa hai judge cao (`0.9592`), nên có thể xem kết quả chấm khá ổn định.

Từ đó có thể kết luận: benchmark hiện tại đã đủ để chỉ ra lỗi hệ thống, nhưng chưa cho thấy chất lượng answer đủ tốt trên tập test 50 câu.

## 3. Failure clustering

Các cụm lỗi dưới đây được rút trực tiếp từ `reports/benchmark_results.json`. Một case có thể rơi vào nhiều cụm cùng lúc.

| Nhóm lỗi | Số case fail | Dấu hiệu nhận biết | Ý nghĩa |
|---|---:|---|---|
| Retrieval miss | 15 | `hit_rate = 0` | Không lấy được passage đúng trong top-3 |
| Supplemental / case-reading gap | 13 | `requires_supplemental = true` | Các câu cần thêm án lệ/phần bổ sung dễ fail hơn |
| Retrieved đúng nhưng faithfulness thấp | 17 | `hit_rate > 0` nhưng `faithfulness < 0.4` | Có evidence đúng nhưng agent không sử dụng tốt |
| On-topic but wrong | 19 | `answer_relevance >= 0.5` nhưng `faithfulness < 0.4` | Trả lời đúng chủ đề nhưng sai rule hoặc sai kết luận |
| Fallback “không đủ thông tin” | 10 | Agent trả về câu fallback | Có cả fail hợp lý do retrieval miss và fail do fallback quá sớm |

### Phân bố fail theo loại câu hỏi

| Loại câu hỏi | Số fail |
|---|---:|
| `case_reading` | 15 |
| `yes_no_application` | 9 |
| `explanatory` | 8 |

### Phân bố fail theo độ khó

| Độ khó | Số fail |
|---|---:|
| `easy` | 11 |
| `medium` | 14 |
| `hard` | 7 |

Điểm đáng chú ý là lỗi xuất hiện cả ở nhóm `easy`, cho thấy hệ thống không chỉ yếu ở câu khó mà còn có vấn đề trong khâu tổng hợp câu trả lời ngay cả với câu hỏi trực diện.

## 4. 5 Whys cho 3 case đại diện

### Case 1: `1-1.6-q2` - retrieval miss hoàn toàn

**Câu hỏi:** *Shaw v. Murphy* có công nhận quyền Tu chính án thứ nhất cho tù nhân tư vấn pháp lý cho tù nhân khác hay không?  
**Kết quả:** fail, `hit_rate = 0`, `final_score = 0.0`.

**Triệu chứng**

Agent trả lời theo mẫu fallback vì không có đủ context phù hợp trong top-3 passage retrieve được.

**5 Whys**

1. Tại sao agent không trả lời được?  
   Vì context đầu vào không chứa `1-1.6` hoặc `1-1.6-q2-supp-1`.
2. Tại sao không có passage đúng?  
   Vì retriever trả về các đoạn không liên quan như `3-3.6-q3-supp-1`, `3-3.3`, `3-3.5`.
3. Tại sao retriever xếp hạng sai?  
   Vì câu hỏi chứa tên án lệ, citation và yêu cầu đọc case, trong khi pipeline retrieval hiện tại chưa ưu tiên mạnh tín hiệu này.
4. Tại sao điều đó ảnh hưởng nhiều đến benchmark?  
   Vì nhóm `case_reading` thường cần cả passage chính và supplemental passage để trả lời trọn ý.
5. Tại sao case này rớt hoàn toàn?  
   Vì khi retrieval sai từ đầu, faithfulness và relevance đều gần như về 0.

**Root cause**

Root cause nằm ở **retrieval cho câu hỏi án lệ chưa đủ tốt**, đặc biệt với truy vấn có legal citation và supplemental passage.

### Case 2: `13-13.2-q2` - retrieve có đúng nhưng vẫn fallback

**Câu hỏi:** *Humanitarian Law Project v. Reno* có uphold 18 U.S.C. §2339 không, và có các challenge hiến pháp nào?  
**Kết quả:** fail, `hit_rate = 1.0`, `ap = 0.1667`, `final_score = 0.0`.

**Triệu chứng**

Agent vẫn trả về fallback dù danh sách retrieved đã có passage liên quan `13-13.2`.

**5 Whys**

1. Tại sao agent vẫn fallback?  
   Vì passage đúng có mặt nhưng đứng thấp trong top-3, còn các passage còn lại gây nhiễu.
2. Tại sao ranking đó chưa đủ tốt?  
   Vì RRF chỉ hợp nhất rank, chưa có bước rerank theo mức độ liên quan cuối cùng.
3. Tại sao passage đúng nhưng vẫn không cứu được câu trả lời?  
   Vì câu hỏi case-reading này cần ghép nhiều ý cùng lúc, nên một passage đúng nhưng đặt sau nhiễu vẫn chưa đủ.
4. Tại sao điểm lại bằng 0 hoàn toàn?  
   Vì agent không trích ra được answer point nào, nên judge chấm 0 cho cả faithfulness và relevance.
5. Tại sao đây là lỗi quan trọng?  
   Vì nó cho thấy benchmark hiện tại không chỉ có lỗi “retrieve sai”, mà còn có lỗi “retrieve chưa đủ sạch để dùng”.

**Root cause**

Root cause chính là **thứ hạng retrieval chưa sạch ở câu hỏi đa ý**, dẫn tới việc agent không khai thác được passage đúng dù nó đã xuất hiện trong top-k.

### Case 3: `1-1.2-q1` - retrieve đúng nhưng suy luận sai hướng

**Câu hỏi:** phân biệt `criminal law` hay `criminal procedure` trong tình huống cảnh sát bắn người đã bị khống chế.  
**Kết quả:** fail, `hit_rate = 1.0`, `faithfulness = 0.3333`, `answer_relevance = 0.5569`.

**Triệu chứng**

Agent trả lời đúng chủ đề nhưng kết luận sai: chọn `criminal procedure` thay vì `criminal law`.

**5 Whys**

1. Tại sao câu trả lời sai dù retrieve đúng?  
   Vì model bám quá mạnh vào từ khóa “arrest”, “law enforcement”, “criminal process”.
2. Tại sao model suy luận lệch?  
   Vì nó chọn nhầm trục lập luận thay vì xác định điểm mấu chốt là “có hành vi phạm tội sau khi arrest hay không”.
3. Tại sao judge vẫn cho relevance khá cao?  
   Vì câu trả lời vẫn nằm đúng miền kiến thức, chỉ sai ở kết luận trung tâm.
4. Tại sao đây là lỗi đáng chú ý?  
   Vì case này thuộc nhóm dễ nhưng vẫn fail, tức là lỗi không chỉ nằm ở retrieval.
5. Tại sao điều này quan trọng cho failure analysis?  
   Vì nó cho thấy benchmark cần nhìn cả answer quality chứ không thể chỉ dựa vào Hit Rate/MRR.

**Root cause**

Root cause nằm ở **answer synthesis**: agent nhận đúng tài liệu nhưng chọn sai rule hoặc sai hướng diễn giải.

## 5. Nhận định nguyên nhân gốc ở cấp hệ thống

Từ các cụm lỗi ở trên, có thể rút ra 4 nguyên nhân chính:

1. **Retrieval chưa tối ưu cho legal citations và supplemental passages**  
   Các câu `case_reading` là nơi lỗi tập trung nhiều nhất.

2. **Top-k = 3 còn khá hẹp với các câu cần nhiều bằng chứng**  
   Chỉ cần một passage nhiễu chen vào là chất lượng answer giảm rõ rệt.

3. **Agent chưa khai thác tốt context đã retrieve được**  
   Minh chứng là có 17 case fail dù `hit_rate > 0`.

4. **Cần đánh giá retrieval và answer song song**  
   Nếu chỉ nhìn retrieval metric thì dễ đánh giá sai chất lượng thực tế của hệ thống.

## 6. Kết luận

Benchmark hiện tại đã hoàn thành đúng mục tiêu của Giai đoạn 3:

- chạy được benchmark trên 50 test cases
- xuất report định lượng ở mức hệ thống và mức từng case
- chỉ ra được các cụm lỗi chính
- truy ngược được nguyên nhân gốc bằng failure analysis

Kết quả quan trọng nhất của giai đoạn này là xác định rõ hệ thống hiện tại đang yếu ở đâu:

- retrieval vẫn còn hụt ở câu hỏi án lệ
- có nhiều trường hợp retrieve đúng nhưng answer vẫn không bám evidence
- quality của câu trả lời cuối cùng chưa tương xứng với retrieval quality

Như vậy, phần benchmark và failure analysis đã hoàn thành vai trò chẩn đoán cho hệ thống hiện tại, đúng phạm vi Giai đoạn 3 của dự án.
