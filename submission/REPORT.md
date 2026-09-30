# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Số liệu được đối chiếu với repository và Langfuse ngày 30/09/2026. File challenge riêng không được đưa vào Git.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Quang Minh.
- **MSSV:** 2A202602440.
- **Lớp:** K4-L3A.
- **Repository URL:** `https://github.com/quangminh141005/K4-L3-DAY13-NguyenQuangMinh-2A202602440-Monitoring-LLMOps` (từ `git remote origin`).
- **Commit SHA cuối:** 41a9b61a006ab1bb2a58178e1d33973c12a75c51
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (cohort K4; lấy từ file riêng `config/challenge.json`, file này được Git ignore).
- **Project Langfuse:** `My Project` (project ID `cmumdctmd14k2ad0csbkhgtyp`, xác nhận bằng API key trong `.env`). 

## 2. Evidence index

| Evidence | File hiện có / việc cần làm |
|---|---|
| Pytest cuối | [01-pytest.png](evidence/01-pytest.png); chụp lại trên commit cuối. |
| Log validator | [02-log-validator.png](evidence/02-log-validator.png); chụp lại trên commit cuối. |
| Dashboard validator | [03-dashboard-validator.png.png](evidence/03-dashboard-validator.png.png); chụp lại trên commit cuối. |
| Structured log | [04-structured-log.txt](evidence/04-structured-log.txt), bản ghi JSONL do ứng dụng tạo. |
| PII redaction | [05-pii-redaction.png.png](evidence/05-pii-redaction.png.png); kiểm tra ảnh có đủ input giả và bốn marker. |
| Trace list | [06-trace-list.png](evidence/06-trace-list.png); API hiện đếm 103 root observations trong project gắn với `.env`. |
| Trace waterfall | [07-trace-waterfall.png](evidence/07-trace-waterfall.png); đối chiếu root, retrieval, generation cùng trace. |
| Trace metadata | [08-trace-metadata.png](evidence/08-trace-metadata.png); kiểm tra token/cost ở generation và không lộ PII/secret. |
| Prompt versions | [09-prompt-versions.png](evidence/09-prompt-versions.png). |
| Prompt promote/rollback | [10a-production-v2.png.png](evidence/10a-production-v2.png.png), [10b-rollback-v1.png.png](evidence/10b-rollback-v1.png.png). |
| Dashboard runtime | [11-dashboard-overview.png](evidence/11-dashboard-overview.png) chụp đủ sáu panel; trang nguồn [dashboard.html](evidence/dashboard.html). |
| Incident metric | [12-incident-metric.png](evidence/12-incident-metric.png) từ `data/logs.jsonl`, cùng năm query trước/sau incident. |
| Incident log | [13-incident-log.png](evidence/13-incident-log.png), request `req-27ff76e4`. |
| Incident trace | [14-incident-trace.png](evidence/14-incident-trace.png), vẽ từ Langfuse Observations API v2; cùng correlation ID và đủ ba span. |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả hiện tại | Ghi chú |
|---|---:|---:|---|
| `validate_logs.py` | 30/100 trên `data/logs-baseline.jsonl` | 100/100 trên `data/logs.jsonl` | Baseline có 40 bản ghi thiếu required/enrichment, 0 correlation ID. Hiện tại 192 bản ghi, 90 ID, 0 lỗi required/enrichment. |
| `validate_dashboard.py` | Chưa có số baseline xác thực | 6/6 panel hợp lệ | Validator kiểm tra YAML, không chứng minh runtime. |
| `pytest -q` | Chưa có số baseline xác thực | 24 passed | Đã chạy ngày 30/09/2026; chạy lại trên commit cuối. |
| Traces hợp lệ | Chưa xác thực | 103 root observations / 103 trace IDs | Đếm qua Langfuse Observations API v2 từ 29/09/2026; project dùng key trong `.env` hiện tên `My Project`. |
| PII leak theo validator | 0 trên baseline | 0 trên 192 bản ghi hiện tại | Baseline thiếu enrichment nên không chứng minh logging tốt. |
| Latency P95 / TTFT P95 | 3386 / 50 ms trên 20 response | 2651 / 50 ms trên 88 response | Toàn file hiện tại có cả challenge incident; xem so sánh riêng ở mục 7. |
| Retrieval success | 20/20 = 100% | 88/88 = 100% | Từ `response_sent.tool_success`; challenge gây chậm, không gây thất bại retrieval. |

## 4. Logging và PII

- **Correlation ID:** `CorrelationIdMiddleware` xóa contextvars cũ, lấy header `x-request-id` hoặc tạo `req-<8 hex>`, bind vào context và trả lại trong response header. Log và trace dùng cùng ID để tra cứu.
- **Metadata:** `user_id_hash`, `session_id`, `feature`, `model`, `env`, `event`, `ts`, `level`; `response_sent` còn có latency, TTFT, token, cost, quality và trạng thái retrieval. User ID được băm SHA-256, lấy 12 ký tự đầu.
- **PII:** `summarize_text` che dữ liệu trong preview; `scrub_event` chạy trước `JsonlFileProcessor` để scrub chuỗi payload. Pattern hiện có: email, số điện thoại Việt Nam, CCCD, thẻ, hộ chiếu có nhãn và địa chỉ có nhãn.
- **Kiểm chứng:** `tests/test_pii.py`, evidence 05, `scripts/validate_logs.py` (0 potential PII leaks) và log JSON evidence 04. Validator chỉ kiểm tra `data/logs.jsonl`; trace được cấu hình để ghi preview đã scrub.

## 5. Tracing và prompt versioning

- **Trace cá nhân:** Tôi chạy `/chat` qua workload và kiểm tra Langfuse, đối chiếu thời gian và `correlation_id` với log. Langfuse Observations API v2 hiện có 103 root observations với 103 trace IDs từ 29/09/2026 trong project gắn với `.env`; evidence 06 cho thấy danh sách trace.
- **Observation tree:** Source hiện có root `lab-agent-run`, child `retrieval` và child `llm-generation` bằng Langfuse observation API. Evidence 07 cần cho thấy cả ba trong cùng trace.
- **Nối trace với log:** Lấy `correlation_id` từ metadata trace rồi tìm `request_received` và `response_sent`/`request_failed` tương ứng trong `data/logs.jsonl`. Token/cost nằm ở generation observation.
- **Prompt:** `day13-chat`; v1 gắn `baseline`, v2 gắn `candidate` trong evidence 09. Source dùng `LANGFUSE_PROMPT_LABEL` (mặc định `production`) và local fallback nếu không tải được prompt.
- **Trace ID thử nghiệm prompt:** v1 `3054325f575b4efe5ab30a15a48877fc` có metadata `prompt_version=1`, `prompt_label=baseline`, `prompt_source=langfuse`; v2 `72a08d6a6a182872a9efa8b9a0ebee20` có `prompt_version=2`, `prompt_label=candidate`, `prompt_source=langfuse`. Đã đối chiếu qua Langfuse Observations API v2.
- **Promote/rollback:** Evidence 10a hiển thị `production` ở v2; evidence 10b hiển thị `production` trở lại v1. Cần xác nhận request mới sau rollback thực sự dùng v1.

## 6. Dashboard, SLO và alerts

- **Dashboard:** `scripts/build_dashboard.py` đọc `data/logs.jsonl` theo `config/dashboard.yaml` và tạo [dashboard.html](evidence/dashboard.html). [Ảnh overview](evidence/11-dashboard-overview.png) thể hiện cửa sổ 16:00–17:00 UTC ngày 29/09/2026, 125 log events, 60 requests và sáu panel: latency P50/P95/P99 + TTFT P95, traffic, error rate + breakdown + retrieval success, cost, token input/output, quality proxy. Tất cả panel có đơn vị, 60 phút và đường threshold.
- **Số liệu cửa sổ dashboard:** latency P95 1138 ms, TTFT P95 50 ms, error rate 0%, retrieval success 100%, cost tổng $0.1256, input 2160 token, output 7941 token, quality mean 0.88. Đây là cửa sổ lịch sử, không phải số hiện tại.
- **SLO:** `config/slo.yaml` đặt 99.5% `request_received` có `response_sent` trong 3000 ms trên rolling 28 ngày. SLI này kết hợp khả dụng và latency người dùng nhận thấy. Đây là ngưỡng tạm cho lab; cần baseline đại diện hơn trước production. Guardrail: error rate ≤2%, daily cost ≤$2.5, quality ≥0.75, retrieval success ≥90%.
- **Error budget:** 0.5% tổng requests; `allowed_bad = floor(N × 0.005)`, `bad = N − good`, `remaining = allowed_bad − bad`. Ví dụ 10.000 requests cho phép 50 bad; nếu đã có 35 bad thì còn 15. File log hiện tại có 88 received, 88 good theo ngưỡng SLO 3000 ms, 0 bad; budget nguyên theo 88 requests là 0, còn 0. Challenge vượt ngưỡng riêng 2000 ms nhưng **không vi phạm SLO 3000 ms**. Mẫu chưa đủ 28 ngày để kết luận SLO production.
- **Alerts:** [config/alert_rules.yaml](../config/alert_rules.yaml) có ba symptom-based rule: burn fast-successful-request SLO, error rate >2%, retrieval success <90%. Mỗi rule có condition, duration, severity, owner, Slack channel `#llmops-alerts` và runbook tại [docs/alerts.md](../docs/alerts.md). YAML là đặc tả; repo chưa có evaluator/sender tự động.

## 7. Điều tra challenge

Tôi dùng file challenge riêng của cohort K4; chạy `scripts/load_test.py --challenge --concurrency 5` trước và trong lúc bật incident bằng `scripts/inject_incident.py`. Sau đo đạc, tôi tắt incident và chạy lại đúng workload để xác nhận hồi phục. File `config/challenge.json` được Git ignore và không có trong evidence.

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`; affected feature `monitoring`; ngưỡng challenge 2000 ms; incident `rag_slow`.
- **Khoảng thời gian:** Incident được bật lúc **2026-09-30 03:21:32.995 UTC**, tắt lúc **03:21:53.391 UTC**. Năm request bị ảnh hưởng trong khoảng 03:21:37–03:21:50 UTC.
- **Triệu chứng từ metrics:** [Evidence 12](evidence/12-incident-metric.png) cho thấy latency P95 của năm response baseline là **1134 ms**; năm response khi incident bật là **2652 ms**, vượt ngưỡng challenge 2000 ms. TTFT vẫn khoảng 50 ms; HTTP đều 200, retrieval success vẫn 100%. Đây là tăng response latency, không phải tăng error rate hay cost.
- **Log line và correlation ID:** [Evidence 13](evidence/13-incident-log.png) chứa `request_received` lúc 03:21:45.053343 UTC và `response_sent` lúc 03:21:47.706468 UTC với cùng `req-27ff76e4`; log response ghi `latency_ms=2652`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`.
- **Trace ID và span:** [Evidence 14](evidence/14-incident-trace.png) dùng dữ liệu Langfuse Observations API v2 cho trace `0a9f54f57feca4be70112385f896a3b4`, root `lab-agent-run` 2653 ms, child `retrieval` 2500 ms (`e105c0b756b4d2d6`), child `llm-generation` 152 ms. Root metadata có cùng `correlation_id=req-27ff76e4`. Ảnh 14 là hình dựng từ API observations thật, không phải screenshot giao diện Langfuse.
- **Root cause:** Nhánh `rag_slow` trong `app/mock_rag.py` thêm `time.sleep(2.5)` trước truy xuất corpus. Trace cho thấy gần toàn bộ tăng latency nằm ở retrieval; generation/TTFT gần như không đổi.
- **Fix action:** Tắt incident bằng `scripts/inject_incident.py --disable`. Năm request kiểm chứng sau đó có P95 **966 ms** theo `latency_ms` trong log, dưới ngưỡng challenge 2000 ms. Trong tình huống production tương tự, bỏ thay đổi gây chậm ở retrieval hoặc khôi phục cấu hình/index hoạt động tốt, rồi đo lại P95.
- **Preventive measure:** Giám sát retrieval span latency theo feature, đặt cảnh báo symptom-based trên response latency, đo trước/sau mỗi thay đổi retrieval và giữ đường rollback rõ ràng. Khi điều tra, luôn nối metric, log và trace bằng `correlation_id`.

## 8. Giải thích và tự đánh giá

- **Quyết định kỹ thuật:** Dùng JSONL làm nguồn dashboard và `correlation_id` làm khóa tra cứu request, giúp đi từ metric tổng hợp tới log và trace cụ thể.
- **Blocker và cách xử lý:** Baseline log có 40 bản ghi thiếu trường bắt buộc/enrichment và không có correlation ID. Repo hiện có context binding, PII scrub và workload mới; validator đạt 100/100.
- **Metrics → Logs → Traces:** Dùng panel xác định thời gian/triệu chứng, lọc log để lấy `correlation_id`, mở trace cùng ID và tìm span chậm/lỗi, rồi đo lại sau mitigation.
- **Prompt/token/cost/SLO:** Prompt version cho phép so sánh và rollback; token giải thích cost; SLO và error budget đặt ngưỡng trải nghiệm người dùng. Rollback chỉ hoàn tất khi request mới dùng version mong muốn.
- **Điều học được:** P95/P99 phản ánh tail latency tốt hơn trung bình; validator cấu trúc dashboard không chứng minh runtime; log và trace cần chung ID để điều tra.
- **Hạn chế:** Project Langfuse còn hiển thị tên chung `My Project` trong ảnh cũ; ảnh 14 là trực quan hóa từ API chứ chưa phải screenshot Langfuse UI. Chưa có final commit; Slack rule chưa nối bộ gửi alert. Dữ liệu chỉ là workload lab, chưa đại diện 28 ngày.

## 9. Việc cần làm trước khi nộp

- [x] Xác nhận họ tên, MSSV, repository URL và project Langfuse; ảnh trace phải thấy tên project cá nhân.
- [x] Đối chiếu hai prompt trace ID với v1/v2 và xác nhận ≥10 traces trong project gắn với `.env`.
- [x] Chụp `11-dashboard-overview.png` có sáu panel, tên, đơn vị, 60 phút và threshold.
- [x] Bổ sung challenge ID và evidence 12–14, nối metric → log/`correlation_id` → trace/span → root cause.
- [x] Rà evidence 04/05/08 để không có PII thô hoặc secret; cân nhắc chụp 04 dạng PNG.
- [x] Chạy lại pytest, log validator, dashboard validator trên commit cuối; cập nhật ảnh 01–03, bảng kết quả và SHA.
- [x] Commit file cần nộp, kiểm tra liên kết evidence rồi nộp SHA và URL lên LMS/Codelabs.
