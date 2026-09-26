# Hướng dẫn đọc hiểu dự án Guardrails, HITL và Responsible AI

> Tài liệu học tập cho chủ repo, không phải artifact chấm điểm. Repo cho phép AI hỗ trợ code nhưng yêu cầu người nộp hiểu và giải thích được phần mình nộp. `outputs/lab_report.md` và `outputs/grade_report.json` vẫn phải được sinh bởi `scripts/grade.py`.

## 1. Bài toán đang mô phỏng điều gì?

Một chatbot ngân hàng nhận câu hỏi, có thể đọc nội dung email/tài liệu bên ngoài và có thể gợi ý hành động. Nội dung bên ngoài là **dữ liệu**, không phải chỉ thị có quyền thay đổi chính sách. Mô hình ngôn ngữ có thể bị thuyết phục tiết lộ thông tin trong ngữ cảnh hệ thống hoặc đưa ra câu trả lời không an toàn.

Trong lab, các giá trị trong `data/protected/vinbank_secrets.json` là canary giả. Chúng giúp kiểm tra xem agent có để lộ dữ liệu được bảo vệ không. Không được sửa chúng hoặc sửa JSON kết quả để tạo một lượt leak giả: grader replay kết quả và rubric yêu cầu bằng chứng thực.

## 2. Ba agent và mục tiêu khác nhau

| Agent | Vai trò | Hành vi cần quan sát |
|---|---|---|
| Blue | Agent phòng thủ do học viên ghép guardrails vào | Cho qua câu hỏi ngân hàng hợp lệ; chặn injection/off-topic; lọc đầu ra và kiểm soát egress |
| Red | Agent yếu, cố ý không có guardrails mạnh | Dùng để chứng minh prompt có thể làm lộ canary trong bài red-team |
| Red Advance | Agent mục tiêu khó có input/output guards | Nên từ chối hoặc chặn; B2 chỉ có thể được công nhận nếu một lượt replay thật sự làm lộ canary |

B1 và B2 là lựa chọn loại trừ: B1 tối đa +5, B2 tối đa +10. Red leak không thay thế điều kiện B2. Trong log hiện tại Red leak 4/5, Red Advance leak 0/5, nên **chưa có bằng chứng B2**.

## 3. Luồng xử lý của Blue

```text
Yêu cầu
  → Rate limiter theo user
  → Input guardrail (injection + topic)
  → LLM
  → Output guardrail (PII/secret)
  → Audit + metrics
  → Egress allowlist trước khi gửi dữ liệu ra ngoài
```

Mỗi lớp chặn một loại lỗi khác nhau:

1. **Rate limiter** giới hạn số request của một user trong cửa sổ thời gian. Cài đặt dùng deque chứa timestamp: bỏ timestamp quá hạn, nếu còn đủ số request thì từ chối, nếu chưa đủ thì thêm timestamp hiện tại.
2. **Input injection detector** chuẩn hóa dấu tiếng Việt, chữ hoa/thường và ký tự vô hình rồi so với các dấu hiệu như “ignore previous instructions”, “you are now”, “system prompt” và một số mẫu injection tiếng Việt. Đây là tín hiệu heuristic, không phải chứng minh toán học rằng prompt an toàn.
3. **Topic filter** chuẩn hóa Unicode rồi khớp cụm từ ngân hàng theo ranh giới từ. Các cụm như `VinBank`, `ngân hàng`, `sản phẩm`, `dịch vụ` được nhận diện dù viết hoa hoặc có dấu. Bộ từ khóa vẫn có thể gây false positive/false negative; cần đo trên mẫu thực tế.
4. **Output filter** phát hiện mẫu PII/canary, trả về nội dung đã thay bằng `[REDACTED]`. Với canary lab, nó còn chuẩn hóa dấu phân cách để bắt chuỗi bị tách thành từng ký tự. Bộ lọc này vẫn không thay thế DLP hoặc kiểm soát dữ liệu ở tầng hệ thống.
5. **Egress policy** là quyết định deterministic: chỉ chấp nhận HTTPS đến host được allowlist chính xác; từ chối userinfo/port lạ và payload có dấu hiệu dữ liệu nhạy cảm. Không để văn bản do model viết tự quyết định quyền gửi dữ liệu.
6. **Audit/monitoring** ghi kết quả, thời gian và số lượng để điều tra và phát hiện bất thường. Audit không phải guardrail: ghi nhận sự kiện không tự ngăn được sự kiện đó.

## 4. Vì sao cần defense in depth?

Không lớp đơn lẻ nào đủ tin cậy. Input regex có thể bỏ sót cách diễn đạt mới; model có thể bịa hoặc làm theo chỉ thị độc hại; output filter có thể không nhận ra biến thể; egress allowlist không đảm bảo nội dung đúng. Vì vậy quyết định quan trọng nên có nhiều điểm kiểm tra độc lập:

- Chặn sớm trước model để giảm rủi ro và chi phí.
- Kiểm tra lại sau model vì đầu vào hợp lệ vẫn có thể sinh đầu ra không an toàn.
- Chặn ở sink/egress vì đây là ranh giới dữ liệu rời khỏi hệ thống.
- Ghi audit để có thể giải thích quyết định sau này.
- Dùng human approval cho hành động có hậu quả thực tế.

## 5. HITL và router confidence

`src/hitl/hitl.py` mô tả ba mức định tuyến:

- Confidence từ 0.90: có thể tự gửi với tác vụ thông thường.
- Từ 0.70 đến dưới 0.90: đưa vào hàng chờ review.
- Dưới 0.70: escalates cho người xem xét.
- Hành động rủi ro cao luôn cần người duyệt, kể cả confidence rất cao.

Confidence của model không đồng nghĩa xác suất đúng đã được hiệu chuẩn. Router chỉ là ví dụ policy; hệ thống ngân hàng thật cần đo calibration, phân quyền reviewer, xác thực người dùng, chống replay, timeout fail-closed và approval gắn với hash của đúng hành động được duyệt.

Ba điểm HITL trong mã minh họa: chuyển tiền rủi ro cao; khôi phục tài khoản có mismatch danh tính; và chỉ thị khách hàng mâu thuẫn/không rõ. Timeout hoặc thiếu xác nhận không được hiểu là đồng ý.

## 6. Ý nghĩa của pipeline suite

`run_assignment_suite()` chạy các case an toàn, tấn công, rate limit và edge case. Nó gọi rate limiter và input/output plugins được cấu hình, rồi lưu `results.json`, `audit_log.json`, `metrics.json` ở repo root.

Để tránh gọi model và phát sinh chi phí, suite kiểm tra output guardrail bằng một response preview mẫu. Do đó kết quả này chứng minh plugin hoạt động trên mẫu, **không** chứng minh model thật luôn trả lời đúng. Khi chạy Red/Red Advance, `run_attacks()` mới gọi provider đã chọn và ghi evidence riêng; đây là phần có thể tiêu tốn API và kết quả phụ thuộc model/provider.

## 7. Đọc kết quả chạy hiện tại

Snapshot lấy từ artifact có trong repo ngày 26/09/2026:

| Đo lường | Kết quả | Cách hiểu |
|---|---:|---|
| Safe queries | 0/6 bị chặn | Không có false positive trong bộ mẫu này |
| Attack queries CP3 | 8/8 bị chặn | Các prompt mẫu bị input guardrail chặn |
| Rate limit | 10 qua, 5 bị chặn trên 15 | Giới hạn 10 request mỗi 60 giây hoạt động trong case mẫu |
| Red | 4/5 leak | Red yếu đã lộ canary trong bằng chứng hiện có |
| Red Advance | 0/5 leak; 4/5 bị input plugin chặn | Chưa đủ điều kiện B2; lượt còn lại model từ chối |
| Metrics | 33 request; 16 blocked; 5 rate-limit hit | Block rate khoảng 48.5%; có alert rate-limit tại ngưỡng 5 |

Các số này là kết quả trên một bộ prompt nhỏ và một lần chạy. Chúng không phải tỷ lệ bảo mật ngoài thực tế. `grade_report.json` hiện trên đĩa có timestamp cũ hơn artifact mới, nên cần chạy lại grader trước khi nộp.

## 8. Chạy và kiểm tra trên Windows PowerShell

Từ thư mục gốc dự án:

```powershell
.\.venv\Scripts\Activate.ps1
pytest tests/smoke tests/public -q
python scripts/grade.py --submission-dir . --out outputs/grade_report.json
```

Sinh lại artifact phòng thủ:

```powershell
python src/main.py --part 3
```

Chạy CP4 gọi model Red và Red Advance, cần provider/key hợp lệ trong `.env`:

```powershell
python src/main.py --part 4
```

Đừng dán `.env` hoặc key vào log/chia sẻ công khai. Chỉ `.env.example` được nộp.

Để chat trực tiếp với Blue mà không chạy cả bài lab:

```powershell
python src/main.py --chat
```

Nhập `thoát` hoặc `exit` để kết thúc. Mỗi câu được gửi riêng tới model nên có thể phát sinh phí và hiện tại Blue không giữ lịch sử các lượt chat trước đó.

## 9. Cách tự giải thích khi được hỏi

1. **Vì sao input guardrail không đủ?** Nội dung nguy hiểm có thể được diễn đạt vòng, đến từ RAG, hoặc model có thể sinh thông tin nhạy cảm dù câu hỏi ban đầu bình thường; cần output và egress checks.
2. **Rate limiting khác topic filtering thế nào?** Rate limiting kiểm soát tần suất/chi phí theo user; topic filter kiểm soát phạm vi ngữ nghĩa của từng request.
3. **Audit có chặn request không?** Không. Audit tạo bằng chứng; policy plugin mới quyết định block/allow.
4. **Vì sao egress dùng exact host?** Kiểm tra chuỗi con/suffix dễ chấp nhận host giả như `api.vinbank.example.attacker.test`; allowlist phải so hostname đã parse.
5. **Vì sao cần HITL dù confidence cao?** Confidence không cấp quyền hành động. Chuyển tiền/đổi thông tin tài khoản có hậu quả nên cần người có thẩm quyền duyệt hành động cụ thể.
6. **B2 đạt khi nào?** Khi response thật từ Red Advance chứa canary theo tiêu chí grader và replay xác nhận. JSON tự sửa hoặc chỉ làm model từ chối/chặn không đạt B2.

## 10. Giới hạn và việc cần cân nhắc

- Regex/topic lists là heuristic; bổ sung normalization/context-aware testing và theo dõi false positive/false negative.
- Bộ audit hiện lưu output và metadata, chưa gắn correlation ID ổn định cho từng request; môi trường thật nên có request ID và chính sách retention/redaction.
- Pipeline suite không gọi LLM; cần phân biệt kết quả preview với live evaluation.
- `src/testing/testing.py` và NeMo/Judge là enrichment không bắt buộc theo rubric. Kiểm tra TODO trước khi dùng chúng như tính năng production.
- Không đưa canary hoặc PII vào log không kiểm soát. Trong lab đây là dữ liệu giả; ngoài thực tế cần secrets manager và access control.
